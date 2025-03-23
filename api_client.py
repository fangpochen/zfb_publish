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
import random
import urllib.parse
import uuid

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ApiClient")

class ApiClient:
    """API客户端类，处理所有与服务器的交互"""
    
    def __init__(self, log_callback=None, thread_control=None):
        """初始化API客户端
        
        Args:
            log_callback: 日志回调函数
            thread_control: 线程控制器，用于停止长时间运行的任务
        """
        self.log_callback = log_callback or print
        self.logger = logging.getLogger('ApiClient')
        self.thread_control = thread_control
    
    def log_message(self, message):
        """记录日志消息
        
        Args:
            message: 日志消息
        """
        # 记录到logger
        logging.getLogger('ApiClient').info(message)
        
        # 回调函数（如果有）
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception as e:
                # 不阻止程序运行，只记录错误
                logging.getLogger('ApiClient').warning(f"记录日志时出错: {str(e)}")
    
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
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
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
            cookies: 当前账号的cookies
            appid: 目标账号的appid
            
        Returns:
            dict: 更新后的cookies，如果失败则返回None
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
            
            # 保存原始cookies用于比较
            original_cookies = cookies.copy()
            
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
                
            # 更新cookies
            res_cookie = cookies.copy()
            
            # 从响应中更新cookies
            for cookie in response.cookies:
                res_cookie[cookie.name] = cookie.value
            
            # 从JSON响应中更新cookies（如果有）
            if 'result' in data and isinstance(data['result'], dict):
                result = data['result']
                if 'switchCookie' in result and isinstance(result['switchCookie'], dict):
                    switch_cookie = result['switchCookie']
                    for key, value in switch_cookie.items():
                        res_cookie[key] = value
            
            # 完整比较cookies变化
            changed_keys = []
            for key in set(list(original_cookies.keys()) + list(res_cookie.keys())):
                if key not in original_cookies:
                    changed_keys.append(f"{key}(新增)")
                elif key not in res_cookie:
                    changed_keys.append(f"{key}(删除)")
                elif original_cookies[key] != res_cookie[key]:
                    changed_keys.append(key)
            
            if changed_keys:
                self.log_message(f"cookies变化的字段: {', '.join(changed_keys)}")
            else:
                self.log_message("警告: 切换账号后cookies没有变化，这可能表示切换失败")
            
            self.log_message(f"成功切换到账号 {appid}")
            return res_cookie
            
        except Exception as e:
            self.log_message(f"切换账号时出错: {str(e)}")
            traceback.print_exc()
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
    
    def get_traid(self):
        """生成交易ID
        
        Returns:
            str: 交易ID
        """
        return f"traid_{uuid.uuid4().hex}"
    
    def get_mt(self,cookies):
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            # 'cookie': 'JSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; session.cookieNameId=ALIPAYJSESSIONID; cna=ova4H2k/PjoBASQOA3pmflO9; receive-cookie-deprecation=1; tfstk=fjASH1YyuuqS85MrCy3VcDAkuYfQLHGw2y_pSeFzJ_CRAMKp24Xe840BhH-vzMkuUKsBDnsRU85FOHtXDUWEreUCJn5RKLSF4M1B-hgqbflwrUfhMcoZ_-l8X61gpze8YoFAz4Yt0RlwrU4Aut_oafrCoxd62MKdetBA8iU8pHBpkjIc-wERJ73jlwjYwuCLejFARaU8pHCKlEIcJb2T5wM5qUgqX06jAmckriNL1PvVebLzLWPeGa6W9ejfFTOfPTsOn39DdQK2JQRlnxyctEJ6ApKnQ-fWJLCR7Uc7G1LJ3B_2T2yC23AXkQXb75WWpw6O9taL9E1lctdC6fEfoKLypQx7RWQkaCWCjtgLt95v_Op9Vy0Mk_QpxOAEj7jJJFAMQ1G4e1LXph9C4dNNfEVLdr6gOZsZlqw3KESn1BlzzPIPeZb53qgb2pXRoZswTqwkKTQcPNujluph.; EXC_ANT_KEY=excashier_20001_FP_SENIOR_HJPGP11505070830582; LoginForm=alipay_login_auth; CLUB_ALIPAY_COM=2088442960985162; iw.userid="K1iSL120ipFvFLCnWp3Rzw=="; ali_apache_tracktmp="uid=2088442960985162"; ALI_PAMIR_SID=U16UPhMbPMFmHACo+5UbbeIqTE2#v7dhBGJlS0WhITjHKU3RJTE2; __TRACERT_COOKIE_bucUserId=2088442960985162; auth_goto_http_type=https; ctoken=R6PCbj3w7TAYSw-o; _CHIPS-ctoken=R6PCbj3w7TAYSw-o; alipay="K1iSL120ipFvFLCnWp3Rz9W5rYlr9VP9dcKwk8Zv/g=="; auth_jwt=e30.eyJleHAiOjE3MzM3NTIyMDcyOTIsInJsIjoiNSwwLDI3LDE5LDI5LDEzLDEwIiwic2N0IjoiY1NQbERpWU5DK3pJRW5ja0V5NE1vK2lGTHhXeHlhSmI1OGYwM2V2IiwidWlkIjoiMjA4ODQ0Mjk2MDk4NTE2MiJ9._DCO3Uk3vQWyIwid3mx_QH_QS2jyx2GF_jnJAvElo-s; _CHIPS-ALIPAYJSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43; zone=GZ00F; ALIPAYJSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43GZ00; rtk=bXk6Oqseuv4JU4DLLXnqJ9ojkfUMBQACD3KTlhIozGT2BQgizes; userId=2088442960985162; JSESSIONID=C3C2EBAE3D29394EBDCF0CD321DACF66; spanner=YAtShxmvaflihRYh57A31ceymNvmR9/NXt2T4qEYgj0=',
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

        response = requests.get('https://contentweb.alipay.com/life/queryMasstoken.json', params=params, cookies=cookies,
                                headers=headers)
        return json.loads(response.text).get("result").get("massToken")
    
    
    def upload_4m_video(self, mt, file_path):
        """上传小视频文件（<4MB）
        
        Args:
            mt: MT令牌
            file_path: 视频文件路径
            
        Returns:
            str: 文件ID，失败则返回None
        """
        try:
            file_name = os.path.basename(file_path)
            self.log_message(f"开始上传小视频: {file_name}")
            
            # 构建请求头
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Origin': 'https://c.alipay.com',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 准备表单数据
            form_data = {
                'fileType': '4',  # 视频文件类型
                'mt': mt,
                'rmsToken': ''
            }
            
            # 准备文件
            files = {
                'file': (file_name, open(file_path, 'rb'), 'application/octet-stream')
            }
            
            # 发送请求
            response = requests.post(
                'https://contentweb.alipay.com/mtcontent/uploadFile.json',
                data=form_data,
                files=files,
                headers=headers
            )
            
            # 关闭文件
            files['file'][1].close()
            
            if response.status_code != 200:
                self.log_message(f"上传视频请求失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get('stat') != 'ok':
                self.log_message(f"上传视频失败: {data.get('message', '未知错误')}")
                return None
                
            file_id = data.get('result', {}).get('fileId', '')
            if not file_id:
                self.log_message("未返回有效的文件ID")
                return None
                
            self.log_message(f"小视频上传成功: {file_name} (fileId: {file_id})")
            return file_id
            
        except Exception as e:
            self.log_message(f"上传小视频时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def upload_large_video(self, mt, file_path, file_size=None):
        """上传大视频文件，使用分块上传方式
        
        Args:
            mt: MT令牌
            file_path: 视频文件路径
            file_size: 文件大小，如果为None则自动获取
            
        Returns:
            tuple: (file_id, file_name) 文件ID和文件名，失败则返回None
        """
        try:
            # 获取文件大小
            if file_size is None:
                file_size = os.path.getsize(file_path)
            
            file_name = os.path.basename(file_path)
            self.log_message(f"开始上传视频: {file_name} ({file_size} 字节)")
            
            # 打开文件
            with open(file_path, 'rb') as file:
                # 构建文件数据
                files = {
                    'file': (file.name, file, 'video/mp4')  # 'file' 是表单字段名，file.name 是文件名，'video/mp4' 是文件的 MIME 类型
                }
                
                # 计算文件MD5
                file_md5 = self._calculate_file_md5(file)
                
                # 获取交易ID
                traid = self.get_traid()
                
                # 构建请求头
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
                    'x-mass-file-multipart-slice-size': '4194304',
                    'x-mass-filename': urllib.parse.quote(file.name),
                    'x-mass-public': 'false',
                    'x-mass-token': mt,
                    'x-mass-traceid': traid,
                }
                
                # 初始化上传
                self.log_message("初始化上传请求")
                response = requests.post('https://mass.alipay.com/file/multipart/upload/claim', headers=headers)
                
                # 检查响应状态
                if response.status_code != 200:
                    self.log_message(f"初始化上传失败: HTTP {response.status_code}")
                    return None
                
                # 解析响应
                try:
                    data = json.loads(response.text)
                    if not data.get('success', False):
                        error_msg = data.get('errorMsg', '未知错误')
                        self.log_message(f"初始化上传失败: {error_msg}")
                        return None
                    
                    file_id = data.get('data', {}).get('fileId')
                    if not file_id:
                        self.log_message("未获取到文件ID")
                        return None
                    
                    self.log_message(f"成功获取文件ID: {file_id}")
                except Exception as e:
                    self.log_message(f"解析响应数据失败: {str(e)}")
                    traceback.print_exc()
                    return None
            
            # 定义上传分块函数
            def upload_part(args):
                """上传单个分块的函数"""
                try:
                    part_num, part_data, start_pos = args
                    part_headers = {
                        'accept': 'application/json, text/plain, */*',
                        'accept-language': 'zh-CN,zh;q=0.9',
                        'origin': 'https://c.alipay.com',
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
                        'x-mass-file-multipart-length': str(len(part_data)),
                        'x-mass-file-multipart-num': str(part_num),
                        'x-mass-file-multipart-start': str(start_pos),
                        'x-mass-token': mt,
                        'x-mass-traceid': self.get_traid()
                    }
                    
                    part_files = {
                        'file': ('blob', part_data, 'application/octet-stream'),
                    }
                    
                    part_response = requests.post(
                        'https://mass.alipay.com/file/multipart/upload/part', 
                        headers=part_headers, 
                        files=part_files,
                        timeout=(30, 120)
                    )
                    return part_response.json()
                except Exception as e:
                    self.log_message(f"分块 {part_num} 上传失败: {str(e)}")
                    raise
            
            # 开始分块上传
            with open(file_path, 'rb') as file:
                # 设置分块大小
                max_size = 4 * 1024 * 1024  # 4MB
                # 计算分块数量
                num_parts = (file_size // max_size) + (1 if file_size % max_size else 0)
                
                # 准备所有分块数据
                upload_args = []
                for i in range(num_parts):
                    part_data = file.read(max_size)
                    if not part_data:
                        break
                    upload_args.append((i + 1, part_data, i * max_size))
                
                # 使用线程池并行上传分块
                import concurrent.futures
                from concurrent.futures import ThreadPoolExecutor
                
                max_workers = min(5, num_parts)  # 最多5个线程
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for args in upload_args:
                        future = executor.submit(upload_part, args)
                        futures.append(future)
                    
                    # 等待所有分块上传完成
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()  # 检查是否有异常
                        except Exception as e:
                            self.log_message(f"分块上传失败: {str(e)}")
                            raise
            
            # 完成上传
            self._upload_complete(mt, file_id)
            
            return file_id, file_name
            
        except Exception as e:
            self.log_message(f"上传视频时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def _upload_complete(self, mt, file_id):
        """完成分块上传
        
        Args:
            mt: MT令牌
            file_id: 文件ID
        """
        try:
            self.log_message(f"完成文件上传: {file_id}")
            
            # 构建请求头
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
                'x-mass-file-multipart-id': file_id,
                'x-mass-token': mt
            }
            
            # 发送完成请求
            response = requests.post('https://mass.alipay.com/file/multipart/upload/complete', headers=headers)
            
            # 记录响应
            self.log_message(f"完成上传响应: {response.json()}")
            
        except Exception as e:
            self.log_message(f"完成上传时出错: {str(e)}")
            traceback.print_exc()
    
    def _calculate_file_md5(self, file):
        """计算文件MD5
        
        Args:
            file: 文件对象
            
        Returns:
            str: 文件MD5哈希值
        """
        # 保存当前文件位置
        current_position = file.tell()
        
        # 重置文件指针到开始
        file.seek(0)
        
        # 创建MD5对象
        import hashlib
        md5_hash = hashlib.md5()
        
        # 分块读取文件并更新MD5
        chunk_size = 8192
        chunk = file.read(chunk_size)
        while chunk:
            md5_hash.update(chunk)
            chunk = file.read(chunk_size)
        
        # 恢复文件指针位置
        file.seek(current_position)
        
        # 返回MD5哈希值
        return md5_hash.hexdigest()
    
    def upload_pic(self, cookies, video_file_path=None):
        """上传视频封面图片
        
        Args:
            cookies: 账号的cookies
            video_file_path: 视频文件路径，用于生成封面图像
            
        Returns:
            str: 图片URL，失败则返回None
        """
        try:
            # 将视频文件路径的扩展名改为.jpg
            if not video_file_path:
                self.log_message("未提供视频文件路径")
                return None
                
            image_path = os.path.splitext(video_file_path)[0] + '.jpg'
            self.log_message(f"封面图片路径: {image_path}")
            
            # 检查图片是否存在
            if not os.path.exists(image_path):
                self.log_message(f"封面图片不存在: {image_path}")
                return None
                
            # 构建请求头
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
            with open(image_path, 'rb') as file:
                files = {
                    'Filedata': (file.name, file, 'application/octet-stream'),
                }

                response = requests.post('https://contentweb.alipay.com/life/uploadPicAjax.json',
                cookies=cookies,
                headers=headers,
                                        files=files)
                return json.loads(response.text).get('extProperty')
                
        except Exception as e:
            self.log_message(f"上传封面时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def get_video_url(self, file_id=None, mt=None, max_retries=12, retry_interval=10, cookies=None, appid=None):
        """获取视频URL，10分钟内每10秒重试一次
        
        Args:
            file_id: 文件ID，如果为None则从cookies获取
            mt: MT令牌，如果为None则从cookies获取
            max_retries: 最大重试次数，默认12次
            retry_interval: 重试间隔，单位秒，默认10秒
            cookies: cookies对象，用于从中获取file_id和mt
            appid: 应用ID，默认不需要
            
        Returns:
            str: 视频URL或None（如果获取失败）
            
        Raises:
            Exception: 超过重试次数仍未获取到视频URL时抛出异常
        """
        try:
            # 如果没有提供file_id和mt，尝试从cookies中获取
            if (file_id is None or mt is None) and cookies is None:
                self.log_message("错误：未提供file_id和mt，且没有提供cookies以获取这些值")
                return None
            
            # 如果mt为None且cookies不为None，尝试从cookies中获取mt
            if mt is None and cookies is not None:
                mt = self.get_mt(cookies)
                if mt is None:
                    self.log_message("从cookies中获取MT令牌失败")
                    return None
            
            # 如果file_id仍然为None
            if file_id is None:
                self.log_message("错误：未提供file_id，无法获取视频URL")
                return None
            
            # 构建请求头
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
            
            # 开始尝试获取视频URL
            for attempt in range(max_retries):
                try:
                    # 发送请求
                    url = f'https://mmtcapi.alipay.com/video/2.0/convert/query?fileId={file_id}&mt={mt}&bizKey=content_lifetab'
                    
                    response = requests.get(url, headers=headers)
                    
                    # 解析响应
                    try:
                        data = json.loads(response.text).get('data', {})
                        trans_code = data.get('transCode', {})
                        convert_results = trans_code.get('convertResults', [])
                        
                        if convert_results and convert_results[0].get('url'):
                            video_url = convert_results[0].get('url')
                            self.log_message(f"成功获取视频URL: {video_url}")
                            return video_url
                        
                        time.sleep(retry_interval)
                    
                    except Exception as e:
                        self.log_message(f"解析响应数据失败: {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_interval)
                
                except Exception as e:
                    self.log_message(f'获取视频URL失败: {str(e)}')
                    if attempt < max_retries - 1:
                        time.sleep(retry_interval)
                    else:
                        raise Exception(f"获取视频URL失败，已超过10分钟重试时间")
            
            # 如果所有尝试都失败
            raise Exception(f"获取视频URL失败，已超过10分钟重试时间")
        
        except Exception as e:
            self.log_message(f"获取视频URL时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def publish(self, loginPublicId, videoId, videoFile, videoFileName, extProperty, mt, scheduleTime, title, cookies, topics=None):
        """发布视频
        
        Args:
            loginPublicId: 账号ID
            videoId: 视频ID
            videoFile: 视频文件路径
            videoFileName: 视频文件名
            extProperty: 额外属性（包含封面图片信息）
            mt: MT令牌
            scheduleTime: 定时发布时间
            title: 视频标题
            cookies: 账号cookies
            topics: 话题标签列表
            
        Returns:
            dict: 发布响应数据，失败则抛出异常
        """
        try:
            self.log_message(f"准备发布视频: {title}")
            self.log_message(f"传入的话题原始数据: {topics}")
            
            # 构建请求头
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
            
            # 准备请求参数
            params = {
                'loginPublicId': loginPublicId,
            }
            
            # 准备请求数据
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
                        'djangoId': extProperty.get('djangoId'),
                        'imageUrl': extProperty.get('filePath'),
                        'width': extProperty.get('width'),
                        'height': extProperty.get('height'),
                        'type': 'cover_static',
                        'index': 0,
                    },
                    {
                        'djangoId': extProperty.get('djangoId'),
                        'imageUrl': extProperty.get('filePath'),
                        'width': extProperty.get('width'),
                        'height': extProperty.get('height'),
                        'type': 'cover_vertical_static',
                        'index': 1,
                    },
                    {
                        'djangoId': extProperty.get('djangoId'),
                        'imageUrl': extProperty.get('filePath'),
                        'width': extProperty.get('width'),
                        'height': extProperty.get('height'),
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
            
            # 处理话题信息 - 两种方式:
            # 1. 如果传入了topics参数，直接使用
            if topics and isinstance(topics, dict) and 'topicInfoVOList' in topics:
                json_data['topicInfoVOList'] = topics['topicInfoVOList']
                self.log_message(f"使用API话题信息: {topics['topicInfoVOList']}")
            # 2. 传入了列表形式的话题
            elif topics and isinstance(topics, list):
                topic_list = []
                for topic in topics:
                    if isinstance(topic, dict):
                        # 如果是字典形式，检查是否已格式化
                        if 'topicName' in topic:
                            topic_list.append(topic)
                        elif 'name' in topic:
                            topic_list.append({
                                "topicName": f"#{topic['name']}#",
                                "topicId": topic.get('id', ''),
                                "topicType": "NORMAL"
                            })
                    elif isinstance(topic, str):
                        # 字符串形式，确保有#符号
                        topic = topic.strip()
                        if not topic.startswith('#'):
                            topic = '#' + topic
                        if not topic.endswith('#'):
                            topic = topic + '#'
                        topic_list.append({
                            "topicName": topic,
                            "topicId": "",
                            "topicType": "NORMAL"
                        })
                
                if topic_list:
                    self.log_message(f"从列表转换的话题: {topic_list}")
                    json_data['topicInfoVOList'] = topic_list
            # 3. 从标题中提取话题
            elif title and "#" in title:
                # 提取所有带 # 的话题
                topic_list = []
                parts = title.split("#")
                # 跳过第一个部分（如果以#开头，第一个元素是空的）
                for i in range(1, len(parts)):
                    if parts[i].strip():
                        # 获取话题内容（去除可能的结尾#）
                        topic_text = parts[i].strip().split("#")[0].strip()
                        if topic_text:
                            topic_list.append({
                                "topicName": f"#{topic_text}#",
                                "topicId": "",
                                "topicType": "NORMAL"
                            })
                
                if topic_list:
                    self.log_message(f"从标题提取话题: {topic_list}")
                    json_data['topicInfoVOList'] = topic_list
            
            # 只有当 scheduleTime 有值时才添加到 json_data
            if scheduleTime:
                self.log_message(f"使用定时发布时间: {scheduleTime}")
                json_data['scheduleTime'] = self.format_time_string(scheduleTime)
            
            # 发送请求
            response = requests.post(
                'https://contentweb.alipay.com/life/publishShortVideo.json',
                params=params,
                cookies=cookies,
                headers=headers,
                json=json_data,
            )
            
            # 解析响应数据
            response_data = json.loads(response.text)
            
            # 检查发布状态
            if response_data.get('stat') == 'failed':
                error_message = response_data.get('errorMessage', '未知错误')
                error_code = response_data.get('errorCode', 'unknown')
                self.log_message(f'发布失败 - 错误码: {error_code}, 错误信息: {error_message}')
                raise Exception(f'发布失败: {error_message}')
            
            return response_data
            
        except Exception as e:
            self.log_message(f"发布视频时出错: {str(e)}")
            traceback.print_exc()
            raise  # 重新抛出异常，与zfb.py保持一致
            
    def format_time_string(self, time_str):
        """格式化时间字符串为 YYYY-MM-DD HH:MM 格式
        
        Args:
            time_str: 时间字符串，格式为 YYYY-MM-DD HH:MM
            
        Returns:
            str: 格式化后的时间字符串
        """
        try:
            # 导入datetime模块的datetime类
            from datetime import datetime
            
            # 解析时间字符串
            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            
            # 重新格式化，确保小时是两位数
            formatted_time = dt.strftime('%Y-%m-%d %H:%M')
            
            self.log_message(f"时间格式化成功: {time_str} -> {formatted_time}")
            
            return formatted_time
        except Exception as e:
            self.log_message(f"时间格式化出错: {str(e)}")
            # 如果格式化失败，返回原始字符串
            return time_str
    
    def search_topics(self, cookies, appid, keywords):
        """搜索话题
        
        根据关键词搜索支付宝平台的话题标签
        
        Args:
            cookies: 账号的cookies
            appid: 账号ID
            keywords: 搜索关键词
            
        Returns:
            list: 话题列表，每个话题包含name和topicId，失败则返回None
        """
        try:
            import requests  # 确保导入requests库
            
            if not keywords or not appid:
                self.log_message("搜索话题缺少必要参数")
                return None
            
            self.log_message(f"开始搜索话题: {keywords}")
            
            # 构建请求头
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Connection': 'keep-alive',
                'Content-Type': 'application/json;charset=UTF-8',
                'Origin': 'https://c.alipay.com',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            # 构建参数
            params = {
                '_input_charset': 'utf-8',
                '_output_charset': 'utf-8',
            }
            
            # 构建请求数据
            json_data = {
                'keywords': keywords,
                'publicId': appid,
                'sourceId': 'S',
            }
            
            # 发送请求
            response = requests.post(
                'https://fuwu.alipay.com/platform/queryTopicRecommend.json',
                params=params,
                cookies=cookies,
                headers=headers,
                json=json_data,
                timeout=15
            ) 
            if response.status_code == 200:
                data = response.json()
                if data.get("stat") == "ok":
                    # 获取话题列表
                    topics = data.get("result", [])
                    if not topics:
                        self.log_message("未找到相关话题")
                        return []
                        
                    # 格式化话题列表
                    formatted_topics = []
                    for topic in topics:
                        topic_name = topic.get("name", "")
                        topic_id = topic.get("topicId", "")
                        if topic_name:
                            formatted_topics.append({
                                'name': topic_name,
                                'topicId': topic_id,
                                'display': f"#{topic_name}#"  # 添加#前缀和后缀
                            })
                    
                    return formatted_topics
                else:
                    error_msg = data.get("errorMessage", "未知错误")
                    self.log_message(f"搜索话题失败: {error_msg}")
                    return None
            else:
                self.log_message(f"搜索话题请求失败: HTTP {response.status_code}")
                return None
            
        except Exception as e:
            self.log_message(f"搜索话题时出错: {str(e)}")
            traceback.print_exc()
            return None
            
    def format_topic_for_publish(self, topics):
        """将话题列表格式化为发布接口所需的格式
        
        Args:
            topics: 话题列表，可以是字符串列表或者包含name和topicId的字典列表
            
        Returns:
            dict: 格式化后的话题对象，适用于发布接口
        """
        try:
            self.log_message(f"格式化话题输入: {topics}")
            
            if not topics:
                return {"topicInfoVOList": []}
            
            # 如果已经是完整的topicInfoVOList格式，直接返回
            if isinstance(topics, dict) and 'topicInfoVOList' in topics:
                self.log_message(f"使用已有话题信息: {topics}")
                return topics
            
            topic_list = []
            
            for topic in topics:
                if isinstance(topic, str):
                    # 确保有#前缀和后缀
                    topic = topic.strip()
                    if not topic.startswith('#'):
                        topic = '#' + topic
                    if not topic.endswith('#'):
                        topic = topic + '#'
                    
                    topic_list.append({
                        "topicName": topic,
                        "topicId": "",  # 没有ID信息
                        "topicType": "NORMAL"
                    })
                    
                elif isinstance(topic, dict):
                    # 已经是字典格式，根据字段决定处理方式
                    if 'topicName' in topic and 'topicId' in topic:
                        # 已经是API需要的格式，包含topicId
                        topic_list.append(topic)
                        
                    elif 'display' in topic or 'name' in topic:
                        # 获取话题名称
                        topic_name = topic.get('display', '') or topic.get('name', '')
                        if not topic_name:
                            continue
                            
                        # 确保有#前缀和后缀
                        topic_name = topic_name.strip()
                        if not topic_name.startswith('#'):
                            topic_name = '#' + topic_name
                        if not topic_name.endswith('#'):
                            topic_name = topic_name + '#'
                        
                        # 获取话题ID，优先使用topicId字段，其次使用id字段
                        topic_id = topic.get('topicId', '') or topic.get('id', '')
                        
                        topic_list.append({
                            "topicName": topic_name,
                            "topicId": topic_id,
                            "topicType": "NORMAL"
                        })
            
            formatted_topics = {"topicInfoVOList": topic_list}
            self.log_message(f"格式化话题输出: {formatted_topics}")
            return formatted_topics
            
        except Exception as e:
            self.log_message(f"格式化话题时出错: {str(e)}")
            traceback.print_exc()
            return {"topicInfoVOList": []}