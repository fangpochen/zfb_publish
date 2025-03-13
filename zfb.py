import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import urllib
import concurrent.futures
from datetime import datetime
import cv2
import random
from logger import logger
import requests
from ratelimit import limits, sleep_and_retry
from DrissionPage import ChromiumPage, ChromiumOptions
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
from PIL import Image
import queue
import traceback
import uuid


# 在文件开头添加线程控制类
class ThreadControl:
    def __init__(self):
        self._stop_event = threading.Event()
        self.active_futures = set()
        self.lock = threading.Lock()
        
    def stop(self):
        """设置停止标志并取消所有活动任务"""
        self._stop_event.set()
        with self.lock:
            for future in self.active_futures:
                if not future.done():
                    future.cancel()
            self.active_futures.clear()
    
    def clear(self):
        """清除停止标志"""
        self._stop_event.clear()
        
    def should_stop(self):
        """检查是否应该停止"""
        return self._stop_event.is_set()
    
    def add_future(self, future):
        """添加future到活动任务集合"""
        with self.lock:
            self.active_futures.add(future)
            
    def remove_future(self, future):
        """从活动任务集合中移除future"""
        with self.lock:
            self.active_futures.discard(future)

# 创建全局实例
thread_control = ThreadControl()

# 创建自定义的日志格式化器
class ThreadIdFormatter(logging.Formatter):
    def format(self, record):
        record.threadid = f"Thread-{threading.current_thread().ident}"
        return super().format(record)

# 获取logger
logger = logging.getLogger()

# 如果还没有配置过formatter
if not logger.handlers:
    formatter = ThreadIdFormatter('%(asctime)s - %(threadid)s - %(levelname)s - %(message)s')
    
    # 配置文件处理器
    file_handler = logging.FileHandler('log.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

def create_table():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # 创建表格(如果不存在)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            appid CHAR(64) PRIMARY KEY,          
            account_name TEXT,                   
            cookies TEXT,                        
            cookies_status TEXT DEFAULT '正常',  
            check_ INTEGER DEFAULT 0,             
            daily_recommendations INTEGER DEFAULT 0, 
            total_uploads INTEGER DEFAULT 50,     
            current_uploads INTEGER DEFAULT 0,   
            topic_settings TEXT DEFAULT '', 
            delete_unrecommended INTEGER DEFAULT 0, 
            total_files INTEGER DEFAULT 0,       
            folder_path TEXT DEFAULT NULL,       
            is_main_account INTEGER DEFAULT 1,   
            user_name TEXT,                      
            request_all TEXT,
            mian_account_appid CHAR(64),
            daily_success INTEGER DEFAULT 0,      -- 新增：今日成功数
            daily_failed INTEGER DEFAULT 0,       -- 新增：今日失败数
            last_publish_time TEXT               -- 新增：最近发布时间
        );
    ''')
    
    # 检查并添加新列（如果不存在）
    try:
        cursor.execute('ALTER TABLE user_data ADD COLUMN daily_success INTEGER DEFAULT 0;')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('ALTER TABLE user_data ADD COLUMN daily_failed INTEGER DEFAULT 0;')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('ALTER TABLE user_data ADD COLUMN last_publish_time TEXT;')
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()


def get_appid(cookies):
    '''

    :param cookies: 传入cookie
    :return:  返回用户的appid
    '''
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        # 'cookie': 'JSESSIONID=RZ43Fk6xgZEXlmuXKkMG4PLc5kSSMTauthRZ42GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; auth_goto_http_type=https; ctoken=9wKSgr_kG8zycmgQ; _CHIPS-ctoken=9wKSgr_kG8zycmgQ; LoginForm=alipay_login_home; alipay="K1iSL19mwb+fHm8DIo6SzyPb35M2atCZSixKUi1DCw=="; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; auth_jwt=e30.eyJleHAiOjE3MzM2NzM2MTI1MTgsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiT2d4VzJnOEhOeU9pUkxNc3lhRTQ0SFhGZ2V0TUlwdGUxYmNhNjdiIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.GmIxvPXX0zwtUTGwOlP9QCU_SPJDkoEn65Md-LJwS90; _CHIPS-ALIPAYJSESSIONID=RZ43Fk6xgZEXlmuXKkMG4PLc5kSSMTauthRZ42GZ00; ALIPAYJSESSIONID=RZ43Fk6xgZEXlmuXKkMG4PLc5kSSMTauthRZ42GZ00; rtk=aycvC3UK1/YGP+xr5yOZifWQIOxfxnCVjPagrm8p1Zidxn4T1jU; __TRACERT_COOKIE_bucUserId=2088642500352911; zone=GZ00G; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#/WtSNKt2SHa3IqX061Rhdzkx"; JSESSIONID=B7B3893F2D1FA8511BE4B89AEE85D2E2; spanner=sDmQ/tfsbusli0eTx1P4ZmbZwowxMu3ZXt2T4qEYgj0=',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    params = {
        'sourceId': 'S',
    }

    response = requests.get('https://contentweb.alipay.com/life/getAppEnv.json', params=params, cookies=cookies,
                            headers=headers)
    json_data = response.json()
    logger.info(json_data)
    result = json_data.get('result')
    appname = result.get('appName')
    appId = result.get('appId')
    account_name = result.get('logonId')
    logger.info(f'获取appid成功：{appId}')
    return str(appId), appname, account_name


# 登录
def login():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    ''''
    return :返回cookie和保持cookie所用的请求数据data
    '''
    # 获取 Chrome 路径
    chrome_path = None
    if os.path.exists('config.json'):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                chrome_path = config.get('chrome_path')
        except Exception as e:
            logger.error(f"读取Chrome配置失败: {str(e)}")
    
    # 设置 ChromiumOptions
    co = ChromiumOptions().auto_port()
    co.set_argument('--window-size', '800,600')
    
    # 如果有配置的 Chrome 路径，使用它
    if chrome_path and os.path.exists(chrome_path):
        co.set_browser_path(chrome_path)
        logger.info(f"使用配置的Chrome路径: {chrome_path}")
    else:
        logger.warning("未找到配置的Chrome路径，使用默认路径")
    
    page = ChromiumPage(co)
    page.set.cookies.clear()
    page.get('https://c.alipay.com/page/portal/home')
    # page.wait.load_start()
    page.scroll.to_rightmost()
    page.wait.url_change('https://c.alipay.com/page/life-account/index',timeout=90)
    page.listen.start('dwcookie?biztype=pcwallet')
    for i in range(3):
        try:
            page.ele('@@text()=内容发布', timeout=5).click()
            # print('触发点击')
        except Exception as e:
            # print(e)
            pass

    packets = page.listen.wait(5)
    # logger.info(packets)
    # print('packets:', packets)
    cookies_list = page.cookies()
    # print('cookies_list', cookies_list)
    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
    appid, user_name, account_name = get_appid(cookies_dict)
    all_request = []
    for packet in packets:
        request_data = dict()
        request_data['url'] = packet.url
        request_data['data'] = packet.request.postData
        # print(packet.request.postData)
        all_request.append(request_data)
    page.quit()
    
    # 检查是否存在相同的appid
    cursor.execute('SELECT COUNT(*) FROM user_data WHERE appid = ?', (appid,))
    exists = cursor.fetchone()[0] > 0
    
    if exists:
        # 如���存在相同appid，更新所有账号的cookies
        logger.info(f"检测到已存在appid: {appid}, 更新所有账号cookies")
        cursor.execute('''
            UPDATE user_data 
            SET cookies = ?
        ''', (json.dumps(cookies_dict),))
        
        # 更新当前登录账号的其他信息
        cursor.execute('''
            UPDATE user_data 
            SET user_name = ?,
                account_name = ?,
                request_all = ?
            WHERE appid = ?
        ''', (user_name, account_name, str(all_request), appid))
    else:
        # 如果是新账号，则插入新记录
        logger.info(f"检测到新appid: {appid}, 创建新账号记录")
        cursor.execute('''
            INSERT INTO user_data (
                appid, cookies, user_name, account_name, 
                request_all, is_main_account
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (appid, json.dumps(cookies_dict), user_name, 
              account_name, str(all_request), 1))
    
    conn.commit()
    conn.close()
    logger.info(f"账号信息更新完成")
    return cookies_dict, appid, user_name, all_request
def get_sub_cookies(cookies, appid):
    '''
    Args:
        cookies:目前账号cookie
        appid: 需要换成的appid账号

    Returns:
        更新后的cookie
    '''
    try:
        # 创建一个复制，避免修改原始cookies
        res_cookie = cookies.copy()
        
        # 尝试从当前cookies获取ctoken
        ctoken = cookies.get('ctoken', '')
        if not ctoken:
            logger.warning(f"无法从cookies获取ctoken，将使用默认值")
            ctoken = 'defaultCtoken'
        
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache',
            'origin': 'https://c.alipay.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://c.alipay.com/',
            'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        }
        
        params = {
            'ctoken': ctoken,
            'appId': f'{appid}',
        }
        
        logger.info(f"正在尝试切换到子账号 {appid} 的cookies")
        
        response = requests.post(
            'https://contentweb.alipay.com/life/lifeSelectSwitch.json',
            params=params,
            cookies=cookies,
            headers=headers,
            timeout=(5, 15)  # 设置连接超时和响应超时
        )
        
        # 记录响应状态
        logger.info(f"切换子账号响应状态: {response.status_code}")
        
        # 检查HTTP状态
        if response.status_code != 200:
            logger.error(f"切换子账号失败，HTTP状态码: {response.status_code}, 响应内容: {response.text}")
            return None
            
        # 检查响应内容是否为空
        if not response.text:
            logger.error("切换子账号接口返回空响应")
            return None
            
        # 检查响应的cookies是否包含任何内容
        if not response.cookies:
            logger.warning("响应中没有cookies，可能需要重新登录")
            
        # 更新cookies
        for cookie in response.cookies:
            logger.debug(f"更新cookie: {cookie.name}={cookie.value}")
            res_cookie[cookie.name] = cookie.value
            
        logger.info(f"已切换至子账号 {appid} 的cookies")
        return res_cookie
        
    except requests.exceptions.RequestException as e:
        logger.error(f"切换子账号时网络错误: {str(e)}")
        logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
        return None
    except Exception as e:
        logger.error(f"切换子账号时发生未知错误: {str(e)}")
        logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
        return None

