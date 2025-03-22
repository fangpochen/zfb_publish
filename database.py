#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
from datetime import datetime
import traceback

class DatabaseManager:
    """数据库管理类，处理所有与数据库相关的操作"""
    
    def __init__(self, db_path='data.db'):
        """初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.initialize_database()
        
    def initialize_database(self):
        """初始化数据库结构"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建账号表（如果不存在）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appid TEXT UNIQUE,
                name TEXT,
                cookies TEXT,
                today_videos INTEGER DEFAULT 0,
                today_recommended INTEGER DEFAULT 0,
                today_views INTEGER DEFAULT 0,
                pass_style INTEGER DEFAULT 0,
                total_uploads INTEGER DEFAULT 0,
                folder_path TEXT,
                last_updated TIMESTAMP,
                cookies_status TEXT DEFAULT '正常',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 创建视频数据表（如果不存在）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                content_id TEXT PRIMARY KEY,
                title TEXT,
                send_time TEXT,
                pv INTEGER,
                praise_count INTEGER,
                reply_count INTEGER,
                account_name TEXT,
                appid TEXT,
                analyze_date TEXT,
                is_abnormal INTEGER,
                recommend INTEGER,
                audit_reason TEXT,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 创建文件夹设置表（如果不存在）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS folder_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appid TEXT,
                folder_path TEXT,
                total_files INTEGER DEFAULT 0,
                max_uploads INTEGER DEFAULT 50,
                uploaded_count INTEGER DEFAULT 0,
                status TEXT DEFAULT '待上传',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(appid, folder_path)
            )
            ''')
            
            # 创建上传记录表（如果不存在）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS upload_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appid TEXT,
                folder_id INTEGER,
                file_path TEXT,
                file_name TEXT,
                file_size INTEGER,
                upload_time TEXT,
                status TEXT,
                FOREIGN KEY (folder_id) REFERENCES folder_settings(id)
            )
            ''')

            # 创建账号分析表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appid TEXT,
                    date DATE,
                    total_videos INTEGER DEFAULT 0,
                    recommend_videos INTEGER DEFAULT 0,
                    total_views INTEGER DEFAULT 0,
                    total_likes INTEGER DEFAULT 0,
                    total_comments INTEGER DEFAULT 0,
                    total_shares INTEGER DEFAULT 0,
                    avg_views INTEGER DEFAULT 0,
                    avg_likes INTEGER DEFAULT 0,
                    avg_comments INTEGER DEFAULT 0,
                    recommend_rate REAL DEFAULT 0,
                    engagement_rate REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(appid, date)
                )
            ''')

            conn.commit()
            conn.close()
            print("数据库初始化成功")
        except Exception as e:
            print(f"数据库初始化失败: {str(e)}")
    
    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
        
    def load_accounts(self):
        """加载所有账号信息
        
        Returns:
            list: 账号信息列表
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT appid, name, cookies, cookies_status, total_uploads, 
                       today_videos, today_recommended, today_views, 
                       pass_style, folder_path
                FROM accounts
                ORDER BY id
            ''')
            
            rows = cursor.fetchall()
            accounts = []
            
            for row in rows:
                appid, name, cookies_str, cookies_status, total_uploads, \
                today_videos, today_recommended, today_views, \
                pass_style, folder_path = row
                
                account = {
                    'appid': appid,
                    'name': name,
                    'cookies': cookies_str,
                    'cookies_status': cookies_status,
                    'total_uploads': total_uploads,
                    'today_videos': today_videos,
                    'today_recommended': today_recommended,
                    'today_views': today_views,
                    'pass_style': bool(pass_style),
                    'folder_path': folder_path
                }
                accounts.append(account)
                
            conn.close()
            return accounts
        except Exception as e:
            print(f"加载账号信息失败: {str(e)}")
            return []
    
    def get_account_cookies(self, appid):
        """获取指定账号的cookies
        
        Args:
            appid: 账号ID
            
        Returns:
            dict: cookies数据，如果未找到则返回None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT cookies FROM accounts WHERE appid = ?', (appid,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                try:
                    return json.loads(result[0])
                except:
                    pass
            return None
        except Exception as e:
            print(f"获取账号cookies失败: {str(e)}")
            return None
    
    def update_account_style_status(self, appid, pass_style):
        """更新账号画风评估状态
        
        Args:
            appid: 账号ID
            pass_style: 是否通过画风检测（布尔值）
        
        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'UPDATE accounts SET pass_style = ?, last_updated = ? WHERE appid = ?',
                (1 if pass_style else 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appid)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新账号画风状态失败: {str(e)}")
            return False
    
    def update_account_stats(self, appid, today_videos, today_recommended, today_views):
        """更新账号统计数据
        
        Args:
            appid: 账号ID
            today_videos: 今日视频数量
            today_recommended: 今日推荐数量
            today_views: 今日播放量
        
        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                '''UPDATE accounts 
                   SET today_videos = ?, today_recommended = ?, 
                       today_views = ?, last_updated = ? 
                   WHERE appid = ?''',
                (today_videos, today_recommended, today_views, 
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appid)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新账号统计数据失败: {str(e)}")
            return False
    
    def update_account_folder(self, appid, folder_path):
        """更新账号绑定的文件夹
        
        Args:
            appid: 账号ID
            folder_path: 文件夹路径
        
        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'UPDATE accounts SET folder_path = ? WHERE appid = ?',
                (folder_path, appid)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新账号文件夹失败: {str(e)}")
            return False
    
    def load_videos_from_db(self, appid, query_date):
        """从本地数据库加载指定日期的视频数据
        
        Args:
            appid: 账号ID
            query_date: 查询日期
            
        Returns:
            dict: 包含视频数据的统计结果，如果没有数据则返回None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 查询该账号在指定日期的所有视频
            cursor.execute('''
                SELECT content_id, title, publish_time, play_count, like_count, 
                       comment_count, is_recommended, has_duplicate, account_name
                FROM videos 
                WHERE appid = ? AND query_date = ?
            ''', (appid, query_date))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return None
                
            # 构建统计数据
            videos = []
            total_videos = 0
            recommended_videos = 0
            total_plays = 0
            duplicate_count = 0
            
            for row in rows:
                content_id, title, publish_time, play_count, like_count, \
                comment_count, is_recommended, has_duplicate, account_name = row
                
                video = {
                    'contentId': content_id,
                    'title': title,
                    'publishTime': publish_time,
                    'playCount': play_count,
                    'praiseTimes': like_count,
                    'commentCount': comment_count,
                    'isRecommend': bool(is_recommended),
                    'hasDuplicate': bool(has_duplicate),
                    'account_name': account_name,
                    'appid': appid
                }
                
                videos.append(video)
                total_videos += 1
                if is_recommended:
                    recommended_videos += 1
                total_plays += play_count
                if has_duplicate:
                    duplicate_count += 1
            
            # 计算平均播放量
            avg_plays = total_plays / total_videos if total_videos > 0 else 0
            
            # 计算重复率
            duplicate_rate = (duplicate_count / total_videos * 100) if total_videos > 0 else 0
            
            return {
                'total_videos': total_videos,
                'recommended_videos': recommended_videos,
                'total_plays': total_plays,
                'avg_plays': avg_plays,
                'duplicate_count': duplicate_count,
                'duplicate_rate': duplicate_rate,
                'videos': videos
            }
            
        except Exception as e:
            print(f"从数据库加载视频数据失败: {str(e)}")
            return None
    
    def save_videos_to_db(self, appid, query_date, videos):
        """保存视频数据到本地数据库
        
        Args:
            appid: 账号ID
            query_date: 查询日期
            videos: 视频数据列表
            
        Returns:
            bool: 是否保存成功
        """
        if not videos:
            print(f"没有可保存的视频数据，appid: {appid}, 日期: {query_date}")
            return False
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 使用事务批量插入数据
            cursor.execute('BEGIN TRANSACTION')
            
            # 记录新增/更新的视频数量
            inserted_count = 0
            updated_count = 0
            
            for video in videos:
                # 处理content_id
                content_id = video.get('contentId', '') or video.get('id', '')
                # 确保content_id不为空且是唯一的
                if not content_id:
                    content_id = f"video_{datetime.now().timestamp()}_{hash(str(video))}"
                    print(f"生成新的content_id: {content_id}")
                    
                # 处理标题
                title = video.get('title', '')
                
                # 处理发布时间
                publish_time = video.get('sendTime', '') or video.get('publishTime', '')
                
                if isinstance(publish_time, int) and publish_time > 0:
                    publish_time = datetime.fromtimestamp(publish_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                # 处理数值字段，确保为整数
                try:
                    play_count = int(video.get('playCount', 0) or video.get('pv', 0))
                except (ValueError, TypeError):
                    play_count = 0
                    
                try:
                    like_count = int(video.get('praiseTimes', 0) or video.get('praiseCount', 0))
                except (ValueError, TypeError):
                    like_count = 0
                    
                try:
                    comment_count = int(video.get('commentCount', 0) or video.get('replyCount', 0))
                except (ValueError, TypeError):
                    comment_count = 0
                
                # 处理布尔值
                is_recommended = 1 if video.get('isRecommend', False) else 0
                has_duplicate = 1 if video.get('hasDuplicate', False) else 0
                
                # 获取账号名称
                account_name = video.get('account_name', '')
                
                # 检查视频是否已存在
                cursor.execute('''
                    SELECT content_id FROM videos 
                    WHERE appid = ? AND content_id = ? AND query_date = ?
                ''', (appid, content_id, query_date))
                
                existing = cursor.fetchone()
                
                # 使用REPLACE确保数据最新
                cursor.execute('''
                    INSERT OR REPLACE INTO videos 
                    (account_name, appid, content_id, title, publish_time, 
                    play_count, like_count, comment_count, is_recommended, 
                    has_duplicate, query_date) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    account_name, appid, content_id, title, publish_time,
                    play_count, like_count, comment_count, is_recommended,
                    has_duplicate, query_date
                ))
                
                if existing:
                    updated_count += 1
                else:
                    inserted_count += 1
            
            # 更新账号今日统计数据
            total_videos = len(videos)
            total_recommended = sum(1 for v in videos if v.get('isRecommend', False))
            
            # 计算总播放量
            try:
                total_plays = sum(int(v.get('playCount', 0) or v.get('pv', 0)) for v in videos)
            except:
                total_plays = 0
                print(f"计算总播放量时出错，使用默认值0")
            
            # 获取账号名称
            account_name = ""
            if videos and 'account_name' in videos[0]:
                account_name = videos[0]['account_name']
                
            # 检查是否有账号记录，如果没有则创建
            cursor.execute('SELECT id FROM accounts WHERE appid = ?', (appid,))
            if not cursor.fetchone():
                print(f"未找到appid为{appid}的账号记录，创建新记录")
                cursor.execute('''
                    INSERT INTO accounts 
                    (appid, name, today_videos, today_recommended, today_views, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    appid, account_name, total_videos, total_recommended, total_plays,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
            else:
                # 更新账号统计信息
                cursor.execute('''
                    UPDATE accounts 
                    SET today_videos = ?, today_recommended = ?, today_views = ?, last_updated = ?
                    WHERE appid = ?
                ''', (
                    total_videos, total_recommended, total_plays,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appid
                ))
            
            conn.commit()
            conn.close()
            print(f"成功保存视频数据: 新增{inserted_count}条，更新{updated_count}条")
            return True
        except sqlite3.Error as e:
            print(f"SQLite错误: {str(e)}")
            try:
                conn.rollback()
                conn.close()
            except:
                pass
            return False
        except Exception as e:
            print(f"保存视频数据到数据库失败: {str(e)}")
            try:
                conn.rollback()
                conn.close()
            except:
                pass
            return False
    
    def add_account(self, appid, name, cookies, folder_path=None):
        """添加新账号
        
        Args:
            appid: 账号ID
            name: 账号名称
            cookies: cookies数据
            folder_path: 绑定的文件夹路径
            
        Returns:
            bool: 是否添加成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 如果是字典类型的cookies，转换为JSON字符串
            if isinstance(cookies, dict):
                cookies = json.dumps(cookies)
                
            cursor.execute('''
                INSERT OR REPLACE INTO accounts
                (appid, name, cookies, folder_path, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                appid, name, cookies, folder_path,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加账号失败: {str(e)}")
            return False
    
    def remove_account(self, appid):
        """删除账号
        
        Args:
            appid: 账号ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 删除账号
            cursor.execute('DELETE FROM accounts WHERE appid = ?', (appid,))
            
            # 同时删除该账号的所有视频数据
            cursor.execute('DELETE FROM videos WHERE appid = ?', (appid,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"删除账号失败: {str(e)}")
            return False

    def save_account(self, appid, account_name, cookies):
        """保存账号信息到数据库
        
        Args:
            appid: 账号ID
            account_name: 账号名称
            cookies: 账号的cookie信息
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 检查账号是否已存在
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM accounts WHERE appid = ?", (appid,))
            account_exists = cursor.fetchone()
            
            # 将cookies转换为字符串存储
            if isinstance(cookies, dict):
                cookies_str = json.dumps(cookies)
            else:
                cookies_str = cookies
            
            if account_exists:
                # 更新现有账号
                cursor.execute("""
                    UPDATE accounts 
                    SET name = ?, cookies = ?, cookies_status = '正常', 
                        last_updated = datetime('now', 'localtime')
                    WHERE appid = ?
                """, (account_name, cookies_str, appid))
            else:
                # 插入新账号
                cursor.execute("""
                    INSERT INTO accounts 
                    (appid, name, cookies, cookies_status, today_videos, 
                    today_recommended, today_views, pass_style, total_uploads, folder_path, 
                    last_updated)
                    VALUES (?, ?, ?, '正常', 0, 0, 0, 0, 0, '', 
                    datetime('now', 'localtime'))
                """, (appid, account_name, cookies_str))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存账号信息失败: {str(e)}")
            traceback.print_exc()
            return False

    def add_folder(self, appid, folder_path, max_uploads, total_files):
        """添加文件夹到数据库
        
        Args:
            appid (str): 账号ID
            folder_path (str): 文件夹路径
            max_uploads (int): 最大上传数量
            total_files (int): 文件夹中的总文件数
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 检查文件夹是否已存在
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id FROM folder_settings 
                WHERE appid=? AND folder_path=?
            ''', (appid, folder_path))
            existing = cursor.fetchone()
            
            if existing:
                print(f"文件夹已存在: {folder_path}")
                return False
            
            # 插入新文件夹
            cursor.execute('''
                INSERT INTO folder_settings 
                (appid, folder_path, total_files, max_uploads, uploaded_count, status)
                VALUES (?, ?, ?, ?, 0, '待上传')
            ''', (appid, folder_path, total_files, max_uploads))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加文件夹失败: {str(e)}")
            conn.rollback()
            return False

    def remove_folder(self, folder_id):
        """从数据库中删除文件夹
        
        Args:
            folder_id (str): 文件夹ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 删除文件夹设置
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM folder_settings 
                WHERE id=?
            ''', (folder_id,))
            
            # 删除与该文件夹相关的上传记录
            cursor.execute('''
                DELETE FROM upload_records 
                WHERE folder_id=?
            ''', (folder_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"删除文件夹失败: {str(e)}")
            conn.rollback()
            return False

    def update_folder_limit(self, folder_id, new_limit):
        """更新文件夹的最大上传数量
        
        Args:
            folder_id (str): 文件夹ID
            new_limit (int): 新的最大上传数量
            
        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE folder_settings 
                SET max_uploads=? 
                WHERE id=?
            ''', (new_limit, folder_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新文件夹上传限制失败: {str(e)}")
            conn.rollback()
            return False

    def get_folder_settings(self, appid):
        """获取账号的文件夹设置列表
        
        Args:
            appid (str): 账号ID
            
        Returns:
            list: 文件夹设置列表
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, folder_path, total_files, max_uploads, uploaded_count, status
                FROM folder_settings
                WHERE appid=?
            ''', (appid,))
            
            folders = cursor.fetchall()
            conn.close()
            
            return folders
        except Exception as e:
            print(f"获取文件夹设置失败: {str(e)}")
            return []

    def get_all_accounts(self):
        """获取所有账号列表
        
        Returns:
            list: 账号列表，包含所有字段信息
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 使用SELECT *获取所有字段
            cursor.execute('SELECT * FROM accounts')
            accounts = cursor.fetchall()
            conn.close()
            return accounts
        except Exception as e:
            print(f"获取所有账号失败: {str(e)}")
            return []

    def update_upload_count(self, folder_id, new_count):
        """更新文件夹的已上传数量
        
        Args:
            folder_id (str): 文件夹ID
            new_count (int): 新的已上传数量
            
        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE folder_settings 
                SET uploaded_count=? 
                WHERE id=?
            ''', (new_count, folder_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新已上传数量失败: {str(e)}")
            conn.rollback()
            return False

    def get_folder_by_id(self, folder_id):
        """根据ID获取文件夹信息
        
        Args:
            folder_id (str): 文件夹ID
            
        Returns:
            tuple: 文件夹信息(id, folder_path, total_files, max_uploads, uploaded_count, status)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, folder_path, total_files, max_uploads, uploaded_count, status
                FROM folder_settings
                WHERE id=?
            ''', (folder_id,))
            
            folder = cursor.fetchone()
            conn.close()
            
            return folder
        except Exception as e:
            print(f"获取文件夹信息失败: {str(e)}")
            return None

    def add_upload_record(self, appid, folder_id, file_path, file_name, file_size, upload_time, status):
        """添加视频上传记录
        
        Args:
            appid (str): 账号ID
            folder_id (int): 文件夹ID
            file_path (str): 文件路径
            file_name (str): 文件名
            file_size (int): 文件大小(字节)
            upload_time (str): 上传时间
            status (str): 上传状态
            
        Returns:
            bool: 是否添加成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 确保存在上传记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS upload_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appid TEXT,
                    folder_id INTEGER,
                    file_path TEXT,
                    file_name TEXT,
                    file_size INTEGER,
                    upload_time TEXT,
                    status TEXT,
                    FOREIGN KEY (folder_id) REFERENCES folder_settings(id)
                )
            ''')
            
            cursor.execute('''
                INSERT INTO upload_records 
                (appid, folder_id, file_path, file_name, file_size, upload_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (appid, folder_id, file_path, file_name, file_size, upload_time, status))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加上传记录失败: {str(e)}")
            conn.rollback()
            return False

    def update_folder_status(self, folder_id, status):
        """更新文件夹状态
        
        Args:
            folder_id (str): 文件夹ID
            status (str): 新状态
            
        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE folder_settings 
                SET status=? 
                WHERE id=?
            ''', (status, folder_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新文件夹状态失败: {str(e)}")
            conn.rollback()
            return False

    def migrate_user_data(self):
        """将user_data表中的数据迁移到accounts表
        
        Returns:
            bool: 是否迁移成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 检查user_data表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user_data'
            """)
            if not cursor.fetchone():
                print("user_data表不存在，无需迁移")
                return True
                
            # 获取user_data表中的所有数据
            cursor.execute("""
                SELECT appid, user_name, cookies, is_main_account, mian_account_appid,
                       daily_success, daily_failed, last_publish_time
                FROM user_data
            """)
            rows = cursor.fetchall()
            
            # 开始事务
            cursor.execute('BEGIN TRANSACTION')
            
            migrated_count = 0
            for row in rows:
                appid, name, cookies, is_main, main_appid, daily_success, daily_failed, last_publish = row
                
                # 检查账号是否已存在于accounts表
                cursor.execute("SELECT id FROM accounts WHERE appid = ?", (appid,))
                if not cursor.fetchone():
                    # 插入新账号
                    cursor.execute("""
                        INSERT INTO accounts 
                        (appid, name, cookies, cookies_status, today_videos, 
                        today_recommended, today_views, pass_style, total_uploads, 
                        folder_path, last_updated)
                        VALUES (?, ?, ?, '正常', 0, 0, 0, 0, ?, '', 
                        datetime('now', 'localtime'))
                    """, (appid, name, cookies, daily_success))
                    migrated_count += 1
            
            # 提交事务
            conn.commit()
            
            print(f"成功迁移 {migrated_count} 个账号")
            
            # 备份并删除user_data表
            cursor.execute("ALTER TABLE user_data RENAME TO user_data_backup")
            conn.commit()
            
            conn.close()
            return True
        except Exception as e:
            print(f"迁移数据失败: {str(e)}")
            traceback.print_exc()
            try:
                conn.rollback()
            except:
                pass
            return False

    def init_db(self):
        """初始化数据库，创建必要的表"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 创建账号表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appid TEXT UNIQUE,
                    name TEXT,
                    cookies TEXT,
                    pass_style INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建视频表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    content_id TEXT PRIMARY KEY,
                    title TEXT,
                    send_time TEXT,
                    pv INTEGER,
                    praise_count INTEGER,
                    reply_count INTEGER,
                    account_name TEXT,
                    appid TEXT,
                    analyze_date TEXT,
                    is_abnormal INTEGER,
                    recommend INTEGER,
                    audit_reason TEXT,
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建账号分析表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appid TEXT,
                    date DATE,
                    total_videos INTEGER DEFAULT 0,
                    recommend_videos INTEGER DEFAULT 0,
                    total_views INTEGER DEFAULT 0,
                    total_likes INTEGER DEFAULT 0,
                    total_comments INTEGER DEFAULT 0,
                    total_shares INTEGER DEFAULT 0,
                    avg_views INTEGER DEFAULT 0,
                    avg_likes INTEGER DEFAULT 0,
                    avg_comments INTEGER DEFAULT 0,
                    recommend_rate REAL DEFAULT 0,
                    engagement_rate REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(appid, date)
                )
            ''')
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"初始化数据库失败: {str(e)}")
            if 'conn' in locals():
                conn.close()
            return False

    def get_video_count_by_id(self, video_id):
        """
        获取指定视频ID的数量
        
        Args:
            video_id: 视频ID
            
        Returns:
            int: 视频数量
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM videos WHERE content_id = ?', (video_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"查询视频数量失败: {str(e)}")
            if 'conn' in locals():
                conn.close()
            return 0

    def save_videos(self, videos, appid=None, query_date=None):
        """保存视频数据到数据库
        
        Args:
            videos: 视频数据列表
            appid: 账号ID(可选)
            query_date: 查询日期(可选)
            
        Returns:
            bool: 是否保存成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 确保videos表存在
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    content_id TEXT PRIMARY KEY,
                    title TEXT,
                    send_time TEXT,
                    pv INTEGER,
                    praise_count INTEGER,
                    reply_count INTEGER,
                    account_name TEXT,
                    appid TEXT,
                    analyze_date TEXT,
                    is_abnormal INTEGER,
                    recommend INTEGER,
                    audit_reason TEXT,
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            inserted_count = 0
            updated_count = 0
            
            for video in videos:
                # 使用INSERT OR REPLACE语句更新数据
                cursor.execute('''
                    INSERT OR REPLACE INTO videos (
                        content_id, title, send_time, pv, praise_count, reply_count,
                        account_name, appid, analyze_date, is_abnormal, recommend, audit_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video['content_id'],
                    video['title'],
                    video['send_time'],
                    video['pv'],
                    video['praise_count'],
                    video['reply_count'],
                    video['account_name'],
                    video.get('appid', appid),  # 优先使用video中的appid
                    video.get('analyze_date', query_date),  # 优先使用video中的analyze_date
                    1 if video.get('is_abnormal', False) else 0,
                    1 if video.get('recommend', False) else 0,
                    video.get('audit_reason', '')
                ))
                
                if cursor.rowcount == 1:
                    inserted_count += 1
                else:
                    updated_count += 1
            
            # 如果提供了appid,更新账号统计信息
            if appid:
                total_videos = len(videos)
                total_recommended = sum(1 for v in videos if v.get('recommend', False))
                total_plays = sum(v.get('pv', 0) for v in videos)
                
                cursor.execute('''
                    UPDATE accounts 
                    SET today_videos = ?, today_recommended = ?, today_views = ?, last_updated = ?
                    WHERE appid = ?
                ''', (
                    total_videos, total_recommended, total_plays,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appid
                ))
            
            conn.commit()
            conn.close()
            print(f"成功保存视频数据: 新增{inserted_count}条，更新{updated_count}条")
            return True
            
        except Exception as e:
            print(f"保存视频数据时出错: {str(e)}")
            if 'conn' in locals():
                conn.close()
            return False

    def check_duplicate_video(self, content_id):
        """检查视频是否已存在
        
        Args:
            content_id: 视频内容ID
            
        Returns:
            int: 视频在数据库中的数量
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM videos WHERE content_id = ?', (content_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"查询视频数量失败: {str(e)}")
            if 'conn' in locals():
                conn.close()
            return 0

    def get_today_videos(self):
        """获取今日的所有视频数据
        
        Returns:
            list: 包含今日所有视频数据的列表
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            print(f"正在查询今日({today})的视频数据...")
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 查询今天的所有视频数据
            cursor.execute('''
                SELECT content_id, title, send_time, pv, praise_count, reply_count,
                       account_name, appid, analyze_date, is_abnormal, recommend, audit_reason
                FROM videos 
                WHERE analyze_date = ?
                ORDER BY pv DESC
            ''', (today,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                print(f"数据库中未找到{today}的视频数据")
                return []
                
            # 构建视频数据列表
            videos = []
            for row in rows:
                content_id, title, send_time, pv, praise_count, reply_count, \
                account_name, appid, analyze_date, is_abnormal, recommend, audit_reason = row
                
                # 处理时间戳
                if send_time and isinstance(send_time, (int, float)) or (isinstance(send_time, str) and send_time.isdigit()):
                    try:
                        send_time_value = int(send_time) if isinstance(send_time, str) else send_time
                        send_time = datetime.fromtimestamp(send_time_value/1000).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                video = {
                    'content_id': content_id,
                    'title': title,
                    'send_time': send_time,
                    'pv': pv,
                    'praise_count': praise_count,
                    'reply_count': reply_count,
                    'account_name': account_name,
                    'appid': appid,
                    'analyze_date': analyze_date,
                    'is_abnormal': is_abnormal == 1,
                    'recommend': recommend == 1,
                    'audit_reason': audit_reason
                }
                videos.append(video)
            
            print(f"成功获取{today}的视频数据，共{len(videos)}条")
            # 打印前5条视频数据以便调试
            if videos:
                print("视频数据示例:")
                for i, video in enumerate(videos[:5]):
                    print(f"  {i+1}. {video['title']} (播放量: {video['pv']})")
            return videos
        except Exception as e:
            print(f"获取今日视频数据失败: {str(e)}")
            traceback.print_exc()
            return []

    def get_videos_by_date(self, query_date):
        """按指定日期获取视频数据
        
        Args:
            query_date (str): 查询日期，格式为'yyyy-MM-dd'
            
        Returns:
            list: 包含指定日期所有视频数据的列表
        """
        try:
            print(f"正在查询{query_date}的视频数据...")
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 查询指定日期的所有视频数据
            cursor.execute('''
                SELECT content_id, title, send_time, pv, praise_count, reply_count,
                       account_name, appid, analyze_date, is_abnormal, recommend, audit_reason
                FROM videos 
                WHERE analyze_date = ?
                ORDER BY pv DESC
            ''', (query_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                print(f"数据库中未找到{query_date}的视频数据")
                return []
                
            # 构建视频数据列表
            videos = []
            for row in rows:
                content_id, title, send_time, pv, praise_count, reply_count, \
                account_name, appid, analyze_date, is_abnormal, recommend, audit_reason = row
                
                # 处理时间戳
                if send_time and isinstance(send_time, (int, float)) or (isinstance(send_time, str) and send_time.isdigit()):
                    try:
                        send_time_value = int(send_time) if isinstance(send_time, str) else send_time
                        send_time = datetime.fromtimestamp(send_time_value/1000).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                video = {
                    'content_id': content_id,
                    'title': title,
                    'send_time': send_time,
                    'pv': pv,
                    'praise_count': praise_count,
                    'reply_count': reply_count,
                    'account_name': account_name,
                    'appid': appid,
                    'analyze_date': analyze_date,
                    'is_abnormal': is_abnormal == 1,
                    'recommend': recommend == 1,
                    'audit_reason': audit_reason
                }
                videos.append(video)
            
            print(f"成功获取{query_date}的视频数据，共{len(videos)}条")
            return videos
        except Exception as e:
            print(f"获取{query_date}视频数据失败: {str(e)}")
            traceback.print_exc()
            return []

    def get_today_published_videos(self):
        """获取今日发布的所有视频数据（通过send_time匹配）
        
        Returns:
            list: 包含今日发布的所有视频数据的列表
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            print(f"正在查询今日({today})发布的视频数据...")
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 查询今天发布的所有视频数据，匹配send_time字段中包含今日日期的记录
            # 注意：send_time可能是时间戳也可能是格式化后的时间字符串
            cursor.execute('''
                SELECT content_id, title, send_time, pv, praise_count, reply_count,
                       account_name, appid, analyze_date, is_abnormal, recommend, audit_reason
                FROM videos 
                WHERE send_time LIKE ?
                ORDER BY pv DESC
            ''', (f'%{today}%',))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                print(f"数据库中未找到{today}发布的视频数据")
                return []
                
            # 构建视频数据列表
            videos = []
            for row in rows:
                content_id, title, send_time, pv, praise_count, reply_count, \
                account_name, appid, analyze_date, is_abnormal, recommend, audit_reason = row
                
                # 处理时间戳
                if send_time and isinstance(send_time, (int, float)) or (isinstance(send_time, str) and send_time.isdigit()):
                    try:
                        send_time_value = int(send_time) if isinstance(send_time, str) else send_time
                        send_time = datetime.fromtimestamp(send_time_value/1000).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                video = {
                    'content_id': content_id,
                    'title': title,
                    'send_time': send_time,
                    'pv': pv,
                    'praise_count': praise_count,
                    'reply_count': reply_count,
                    'account_name': account_name,
                    'appid': appid,
                    'analyze_date': analyze_date,
                    'is_abnormal': is_abnormal == 1,
                    'recommend': recommend == 1,
                    'audit_reason': audit_reason
                }
                videos.append(video)
            
            print(f"成功获取{today}发布的视频数据，共{len(videos)}条")
            # 打印前5条视频数据以便调试
            if videos:
                print("视频数据示例:")
                for i, video in enumerate(videos[:5]):
                    print(f"  {i+1}. {video['title']} (发布时间: {video['send_time']}, 播放量: {video['pv']})")
            return videos
        except Exception as e:
            print(f"获取今日发布视频数据失败: {str(e)}")
            traceback.print_exc()
            return []

# 单例模式
db_manager = DatabaseManager() 