#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import logging
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

class ThreadPool:
    """线程池管理器，负责管理上传、处理和发布线程"""
    
    def __init__(self, upload_workers=3, process_workers=3, publish_workers=3):
        """初始化线程池管理器
        
        Args:
            upload_workers: 上传线程数
            process_workers: 处理线程数
            publish_workers: 发布线程数
        """
        # 创建线程池
        self.upload_pool = ThreadPoolExecutor(max_workers=upload_workers, thread_name_prefix="Upload")
        self.process_pool = ThreadPoolExecutor(max_workers=process_workers, thread_name_prefix="Process")
        self.publish_pool = ThreadPoolExecutor(max_workers=publish_workers, thread_name_prefix="Publish")
        
        # 创建结果回调线程
        self.result_thread = None
        
        # 停止标志
        self._stop_event = threading.Event()
        
        # 活跃工作线程计数
        self.active_workers = {
            'upload': 0,
            'process': 0,
            'publish': 0
        }
        self.workers_lock = threading.RLock()
        
        # 日志记录器
        self.logger = logging.getLogger('ThreadPool')
    
    def submit_upload_task(self, task_fn, task):
        """提交上传任务到线程池
        
        Args:
            task_fn: 任务处理函数
            task: VideoTask对象
            
        Returns:
            Future: 线程池任务Future对象
        """
        try:
            with self.workers_lock:
                self.active_workers['upload'] += 1
                
            # 使用当前线程名作为线程ID
            thread_id = f"upload-{uuid.uuid4().hex[:8]}"
            task.thread_id = thread_id
            
            # 提交任务
            future = self.upload_pool.submit(self._wrap_task, task_fn, task, 'upload')
            return future
            
        except Exception as e:
            self.logger.error(f"提交上传任务时出错: {str(e)}")
            traceback.print_exc()
            with self.workers_lock:
                self.active_workers['upload'] -= 1
            return None
    
    def submit_process_task(self, task_fn, task):
        """提交处理任务到线程池
        
        Args:
            task_fn: 任务处理函数
            task: VideoTask对象
            
        Returns:
            Future: 线程池任务Future对象
        """
        try:
            with self.workers_lock:
                self.active_workers['process'] += 1
                
            # 使用当前线程名作为线程ID
            thread_id = f"process-{uuid.uuid4().hex[:8]}"
            task.thread_id = thread_id
            
            # 提交任务
            future = self.process_pool.submit(self._wrap_task, task_fn, task, 'process')
            return future
            
        except Exception as e:
            self.logger.error(f"提交处理任务时出错: {str(e)}")
            traceback.print_exc()
            with self.workers_lock:
                self.active_workers['process'] -= 1
            return None
    
    def submit_publish_task(self, task_fn, task):
        """提交发布任务到线程池
        
        Args:
            task_fn: 任务处理函数
            task: VideoTask对象
            
        Returns:
            Future: 线程池任务Future对象
        """
        try:
            with self.workers_lock:
                self.active_workers['publish'] += 1
                
            # 使用当前线程名作为线程ID
            thread_id = f"publish-{uuid.uuid4().hex[:8]}"
            task.thread_id = thread_id
            
            # 提交任务
            future = self.publish_pool.submit(self._wrap_task, task_fn, task, 'publish')
            return future
            
        except Exception as e:
            self.logger.error(f"提交发布任务时出错: {str(e)}")
            traceback.print_exc()
            with self.workers_lock:
                self.active_workers['publish'] -= 1
            return None
    
    def _wrap_task(self, task_fn, task, stage):
        """包装任务函数，用于统计线程信息
        
        Args:
            task_fn: 任务处理函数
            task: VideoTask对象
            stage: 任务阶段
            
        Returns:
            任务函数返回值
        """
        try:
            # 记录当前线程ID
            task.thread_id = threading.current_thread().name
            # 执行任务
            return task_fn(task)
        except Exception as e:
            self.logger.error(f"{stage}任务执行错误: {str(e)}")
            traceback.print_exc()
            return False
        finally:
            # 减少活跃工作线程计数
            with self.workers_lock:
                self.active_workers[stage] -= 1
    
    def start_result_thread(self, result_fn, stop_event=None):
        """启动结果处理线程
        
        Args:
            result_fn: 结果处理函数
            stop_event: 停止事件
            
        Returns:
            bool: 是否成功启动
        """
        if self.result_thread and self.result_thread.is_alive():
            return False
            
        self._stop_event = stop_event or threading.Event()
        
        # 创建线程
        self.result_thread = threading.Thread(
            target=self._result_worker,
            args=(result_fn,),
            name="ResultProcessor"
        )
        
        # 启动线程
        self.result_thread.daemon = True
        self.result_thread.start()
        
        return True
    
    def _result_worker(self, result_fn):
        """结果处理线程函数
        
        Args:
            result_fn: 结果处理函数
        """
        self.logger.info("结果处理线程已启动")
        
        while not self._stop_event.is_set():
            try:
                result_fn()
            except Exception as e:
                self.logger.error(f"结果处理线程执行错误: {str(e)}")
                traceback.print_exc()
            
            # 休眠一段时间
            time.sleep(0.2)
        
        self.logger.info("结果处理线程已停止")
    
    def stop(self):
        """停止线程池
        
        Returns:
            bool: 是否成功停止
        """
        try:
            # 设置停止标志
            self._stop_event.set()
            
            # 关闭所有线程池
            self.upload_pool.shutdown(wait=False)
            self.process_pool.shutdown(wait=False)
            self.publish_pool.shutdown(wait=False)
            
            self.logger.info("线程池已停止")
            return True
            
        except Exception as e:
            self.logger.error(f"停止线程池时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def wait(self, timeout=None):
        """等待所有任务完成
        
        Args:
            timeout: 超时时间，默认为None表示无限等待
            
        Returns:
            bool: 是否所有任务都已完成
        """
        try:
            # 关闭所有线程池，等待任务完成
            self.upload_pool.shutdown(wait=True, timeout=timeout)
            self.process_pool.shutdown(wait=True, timeout=timeout)
            self.publish_pool.shutdown(wait=True, timeout=timeout)
            
            # 等待结果线程结束
            if self.result_thread and self.result_thread.is_alive():
                self.result_thread.join(timeout)
            
            return True
            
        except Exception as e:
            self.logger.error(f"等待任务完成时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def get_active_workers(self):
        """获取活跃工作线程数
        
        Returns:
            dict: 活跃工作线程数
        """
        with self.workers_lock:
            return self.active_workers.copy()
    
    def resize_pools(self, upload_workers=None, process_workers=None, publish_workers=None):
        """调整线程池大小
        
        Args:
            upload_workers: 上传线程数
            process_workers: 处理线程数
            publish_workers: 发布线程数
            
        Returns:
            bool: 是否成功调整
        """
        try:
            if upload_workers is not None and upload_workers > 0:
                # 创建新的线程池
                new_upload_pool = ThreadPoolExecutor(max_workers=upload_workers, thread_name_prefix="Upload")
                # 关闭原线程池
                self.upload_pool.shutdown(wait=False)
                # 替换线程池
                self.upload_pool = new_upload_pool
            
            if process_workers is not None and process_workers > 0:
                # 创建新的线程池
                new_process_pool = ThreadPoolExecutor(max_workers=process_workers, thread_name_prefix="Process")
                # 关闭原线程池
                self.process_pool.shutdown(wait=False)
                # 替换线程池
                self.process_pool = new_process_pool
            
            if publish_workers is not None and publish_workers > 0:
                # 创建新的线程池
                new_publish_pool = ThreadPoolExecutor(max_workers=publish_workers, thread_name_prefix="Publish")
                # 关闭原线程池
                self.publish_pool.shutdown(wait=False)
                # 替换线程池
                self.publish_pool = new_publish_pool
            
            return True
            
        except Exception as e:
            self.logger.error(f"调整线程池大小时出错: {str(e)}")
            traceback.print_exc()
            return False 