# 获取子账号
def get_lifeOptionList(cookies, appid):
    '''
      :param cookies: 传入主账号cookie，主账号appid
      :return:
      '''
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    params = {
        'ctoken': 'Ja45PCG8BmCTtxsy',
        'sourceId': 'lifestream',
    }
    try:
        response = requests.post('https://contentweb.alipay.com/life/lifeOptionList.json', params=params,
                                 cookies=cookies,
                                 headers=headers)
        json_data = response.json()
        stat = json_data.get('stat')
        operator_list = []
        if stat == 'ok':
            list = json_data.get('result')
            for ope in list:
                operator = dict()
                operator['appId'] = ope.get('appId')
                if operator['appId'] == appid:
                    pass
                    # operator['appName'] = ope.get('appName')
                    # operator['cookies'] = get_sub_cookies(cookies, operator['appId'])
                    # operator_list.append(operator)
                    # cursor.execute('''
                    #                        INSERT INTO user_data (appid, cookies, user_name, is_main_account,mian_account_appid)
                    #                        VALUES (?, ?, ?, ?, ?)
                    #                        ON CONFLICT(appid) DO UPDATE SET
                    #                            cookies = excluded.cookies
                    #                        ''', (operator['appId'], json.dumps(operator['cookies']), operator['appName'], 0, appid))
                    # conn.commit()
                else:
                    operator['appName'] = ope.get('appName')
                    # operator['cookies'] = get_sub_cookies(cookies, operator['appId'])
                    operator_list.append(operator)
                    cursor.execute('''
                        INSERT INTO user_data (appid, cookies, user_name, is_main_account,mian_account_appid)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(appid) DO UPDATE SET
                            cookies = excluded.cookies
                        ''', (operator['appId'], json.dumps(cookies), operator['appName'], 0, appid))
                    conn.commit()
            # main_cookie = get_sub_cookies(cookies, appid)
            # cursor.execute('''
            #                             UPDATE user_data
            #                             SET cookies = ?
            #                             WHERE appid = ?
            #                         ''', (main_cookie, appid))
            # conn.commit()
            conn.close()
            logger.info(f'{appid}获取子账号成功')
            return operator_list
        else:
            logger.info(f'{appid}获取子账号失败')
            conn.close()
            return None
    except Exception as e:
        logger.info(f'{appid}获取子账号失败:', e)
        conn.close()
        return None


def get_operator(cookies, appid):
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=RZ434gxpCU1IajMt5Qu1XrVBMz2yf1authRZ42GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; auth_goto_http_type=https; alipay="K1iSL19mwb+fHm8DIo6SzyPb35M2atCZSixKUi1DCw=="; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ctoken=WWc3uZPtU0BvsU9-; _CHIPS-ctoken=WWc3uZPtU0BvsU9-; LoginForm=alipay_login_auth; CLUB_ALIPAY_COM=2088642500352911; ali_apache_tracktmp="uid=2088642500352911"; auth_jwt=e30.eyJleHAiOjE3MzQxNDg1NzYyNzUsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiVE1kbzZESTRvMXMwWXJwNTFUaXZmaGpGZzJHd2ZMTDhuVUlyQUwwY2RlYjQ5IiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.sRy8tthGuP-nPEtSFh2_yCEOqjvbShv5NrfOD-YSYtg; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-ALIPAYJSESSIONID=RZ434gxpCU1IajMt5Qu1XrVBMz2yf1authRZ42GZ00; ALIPAYJSESSIONID=RZ434gxpCU1IajMt5Qu1XrVBMz2yf1authRZ42GZ00; rtk=rf4qNdpgojWjJx+aufCe/yYEKC+y+7OzGJrkal6Ule/3+7SvlGp; __TRACERT_COOKIE_bucUserId=2088642500352911; zone=GZ00G; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#t0shNb2lQ8ewzYGmmWN3pzkx"; JSESSIONID=401C17CE67E7A60EE9B1B89FDE366446; spanner=4j9Wn2hAD+tEXtClWMqo376I7aVpoidu4EJoL7C0n0A=',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    params = {
        'action': 'getOperators',
        'sourceId': 'S',
        '_input_charset': 'utf-8',
        '_output_charset': 'utf-8',
        '_ksTS': '1734148016736_7',
        'ctoken': 'WWc3uZPtU0BvsU9-',
    }

    data = {
        'appId': f'{appid}',
    }
    response = requests.post(
        'https://contentweb.alipay.com/life/operator.json',
        params=params,
        cookies=cookies,
        headers=headers,
        data=data,
    )
    json_data = response.json()
    stat = json_data.get('stat')
    operator_list = []
    if stat == 'ok':
        list = json_data.get('list')
        for ope in list:
            operator = dict()
            operator['logonId'] = ope.get('logonId')
            operator['status'] = ope.get('status')
            operator['userId'] = ope.get('userId')
            operator['userName'] = ope.get('userName')
            operator_list.append(operator)
        return operator_list
    else:
        return None


# 保持主账号cookie
def keep_cookies(request_all, cookies=None, appid=None):
    '''
    :param request_all: 账号的request_all,类型为列表
    :param cookies: 数据库中的cookies
    :param appid: 主账号的appid
    '''
    # 先调用get_public_list保持登录状态
    if cookies and appid:
        cookies_dict = json.loads(cookies) if isinstance(cookies, str) else cookies
        get_public_list(cookies_dict, appid, 'recommend', False, None)
        logger.info(f"使用appid={appid}调用保持登录")
    
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    
    for request_param in request_all:
        url = request_param.get('url')
        data = request_param.get('data')
        datas = f'{data}'
        response = requests.post(url, headers=headers, data=datas)
        jsondata = response.json()
        code = jsondata['code']
        code_v2 = jsondata['code_v2']
        if code == 200 and code_v2 == 200:
            logger.info("触发点击事件成功")
            return True
        else:
            logger.warning("触发点击事件失败")
            return False


# 获取appid

# get_appid(cookies)
# 获取视频列表
def get_public_list(cookie, appid, type, is_sun_account, mian_account_appid):
    '''
    :param cookies:传入cookies
    :param appid:用户的id
    :param type:使用类型，传入'delete'是获取需要删除的视频列表，传入recommend为获取当日推荐视频列表
    :param is_sun_account:布尔值或者0/1，判断是否为子账号，为子账号则为True
    :param mian_account_appid:所属主账号的appid
    :return:
    返回需要删除的视频id，或者推荐视频id
    '''

    if is_sun_account:
        cookies = get_sub_cookies(cookie, appid)
    else:
        cookies = cookie
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ42GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#bnz+ctsBQbm5M9QJsMj9Vjkx"; ctoken=Z-dPkcYColZussmH; _CHIPS-ctoken=Z-dPkcYColZussmH; LoginForm=alipay_login_auth; auth_jwt=e30.eyJleHAiOjE3MzM2MjU5NjYzNjEsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiSnQ5YmMzZWE4a1dIRzJib3pKSUp5ZDFYRjIwa2dGZ0lBcXRPQWtBIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.npZb6KjqQ8TQrainac26ahDx1toiR3gEAk-acJZQHhc; rtk=ln/sySw8Nl2Nvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; _CHIPS-ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authGZ00RZ43; ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ43GZ00; zone=GZ00G; JSESSIONID=755D2546CB0D857145466FC7902813C5; spanner=TFXHJ4uXsSqN2bxWf2KfwQ9UcXGcquKG4EJoL7C0n0A=',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    params = {
        'loginPublicId': f'{appid}',
        'sourceId': 'S',
        'appId': f'{appid}',
        '_input_charset': 'utf-8',
        '_output_charset': 'utf-8',

        '_ksTS': '1733630499679_14',
        'ctoken': 'RAagTh_i7gO7Mypd',
    }
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    stop = False
    delete_id_list = []
    Recommended_list = []
    if type == 'delete':
        page = 1
        while not stop:
            data = {
                'sourceId': 'sweb',
                'page': f'{page}',
                'pageSize': '10',
                'auditSource': 'QUALITY',
                'statusList': 'all',
            }
            try:
                response = requests.post(
                    'https://contentweb.alipay.com/life/publishListV2.json',
                    params=params,
                    cookies=cookies,
                    headers=headers,
                    data=data,
                )
                stat = response.json().get('stat')
                logger.debug(response.json())
                if stat == 'ok':
                    result = response.json().get('result')
                    publishContents = result.get('publishContents')
                    for item in publishContents:
                        rec_data = dict()
                        state = item.get('state')
                        if state == '已发布':
                            canContentRecommended = item.get('canContentRecommended')
                            if canContentRecommended == True:
                                pass
                                # rec_data['id']=item.get('contentId')
                                # rec_data['title']=item.get('title')
                                # Recommended_list.append(rec_data)
                            else:
                                contentId = item.get('contentId')
                                delete_id_list.append(contentId)

                    if not publishContents or len(publishContents) < 10:
                        stop = True
                    page = page + 1
                else:
                    return None
            except Exception as e:
                logger.info(f'{appid}获取删除视频列表失败：{e}')
                return None
        # conn.close()
        if is_sun_account:
            cookies = get_sub_cookies(cookies, mian_account_appid)
            cookies=json.dumps(cookies)
            try:
                cursor.execute('''
                                UPDATE user_data
                                SET cookies = ?
                                WHERE appid = ?
                            ''', (cookies, mian_account_appid))
                conn.commit()
            except Exception as e:
                logger.info(e)
        conn.close()
        return delete_id_list
    elif type == 'recommend':

        current_date = datetime.now()
        formatted_date = current_date.strftime('%Y%m%d')
        page = 1
        while not stop:
            data = {
                'sourceId': 'sweb',
                'page': f'{page}',
                'pageSize': '10',
                'startDate': f'{formatted_date}',
                'endDate': f'{formatted_date}',
                'auditSource': 'QUALITY',
                'statusList': 'all',
            }
            try:
                response = requests.post(
                    'https://contentweb.alipay.com/life/publishListV2.json',
                    params=params,
                    cookies=cookies,
                    headers=headers,
                    data=data,
                )
                logger.debug(response.json())
                stat = response.json().get('stat')
                if stat == 'ok':
                    result = response.json().get('result')
                    publishContents = result.get('publishContents')
                    for item in publishContents:
                        rec_data = dict()
                        state = item.get('state')
                        if state == '已发布':
                            canContentRecommended = item.get('canContentRecommended')
                            if canContentRecommended == True:
                                rec_data['id'] = item.get('contentId')
                                rec_data['title'] = item.get('title')
                                Recommended_list.append(rec_data)
                            else:
                                pass
                                # contentId = item.get('contentId')
                                # delete_id_list.append(contentId)

                    if not publishContents or len(publishContents) < 10:
                        stop = True
                    page = page + 1
                else:
                    return None
            except Exception as e:
                logger.info(f'{appid}获取推荐视频列表失败：{e}')
        cursor.execute('''
            UPDATE user_data
            SET daily_recommendations = ?
            WHERE appid = ?
        ''', (len(Recommended_list), appid))

        conn.commit()

        if is_sun_account:
            cookies = get_sub_cookies(cookies, mian_account_appid)
            cookies = json.dumps(cookies)
            cursor.execute('''
                UPDATE user_data
                SET cookies = ?
                WHERE appid = ?
            ''', (cookies, mian_account_appid))
            conn.commit()
        conn.close()
        return Recommended_list
    else:
        return None


