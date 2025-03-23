#!/usr/bin/env python
# -*- coding: utf-8 -*-

import queue
import threading
import logging
import time
import traceback
from utils.video_task import VideoTask

class QueueManager:
    """队列管理器，负责管理上传、处理和发布队列"""
    
    def __init__(self, upload_max_size=100, process_max_size=100, publish_max_size=100):
        """初始化队列管理器
        
        Args:
            upload_max_size: 上传队列最大容量
            process_max_size: 处理队列最大容量
            publish_max_size: 发布队列最大容量
        """
        # 创建队列
        self.upload_queue = queue.Queue(maxsize=upload_max_size)
        self.process_queue = queue.Queue(maxsize=process_max_size)
        self.publish_queue = queue.Queue(maxsize=publish_max_size)
        self.result_queue = queue.Queue()
        
        # 创建任务集合和锁，用于快速查找任务
        self.account_task_map = {}  # {account_id: [task_trace_id, ...]}
        self.task_map = {}  # {trace_id: task}
        self.account_lock = threading.RLock()
        
        # 计数器
        self.counts = {
            'upload_total': 0,
            'upload_success': 0,
            'upload_failed': 0,
            'process_total': 0,
            'process_success': 0,
            'process_failed': 0,
            'publish_total': 0,
            'publish_success': 0,
            'publish_failed': 0,
            'total': 0,
            'success': 0,
            'failed': 0
        }
        self.counts_lock = threading.RLock()
        
        # 日志记录器
        self.logger = logging.getLogger('QueueManager')
    
    def add_upload_task(self, task):
        """添加上传任务到队列
        
        Args:
            task: VideoTask对象
            
        Returns:
            bool: 是否成功添加
        """
        try:
            # 记录任务
            with self.account_lock:
                account_id = task.appid
                trace_id = task.trace_id
                
                # 将任务添加到账号任务映射
                if account_id not in self.account_task_map:
                    self.account_task_map[account_id] = []
                
                if trace_id not in self.account_task_map[account_id]:
                    self.account_task_map[account_id].append(trace_id)
                
                # 将任务添加到任务映射
                self.task_map[trace_id] = task
            
            # 添加到上传队列
            self.upload_queue.put(task, block=True, timeout=1)
            
            # 更新计数
            with self.counts_lock:
                self.counts['upload_total'] += 1
                self.counts['total'] += 1
                
            return True
            
        except queue.Full:
            self.logger.warning(f"上传队列已满，无法添加任务: {task.file_name}")
            return False
        except Exception as e:
            self.logger.error(f"添加上传任务时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def add_process_task(self, task):
        """添加处理任务到队列
        
        Args:
            task: VideoTask对象
            
        Returns:
            bool: 是否成功添加
        """
        try:
            # 添加到处理队列
            self.process_queue.put(task, block=True, timeout=1)
            
            # 更新计数
            with self.counts_lock:
                self.counts['process_total'] += 1
                
            return True
            
        except queue.Full:
            self.logger.warning(f"处理队列已满，无法添加任务: {task.file_name}")
            return False
        except Exception as e:
            self.logger.error(f"添加处理任务时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def add_publish_task(self, task):
        """添加发布任务到队列
        
        Args:
            task: VideoTask对象
            
        Returns:
            bool: 是否成功添加
        """
        try:
            # 添加到发布队列
            self.publish_queue.put(task, block=True, timeout=1)
            
            # 更新计数
            with self.counts_lock:
                self.counts['publish_total'] += 1
                
            return True
            
        except queue.Full:
            self.logger.warning(f"发布队列已满，无法添加任务: {task.file_name}")
            return False
        except Exception as e:
            self.logger.error(f"添加发布任务时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def add_result(self, task, success=True, stage=None):
        """添加任务结果
        
        Args:
            task: VideoTask对象
            success: 是否成功
            stage: 当前阶段
        """
        try:
            # 更新计数
            with self.counts_lock:
                if stage == 'upload':
                    if success:
                        self.counts['upload_success'] += 1
                    else:
                        self.counts['upload_failed'] += 1
                elif stage == 'process':
                    if success:
                        self.counts['process_success'] += 1
                    else:
                        self.counts['process_failed'] += 1
                elif stage == 'publish':
                    if success:
                        self.counts['publish_success'] += 1
                        self.counts['success'] += 1
                    else:
                        self.counts['publish_failed'] += 1
                        self.counts['failed'] += 1
            
            # 对于完成的任务，添加到结果队列
            if stage == 'publish' or (not success and stage in ['upload', 'process']):
                self.result_queue.put(task)
                
        except Exception as e:
            self.logger.error(f"添加任务结果时出错: {str(e)}")
            traceback.print_exc()
    
    def get_upload_task(self, block=True, timeout=None):
        """获取上传任务
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间
            
        Returns:
            VideoTask: 视频任务对象，如果队列为空则返回None
        """
        try:
            task = self.upload_queue.get(block=block, timeout=timeout)
            
            # 检查任务是否被取消
            if task.is_cancelled:
                # 标记任务完成
                self.mark_upload_done()
                # 重新获取任务
                return self.get_upload_task(block=False)
                
            return task
        except queue.Empty:
            return None
    
    def get_process_task(self, block=True, timeout=None):
        """获取处理任务
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间
            
        Returns:
            VideoTask: 视频任务对象，如果队列为空则返回None
        """
        try:
            task = self.process_queue.get(block=block, timeout=timeout)
            
            # 检查任务是否被取消
            if task.is_cancelled:
                # 标记任务完成
                self.mark_process_done()
                # 重新获取任务
                return self.get_process_task(block=False)
                
            return task
        except queue.Empty:
            return None
    
    def get_publish_task(self, block=True, timeout=None):
        """获取发布任务
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间
            
        Returns:
            VideoTask: 视频任务对象，如果队列为空则返回None
        """
        try:
            task = self.publish_queue.get(block=block, timeout=timeout)
            
            # 检查任务是否被取消
            if task.is_cancelled:
                # 标记任务完成
                self.mark_publish_done()
                # 重新获取任务
                return self.get_publish_task(block=False)
                
            return task
        except queue.Empty:
            return None
    
    def get_result(self, block=True, timeout=None):
        """获取任务结果
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间
            
        Returns:
            VideoTask: 视频任务对象，如果队列为空则返回None
        """
        try:
            return self.result_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def mark_upload_done(self):
        """标记上传任务完成"""
        self.upload_queue.task_done()
    
    def mark_process_done(self):
        """标记处理任务完成"""
        self.process_queue.task_done()
    
    def mark_publish_done(self):
        """标记发布任务完成"""
        self.publish_queue.task_done()
    
    def mark_result_done(self):
        """标记结果任务完成"""
        self.result_queue.task_done()
    
    def is_account_has_pending_tasks(self, account_id):
        """检查账号是否有未完成的任务
        
        Args:
            account_id: 账号ID
            
        Returns:
            bool: 是否有未完成的任务
        """
        with self.account_lock:
            if account_id not in self.account_task_map:
                self.logger.info(f"账号 {account_id} 没有任何任务")
                return False
            
            # 获取账号任务数量    
            task_count = len(self.account_task_map[account_id])
            pending_tasks = []
            completed_tasks = []
            
            for trace_id in self.account_task_map[account_id]:
                if trace_id in self.task_map:
                    task = self.task_map[trace_id]
                    # 使用VideoTask类的常量检查状态
                    if task.status not in [VideoTask.STATUS_COMPLETED, VideoTask.STATUS_FAILED]:
                        pending_tasks.append(task)
                    else:
                        completed_tasks.append(task)
            
            # 输出详细任务信息
            pending_count = len(pending_tasks)
            completed_count = len(completed_tasks)
            self.logger.info(f"账号 {account_id} 任务检查: 总数 {task_count}, 待处理 {pending_count}, 已完成 {completed_count}")
            
            if pending_count > 0:
                pending_status = {}
                for task in pending_tasks:
                    if task.status not in pending_status:
                        pending_status[task.status] = 0
                    pending_status[task.status] += 1
                self.logger.info(f"账号 {account_id} 待处理任务状态分布: {pending_status}")
            
            return pending_count > 0
    
    def clear_account_completed_tasks(self, account_id):
        """清除账号已完成的任务
        
        Args:
            account_id: 账号ID
            
        Returns:
            int: 清除的任务数量
        """
        with self.account_lock:
            if account_id not in self.account_task_map:
                return 0
                
            completed_tasks = []
            for trace_id in self.account_task_map[account_id]:
                if trace_id in self.task_map:
                    task = self.task_map[trace_id]
                    if task.status in ['completed', 'failed']:
                        completed_tasks.append(trace_id)
            
            # 清除已完成的任务
            for trace_id in completed_tasks:
                self.task_map.pop(trace_id, None)
                
            # 从账号任务映射中移除
            self.account_task_map[account_id] = [
                trace_id for trace_id in self.account_task_map[account_id]
                if trace_id not in completed_tasks
            ]
            
            return len(completed_tasks)
    
    def get_queue_sizes(self):
        """获取各队列大小
        
        Returns:
            dict: 队列大小信息
        """
        return {
            'upload': self.upload_queue.qsize(),
            'process': self.process_queue.qsize(),
            'publish': self.publish_queue.qsize(),
            'result': self.result_queue.qsize()
        }
    
    def get_stats(self):
        """获取统计信息
        
        Returns:
            dict: 统计信息
        """
        try:
            with self.counts_lock:
                return self.counts.copy()
        except Exception as e:
            # 输出完整堆栈跟踪
            logging.error(f"获取统计信息时出错: {str(e)}")
            traceback.print_exc()
            
            # 返回一个带有默认值的完整字典
            return {
                'upload_total': 0,
                'upload_success': 0,
                'upload_failed': 0,
                'process_total': 0,
                'process_success': 0,
                'process_failed': 0,
                'publish_total': 0,
                'publish_success': 0,
                'publish_failed': 0,
                'total': 0,
                'success': 0,
                'failed': 0
            }
    
    def reset_stats(self):
        """重置统计信息"""
        with self.counts_lock:
            for key in self.counts:
                self.counts[key] = 0 