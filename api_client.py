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
    
    def get_mt(self, cookies):
        """获取上传所需的MT令牌
        
        Args:
            cookies: 账号的cookies
            
        Returns:
            str: MT令牌，失败则返回None
        """
        try:
            self.log_message("正在获取MT令牌...")
            
            # 验证cookies
            if not cookies or 'ctoken' not in cookies:
                self.log_message("Cookie无效，无法获取MT令牌")
                return None
                
            # 构建请求
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Cache-Control': 'no-cache',
                'Content-Type': 'application/json',
                'Origin': 'https://c.alipay.com',
                'Pragma': 'no-cache',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 构建参数
            params = {
                'ctoken': cookies.get('ctoken', ''),
                '_input_charset': 'utf-8',
            }
            
            # 发送请求
            response = requests.get(
                'https://contentweb.alipay.com/mtcontent/mt.json',
                params=params,
                cookies=cookies,
                headers=headers
            )
            
            if response.status_code != 200:
                self.log_message(f"获取MT令牌请求失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get('stat') != 'ok':
                self.log_message(f"获取MT令牌失败: {data.get('message', '未知错误')}")
                return None
                
            mt_token = data.get('result', {}).get('mt', '')
            if not mt_token:
                self.log_message("未返回有效的MT令牌")
                return None
                
            self.log_message("成功获取MT令牌")
            return mt_token
            
        except Exception as e:
            self.log_message(f"获取MT令牌时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def get_traid(self):
        """获取上传交易ID
        
        Returns:
            str: 上传交易ID
        """
        return f"tr_{int(time.time() * 1000)}_{random.randint(100000, 999999)}"
    
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
        """上传大视频文件（>=4MB），采用分片上传
        
        Args:
            mt: MT令牌
            file_path: 视频文件路径
            file_size: 文件大小，如果为None则自动获取
            
        Returns:
            str: 文件ID，失败则返回None
        """
        try:
            if file_size is None:
                file_size = os.path.getsize(file_path)
            
            file_name = os.path.basename(file_path)
            self.log_message(f"开始分片上传大视频: {file_name} ({file_size} 字节)")
            
            # 获取交易ID
            traid = self.get_traid()
            
            # 构建请求头
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Origin': 'https://c.alipay.com',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/json'
            }
            
            # 初始化分片上传
            init_data = {
                'uploadType': 'video',
                'fileType': '4',
                'fileName': file_name,
                'fileSize': file_size,
                'mt': mt,
                'tradeId': traid
            }
            
            init_response = requests.post(
                'https://contentweb.alipay.com/mtcontent/initMultipartUpload.json',
                json=init_data,
                headers=headers
            )
            
            if init_response.status_code != 200:
                self.log_message(f"初始化分片上传请求失败: HTTP {init_response.status_code}")
                return None
                
            init_data = init_response.json()
            if init_data.get('stat') != 'ok':
                self.log_message(f"初始化分片上传失败: {init_data.get('message', '未知错误')}")
                return None
                
            file_id = init_data.get('result', {}).get('fileId', '')
            if not file_id:
                self.log_message("未返回有效的文件ID")
                return None
                
            # 打开文件
            with open(file_path, 'rb') as f:
                # 分片上传，每片 4M
                chunk_size = 4 * 1024 * 1024
                part_number = 1
                
                while True:
                    if self.thread_control and self.thread_control.should_stop():
                        self.log_message("用户取消上传")
                        return None
                        
                    # 读取块数据
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                        
                    # 设置分片参数
                    part_data = {
                        'mt': mt,
                        'fileId': file_id,
                        'partNumber': part_number,
                        'partSize': len(chunk_data),
                        'tradeId': traid
                    }
                    
                    # 获取上传URL
                    part_url_resp = requests.post(
                        'https://contentweb.alipay.com/mtcontent/getMultipartUrl.json',
                        json=part_data,
                        headers=headers
                    )
                    
                    if part_url_resp.status_code != 200:
                        self.log_message(f"获取分片上传URL失败: HTTP {part_url_resp.status_code}")
                        return None
                        
                    part_url_data = part_url_resp.json()
                    if part_url_data.get('stat') != 'ok':
                        self.log_message(f"获取分片上传URL失败: {part_url_data.get('message', '未知错误')}")
                        return None
                        
                    upload_url = part_url_data.get('result', {}).get('url', '')
                    if not upload_url:
                        self.log_message("未返回有效的分片上传URL")
                        return None
                    
                    # 上传分片
                    upload_headers = {
                        'Content-Type': 'application/octet-stream',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    
                    upload_resp = requests.put(
                        upload_url,
                        data=chunk_data,
                        headers=upload_headers
                    )
                    
                    if upload_resp.status_code not in [200, 201, 204]:
                        self.log_message(f"上传分片失败: HTTP {upload_resp.status_code}")
                        return None
                    
                    # 显示上传进度
                    progress = min(100, int(part_number * chunk_size * 100 / file_size))
                    self.log_message(f"上传进度: {progress}% (分片 {part_number})")
                    
                    # 下一个分片
                    part_number += 1
            
            # 完成上传
            return self.upload_complete(mt, file_id, traid)
            
        except Exception as e:
            self.log_message(f"上传大视频时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def upload_complete(self, mt, file_id, traid):
        """完成分片上传
        
        Args:
            mt: MT令牌
            file_id: 文件ID
            traid: 交易ID
            
        Returns:
            str: 文件ID，失败则返回None
        """
        try:
            self.log_message(f"完成文件上传: {file_id}")
            
            # 构建请求头
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Origin': 'https://c.alipay.com',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/json'
            }
            
            # 完成上传
            complete_data = {
                'mt': mt,
                'fileId': file_id,
                'tradeId': traid
            }
            
            response = requests.post(
                'https://contentweb.alipay.com/mtcontent/completeMultipartUpload.json',
                json=complete_data,
                headers=headers
            )
            
            if response.status_code != 200:
                self.log_message(f"完成上传请求失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get('stat') != 'ok':
                self.log_message(f"完成上传失败: {data.get('message', '未知错误')}")
                return None
                
            self.log_message("分片上传完成")
            return file_id
            
        except Exception as e:
            self.log_message(f"完成上传时出错: {str(e)}")
            traceback.print_exc()
            return None
    
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
                
            # 获取MT令牌
            mt = self.get_mt(cookies)
            if not mt:
                self.log_message("获取MT令牌失败，无法上传封面")
                return None
                
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
                'fileType': '3',  # 图片文件类型
                'mt': mt,
                'rmsToken': ''
            }
            
            # 准备文件
            files = {
                'file': (os.path.basename(image_path), open(image_path, 'rb'), 'image/jpeg')
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
                self.log_message(f"上传封面请求失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get('stat') != 'ok':
                self.log_message(f"上传封面失败: {data.get('message', '未知错误')}")
                return None
                
            pic_url = data.get('result', {}).get('url', '')
            if not pic_url:
                self.log_message("未返回有效的封面URL")
                return None
                
            self.log_message(f"封面上传成功: {pic_url}")
            return pic_url
            
        except Exception as e:
            self.log_message(f"上传封面时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def get_video_url(self, file_id, mt, max_retries=12, retry_interval=10):
        """获取处理完成的视频URL
        
        Args:
            file_id: 文件ID
            mt: MT令牌
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）
            
        Returns:
            str: 视频URL，失败则返回None
        """
        try:
            self.log_message(f"等待视频处理完成，文件ID: {file_id}")
            
            # 构建请求头
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Origin': 'https://c.alipay.com',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/json'
            }
            
            # 准备请求数据
            request_data = {
                'mt': mt,
                'fileId': file_id
            }
            
            # 循环查询视频处理状态
            for retry in range(max_retries):
                if self.thread_control and self.thread_control.should_stop():
                    self.log_message("用户取消获取视频URL")
                    return None
                    
                # 发送请求
                response = requests.post(
                    'https://contentweb.alipay.com/mtcontent/getUrl.json',
                    json=request_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    self.log_message(f"获取视频URL请求失败: HTTP {response.status_code}")
                    time.sleep(retry_interval)
                    continue
                    
                try:
                    data = response.json()
                except Exception as e:
                    self.log_message(f"解析响应失败: {str(e)}")
                    time.sleep(retry_interval)
                    continue
                    
                if data.get('stat') != 'ok':
                    error_msg = data.get('message', '未知错误')
                    if "处理中" in error_msg or "尚未处理完成" in error_msg:
                        self.log_message(f"视频处理中 ({retry+1}/{max_retries})，等待 {retry_interval} 秒...")
                        time.sleep(retry_interval)
                        continue
                    else:
                        self.log_message(f"获取视频URL失败: {error_msg}")
                        return None
                
                # 获取视频URL
                video_url = data.get('result', {}).get('url', '')
                if not video_url:
                    self.log_message(f"未返回有效的视频URL ({retry+1}/{max_retries})，等待 {retry_interval} 秒...")
                    time.sleep(retry_interval)
                    continue
                    
                self.log_message(f"成功获取视频URL: {video_url}")
                return video_url
                
            self.log_message(f"获取视频URL超时，已重试 {max_retries} 次")
            return None
            
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
            extProperty: 额外属性
            mt: MT令牌
            scheduleTime: 定时发布时间
            title: 视频标题
            cookies: 账号cookies
            topics: 话题标签列表
            
        Returns:
            str: 内容ID，失败则返回None
        """
        try:
            self.log_message(f"准备发布视频: {title}")
            
            # 上传封面
            cover_url = self.upload_pic(cookies, videoFile)
            if not cover_url:
                self.log_message("上传封面失败，使用视频默认封面")
                
            # 获取视频URL
            video_url = self.get_video_url(videoId, mt)
            if not video_url:
                self.log_message("获取视频URL失败")
                return None
                
            # 处理话题标签
            topic_list = []
            if topics and isinstance(topics, list):
                for topic in topics:
                    if topic and isinstance(topic, str):
                        topic_list.append({"topicId": "", "topicName": topic})
            
            # 构建请求头
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Origin': 'https://c.alipay.com',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/json'
            }
            
            # 准备请求数据
            content_data = {
                "contentTitle": title,
                "contentDesc": "",
                "contentType": "VIDEO",
                "videoUrl": video_url,
                "topicList": topic_list
            }
            
            # 如果有封面，添加封面URL
            if cover_url:
                content_data["coverImageUrl"] = cover_url
                
            # 如果有定时发布时间，添加发布时间
            if scheduleTime:
                content_data["publishTime"] = scheduleTime
            
            request_data = {
                "content": content_data,
                "loginPublicId": loginPublicId,
                "sourceId": "lifestream"
            }
            
            # 参数
            params = {
                'ctoken': cookies.get('ctoken', '')
            }
            
            # 发送请求
            response = requests.post(
                'https://contentweb.alipay.com/life/publishContentV2.json',
                params=params,
                json=request_data,
                cookies=cookies,
                headers=headers
            )
            
            if response.status_code != 200:
                self.log_message(f"发布视频请求失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get('stat') != 'ok':
                self.log_message(f"发布视频失败: {data.get('message', '未知错误')}")
                return None
                
            # 获取内容ID
            content_id = data.get('result', {}).get('contentId', '')
            if not content_id:
                self.log_message("未返回有效的内容ID")
                return None
                
            if scheduleTime:
                self.log_message(f"视频已定时发布: {title} (ID: {content_id}, 时间: {scheduleTime})")
            else:
                self.log_message(f"视频已成功发布: {title} (ID: {content_id})")
                
            return content_id
            
        except Exception as e:
            self.log_message(f"发布视频时出错: {str(e)}")
            traceback.print_exc()
            return None
            
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
            if not keywords or not cookies or not appid:
                self.log_message("搜索话题参数不完整")
                return None
                
            self.log_message(f"正在搜索话题: {keywords}")
            
            # 验证cookies
            if not cookies or 'ctoken' not in cookies:
                self.log_message("Cookie无效，无法搜索话题")
                return None
                
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
            
            self.log_message(f"搜索话题请求参数: {json_data}")
            
            # 发送请求
            response = requests.post(
                'https://fuwu.alipay.com/platform/queryTopicRecommend.json',
                params=params,
                cookies=cookies,
                headers=headers,
                json=json_data,
            )
            
            if response.status_code != 200:
                self.log_message(f"搜索话题请求失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get("stat") != "ok":
                error_msg = data.get("errorMessage", "未知错误")
                self.log_message(f"搜索话题失败: {error_msg}")
                return None
                
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
            
            self.log_message(f"成功找到 {len(formatted_topics)} 个话题")
            return formatted_topics
            
        except Exception as e:
            self.log_message(f"搜索话题时出错: {str(e)}")
            traceback.print_exc()
            return None
            
    def format_topic_for_publish(self, topics):
        """将话题列表格式化为发布接口所需的格式
        
        Args:
            topics: 话题列表，可以是字符串列表或者包含name和topicId的字典列表
            
        Returns:
            list: 格式化后的话题列表，适用于发布接口
        """
        try:
            if not topics:
                return []
                
            formatted_topics = []
            
            for topic in topics:
                if isinstance(topic, str):
                    # 移除前后的#号
                    topic_name = topic.strip('#')
                    formatted_topics.append({
                        "topicId": "",
                        "topicName": topic_name
                    })
                elif isinstance(topic, dict):
                    # 已经是字典格式，提取name和topicId
                    topic_name = topic.get('name', '')
                    topic_id = topic.get('topicId', '')
                    if topic_name:
                        formatted_topics.append({
                            "topicId": topic_id,
                            "topicName": topic_name
                        })
            
            return formatted_topics
            
        except Exception as e:
            self.log_message(f"格式化话题时出错: {str(e)}")
            traceback.print_exc()
            return []