# 删除不推荐视频
def delete_note(cookie, appid, id_listm,is_sun_account, mian_account_appid):
    if is_sun_account:
        cookies = get_sub_cookies(cookie, appid)
    else:
        cookies = cookie
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    '''
      :param cookies:传入cookies
      :param appid:用户的id
      :param id_listm:需要删除的视频id列表
      '''
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ42GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#bnz+ctsBQbm5M9QJsMj9Vjkx"; ctoken=Z-dPkcYColZussmH; _CHIPS-ctoken=Z-dPkcYColZussmH; LoginForm=alipay_login_auth; auth_jwt=e30.eyJleHAiOjE3MzM2MjU5NjYzNjEsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiSnQ5YmMzZWE4a1dIRzJib3pKSUp5ZDFYRjIwa2dGZ0lBcXRPQWtBIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.npZb6KjqQ8TQrainac26ahDx1toiR3gEAk-acJZQHhc; rtk=ln/sySw8Nl2Nvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; _CHIPS-ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authGZ00RZ43; ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ43GZ00; zone=GZ00G; JSESSIONID=D7B73594156831D45F54EB4DE44A2D8B; spanner=Jvs5gUaFRjnpFelks+N7jOytew30C/SfXt2T4qEYgj0=',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    for note_id in id_listm:
        data = {
            'contentId': f'{note_id}',
            'bizOwner': 'LIFE',
            'sourceId': 'sweb',
        }
        params = {
            'sourceId': 'S',
            'appId': f'{appid}',
            '_input_charset': 'utf-8',
            '_output_charset': 'utf-8',
            '_ksTS': '1733658548854_5',
            'ctoken': 'Z-dPkcYColZussmH',
        }
        try:
            response = requests.post(
                'https://contentweb.alipay.com/life/recall.json',
                params=params,
                cookies=cookies,
                headers=headers,
                data=data,
            )
            logger.info(response.json())
            logger.info(f'{appid}-视频{note_id}已删除')
        except Exception as e:
            logger.info(f'{appid}-视频{note_id}删除失败：{e}')
    cursor.execute('''
                       UPDATE user_data
                       SET delete_unrecommended = ?
                       WHERE appid = ?
                   ''', (len(id_listm), appid))

    conn.commit()
    if is_sun_account:
        cookies = get_sub_cookies(cookies, mian_account_appid) #切回主账号
        cursor.execute('''
                               UPDATE user_data
                               SET cookies = ?
                               WHERE appid = ?
                           ''', (cookies, mian_account_appid))
        conn.commit()
    conn.close()


# 获取参加可参加活动:
def get_recomment_tasks(cookies, appid):
    '''
          :param cookies:传入cookies
          :param appid:用户的id
          :return:
          返回可参加任务id列表
          '''
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=176CBD10DE01B1F9D5428EB0F9BB9007; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; spanner=XkPiOoqH57LBX8DpqbudpLumcFIkbrTs4EJoL7C0n0A=; auth_goto_http_type=https; umt=Ld88cfefd4afb2413eba1fdca973aa9af; JSESSIONID=9388745E1BCF08B4FC77DC56638B1F89; ctoken=ml0GAin-nlx2oNeg; _CHIPS-ctoken=ml0GAin-nlx2oNeg; LoginForm=alipay_login_home; alipay="K1iSL19mwb+fHm8DIo6SzyPb35M2atCZSixKUi1DCw=="; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; auth_jwt=e30.eyJleHAiOjE3MzM2NzI2MjIxNjQsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiVzcxeVZ5TmlWeFJTa2c4N3g0R2xSZ1ZGZ1VnY2lEOVo0ZTdlNGNRIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.ZDq42nh-UgWWuz7lraXFXHDsKDxfZqh5W3k2d9JHvXA; rtk=ln0gqSwJpagNvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#pLfqLzIRSAqY/mnvlGyNJzkx"; _CHIPS-ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthGZ00RZ43; zone=GZ00G; ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthRZ43GZ00',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    params = {
        'sourceId': 'S',
        'appId': f'{appid}',
        '_input_charset': 'utf-8',
        '_output_charset': 'utf-8',
        '_ksTS': '1733672372270_16',
        'ctoken': 'ml0GAin-nlx2oNeg',
    }
    data = {
        'targetId': f'{appid}',
        'bizScene': 'CREATOR_GROWTH_TASK',
        'requestSource': 'S',
    }
    taskId_list = []
    try:
        response = requests.post(
            'https://fuwu.alipay.com/platform/getNewPlatformTasks.json',
            params=params,
            cookies=cookies,
            headers=headers,
            data=data,
        )
        json_data = response.json()
        result = json_data.get('result')
        taskDetailVOS = result.get('taskDetailVOS')
        for task in taskDetailVOS:
            taskId = task.get('taskId')
            taskId_list.append(taskId)
        return taskId_list
    except Exception as e:
        logger.info(f'{appid}获取任务列表失败：{e}')


# 参加活动：
def collecting_tasks(cookies, appid, taskId_list):
    '''
              :param cookies:传入cookies
              :param appid:用户的id
              :param taskId_list:可参加任务的id列表
              '''
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=176CBD10DE01B1F9D5428EB0F9BB9007; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; spanner=XkPiOoqH57LBX8DpqbudpLumcFIkbrTs4EJoL7C0n0A=; auth_goto_http_type=https; umt=Ld88cfefd4afb2413eba1fdca973aa9af; JSESSIONID=9388745E1BCF08B4FC77DC56638B1F89; ctoken=ml0GAin-nlx2oNeg; _CHIPS-ctoken=ml0GAin-nlx2oNeg; LoginForm=alipay_login_home; alipay="K1iSL19mwb+fHm8DIo6SzyPb35M2atCZSixKUi1DCw=="; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; auth_jwt=e30.eyJleHAiOjE3MzM2NzI2MjIxNjQsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiVzcxeVZ5TmlWeFJTa2c4N3g0R2xSZ1ZGZ1VnY2lEOVo0ZTdlNGNRIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.ZDq42nh-UgWWuz7lraXFXHDsKDxfZqh5W3k2d9JHvXA; rtk=ln0gqSwJpagNvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#pLfqLzIRSAqY/mnvlGyNJzkx"; _CHIPS-ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthGZ00RZ43; zone=GZ00G; ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthRZ43GZ00',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    for taskId in taskId_list:
        try:
            params = {
                'sourceId': 'S',
                'appId': f'{appid}',
                '_input_charset': 'utf-8',
                '_output_charset': 'utf-8',
                '_ksTS': '1733818224706_15',
                'ctoken': 'mtkiWnGmHrI9WE2K',
            }

            data = {
                'targetId': f'{appid}',
                'bizScene': 'CREATOR_GROWTH_TASK',
                'requestSource': 'S',
                'taskIds': f'{taskId}',
            }

            response = requests.post(
                'https://fuwu.alipay.com/platform/receiveNewPlatformTasks.json',
                params=params,
                cookies=cookies,
                headers=headers,
                data=data,
            )
            logger.info(response.json())
            logger.info(f'{appid}-任务 {taskId} 领取成功')
        except Exception as e:
            logger.info(f'{str(e)}')
            logger.info(f'{appid}领取失败')


def get_mt(cookies):
    import traceback
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        # 'cookie': 已删除原有注释中的cookie字符串
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    params = {
        'type': 'VIDEO',
    }

    try:
        logger.info("开始获取massToken...")
        response = requests.get(
            'https://contentweb.alipay.com/life/queryMasstoken.json', 
            params=params, 
            cookies=cookies,
            headers=headers,
            timeout=15  # 添加超时设置
        )
        
        # 记录响应状态
        logger.info(f"获取massToken响应状态: {response.status_code}")
        
        # 检查HTTP状态
        if response.status_code != 200:
            logger.error(f"获取massToken失败，HTTP状态码: {response.status_code}，响应内容: {response.text}")
            return None
            
        
        # 解析JSON响应
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"解析massToken响应JSON失败: {str(e)}")
            logger.error(f"响应内容: {response.text}")
            logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
            return None
        
        # 检查结果
        if not data.get("result"):
            logger.error(f"获取massToken失败，响应不包含result字段: {data}")
            return None
            
        mass_token = data.get("result").get("massToken")
        if not mass_token:
            logger.error(f"获取massToken失败，massToken为空: {data}")
            return None
            
        logger.info("成功获取massToken")
        return mass_token
        
    except requests.exceptions.RequestException as e:
        logger.error(f"请求massToken时网络错误: {str(e)}")
        logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
        return None
    except Exception as e:
        logger.error(f"获取massToken时发生未知错误: {str(e)}")
        logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
        return None


def get_traid():
    l = "useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict"
    Ft = 21
    return ''.join(secrets.choice(l) for _ in range(Ft))


