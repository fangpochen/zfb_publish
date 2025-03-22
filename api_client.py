#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sqlite3
import datetime
import requests
import logging
import time
import traceback
import os
from DrissionPage import ChromiumPage, ChromiumOptions

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ApiClient")

class ApiClient:
    """API客户端类，处理所有与服务器的交互"""
    
    def __init__(self, log_callback=None):
        """初始化API客户端
        
        Args:
            log_callback: 日志回调函数
        """
        self.log_callback = log_callback or print
        self.logger = logging.getLogger('ApiClient')
    
    def log_message(self, message):
        """记录日志消息"""
        self.logger.info(message)
        if self.log_callback:
            self.log_callback(message)
    
    def login_account(self):
        """登录账号并获取信息
        
        Returns:
            tuple: (cookies_dict, appid, user_name, all_request) 如果成功
            None: 如果失败
        """
        try:
            self.log_message("开始登录流程...")
            
            # 获取 Chrome 路径
            chrome_path = None
            if os.path.exists('config.json'):
                try:
                    with open('config.json', 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        chrome_path = config.get('chrome_path')
                except Exception as e:
                    self.log_message(f"读取Chrome配置失败: {str(e)}")
            
            # 设置 ChromiumOptions
            co = ChromiumOptions().auto_port()
            co.set_argument('--window-size', '800,600')
            
            # 如果有配置的 Chrome 路径，使用它
            if chrome_path and os.path.exists(chrome_path):
                co.set_browser_path(chrome_path)
                self.log_message(f"使用配置的Chrome路径: {chrome_path}")
            else:
                self.log_message("未找到配置的Chrome路径，使用默认路径")
            
            page = ChromiumPage(co)
            page.set.cookies.clear()
            page.get('https://c.alipay.com/page/portal/home')
            page.scroll.to_rightmost()
            page.wait.url_change('https://c.alipay.com/page/life-account/index', timeout=90)
            page.listen.start('dwcookie?biztype=pcwallet')
            
            # 点击内容发布按钮
            for i in range(3):
                try:
                    page.ele('@@text()=内容发布', timeout=5).click()
                except Exception as e:
                    pass

            # 获取网络请求和cookies
            packets = page.listen.wait(5)
            cookies_list = page.cookies()
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
            
            # 获取用户信息
            from zfb import get_appid
            appid, user_name, account_name = get_appid(cookies_dict)
            
            # 记录请求信息
            all_request = []
            for packet in packets:
                request_data = dict()
                request_data['url'] = packet.url
                request_data['data'] = packet.request.postData
                all_request.append(request_data)
            
            # 关闭浏览器
            page.quit()
            
            # 保存到数据库
            from database import db_manager
            if db_manager.save_account(appid, user_name, cookies_dict):
                self.log_message(f"成功保存账号信息: {user_name} ({appid})")
            else:
                self.log_message(f"保存账号信息失败: {user_name} ({appid})")
            
            return cookies_dict, appid, user_name, all_request
            
        except Exception as e:
            self.log_message(f"登录过程出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def get_life_option_list(self, cookies, appid):
        """
        获取子账号列表
        
        Args:
            cookies: 主账号的cookies
            appid: 主账号的appid
            
        Returns:
            list: 子账号列表，每个子账号包含appId和appName
        """
        try:
            self.log_message(f"正在获取账号 {appid} 的子账号列表...")
            
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
                'ctoken': cookies.get('ctoken', ''),
                'sourceId': 'lifestream',
            }

            response = requests.post(
                'https://contentweb.alipay.com/life/lifeOptionList.json',
                params=params,
                cookies=cookies,
                headers=headers
            )

            if response.status_code != 200:
                self.log_message(f"获取子账号列表请求失败: HTTP {response.status_code}")
                return None

            json_data = response.json()
            if json_data.get('stat') != 'ok':
                self.log_message(f"获取子账号列表失败: {json_data.get('message', '未知错误')}")
                return None

            result = json_data.get('result', [])
            operator_list = []
            
            for operator in result:
                sub_appid = operator.get('appId')
                if sub_appid and sub_appid != appid:  # 跳过主账号
                    operator_list.append({
                        'appId': sub_appid,
                        'appName': operator.get('appName', '')
                    })

            self.log_message(f"成功获取 {len(operator_list)} 个子账号")
            return operator_list

        except Exception as e:
            self.log_message(f"获取子账号列表时出错: {str(e)}")
            return None

    def fetch_sub_accounts(self, cookies, appid):
        """
        获取子账号列表并保存到数据库
        
        Args:
            cookies: 主账号的cookies
            appid: 主账号的appid
            
        Returns:
            list: 子账号列表，每个子账号包含appId和appName
        """
        try:
            # 验证cookies中是否包含必要的字段
            if not cookies or 'ctoken' not in cookies:
                self.log_message(f"Cookie无效: 缺少ctoken")
                return None

            # 获取子账号列表
            sub_accounts = self.get_life_option_list(cookies, appid)
            if not sub_accounts:
                self.log_message(f"未找到子账号数据")
                return None

            processed_accounts = []
            for account in sub_accounts:
                try:
                    # 验证子账号数据的完整性
                    if not isinstance(account, dict):
                        self.log_message(f"子账号数据格式错误: {account}")
                        continue

                    # 获取appId和name
                    sub_appid = account.get('appId')
                    name = account.get('appName')
                    
                    if not sub_appid or not name:
                        self.log_message(f"子账号数据不完整: {account}")
                        continue

                    # 使用db_manager保存子账号信息
                    from database import db_manager
                    if db_manager.save_account(sub_appid, name, cookies):
                        processed_accounts.append({
                            'appId': sub_appid,
                            'appName': name
                        })
                        self.log_message(f"成功保存子账号: {name} ({sub_appid})")
                    else:
                        self.log_message(f"保存子账号失败: {name} ({sub_appid})")

                except Exception as e:
                    self.log_message(f"处理子账号时出错: {str(e)}")
                    continue

            self.log_message(f"成功处理 {len(processed_accounts)} 个子账号")
            return processed_accounts if processed_accounts else None

        except Exception as e:
            self.log_message(f"获取子账号失败: {str(e)}")
            return None
    
    def get_sub_cookies(self, cookies, appid):
        """
        切换到指定账号并返回更新后的cookies
        
        Args:
            cookies: 账号的cookies
            appid: 账号的appid
            
        Returns:
            dict: 更新后的cookies，如果失败则返回None
            bool: 如果只需要切换账号（不需要cookies），则返回是否切换成功
        """
        try:
            self.log_message(f"正在切换到账号 {appid}...")
            
            # 验证cookies
            if not cookies or 'ctoken' not in cookies:
                self.log_message("Cookie无效")
                return None
                
            # 调用切换账号接口
            headers = {
                'accept': 'application/json',
                'accept-language': 'zh-CN,zh;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://c.alipay.com',
                'referer': 'https://c.alipay.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            params = {
                'ctoken': cookies['ctoken'],
                'appId': appid
            }
            
            response = requests.post(
                'https://contentweb.alipay.com/life/lifeSelectSwitch.json',
                params=params,
                cookies=cookies,
                headers=headers
            )
            
            if response.status_code != 200:
                self.log_message(f"切换账号请求失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get('stat') != 'ok':
                self.log_message(f"切换账号失败: {data.get('message', '未知错误')}")
                return None
                
            self.log_message(f"成功切换到账号 {appid}")
            
            # 更新并返回cookies
            res_cookie = cookies.copy()
            for cookie in response.cookies:
                res_cookie[cookie.name] = cookie.value
            return res_cookie
            
        except Exception as e:
            self.log_message(f"切换账号时出错: {str(e)}")
            return None
        
    def query_videos(self, cookies, appid, date=None, page=1, size=20):
        """
        查询账号的视频数据
        
        Args:
            cookies (dict): Cookie数据
            appid (str): 账号ID
            date (str, optional): 日期字符串，格式为'yyyy-MM-dd'。如果不指定，则查询全部日期。
            page (int, optional): 页码。默认为1。
            size (int, optional): 每页记录数。默认为20。
        
        Returns:
            tuple: (videos, total) 其中 videos 是视频列表，total 是总数
            None: 如果查询失败
        """
        try:
            # 构建请求
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'Referer': 'https://contentweb.alipay.com/life/'
            }
            
            # 处理日期参数
            params = {}
            data = {
                'sourceId': 'sweb',
                'appid': appid,
                'page': page,
                'pageSize': size,
                'auditSource': 'QUALITY',
                'statusList': 'all'
            }
            
            # 添加日期参数（如果指定了日期）
            if date:
                # 将yyyy-MM-dd格式转换为yyyyMMdd格式
                date_no_hyphen = date.replace('-', '')
                data['startDate'] = date_no_hyphen
                data['endDate'] = date_no_hyphen
                self.log_message(f"查询指定日期: {date} (格式化为: {date_no_hyphen})")

            # 打印请求信息用于调试
            self.log_message(f"请求URL: https://contentweb.alipay.com/life/publishListV2.json")
            self.log_message(f"请求参数: {json.dumps(params, ensure_ascii=False)}")
            self.log_message(f"请求数据: {json.dumps(data, ensure_ascii=False)}")

            response = requests.post(
                'https://contentweb.alipay.com/life/publishListV2.json',
                params=params,
                cookies=cookies,
                headers=headers,
                data=data
            )

            # 打印响应状态和内容用于调试
            self.log_message(f"响应状态码: {response.status_code}")
            self.log_message(f"响应内容: {response.text[:200]}...")  # 只打印前200个字符避免日志过长

            # 处理响应
            if response.status_code != 200:
                self.log_message(f"获取视频列表失败: HTTP {response.status_code}")
                return None
                
            try:
                json_data = response.json()
            except json.JSONDecodeError:
                self.log_message("解析响应JSON数据失败")
                return None
                
            if json_data.get('stat') != 'ok':
                self.log_message(f"获取视频列表失败: {json_data.get('message', '未知错误')}")
                return None
                
            result = json_data.get('result', {})
            videos = result.get('publishContents', [])
            total = result.get('total', 0)
            
            if not videos:
                self.log_message("未找到视频数据")
                return None
                
            self.log_message(f"成功获取 {len(videos)} 个视频")
            return videos, total

        except Exception as e:
            self.log_message(f"查询视频数据时出错: {str(e)}")
            return None
        
    
    def check_account_style(self, cookies, appid):
        """
        查询账号画风是否符合平台要求
        
        Args:
            cookies: 账号的cookies
            appid: 账号的appid
            
        Returns:
            dict: 包含画风评估结果的字典，如果失败则返回None
        """
        try:
            self.log_message(f"正在查询账号 {appid} 的画风评估...")
            
            # 验证cookies
            if not cookies or 'ctoken' not in cookies:
                self.log_message("Cookie无效")
                return None
                
            # 构建请求
            headers = {
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'origin': 'https://c.alipay.com',
                'referer': 'https://c.alipay.com/',
                'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            }
            
            params = {
                'sourceId': 'S',
                'appId': appid,
                'publicId': appid,
                '_input_charset': 'utf-8',
                '_output_charset': 'utf-8',
                '_ksTS': f'{int(time.time() * 1000)}_{str(int(time.time() * 100))[-1]}',
                'ctoken': cookies.get('ctoken', ''),
            }
            
            response = requests.get(
                'https://contentweb.alipay.com/life/style/queryAccountStyleEvaluation.json',
                params=params,
                cookies=cookies,
                headers=headers,
            )
            
            if response.status_code != 200:
                self.log_message(f"查询账号画风请求失败: HTTP {response.status_code}")
                return None
                
            result = response.json()
            if result.get('stat') != 'ok':
                self.log_message(f"查询账号画风失败: {result.get('message', '未知错误')}")
                return None
            
            # 提取画风评估结果
            style_result = {
                'is_matching': False,
                'title': '未知',
                'raw_data': result
            }
            
            style_data = result.get('result', {})
            style_title = style_data.get('styleEvaluationTitle', '')
            
            # 根据返回的标题判断是否符合画风
            if style_title:
                style_result['title'] = style_title
                # 修复判断逻辑：只有完全等于"符合平台画风"时才算通过
                style_result['is_matching'] = style_title == "符合平台画风"
                
            self.log_message(f"账号 {appid} 画风评估结果: {style_title}")
            return style_result
            
        except Exception as e:
            self.log_message(f"查询账号画风时出错: {str(e)}")
            return None