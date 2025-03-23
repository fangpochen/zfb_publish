#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import json
import sqlite3
import threading
from datetime import datetime
import logging
from datetime import timedelta

class UploadStatistics:
    """上传统计类，负责统计上传结果并存储到数据库"""
    
    def __init__(self, db_path=None):
        """初始化上传统计
        
        Args:
            db_path: 数据库路径，可选，不提供则只在内存中统计，不持久化
        """
        # 统计数据
        self.account_stats = {}  # {account_id: {success: 0, failed: 0, last_time: None}}
        self.daily_stats = {}    # {date: {account_id: {success: 0, failed: 0}}}
        
        # 数据库路径和连接
        self.db_path = db_path
        self.conn = None
        
        # 线程锁
        self.lock = threading.RLock()
        
        # 日志记录器
        self.logger = logging.getLogger('UploadStatistics')
        
        # 初始化数据库
        if db_path:
            self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        try:
            # 创建数据库目录
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            # 连接数据库
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()
            
            # 创建上传记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS upload_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT UNIQUE,
                account_id TEXT,
                file_path TEXT,
                file_name TEXT,
                file_size INTEGER,
                status TEXT,
                error TEXT,
                error_detail TEXT,
                error_code TEXT,
                create_time REAL,
                update_time REAL,
                upload_start_time REAL,
                upload_end_time REAL,
                process_start_time REAL,
                process_end_time REAL,
                publish_start_time REAL,
                publish_end_time REAL,
                video_url TEXT,
                publish_id TEXT,
                day_key TEXT,
                extra_data TEXT
            )
            ''')
            
            # 创建账号日统计表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_key TEXT,
                account_id TEXT,
                success_count INTEGER,
                failed_count INTEGER,
                pending_count INTEGER,
                last_upload_time REAL,
                update_time REAL,
                UNIQUE(day_key, account_id)
            )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_records_trace_id ON upload_records (trace_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_records_account_id ON upload_records (account_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_records_day_key ON upload_records (day_key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_records_status ON upload_records (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_daily_stats_day_key_account_id ON account_daily_stats (day_key, account_id)')
            
            self.conn.commit()
            
            self.logger.info(f"数据库初始化成功: {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"初始化数据库时出错: {str(e)}")
            if self.conn:
                self.conn.close()
                self.conn = None
    
    def update_account_stat(self, account_id, success=None, failed=None, pending=None):
        """更新账号统计信息
        
        Args:
            account_id: 账号ID
            success: 成功数量增量，可选
            failed: 失败数量增量，可选
            pending: 待处理数量增量，可选
            
        Returns:
            dict: 更新后的账号统计信息
        """
        with self.lock:
            # 获取当前日期键
            day_key = datetime.now().strftime('%Y-%m-%d')
            
            # 初始化账号统计
            if account_id not in self.account_stats:
                self.account_stats[account_id] = {
                    'success': 0,
                    'failed': 0,
                    'pending': 0,
                    'last_time': None
                }
            
            # 初始化日期统计
            if day_key not in self.daily_stats:
                self.daily_stats[day_key] = {}
            
            if account_id not in self.daily_stats[day_key]:
                self.daily_stats[day_key][account_id] = {
                    'success': 0,
                    'failed': 0,
                    'pending': 0
                }
            
            # 更新账号统计
            if success:
                self.account_stats[account_id]['success'] += success
                self.daily_stats[day_key][account_id]['success'] += success
                self.account_stats[account_id]['last_time'] = time.time()
            
            if failed:
                self.account_stats[account_id]['failed'] += failed
                self.daily_stats[day_key][account_id]['failed'] += failed
                self.account_stats[account_id]['last_time'] = time.time()
            
            if pending:
                self.account_stats[account_id]['pending'] += pending
                self.daily_stats[day_key][account_id]['pending'] += pending
            
            # 更新数据库
            if self.conn and (success or failed):
                self._update_db_stats(day_key, account_id)
            
            return self.account_stats[account_id]
    
    
    
    def _update_db_stats(self, day_key, account_id):
        """更新数据库中的账号统计
        
        Args:
            day_key: 日期键
            account_id: 账号ID
            
        Returns:
            bool: 是否成功更新
        """
        if not self.conn:
            return False
        
        try:
            # 准备数据
            account_stat = self.daily_stats[day_key][account_id]
            success_count = account_stat['success']
            failed_count = account_stat['failed']
            pending_count = account_stat['pending']
            last_upload_time = self.account_stats[account_id]['last_time']
            update_time = time.time()
            
            # 更新数据
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO account_daily_stats (
                day_key, account_id, success_count, failed_count, pending_count, last_upload_time, update_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                day_key, account_id, success_count, failed_count, pending_count, last_upload_time, update_time
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"更新账号统计时出错: {str(e)}")
            return False
    
    def get_account_stats(self, account_id, days=1):
        """获取账号统计信息
        
        Args:
            account_id: 账号ID
            days: 天数，默认为1表示只获取今天的统计
            
        Returns:
            dict: 账号统计信息
        """
        with self.lock:
            if account_id not in self.account_stats:
                # 尝试从数据库加载
                if self.conn:
                    stats = self.get_account_stats_from_db(account_id, days)
                    if stats:
                        return stats
                
                # 初始化统计
                self.account_stats[account_id] = {
                    'success': 0,
                    'failed': 0,
                    'pending': 0,
                    'last_time': None
                }
            
            return self.account_stats[account_id]
    
    def get_account_stats_from_db(self, account_id, days=1):
        """从数据库获取账号统计信息
        
        Args:
            account_id: 账号ID
            days: 天数，默认为1表示只获取今天的统计
            
        Returns:
            dict: 账号统计信息
        """
        if not self.conn:
            return None
        
        try:
            # 计算日期范围
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = today - timedelta(days=days-1)
            
            # 生成日期键列表
            date_keys = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                date_keys.append(date.strftime('%Y-%m-%d'))
            
            # 获取统计信息
            cursor = self.conn.cursor()
            stats = {
                'success': 0,
                'failed': 0,
                'pending': 0,
                'last_time': None,
                'daily': {}
            }
            
            for date_key in date_keys:
                # 查询日期统计
                cursor.execute('''
                SELECT success_count, failed_count, pending_count, last_upload_time
                FROM account_daily_stats
                WHERE day_key = ? AND account_id = ?
                ''', (date_key, account_id))
                
                row = cursor.fetchone()
                if row:
                    success_count, failed_count, pending_count, last_upload_time = row
                    
                    # 统计合计
                    stats['success'] += success_count
                    stats['failed'] += failed_count
                    stats['pending'] += pending_count
                    
                    # 更新最后上传时间
                    if last_upload_time and (stats['last_time'] is None or last_upload_time > stats['last_time']):
                        stats['last_time'] = last_upload_time
                    
                    # 保存日期统计
                    stats['daily'][date_key] = {
                        'success': success_count,
                        'failed': failed_count,
                        'pending': pending_count,
                        'last_time': last_upload_time
                    }
                else:
                    # 无数据，填充0
                    stats['daily'][date_key] = {
                        'success': 0,
                        'failed': 0,
                        'pending': 0,
                        'last_time': None
                    }
            
            # 更新内存中的统计
            if stats['success'] > 0 or stats['failed'] > 0:
                today_key = datetime.now().strftime('%Y-%m-%d')
                
                # 更新今日统计
                if today_key in stats['daily']:
                    if today_key not in self.daily_stats:
                        self.daily_stats[today_key] = {}
                    
                    if account_id not in self.daily_stats[today_key]:
                        self.daily_stats[today_key][account_id] = {
                            'success': 0,
                            'failed': 0,
                            'pending': 0
                        }
                    
                    self.daily_stats[today_key][account_id]['success'] = stats['daily'][today_key]['success']
                    self.daily_stats[today_key][account_id]['failed'] = stats['daily'][today_key]['failed']
                    self.daily_stats[today_key][account_id]['pending'] = stats['daily'][today_key]['pending']
                
                # 更新账号统计
                self.account_stats[account_id] = {
                    'success': stats['success'],
                    'failed': stats['failed'],
                    'pending': stats['pending'],
                    'last_time': stats['last_time']
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"从数据库获取账号统计时出错: {str(e)}")
            return None
    
    def get_task_records(self, account_id=None, status=None, day_key=None, limit=100, offset=0):
        """获取任务记录
        
        Args:
            account_id: 账号ID，可选，不提供则获取所有账号
            status: 状态，可选，不提供则获取所有状态
            day_key: 日期键，可选，不提供则获取所有日期
            limit: 限制数量，默认100
            offset: 偏移量，默认0
            
        Returns:
            list: 任务记录列表
        """
        if not self.conn:
            return []
        
        try:
            # 构建查询条件
            query = 'SELECT * FROM upload_records WHERE 1=1'
            params = []
            
            if account_id:
                query += ' AND account_id = ?'
                params.append(account_id)
            
            if status:
                if isinstance(status, list):
                    placeholders = ', '.join(['?' for _ in status])
                    query += f' AND status IN ({placeholders})'
                    params.extend(status)
                else:
                    query += ' AND status = ?'
                    params.append(status)
            
            if day_key:
                query += ' AND day_key = ?'
                params.append(day_key)
            
            # 添加排序和分页
            query += ' ORDER BY create_time DESC LIMIT ? OFFSET ?'
            params.append(limit)
            params.append(offset)
            
            # 执行查询
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            
            # 获取列名
            columns = [col[0] for col in cursor.description]
            
            # 获取结果
            records = []
            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                
                # 解析额外数据
                if 'extra_data' in record and record['extra_data']:
                    try:
                        record['extra_data'] = json.loads(record['extra_data'])
                    except:
                        pass
                
                records.append(record)
            
            return records
            
        except Exception as e:
            self.logger.error(f"获取任务记录时出错: {str(e)}")
            return []
    
    def get_daily_summary(self, days=7):
        """获取每日上传汇总
        
        Args:
            days: 天数，默认为7
            
        Returns:
            dict: 每日上传汇总
        """
        if not self.conn:
            return {}
        
        try:
            # 计算日期范围
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = today - timedelta(days=days-1)
            
            # 生成日期键列表
            date_keys = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                date_keys.append(date.strftime('%Y-%m-%d'))
            
            # 获取每日汇总
            cursor = self.conn.cursor()
            summary = {}
            
            for date_key in date_keys:
                # 查询成功数量
                cursor.execute('''
                SELECT COUNT(*) FROM upload_records 
                WHERE day_key = ? AND status = 'completed'
                ''', (date_key,))
                success_count = cursor.fetchone()[0]
                
                # 查询失败数量
                cursor.execute('''
                SELECT COUNT(*) FROM upload_records 
                WHERE day_key = ? AND (status = 'failed' OR status LIKE '%_failed')
                ''', (date_key,))
                failed_count = cursor.fetchone()[0]
                
                # 保存日期汇总
                summary[date_key] = {
                    'success': success_count,
                    'failed': failed_count,
                    'total': success_count + failed_count
                }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"获取每日上传汇总时出错: {str(e)}")
            return {}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None 