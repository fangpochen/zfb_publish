#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import json
import logging
import traceback
import threading
import datetime
import concurrent.futures
import random
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UploadManager")

class ThreadControl:
    """线程控制类，用于控制上传线程的启动、停止和状态监控"""
    
    def __init__(self):
        """初始化线程控制器"""
        self._stop_flag = False
        self._futures = []
        self._mutex = QMutex()
        
    def stop(self):
        """设置停止标志，通知所有线程停止运行"""
        self._stop_flag = True
        # 取消所有未完成的future
        for future in self._futures:
            if not future.done():
                future.cancel()
                
    def clear(self):
        """清除停止标志和未完成的任务"""
        self._stop_flag = False
        self._futures = []
        
    def should_stop(self):
        """检查是否应该停止
        
        Returns:
            bool: 如果设置了停止标志，则返回True，否则返回False
        """
        return self._stop_flag
        
    def add_future(self, future):
        """添加一个future到列表中
        
        Args:
            future: 并发任务的future对象
        """
        self._mutex.lock()
        self._futures.append(future)
        self._mutex.unlock()
        
    def remove_future(self, future):
        """从列表中移除一个future
        
        Args:
            future: 要移除的future对象
        """
        self._mutex.lock()
        if future in self._futures:
            self._futures.remove(future)
        self._mutex.unlock()

class UploadSignals(QObject):
    """上传进度信号类"""
    
    upload_progress = pyqtSignal(str, int, int)  # 文件名, 当前进度, 总大小
    upload_success = pyqtSignal(str, str)  # 文件名, 内容ID
    upload_failed = pyqtSignal(str, str)  # 文件名, 错误信息
    upload_complete = pyqtSignal(dict)  # 上传统计结果
    upload_status = pyqtSignal(str)  # 状态信息
    
class UploadManager(QObject):
    """视频上传管理器，处理视频上传的所有功能"""
    
    def __init__(self, parent=None, log_callback=None):
        """初始化上传管理器
        
        Args:
            parent: 父对象
            log_callback: 日志回调函数
        """
        super().__init__(parent)
        self.log_callback = log_callback or print
        self.logger = logging.getLogger('UploadManager')
        self.signals = UploadSignals()
        self.thread_control = ThreadControl()
        self.max_workers = 3  # 默认线程数
        self.is_uploading = False
        self.upload_thread = None
        
    def log_message(self, message):
        """记录日志消息
        
        Args:
            message: 日志消息
        """
        self.logger.info(message)
        if self.log_callback:
            self.log_callback(message)
        
    def set_max_workers(self, max_workers):
        """设置最大线程数
        
        Args:
            max_workers: 最大线程数
        """
        if max_workers > 0:
            self.max_workers = max_workers
            self.log_message(f"已设置最大线程数为 {max_workers}")
        
    def start_upload(self, account_folders, topics=None, max_uploads=None, delete_original=False, schedule_time=None, cover_path=None, use_random_cover=True):
        """开始上传视频
        
        Args:
            account_folders: 账号与文件夹的映射字典 {appid: {'folder': folder_path, 'cookies': cookies}}
            topics: 视频标签列表
            max_uploads: 每个账号最大上传数量
            delete_original: 上传后是否删除原始文件
            schedule_time: 定时发布时间，格式为字符串'HH:MM:SS'或None（不定时）
            cover_path: 自定义封面图片路径
            use_random_cover: 是否使用随机封面
            
        Returns:
            bool: 是否成功启动上传
        """
        if self.is_uploading:
            self.log_message("已有上传任务正在进行中")
            return False
            
        self.is_uploading = True
        self.thread_control.clear()
        
        # 创建并启动上传线程
        self.upload_thread = UploadThread(
            account_folders=account_folders,
            topics=topics,
            max_uploads=max_uploads,
            delete_original=delete_original,
            schedule_time=schedule_time,
            cover_path=cover_path,
            use_random_cover=use_random_cover,
            max_workers=self.max_workers,
            thread_control=self.thread_control,
            signals=self.signals,
            log_callback=self.log_message
        )
        
        # 连接信号
        self.upload_thread.signals.upload_complete.connect(self._on_upload_complete)
        
        # 启动线程
        self.upload_thread.start()
        self.log_message("开始上传视频")
        return True
        
    def stop_upload(self):
        """停止上传"""
        if not self.is_uploading:
            self.log_message("没有正在进行的上传任务")
            return
            
        self.log_message("正在停止上传任务...")
        self.thread_control.stop()
        
    def _on_upload_complete(self, stats):
        """上传完成回调
        
        Args:
            stats: 上传统计结果
        """
        self.is_uploading = False
        self.log_message(f"上传任务完成：总计 {stats['total']}，成功 {stats['success']}，失败 {stats['failed']}")