def upload_4m_video(mt, file_path):
    """
    上传小于或等于4MB的视频文件
    
    参数:
    - mt: 上传令牌
    - file_path: 文件路径
    
    返回:
    - file_id和file_name的元组 (与upload_large_video保持一致的返回格式)
    """
    try:
        # 获取文件大小（字节数）
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        # 设置重试次数
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 打开文件
                with open(file_path, 'rb') as file:
                    files = {
                        'file': (file.name, file, 'video/mp4')
                    }

                    headers = {
                        'Accept': '*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9',
                        'content-length': str(file_size),
                        'Origin': 'https://c.alipay.com',
                        'Referer': 'https://c.alipay.com/',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                        'X-Mass-Appkey': 'apwallet',
                        'X-Mass-Biztype': 'content_lifetab',
                        'X-Mass-Cust-Conf': '{"extern":{"isWaterMark":true}}',
                        'X-Mass-Token': mt,
                        'Connection': 'keep-alive'
                    }
                    params = {
                        'mt': mt,
                        'bz': 'content_lifetab',
                        'public': 'false',
                    }

                    response = requests.post(
                        'https://mass.alipay.com/file/auth/upload', 
                        params=params, 
                        headers=headers, 
                        files=files,
                        timeout=(15, 120)  # (连接超时, 读取超时)
                    )
                    
                    
                    # 检查HTTP状态码
                    if response.status_code != 200:
                        error_msg = f"视频上传失败 - HTTP错误: {response.status_code}"
                        if response.text:
                            error_msg += f", 响应内容: {response.text}"
                        
                        if response.status_code == 403:
                            error_msg += " (权限被拒绝，可能需要重新获取mt令牌)"
                            # 403错误重试可能没有意义，抛出特定异常
                            raise Exception(error_msg)
                        else:
                            # 其他状态码可能是临时问题，可以重试
                            raise requests.exceptions.HTTPError(error_msg)
                            
                    # 检查响应内容是否为空
                    if not response.text:
                        raise Exception("服务器返回空响应")
                        
                    # 尝试解析JSON
                    try:
                        json_data = json.loads(response.text)
                    except json.JSONDecodeError as e:
                        raise Exception(f"JSON解析错误: {str(e)}, 原始响应: {response.text}")
                        
                    # 检查是否存在data字段
                    file_id = json_data.get('data', {}).get('id')
                    if not file_id:
                        raise Exception(f"响应中未找到file_id: {response.text}")
                        
                    logger.info(f"视频上传成功 - {file_name}, file_id: {file_id}")
                    # 返回一个元组，与upload_large_video保持一致
                    return file_id, file_name
                    
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # 网络连接问题或超时，适合重试
                retry_count += 1
                logger.warning(f"网络错误(尝试 {retry_count}/{max_retries}) - {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"视频上传失败(网络错误): {str(e)}")
                time.sleep(2 * retry_count)  # 递增等待时间
                
            except requests.exceptions.HTTPError as e:
                # HTTP错误，可能是临时性问题
                retry_count += 1
                logger.warning(f"HTTP错误(尝试 {retry_count}/{max_retries}) - {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"视频上传失败(HTTP错误): {str(e)}")
                time.sleep(2 * retry_count)
                
            except json.JSONDecodeError as e:
                # JSON解析错误
                retry_count += 1
                logger.warning(f"JSON解析错误(尝试 {retry_count}/{max_retries}) - {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"视频上传失败(JSON解析错误): {str(e)}")
                time.sleep(2 * retry_count)
                
            except Exception as e:
                # 其他未预期的错误
                retry_count += 1
                logger.error(f"上传错误(尝试 {retry_count}/{max_retries}) - {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"视频上传失败: {str(e)}")
                time.sleep(2 * retry_count)
                
        # 不应该到达这里，但为了安全
        raise Exception("视频上传失败: 未知错误")
            
    except Exception as e:
        logger.error(f"视频上传失败 - {file_path}: {str(e)}")
        # 确保抛出异常，而不是返回None
        raise Exception(f"视频上传失败: {str(e)}")


def upload_large_video(mt, file_path, file_size):
    """
    分块上传大文件，通过队列控制内存使用
    
    参数:
    - mt: 上传令牌
    - file_path: 文件路径
    - file_size: 文件大小(字节)
    
    返回:
    - file_id: 文件ID (字符串或(file_id, file_name)的元组)
    - file_name: 文件名
    """
    file_name = os.path.basename(file_path)
    logger.info(f"开始分块上传大文件 - {file_name}, 大小: {file_size/1024/1024:.2f}MB")
    
    # 最大重试次数
    max_retries = 3  
    retry_count = 0
    chunk_size = 4 * 1024 * 1024  # 4MB 分块大小
    
    while retry_count < max_retries:
        try:
            # 1. 计算文件MD5
            file_md5 = ""
            with open(file_path, 'rb') as f:
                file_md5 = calculate_file_md5(f)
            
            # 2. 初始化上传 - 获取file_id
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'origin': 'https://c.alipay.com',
                'priority': 'u=1, i',
                'referer': 'https://c.alipay.com/',
                'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'x-mass-appkey': 'apwallet',
                'x-mass-biztype': 'content_lifetab',
                'x-mass-cust-conf': '{"extern":{"isWaterMark":true}}',
                'x-mass-file-length': str(file_size),
                'x-mass-file-md5': file_md5,
                'x-mass-file-multipart-slice-size': '4194304',  # 4MB
                'x-mass-filename': urllib.parse.quote(file_name),
                'x-mass-public': 'false',
                'x-mass-token': mt,
                'x-mass-traceid': get_traid(),
            }

            # 初始化上传请求
            response = requests.post('https://mass.alipay.com/file/multipart/upload/claim', headers=headers)
            
            # 检查状态码
            if response.status_code != 200:
                error_msg = f"初始化上传失败 - HTTP错误: {response.status_code}"
                if response.text:
                    error_msg += f", 响应内容: {response.text}"
                raise Exception(error_msg)
            
            # 获取file_id
            json_data = response.json()
            if not json_data.get('data') or not json_data['data'].get('fileId'):
                raise Exception(f"响应中未找到file_id: {response.text}")
                
            file_id = json_data['data']['fileId']
            logger.info(f"初始化上传成功，获取到file_id: {file_id}")
            
            # 3. 处理分块上传
            num_chunks = (file_size // chunk_size) + (1 if file_size % chunk_size else 0)
            logger.info(f"文件将被分为 {num_chunks} 个块上传")
            
            # 创建任务队列和结果队列
            task_queue = queue.Queue(maxsize=5)  # 限制队列大小更严格控制内存
            result_queue = queue.Queue()
            
            # 创建停止标志
            stop_event = threading.Event()
            
            # 定义生产者函数 - 读取文件块
            def chunk_producer():
                try:
                    with open(file_path, 'rb') as file:
                        for chunk_number in range(1, int(num_chunks) + 1):
                            if stop_event.is_set():
                                break
                            # 读取当前分块
                            chunk_data = file.read(chunk_size)
                            if not chunk_data:
                                break
                            # 计算开始位置
                            start_pos = (chunk_number - 1) * chunk_size
                            # 放入队列
                            task_queue.put((chunk_number, chunk_data, start_pos))
                            logger.info(f"生产者: 已读取分块 {chunk_number}/{num_chunks}")
                finally:
                    # 添加结束标记
                    for _ in range(max_workers):
                        task_queue.put(None)
                    logger.info("生产者: 所有分块已读取完成")
            
            # 定义消费者函数 - 上传分块
            def chunk_consumer():
                while not stop_event.is_set():
                    try:
                        # 从队列获取任务
                        task = task_queue.get(timeout=60)  # 60秒超时
                        if task is None:
                            task_queue.task_done()
                            break
                            
                        chunk_number, chunk_data, start_pos = task
                        logger.info(f"消费者: 开始上传分块 {chunk_number}/{num_chunks}")
                        
                        # 上传分块
                        success = _upload_chunk(
                            mt=mt,
                            file_id=file_id,
                            chunk_number=chunk_number,
                            chunk_data=chunk_data,
                            start_pos=start_pos,
                            total_chunks=num_chunks
                        )
                        
                        # 将结果放入结果队列
                        result_queue.put((chunk_number, success))
                        task_queue.task_done()
                        logger.info(f"消费者: 完成分块 {chunk_number}/{num_chunks} 上传, 成功: {success}")
                        
                    except queue.Empty:
                        logger.warning("消费者: 等待任务超时")
                        continue
                    except Exception as e:
                        logger.error(f"消费者: 分块上传错误: {str(e)}")
                        result_queue.put((chunk_number, False))
                        task_queue.task_done()
            
            # 启动生产者线程
            producer_thread = threading.Thread(target=chunk_producer)
            producer_thread.daemon = True
            producer_thread.start()
            
            # 启动消费者线程池
            max_workers = min(8, int(num_chunks))  # 最多8个线程，降低内存占用
            consumers = []
            for _ in range(max_workers):
                consumer = threading.Thread(target=chunk_consumer)
                consumer.daemon = True
                consumer.start()
                consumers.append(consumer)
            
            # 等待所有分块上传完成
            failed_chunks = []
            completed_chunks = 0
            
            try:
                while completed_chunks < num_chunks and not stop_event.is_set():
                    try:
                        chunk_number, success = result_queue.get(timeout=60)
                        if not success:
                            failed_chunks.append(chunk_number)
                        completed_chunks += 1
                        result_queue.task_done()
                        logger.info(f"主线程: 已完成 {completed_chunks}/{num_chunks} 个分块")
                    except queue.Empty:
                        logger.warning("主线程: 等待上传结果超时")
                        continue
            except KeyboardInterrupt:
                logger.info("接收到中断信号，正在停止上传...")
                stop_event.set()
                raise
            
            # 等待所有线程完成
            producer_thread.join(timeout=60)
            for consumer in consumers:
                consumer.join(timeout=60)
            
            # 如果有失败的分块，抛出异常
            if failed_chunks:
                raise Exception(f"有 {len(failed_chunks)} 个分块上传失败: {failed_chunks}")
            
            # 4. 完成上传
            logger.info(f"所有分块上传完成，开始调用upload complete - file_id: {file_id}")
            upload_complete(mt, file_id=file_id)
            logger.info(f"完成上传成功 - file_id: {file_id}")
            return file_id, file_name
                
        except Exception as e:
            retry_count += 1
            logger.error(f"大文件上传失败(尝试 {retry_count}/{max_retries}) - {str(e)}")
            if retry_count >= max_retries:
                logger.error(f"达到最大重试次数，放弃上传 - {file_name}")
                raise Exception(f"视频上传失败: {str(e)}")
            
            # 等待后重试
            time.sleep(3)
    
    # 不应该到达这里，但为了安全
    raise Exception(f"视频上传失败: 未知错误")


def upload_complete(mt, file_id):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        # 'content-length': '0',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'x-mass-appkey': 'apwallet',
        'x-mass-biztype': 'content_lifetab',
        'x-mass-file-multipart-id': file_id,
        'x-mass-token': mt
    }

    response = requests.post('https://mass.alipay.com/file/multipart/upload/complete', headers=headers)
    logger.info(response.json())

def _upload_chunk(mt, file_id, chunk_number, chunk_data, start_pos, total_chunks):
    """
    上传单个分块
    
    参数:
    - mt: 上传令牌
    - file_id: 文件ID
    - chunk_number: 分块序号
    - chunk_data: 分块数据
    - start_pos: 分块起始位置
    - total_chunks: 总分块数
    
    返回:
    - True: 上传成功
    - False: 上传失败
    """
    max_retries = 3  # 最大重试次数
    retry_count = 0
    base_timeout = (30, 60)  # 基础超时时间(连接超时30秒，读写超时60秒)
    
    while retry_count <= max_retries:
        try:
            # 构建请求头
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'origin': 'https://c.alipay.com',
                'referer': 'https://c.alipay.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'x-mass-appkey': 'apwallet',
                'x-mass-biztype': 'content_lifetab',
                'x-mass-file-multipart-id': file_id,
                'x-mass-file-multipart-length': str(len(chunk_data)),
                'x-mass-file-multipart-num': str(chunk_number),
                'x-mass-file-multipart-start': str(start_pos),
                'x-mass-token': mt,
                'x-mass-traceid': get_traid()
            }
            
            # 打印分块上传请求参数
            logger.info(f"\n分块 {chunk_number}/{total_chunks} 上传请求:")
            logger.info(f"分块信息:")
            logger.info(f"  - 文件ID: {file_id}")
            logger.info(f"  - 分块大小: {human_readable_size(len(chunk_data))}")
            logger.info(f"  - 起始位置: {start_pos}")
            
            # 上传分块
            files = {
                'file': ('blob', chunk_data, 'application/octet-stream'),
            }
            
            # 使用会话以支持重试
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                max_retries=1,
                pool_connections=10,
                pool_maxsize=10
            )
            session.mount('https://', adapter)
            
            # 根据重试次数动态调整超时时间
            current_timeout = (
                base_timeout[0] * (retry_count + 1),  # 连接超时随重试次数增加
                base_timeout[1] * (retry_count + 1)   # 读写超时随重试次数增加
            )
            
            # 发送请求，设置适当的超时
            try:
                logger.info(f"开始上传分块 {chunk_number}/{total_chunks}, 超时设置: 连接{current_timeout[0]}秒, 读写{current_timeout[1]}秒")
                response = session.post(
                    'https://mass.alipay.com/file/multipart/upload/part', 
                    headers=headers, 
                    files=files, 
                    timeout=current_timeout
                )
                
                # 打印完整响应内容
                logger.info(f"\n分块 {chunk_number}/{total_chunks} 上传响应:")
                logger.info(f"状态码: {response.status_code}")
                
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"分块 {chunk_number}/{total_chunks} - 网络错误: {str(e)}")
                raise  # 抛出异常以进入重试逻辑
            finally:
                # 确保会话被关闭
                session.close()
            
            # 检查响应
            if response.status_code == 403:
                # 403错误特殊处理，权限问题，重试意义不大
                logger.error(f"分块 {chunk_number}/{total_chunks} 上传被拒绝(403)")
                return False
            elif response.status_code != 200:
                # 其他HTTP错误，可以重试
                raise requests.exceptions.HTTPError(
                    f"HTTP错误({response.status_code}): {response.text}"
                )
                
            # 解析JSON响应
            try:
                json_data = response.json()
                if json_data.get('success') is not True:
                    error_msg = f"服务器返回失败: {json_data}"
                    if 'data' in json_data and 'missingParts' in json_data['data']:
                        error_msg += f", 缺失分块: {json_data['data']['missingParts']}"
                    raise Exception(error_msg)
                    
                # 上传成功
                logger.info(f"分块 {chunk_number}/{total_chunks} 上传成功")
                return True
                
            except json.JSONDecodeError as e:
                raise Exception(f"解析响应JSON失败: {str(e)}")
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"分块 {chunk_number}/{total_chunks} - 达到最大重试次数")
                return False
                
            # 使用指数退避策略计算等待时间
            wait_time = min(60, (2 ** retry_count) + random.uniform(0, 1))
            logger.warning(f"分块 {chunk_number}/{total_chunks} - 网络错误(尝试 {retry_count}/{max_retries})")
            logger.warning(f"错误详情: {str(e)}")
            logger.warning(f"等待 {wait_time:.1f} 秒后重试...")
            time.sleep(wait_time)
            
        except requests.exceptions.HTTPError as e:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"分块 {chunk_number}/{total_chunks} - 达到最大重试次数")
                return False
                
            wait_time = min(60, retry_count * 5)
            logger.warning(f"分块 {chunk_number}/{total_chunks} - HTTP错误(尝试 {retry_count}/{max_retries}): {str(e)}")
            logger.warning(f"等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
            
        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"分块 {chunk_number}/{total_chunks} - 达到最大重试次数")
                return False
                
            wait_time = min(60, retry_count * 5)
            logger.error(f"分块 {chunk_number}/{total_chunks} - 未知错误(尝试 {retry_count}/{max_retries}): {str(e)}")
            logger.warning(f"等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
    
    # 不应该到达这里，但为了安全
    return False


def upload_pic(cookies, video_file_path):
    # 将视频文件路径的扩展名为.jpg
    pic_path = os.path.splitext(video_file_path)[0] + '.jpg'

    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    # 打开对应的图片文件
    with open(pic_path, 'rb') as file:
        files = {
            'Filedata': (file.name, file, 'application/octet-stream'),
        }

        response = requests.post('https://contentweb.alipay.com/life/uploadPicAjax.json',
                                 cookies=cookies,
                                 headers=headers,
                                 files=files)
        return json.loads(response.text).get('extProperty')


def get_video_url(file_id, mt, max_retries=60, retry_interval=1):  # 60次 * 10秒 = 10分钟
    """
    获取视频URL，10分钟内每10秒重试一次
    """
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    for attempt in range(max_retries):
        try:
            # 构建请求URL
            url = f'https://mmtcapi.alipay.com/video/2.0/convert/query?fileId={file_id}&mt={mt}&bizKey=content_lifetab'
            
            # 打印请求参数
            logger.info(f"\n获取视频URL - 第{attempt + 1}次尝试:")
            logger.info(f"URL: {url}")
            logger.info(f"Headers: {json.dumps(headers, indent=2, ensure_ascii=False)}")
            logger.info(f"参数信息:")
            logger.info(f"  - 文件ID: {file_id}")
            logger.info(f"  - MT令牌: {mt}")
            
            # 发送请求
            response = requests.get(url, headers=headers)
            
            # 打印响应内容
            logger.info(f"\n获取视频URL响应 - 第{attempt + 1}次尝试:")
            logger.info(f"状态码: {response.status_code}")
            logger.info(f"响应头: {json.dumps(dict(response.headers), indent=2, ensure_ascii=False)}")
            
            try:
                response_json = json.loads(response.text)
                logger.info(f"响应内容: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
                
                data = response_json.get('data', {})
                trans_code = data.get('transCode', {})
                convert_results = trans_code.get('convertResults', [])

                if convert_results and convert_results[0].get('url'):
                    video_url = convert_results[0].get('url')
                    logger.info(f"成功获取到视频URL: {video_url}")
                    return video_url
                else:
                    logger.info("未获取到视频URL，等待重试...")
            except json.JSONDecodeError as e:
                logger.error(f"解析响应JSON失败: {str(e)}")
                logger.info(f"原始响应内容: {response.text}")

            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_interval} 秒后重试...")
            time.sleep(retry_interval)

        except Exception as e:
            logger.error(f'获取视频URL失败: {str(e)}')
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_interval} 秒后重试...")
                time.sleep(retry_interval)
            else:
                raise Exception(f"获取视频URL失败，已重试{max_retries}次: {str(e)}")

    raise Exception(f"获取视频URL失败，已达到最大重试次数({max_retries}次)")