class UploadThread(QThread):
    """上传线程类"""
    
    def __init__(self, account_folders, topics, max_uploads, delete_original, schedule_time, cover_path, use_random_cover, 
                 max_workers, thread_control, signals, log_callback):
        """初始化上传线程
        
        Args:
            account_folders: 账号与文件夹的映射字典
            topics: 视频标签列表
            max_uploads: 每个账号最大上传数量
            delete_original: 上传后是否删除原始文件
            schedule_time: 定时发布时间
            cover_path: 自定义封面图片路径
            use_random_cover: 是否使用随机封面
            max_workers: 最大线程数
            thread_control: 线程控制器
            signals: 信号对象
            log_callback: 日志回调函数
        """
        super().__init__()
        self.account_folders = account_folders
        self.topics = topics
        self.max_uploads = max_uploads
        self.delete_original = delete_original
        self.schedule_time = schedule_time
        self.cover_path = cover_path
        self.use_random_cover = use_random_cover
        self.max_workers = max_workers
        self.thread_control = thread_control
        self.signals = signals
        self.log_callback = log_callback
        
    def log_message(self, message):
        """记录日志消息"""
        if self.log_callback:
            self.log_callback(message)
        
    def run(self):
        """线程运行方法"""
        try:
            total_count = 0
            success_count = 0
            failed_count = 0
            start_time = time.time()
            
            # 遍历每个账号和对应的文件夹
            for appid, data in self.account_folders.items():
                if self.thread_control.should_stop():
                    break
                    
                folder_path = data.get('folder')
                cookies = data.get('cookies')
                limit = self.max_uploads
                
                # 检查文件夹是否存在
                if not folder_path or not os.path.exists(folder_path):
                    self.log_message(f"账号 {appid} 的文件夹不存在：{folder_path}")
                    continue
                    
                # 检查cookies是否有效
                if not cookies or 'ctoken' not in cookies:
                    self.log_message(f"账号 {appid} 的cookies无效")
                    continue
                
                self.log_message(f"开始处理账号 {appid} 的视频，文件夹：{folder_path}")
                
                # 获取文件夹中的视频文件
                video_files = self._get_video_files(folder_path)
                if not video_files:
                    self.log_message(f"账号 {appid} 的文件夹中没有视频文件")
                    continue
                
                # 限制上传数量
                if limit and len(video_files) > limit:
                    self.log_message(f"账号 {appid} 限制上传 {limit} 个视频，实际有 {len(video_files)} 个视频，将只上传前 {limit} 个")
                    video_files = video_files[:limit]
                
                # 实际上传文件
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    
                    for file_path in video_files:
                        if self.thread_control.should_stop():
                            break
                            
                        # 提交上传任务
                        future = executor.submit(
                            self._upload_single_video_mock,
                            appid,
                            cookies,
                            file_path,
                            self.topics,
                            self.schedule_time,
                            self.delete_original
                        )
                        futures.append(future)
                        self.thread_control.add_future(future)
                        
                    # 处理上传结果
                    for future in futures:
                        if self.thread_control.should_stop():
                            break
                            
                        try:
                            total_count += 1
                            is_success, content_id, error_msg = future.result()
                            
                            if is_success:
                                success_count += 1
                            else:
                                failed_count += 1
                                
                        except Exception as e:
                            failed_count += 1
                            self.log_message(f"上传任务执行失败：{str(e)}")
                        finally:
                            self.thread_control.remove_future(future)
            
            # 计算总耗时
            end_time = time.time()
            time_spent = end_time - start_time
            
            # 计算时、分、秒
            hours, remainder = divmod(time_spent, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            # 构建统计结果
            stats = {
                'total': total_count,
                'success': success_count,
                'failed': failed_count,
                'time_spent': {
                    'total_seconds': time_spent,
                    'hours': int(hours),
                    'minutes': int(minutes),
                    'seconds': int(seconds),
                }
            }
            
            self.signals.upload_complete.emit(stats)
            
        except Exception as e:
            self.log_message(f"上传线程发生错误: {str(e)}")
            traceback.print_exc()
            
            # 发送错误信息
            stats = {
                "total": total_count,
                "success": success_count,
                "failed": failed_count,
                "error": str(e)
            }
            self.signals.upload_complete.emit(stats)
            
    def _get_video_files(self, folder_path):
        """获取文件夹中的视频文件
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            list: 视频文件路径列表
        """
        video_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
        video_files = []
        
        try:
            for file in os.listdir(folder_path):
                if self.thread_control.should_stop():
                    break
                    
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file)[1].lower()
                    if ext in video_extensions:
                        video_files.append(file_path)
            
            # 按名称排序
            video_files.sort()
            return video_files
            
        except Exception as e:
            self.log_message(f"获取视频文件失败: {str(e)}")
            return []
            
    def _upload_single_video_mock(self, appid, cookies, file_path, topics, schedule_time, delete_original):
        """模拟上传单个视频（用于测试）
        
        Args:
            appid: 账号ID
            cookies: Cookies
            file_path: 视频文件路径
            topics: 话题列表
            schedule_time: 定时发布时间
            delete_original: 是否删除原始文件
            
        Returns:
            tuple: (是否成功, 内容ID, 错误信息)
        """
        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # 模拟进度
            total_steps = 10
            
            # 步骤1：准备和验证视频文件
            self.signals.upload_progress.emit(file_name, 1, total_steps)
            self.signals.upload_status.emit(f"准备上传视频: {file_name}")
            time.sleep(0.2 + random.random() * 0.3)
            
            # 模拟随机失败情况
            if random.random() < 0.03:  # 3%的失败率
                return False, "", "视频文件验证失败"
            
            # 步骤2：准备封面
            self.signals.upload_progress.emit(file_name, 2, total_steps)
            
            # 处理封面逻辑
            if self.use_random_cover:
                self.signals.upload_status.emit(f"正在生成随机封面: {file_name}")
            else:
                if self.cover_path and os.path.exists(self.cover_path):
                    self.signals.upload_status.emit(f"正在处理自定义封面: {os.path.basename(self.cover_path)}")
                else:
                    self.signals.upload_status.emit(f"未找到自定义封面，使用自动封面")
                    
            time.sleep(0.3 + random.random() * 0.4)
            
            # 模拟随机失败情况
            if random.random() < 0.02:  # 2%的失败率
                return False, "", "封面处理失败"
            
            # 步骤3-9：上传过程
            for i in range(3, 10):
                if self.thread_control.should_stop():
                    return False, "", "用户取消上传"
                
                # 模拟上传进度
                self.signals.upload_progress.emit(file_name, i, total_steps)
                
                if i == 3:
                    self.signals.upload_status.emit(f"开始上传视频: {file_name}")
                elif i == 5:
                    self.signals.upload_status.emit(f"上传进度 50%: {file_name}")
                elif i == 8:
                    self.signals.upload_status.emit(f"上传完成，处理中: {file_name}")
                else:
                    self.signals.upload_status.emit(f"正在上传 {file_name} ({i}/{total_steps})")
                
                # 随机模拟失败情况
                if i > 3 and random.random() < 0.01:  # 上传过程中1%的失败率
                    return False, "", f"上传过程中断: 步骤 {i}/10"
                
                # 休眠一段时间模拟上传过程
                time.sleep(0.3 + random.random() * 0.5)
            
            # 步骤10：完成上传
            self.signals.upload_progress.emit(file_name, 10, total_steps)
            self.signals.upload_status.emit(f"正在完成视频发布: {file_name}")
            time.sleep(0.3 + random.random() * 0.3)
            
            # 生成随机内容ID
            content_id = f"v{int(time.time())}{random.randint(10000, 99999)}"
            
            # 如果需要删除原始文件
            if delete_original:
                try:
                    # 模拟文件删除，实际开发时取消注释
                    # os.remove(file_path)
                    self.log_message(f"已删除原始文件: {file_path}")
                except Exception as e:
                    self.log_message(f"删除原始文件失败: {file_path}, 错误: {str(e)}")
            
            return True, content_id, ""
            
        except Exception as e:
            error_msg = f"上传视频失败: {str(e)}"
            self.log_message(error_msg)
            return False, "", error_msg
    
    # 以下方法将在后续实现：
    # _upload_single_video - 上传单个视频
    # _get_mt_token - 获取MT令牌
    # _upload_small_video - 上传小视频(<4MB)
    # _upload_large_video - 上传大视频(>4MB)
    # _upload_cover - 上传视频封面
    # _complete_upload - 完成上传
    # _get_video_url - 获取视频URL
    # _publish_video - 发布视频 