def format_time_string(time_str):
    # 解析时间字符串
    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
    # 重新格式化，确保小时是两位数
    formatted_time = dt.strftime('%Y-%m-%d %H:%M')
    return formatted_time

def publish(loginPublicId=None, videoId=None, videoFile=None, videoFileName=None, extProperty=None, mt=None,
          scheduleTime=None, title=None, cookies=None, topic_info=None, trace_id=None):
    """
    发布视频
    
    参数:
        loginPublicId: 登录用户ID
        videoId: 视频ID（可能是字符串或元组）
        videoFile: 视频文件URL
        videoFileName: 视频文件名
        extProperty: 封面图属性
        mt: 上传令牌
        scheduleTime: 定时发布时间
        title: 视频标题
        cookies: Cookie
        topic_info: 话题信息，格式为 [[名称,权重], ...]
        trace_id: 追踪ID
        
    返回:
        字典，包含发布结果
    """
    # 更新发布状态为发布中
    if trace_id:
        publish_monitor.update_publish_status(trace_id, 'publishing')
    
    # 最大重试次数和等待时间
    max_retries = 5
    retry_intervals = [5, 10, 15, 30, 60]  # 重试等待时间逐渐增加
    
    # 检查并处理videoId，可能是元组形式
    original_video_id = videoId
    if isinstance(videoId, tuple) and len(videoId) > 0:
        videoId = videoId[0]
        logger.info(f"videoId是元组，提取第一个元素: {videoId}, 原始值: {original_video_id}")
    
    # 处理title参数
    if title is None or title == "":
        title = "无标题视频"
        logger.warning(f"未指定标题，使用默认标题: {title}")
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }
    
    # 添加params参数
    params = {
        'loginPublicId': loginPublicId,
    }

    # 修改请求体结构
    json_data = {
        'loginPublicId': loginPublicId,
        'sourceId': 'sweb',
        'videoId': videoId,
        'videoDjangoId': videoId,
        'massToken': mt,
        'videoFile': videoFile,
        'videoFileName': videoFileName,
        'title': os.path.splitext(os.path.basename(videoFileName))[0],
        'text': title,
        'canSmartCover': True,
        'canReply': True,
        'canSelectReply': False,
        'canDownload': False,
        'contentType': 2,
        'imageList': [
            {
                'djangoId': extProperty.get('djangoId') if extProperty else None,
                'imageUrl': extProperty.get('filePath') if extProperty else None,
                'width': extProperty.get('width') if extProperty else None,
                'height': extProperty.get('height') if extProperty else None,
                'type': 'cover_static',
                'index': 0,
            },
            {
                'djangoId': extProperty.get('djangoId') if extProperty else None,
                'imageUrl': extProperty.get('filePath') if extProperty else None,
                'width': extProperty.get('width') if extProperty else None,
                'height': extProperty.get('height') if extProperty else None,
                'type': 'cover_vertical_static',
                'index': 1,
            },
            {
                'djangoId': extProperty.get('djangoId') if extProperty else None,
                'imageUrl': extProperty.get('filePath') if extProperty else None,
                'width': extProperty.get('width') if extProperty else None,
                'height': extProperty.get('height') if extProperty else None,
                'type': 'message_cover',
                'index': 2,
            },
        ],
        'offerInfoList': [],
        'topicInfoVOList': [],
        'extInfo': {
            'coverSource': 'custom_settings',
        },
    }

    # 如果有话题信息，添加到json数据中
    if topic_info and 'topicInfoVOList' in topic_info:
        json_data['topicInfoVOList'] = topic_info['topicInfoVOList']
        logger.info(f"添加话题信息: {topic_info['topicInfoVOList']}")

    # 只有当 scheduleTime 有值时才添加到 json_data
    if scheduleTime:
        json_data['scheduleTime'] = format_time_string(scheduleTime)

    # 创建会话以支持正确的Cookie处理
    session = requests.Session()
    
    if cookies:
        # 如果cookies是字典，直接使用
        if isinstance(cookies, dict):
            for key, value in cookies.items():
                session.cookies.set(key, value)
        # 如果cookies是RequestsCookieJar，也直接使用
        elif isinstance(cookies, requests.cookies.RequestsCookieJar):
            session.cookies.update(cookies)
        # 如果cookies是字符串，尝试解析JSON
        elif isinstance(cookies, str):
            try:
                cookies_dict = json.loads(cookies)
                for key, value in cookies_dict.items():
                    session.cookies.set(key, value)
            except json.JSONDecodeError:
                logger.error(f"无法解析cookies字符串: {cookies}")
                if trace_id:
                    publish_monitor.update_publish_status(trace_id, 'failed', "无效的cookies格式")
                return {"success": False, "error": "无效的cookies格式"}
    
    # 重试机制
    for retry in range(max_retries):
        try:
            logger.info(f"发布视频尝试 {retry+1}/{max_retries}")
            
            # 打印请求参数
            logger.info("发布视频请求参数:")
            logger.info(f"URL: https://contentweb.alipay.com/life/publishShortVideo.json")
            logger.info(f"Params: {json.dumps(params, indent=2, ensure_ascii=False)}")
            logger.info(f"Headers: {json.dumps(headers, indent=2, ensure_ascii=False)}")
            logger.info(f"JSON数据: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
            
            # 使用会话发送请求
            response = session.post(
                'https://contentweb.alipay.com/life/publishShortVideo.json',
                params=params,
                headers=headers,
                json=json_data,
                timeout=30  # 设置30秒超时
            )
            
            # 打印响应信息
            logger.info(f"发布响应状态码: {response.status_code}")
            logger.info(f"发布响应头: {json.dumps(dict(response.headers), indent=2, ensure_ascii=False)}")
            logger.info(f"发布响应内容: {response.text}")
            
            # 检查HTTP状态码
            if response.status_code != 200:
                error_msg = f"发布失败 - HTTP错误: {response.status_code}"
                
                # 特殊处理状态码502（服务器忙）
                if response.status_code == 502:
                    logger.warning(f"服务器忙(502)，将在 {retry_intervals[retry]} 秒后重试")
                    time.sleep(retry_intervals[retry])
                    continue
                    
                # 对其他错误直接返回失败结果
                if trace_id:
                    publish_monitor.update_publish_status(trace_id, 'failed', error_msg)
                return {"success": False, "error": error_msg}
            
            # 解析JSON响应
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"解析响应JSON失败: {str(e)}, 响应: {response.text}")
                # 判断是否需要重试
                if retry < max_retries - 1:
                    logger.warning(f"将在 {retry_intervals[retry]} 秒后重试")
                    time.sleep(retry_intervals[retry])
                    continue
                if trace_id:
                    publish_monitor.update_publish_status(trace_id, 'failed', f"解析响应JSON失败: {str(e)}")
                return {"success": False, "error": f"解析发布响应失败: {str(e)}"}
            
            # 处理结果
            stat = result.get('stat')
            
            if stat == 'ok':
                # 直接使用result字符串作为发布ID
                publish_id = result.get('result')
                logger.info(f"发布成功，publish_id: {publish_id}")
                
                # 更新发布状态为成功
                if trace_id:
                    publish_monitor.update_publish_status(trace_id, 'success')
                    
                return {"success": True, "publish_id": publish_id}
            else:
                error_msg = result.get('message', '未知错误')
                
                # 处理特定错误类型
                if "已经发布过" in error_msg:
                    logger.warning(f"视频已发布过: {error_msg}")
                    if trace_id:
                        publish_monitor.update_publish_status(trace_id, 'success')
                    return {"success": True, "message": "视频已发布"}
                
                # 判断是否需要重试
                if retry < max_retries - 1 and ("服务器忙" in error_msg or "临时服务不可用" in error_msg):
                    logger.warning(f"服务器忙，将在 {retry_intervals[retry]} 秒后重试: {error_msg}")
                    time.sleep(retry_intervals[retry])
                    continue
                
                # 更新发布状态为失败
                if trace_id:
                    publish_monitor.update_publish_status(trace_id, 'failed', error_msg)
                    
                return {"success": False, "error": error_msg}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"发布请求异常: {str(e)}")
            
            # 判断是否需要重试
            if retry < max_retries - 1:
                logger.warning(f"将在 {retry_intervals[retry]} 秒后重试")
                time.sleep(retry_intervals[retry])
                continue
                
            # 更新发布状态为失败
            if trace_id:
                publish_monitor.update_publish_status(trace_id, 'failed', f"发布请求异常: {str(e)}")
                
            return {"success": False, "error": f"发布请求异常: {str(e)}"}
            
        except Exception as e:
            logger.error(f"发布时出现意外错误: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 判断是否需要重试
            if retry < max_retries - 1:
                logger.warning(f"将在 {retry_intervals[retry]} 秒后重试")
                time.sleep(retry_intervals[retry])
                continue
                
            # 更新发布状态为失败
            if trace_id:
                publish_monitor.update_publish_status(trace_id, 'failed', f"发布时出现意外错误: {str(e)}")
                
            return {"success": False, "error": f"发布时出现意外错误: {str(e)}"}
    
    # 如果所有重试都失败
    if trace_id:
        publish_monitor.update_publish_status(trace_id, 'failed', "已达到最大重试次数，发布失败")
    return {"success": False, "error": "已达到最大重试次数，发布失败"}


def get_app_id(cookies):
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9',
        # 'cookie': 'JSESSIONID=RZ55O44FqJ7TLy6FuB56IeP8I1jioTauthRZ43GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; session.cookieNameId=ALIPAYJSESSIONID; cna=ova4H2k/PjoBASQOA3pmflO9; receive-cookie-deprecation=1; tfstk=fjASH1YyuuqS85MrCy3VcDAkuYfQLHGw2y_pSeFzJ_CRAMKp24Xe840BhH-vzMkuUKsBDnsRU85FOHtXDUWEreUCJn5RKLSF4M1B-hgqbflwrUfhMcoZ_-l8X61gpze8YoFAz4Yt0RlwrU4Aut_oafrCoxd62MKdetBA8iU8pHBpkjIc-wERJ73jlwjYwuCLejFARaU8pHCKlEIcJb2T5wM5qUgqX06jAmckriNL1PvVebLzLWPeGa6W9ejfFTOfPTsOn39DdQK2JQRlnxyctEJ6ApKnQ-fWJLCR7Uc7G1LJ3B_2T2yC23AXkQXb75WWpw6O9taL9E1lctdC6fEfoKLypQx7RWQkaCWCjtgLt95v_Op9Vy0Mk_QpxOAEj7jJJFAMQ1G4e1LXph9C4dNNfEVLdr6gOZsZlqw3KESn1BlzzPIPeZb53qgb2pXRoZswTqwkKTQcPNujluph.; EXC_ANT_KEY=excashier_20001_FP_SENIOR_HJPGP11505070830582; LoginForm=alipay_login_auth; CLUB_ALIPAY_COM=2088442960985162; iw.userid="K1iSL120ipFvFLCnWp3Rzw=="; ali_apache_tracktmp="uid=2088442960985162"; ALI_PAMIR_SID=U16UPhMbPMFmHACo+5UbbeIqTE2#v7dhBGJlS0WhITjHKU3RJTE2; __TRACERT_COOKIE_bucUserId=2088442960985162; auth_goto_http_type=https; ctoken=R6PCbj3w7TAYSw-o; _CHIPS-ctoken=R6PCbj3w7TAYSw-o; alipay="K1iSL120ipFvFLCnWp3Rz9W5rYlr9VP9dcKwk8Zv/g=="; auth_jwt=e30.eyJleHAiOjE3MzM3NTIyMDcyOTIsInJsIjoiNSwwLDI3LDE5LDI5LDEzLDEwIiwic2N0IjoiY1NQbERpWU5DK3pJRW5ja0V5NE1vK2lGTHhXeHlhSmI1OGYwM2V2IiwidWlkIjoiMjA4ODQ0Mjk2MDk4NTE2MiJ9._DCO3Uk3vQWyIwid3mx_QH_QS2jyx2GF_jnJAvElo-s; _CHIPS-ALIPAYJSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43; zone=GZ00F; ALIPAYJSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43GZ00; rtk=bXk6Oqseuv4JU4DLLXnqJ9ojkfUMBQACD3KTlhIozGT2BQgizes; userId=2088442960985162; JSESSIONID=C3C2EBAE3D29394EBDCF0CD321DACF66; spanner=YAtShxmvaflihRYh57A31ceymNvmR9/NXt2T4qEYgj0=',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    params = {
        'sourceId': 'S',
        'appId': '2030095407214168',
        '_input_charset': 'utf-8',
        '_output_charset': 'utf-8',
        '_ksTS': '1733760780838_1',
        'ctoken': 'gwha_z9s2Q7fFA04',
    }
    response = requests.get('https://contentweb.alipay.com/life/getAppEnv.json', params=params, cookies=cookies,
                            headers=headers)
    return json.loads(response.text).get('result').get('appId')


def calculate_file_md5(file_obj):
    """
    计算文件的MD5值
    
    参数:
        file_obj: 文件对象（已打开的文件）
    
    返回:
        文件的MD5哈希值
    """
    # 保存文件当前位置
    current_position = file_obj.tell()
    
    try:
        # 重置文件指针到开头
        file_obj.seek(0)
        
        # 计算MD5
        md5_hash = hashlib.md5()
        for chunk in iter(lambda: file_obj.read(4096), b''):
            md5_hash.update(chunk)
            
        return md5_hash.hexdigest()
    finally:
        # 无论成功失败，都恢复文件指针到原始位置
        file_obj.seek(current_position)


def create_cover_from_video(video_path, output_path=None):
    try:
        video_path = video_path.replace('\\', '/')
        
        # 检查是否已存在同名jpg文件
        default_jpg = os.path.splitext(video_path)[0] + '.jpg'
        if os.path.exists(default_jpg):
            logger.info(f"使用已存在的封面图: {default_jpg}")
            return default_jpg

        if not os.path.exists(video_path):
            logger.info(f"视频文件不存在: {video_path}")
            return None

        if output_path is None:
            output_path = default_jpg

        output_path = output_path.replace('\\', '/')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频文件: {video_path}")
            try:
                # 删除无法打开的视频文件
                os.remove(video_path)
                logger.info(f"已删除无法打开的视频文件: {video_path}")
            except Exception as e:
                logger.error(f"删除视频文件失败: {str(e)}")
            return None

        try:
            # 获取视频的第一秒的帧
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30
            
            # 设置到第一秒的位置
            frame_position = int(fps)  # 取第一秒的帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
            
            # 读取帧
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.error(f"无法读取指定帧: {video_path}")
                try:
                    # 删除无法读取帧的视频文件
                    os.remove(video_path)
                    logger.info(f"已删除无法读取帧的视频文件: {video_path}")
                except Exception as e:
                    logger.error(f"删除视频文件失败: {str(e)}")
                return None

            # 转换颜色空间
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            
            # 获取原始尺寸
            original_width = img.width
            original_height = img.height
            
            # 判断是否为横屏视频
            is_landscape = original_width > original_height
            
            if is_landscape:
                # 横屏视频：1440x1080
                target_width = 1440
                target_height = 1080
                # 计算缩放比例
                scale = max(target_width/original_width, target_height/original_height)
            else:
                # 竖屏视频：2030x2700
                target_width = 2030
                target_height = 2700
                # 计算缩放比例
                scale = max(target_width/original_width, target_height/original_height)
            
            # 等比例缩放
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            resize_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 居中裁剪
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            
            # 裁剪到目标尺寸
            final_img = resize_img.crop((left, top, right, bottom))
            
            # 保存图片
            final_img.save(output_path, "JPEG", quality=95)
            logger.info(f"成功生成封面图: {output_path}")

            # 验证文件是否成功生成
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            return None

        finally:
            cap.release()
            
    except Exception as e:
        logger.error(f"创建封面图过程发生异常: {str(e)}")
        try:
            # 如果处理过程中出现任何错误，删除视频文件
            if os.path.exists(video_path):
                os.remove(video_path)
                logger.info(f"已删除处理失败的视频文件: {video_path}")
        except Exception as del_e:
            logger.error(f"删除视频文件失败: {str(del_e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def update_publish_stats(appid, success=False, error_msg=None):
    """统一处理发布统计更新
    Args:
        appid: 账号ID
        success: 是否发布成功
        error_msg: 错误信息
    """
    try:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        
        if success:
            cursor.execute('''
                UPDATE user_data 
                SET daily_success = daily_success + 1,
                    last_publish_time = ?
                WHERE appid = ?
            ''', (current_time, appid))
        else:
            cursor.execute('''
                UPDATE user_data 
                SET daily_failed = daily_failed + 1,
                    last_publish_time = ?
                WHERE appid = ?
            ''', (current_time, appid))
        
        conn.commit()
        conn.close()
        
        if error_msg:
            logger.error(f"发布失败: {error_msg}")
            
    except Exception as e:
        logger.error(f"更新发布统计失败: {str(e)}")



def upload_publish_video(cookies, dir_path, title, scheduleTime=None, max_workers=3, appid=None, index=None,
                         max_uploads=None, delete_original=True, topic_info=None):
    """
    上传并发布视频 - 高效异步处理版本
    
    参数:
        cookies: 登录后的cookie
        dir_path: 视频目录路径
        title: 视频标题格式
        scheduleTime: 定时发布时间
        max_workers: 最大工作线程数
        appid: 账号ID
        index: 账号索引
        max_uploads: 最大上传数量
        delete_original: 是否删除原始视频
        topic_info: 话题信息
    
    返回:
        字典，包含上传结果统计
    """
    # 确保监控线程已启动
    if not publish_monitor.is_running:
        publish_monitor.start()
        
    # 如果max_uploads为0，直接返回不上传任何视频
    if max_uploads == 0:
        logger.info(f"上传数量设置为0，跳过上传")
        return {"success": 0, "failed": 0, "total": 0, "details": []}
        
    # 使用子账号的cookies（如果提供了appid）
    if appid:
        logger.info(f"检测到appid参数: {appid}，将使用子账号cookies")
        cookies = get_sub_cookies(cookies, appid)
        logger.info(f"已切换至子账号 {appid} 的cookies")
    
    # 获取视频文件列表
    video_files = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv")):
                video_files.append(os.path.join(root, file))
    
    if not video_files:
        logger.info(f"目录 {dir_path} 中没有找到视频文件")
        return {"success": 0, "failed": 0, "total": 0, "details": []}
    
    # 限制上传数量
    if max_uploads and len(video_files) > max_uploads:
        logger.info(f"视频文件超过最大上传数量限制({max_uploads})，将只上传前{max_uploads}个文件")
        video_files = video_files[:max_uploads]
    
    # 初始化统计信息
    total_count = len(video_files)
    thread_control = ThreadControl()
    
    # 创建发布队列和相关同步变量
    publish_queue = queue.Queue()
    upload_completed = threading.Event()
    processing_completed = threading.Event()
    
    # 统计数据，使用线程安全的计数器
    upload_counter = {"success": 0, "failed": 0, "total": total_count, "processed": 0}
    publish_counter = {"success": 0, "failed": 0, "processed": 0}
    processed_details = []
    
    # 线程安全的统计更新函数
    def update_stats(counter, success=None, failed=None, processed=None):
        with threading.Lock():
            if success is not None:
                counter["success"] += success
            if failed is not None:
                counter["failed"] += failed
            if processed is not None:
                counter["processed"] += processed
    
    # 定义发布处理线程
    def publish_worker():
        """发布处理线程"""
        max_wait_time = 60  # 最多等待60秒
        start_time = time.time()
        
        while (not upload_completed.is_set() or not publish_queue.empty()) and time.time() - start_time < max_wait_time:
            try:
                # 从发布队列获取视频信息，设置很短的超时
                try:
                    publish_info = publish_queue.get(timeout=1)
                except queue.Empty:
                    # 检查是否所有任务都已完成
                    if upload_completed.is_set() and publish_queue.empty():
                        logger.info("所有发布任务已完成")
                        processing_completed.set()  # 设置处理完成信号
                        break
                    
                    # 检查是否超时
                    if time.time() - start_time >= max_wait_time:
                        logger.warning("发布处理超时，将强制退出")
                        break
                        
                    continue
                
                if publish_info is None:  # 结束信号
                    logger.info("收到结束信号，发布线程将退出")
                    break
                    
                file_id = publish_info["file_id"]
                video_name = publish_info["video_name"]
                pic_result = publish_info["pic_result"]
                file_path = publish_info["file_path"]
                mt = publish_info["mt"]
                trace_id = publish_info.get("trace_id")  # 获取trace_id
                
                try:
                    # 发布视频
                    publish_result = publish(
                        loginPublicId=appid,
                        videoId=file_id,
                        videoFile=file_id,  # 使用file_id作为videoFile
                        videoFileName=video_name,
                        extProperty=pic_result,
                        mt=mt,
                        scheduleTime=scheduleTime,
                        title=title,
                        cookies=cookies,
                        topic_info=topic_info,
                        trace_id=trace_id  # 传递trace_id
                    )
                    
                    if publish_result.get("success"):
                        update_stats(publish_counter, success=1, processed=1)
                        if delete_original:
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                logger.error(f"删除原始文件失败: {str(e)}")
                    else:
                        update_stats(publish_counter, failed=1, processed=1)
                        
                except Exception as e:
                    logger.error(f"发布视频时出错: {str(e)}")
                    logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
                    update_stats(publish_counter, failed=1, processed=1)
                    
                finally:
                    publish_queue.task_done()
                    
            except Exception as e:
                logger.error(f"发布处理线程异常: {str(e)}")
                logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
                time.sleep(1)  # 发生异常时等待一秒后继续
                
                # 检查是否超时
                if time.time() - start_time >= max_wait_time:
                    logger.warning("发布处理中出现异常，且已超时，将强制退出")
                    break
        
        # 确保在退出时设置完成信号
        if not processing_completed.is_set():
            logger.info("发布处理线程结束，设置完成信号")
            processing_completed.set()
            
        logger.info("发布线程退出")
    
    # 启动发布处理线程
    publish_thread = threading.Thread(target=publish_worker)
    publish_thread.daemon = True
    publish_thread.start()
    
    # 定义上传函数
    def upload_video(file_path):
        """上传单个视频"""
        try:
            # 添加发布任务到监控系统
            video_info = {
                'video_id': None,  # 将在上传成功后更新
                'title': title,
                'file_path': file_path,
                'appid': appid
            }
            trace_id = publish_monitor.add_publish_task(video_info)
            
            # 更新状态为上传中
            publish_monitor.update_publish_status(trace_id, 'uploading')
            
            # 获取上传令牌
            mt = get_mt(cookies)
            if not mt:
                error_msg = "获取上传令牌失败"
                publish_monitor.update_publish_status(trace_id, 'failed', error_msg)
                return None, None, None, None, None
                
            # 上传视频
            file_size = os.path.getsize(file_path)
            if file_size <= 4 * 1024 * 1024:  # 4MB
                file_id, video_name = upload_4m_video(mt, file_path)
            else:
                file_id, video_name = upload_large_video(mt, file_path, file_size)
                
            if not file_id:
                error_msg = "视频上传失败"
                publish_monitor.update_publish_status(trace_id, 'failed', error_msg)
                return None, None, None, None, None
                
            # 更新视频ID
            video_info['video_id'] = file_id
            publish_monitor.update_publish_status(trace_id, 'publishing')
            
            # 生成并上传封面
            cover_path = None
            pic_result = None
            try:
                cover_path = create_cover_from_video(file_path)
                if cover_path and os.path.exists(cover_path):
                    logger.info(f"开始上传封面: {video_name}")
                    pic_result = upload_pic(cookies, cover_path)
                    if not pic_result:
                        logger.warning(f"封面上传失败，将使用系统生成的封面 - {video_name}")
                else:
                    logger.warning(f"封面生成失败，将使用系统生成的封面 - {video_name}")
            except Exception as e:
                logger.error(f"处理封面时出错: {str(e)}")

            # 如果生成了临时封面文件，删除它
            if cover_path and os.path.exists(cover_path):
                try:
                    os.remove(cover_path)
                    logger.info("已删除临时封面文件")
                except Exception as e:
                    logger.error(f"删除临时封面文件失败: {str(e)}")

            # 将视频信息添加到发布队列
            publish_info = {
                "file_id": file_id,
                "video_name": video_name,
                "pic_result": pic_result,
                "file_path": file_path,
                "mt": mt,  # 传递mt给发布函数
                "trace_id": trace_id  # 添加trace_id到发布信息中
            }
            logger.info(f"将视频添加到发布队列: {video_name}")
            publish_queue.put(publish_info)
            update_stats(upload_counter, success=1, processed=1)

            return file_id, video_name, pic_result, mt, trace_id
                
        except Exception as e:
            error_msg = f"上传发布过程出现异常: {str(e)}"
            logger.error(error_msg)
            if trace_id:
                publish_monitor.update_publish_status(trace_id, 'failed', error_msg)
            return None, None, None, None, None
            
    # 使用线程池进行并发上传
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有上传任务
            futures = [executor.submit(upload_video, file_path) for file_path in video_files]
            
            # 等待所有上传任务完成
            for future in as_completed(futures):
                try:
                    result = future.result()  # 获取结果，捕获任何异常
                    if not any(result):  # 如果上传失败
                        update_stats(upload_counter, failed=1, processed=1)
                    # 成功的情况已经在upload_video中更新了计数器
                except Exception as e:
                    logger.error(f"上传任务执行出错: {str(e)}")
                    logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
                    update_stats(upload_counter, failed=1, processed=1)
            
            # 设置上传完成标志
            upload_completed.set()
            logger.info("所有视频上传任务已完成，等待发布队列处理完成...")
            
            # 向发布队列发送结束信号
            publish_queue.put(None)

            # 限制队列等待时间
            wait_start = time.time()
            max_wait_time = 60  # 最多等待60秒
            
            while not publish_queue.empty() and time.time() - wait_start < max_wait_time:
                logger.info(f"等待发布队列处理完成...剩余 {publish_queue.qsize()} 个任务")
                time.sleep(5)
                
            # 如果队列未空但已超时，强制继续
            if not publish_queue.empty():
                logger.warning(f"发布队列处理超时，仍有 {publish_queue.qsize()} 个任务未处理，将强制继续")
    
    except (KeyboardInterrupt, SystemExit):
        logger.info("接收到终止信号，正在停止所有任务...")
        thread_control.stop()
        upload_completed.set()  # 确保发布线程能够退出
    
    # 等待发布线程完成，但设置超时
    logger.info("等待发布线程完成...")
    start_time = time.time()
    max_thread_wait = 30  # 30秒超时
    
    while publish_thread.is_alive() and time.time() - start_time < max_thread_wait:
        time.sleep(1)
        
    if publish_thread.is_alive():
        logger.warning("发布线程等待超时，将强制继续")
    
    # 确保处理完成信号已设置
    if not processing_completed.is_set():
        logger.warning("处理完成信号未设置，将强制设置")
        processing_completed.set()
    
    # 创建最终结果
    logger.info(f"账号 {appid} 的视频处理完成统计:")
    logger.info(f"上传统计 - 总计: {total_count}, 成功: {upload_counter['success']}, 失败: {upload_counter['failed']}")
    logger.info(f"发布统计 - 处理: {publish_counter['processed']}, 成功: {publish_counter['success']}, 失败: {publish_counter['failed']}")
    
    # 真正的成功只有发布成功的
    success_count = publish_counter["success"]
    # 失败包括：上传失败的 + (上传成功但发布失败的)
    # 上传成功但发布失败 = 上传成功数 - 发布成功数
    upload_success_publish_failed = max(0, upload_counter["success"] - publish_counter["success"])
    failed_count = upload_counter["failed"] + upload_success_publish_failed
    
    logger.info(f"最终统计结果 - 总计: {total_count}, 成功: {success_count}, 失败: {failed_count}")
    
    # 构建返回结果
    result = {
        "success": success_count,
        "failed": failed_count,
        "total": total_count,
        "details": processed_details
    }
    
    # 强制停止监控线程 (不再等待)
    try:
        if publish_monitor.is_running:
            publish_monitor.stop()
    except Exception as e:
        logger.error(f"停止监控线程时出错: {str(e)}")
    
    # 确保函数返回
    logger.info("函数即将返回给app...")
    return result

# 辅助函数 - 转换字节为人类可读的大小
def human_readable_size(size, decimal_places=2):
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

create_table()

class VideoPublishMonitor:
    """
    视频发布监控类
    用于追踪视频发布状态和异常情况
    """
    def __init__(self):
        """初始化视频发布监控器"""
        self.publish_status = {}  # 存储发布状态
        self.monitor_thread = None  # 监控线程
        self.is_running = False  # 运行状态标志
        self.lock = threading.Lock()  # 线程锁
        self.total_tasks = 0  # 总任务数
        self.completed_tasks = 0  # 已完成任务数
        self.all_tasks_completed = threading.Event()  # 所有任务完成事件
        logger.info("视频发布监控器初始化完成")
        
    def start(self):
        """启动监控线程"""
        if not self.is_running:
            self.is_running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("视频发布监控线程已启动")
            
    def stop(self):
        """停止监控线程"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join()
            logger.info("视频发布监控线程已停止")
            
    def add_publish_task(self, video_info):
        """
        添加发布任务
        
        参数:
            video_info: 视频信息字典，包含video_id, title, file_path, appid等
            
        返回:
            str: 追踪ID
        """
        trace_id = str(uuid.uuid4())
        with self.lock:
            self.publish_status[trace_id] = {
                'status': 'pending',
                'start_time': datetime.now(),
                'last_update': datetime.now(),
                'video_info': video_info,
                'error_msg': None
            }
            # 增加总任务数
            self.total_tasks += 1
            logger.info(f"添加发布任务: {trace_id}, 当前总任务数: {self.total_tasks}")
        return trace_id
        
    def update_publish_status(self, trace_id, status, error_msg=None):
        """
        更新发布状态
        
        参数:
            trace_id: 追踪ID
            status: 状态 ('pending', 'uploading', 'publishing', 'success', 'failed')
            error_msg: 错误信息（如果有）
        """
        with self.lock:
            if trace_id in self.publish_status:
                self.publish_status[trace_id]['status'] = status
                self.publish_status[trace_id]['last_update'] = datetime.now()
                if error_msg:
                    self.publish_status[trace_id]['error_msg'] = error_msg
                    
                # 如果状态是成功或失败，增加已完成任务计数
                if status in ['success', 'failed']:
                    self.completed_tasks += 1
                    logger.info(f"任务完成计数: {self.completed_tasks}/{self.total_tasks}")
                    
                # 检查是否所有任务都已完成
                if self.completed_tasks == self.total_tasks and self.total_tasks > 0:
                    logger.info("所有任务已完成，设置完成信号")
                    self.all_tasks_completed.set()
                    logger.info("完成信号已设置")
    
    def get_publish_status(self, trace_id):
        """获取发布状态"""
        with self.lock:
            return self.publish_status.get(trace_id)
            
    def wait_for_completion(self, timeout=30):  # 默认30秒超时
        """
        等待所有发布任务完成
        
        参数:
            timeout: 超时时间（秒）
            
        返回:
            bool: 是否所有任务都已完成
        """
        start_time = time.time()
        # 检查是否有未完成的任务
        with self.lock:
            # 如果没有任务，直接返回True
            if self.total_tasks == 0:
                logger.info("没有待处理的任务，直接返回")
                return True
            
            # 如果所有任务已完成，直接返回True
            if self.completed_tasks == self.total_tasks:
                logger.info(f"所有任务已完成 ({self.completed_tasks}/{self.total_tasks})，直接返回")
                return True
            
            # 否则，设置超时时间
            logger.info(f"等待任务完成... {self.completed_tasks}/{self.total_tasks}")
        
        # 等待完成信号，最多等待timeout秒
        result = self.all_tasks_completed.wait(timeout)
        
        # 超时后强制设置完成信号
        if not result:
            logger.warning(f"等待任务完成超时 ({self.completed_tasks}/{self.total_tasks})，强制设置完成信号")
            self.all_tasks_completed.set()
        
        return True  # 无论如何都返回True，以确保函数能继续执行
            
    def _monitor_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 检查所有发布任务的状态
                with self.lock:
                    current_time = datetime.now()
                    for trace_id, info in self.publish_status.items():
                        # 检查是否有超时的任务（3分钟）
                        if (current_time - info['start_time']).total_seconds() > 180:  # 3分钟
                            if info['status'] not in ['success', 'failed']:
                                info['status'] = 'failed'
                                info['error_msg'] = '发布超时'
                                logger.error(f"发布任务超时: {trace_id}")
                                self.completed_tasks += 1
                                
                                # 检查是否所有任务都已完成
                                if self.completed_tasks == self.total_tasks and self.total_tasks > 0:
                                    self.all_tasks_completed.set()
                                    logger.info("所有发布任务已完成（包含超时任务）")
                                
                time.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                logger.error(f"监控线程异常: {str(e)}")
                time.sleep(10)  # 发生异常时等待10秒后继续

# 创建全局监控实例
publish_monitor = VideoPublishMonitor()