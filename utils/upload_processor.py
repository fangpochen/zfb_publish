#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import logging
import threading
import traceback
import uuid
import json
from datetime import datetime

from utils.video_task import VideoTask
from utils.queue_manager import QueueManager
from utils.thread_pool import ThreadPool
from utils.upload_statistics import UploadStatistics


class UploadProcessor:
    """上传处理器，负责控制上传、处理和发布流程"""
    
    def __init__(self, api_client, upload_workers=3, process_workers=3, publish_workers=3,
                 db_path=None, signals=None):
        """初始化上传处理器
        
        Args:
            api_client: API客户端对象
            upload_workers: 上传线程数
            process_workers: 处理线程数
            publish_workers: 发布线程数
            db_path: 数据库路径，可选
            signals: 信号对象，用于通知UI更新
        """
        # API客户端
        self.api_client = api_client
        
        # 创建队列管理器
        self.queue_manager = QueueManager()
        
        # 创建线程池
        self.thread_pool = ThreadPool(
            upload_workers=upload_workers,
            process_workers=process_workers,
            publish_workers=publish_workers
        )
        
        # 创建统计管理器
        self.statistics = UploadStatistics(db_path)
        
        # 停止事件
        self._stop_event = threading.Event()
        
        # 账号锁定管理
        self.account_locks = {}
        self.account_lock = threading.RLock()
        
        # 当前使用的账号和cookies
        self.current_account = None
        self.current_cookies = None
        self.account_cookies_lock = threading.RLock()
        
        # 上传统计(仅内存统计，重启后重置)
        self.success_count = 0
        self.failed_count = 0
        self.stats_lock = threading.RLock()
        
        # 信号对象
        self.signals = signals
        
        # 日志记录器
        self.logger = logging.getLogger('UploadProcessor')
        
        # 是否已启动
        self._is_running = False
    
    def start(self):
        """启动上传处理器
        
        Returns:
            bool: 是否成功启动
        """
        if self._is_running:
            return False
        
        try:
            # 重置停止事件
            self._stop_event.clear()
            
            # 启动结果线程
            self.thread_pool.start_result_thread(self._process_results, self._stop_event)
            
            # 启动主循环线程
            self._main_thread = threading.Thread(
                target=self._main_loop,
                name="MainProcessor"
            )
            self._main_thread.daemon = True
            self._main_thread.start()
            
            self._is_running = True
            self.logger.info("上传处理器已启动")
            return True
            
        except Exception as e:
            self.logger.error(f"启动上传处理器时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def stop(self):
        """停止上传处理器
        
        Returns:
            bool: 是否成功停止
        """
        if not self._is_running:
            return False
        
        try:
            # 设置停止事件
            self._stop_event.set()
            
            # 停止线程池
            self.thread_pool.stop()
            
            # 等待主线程结束
            if self._main_thread and self._main_thread.is_alive():
                self._main_thread.join(timeout=3)
            
            self._is_running = False
            self.logger.info("上传处理器已停止")
            return True
            
        except Exception as e:
            self.logger.error(f"停止上传处理器时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def stop_task(self, trace_id):
        """停止单个任务
        
        Args:
            trace_id: 任务追踪ID
            
        Returns:
            bool: 是否成功停止
        """
        try:
            # 查找任务
            with self.queue_manager.account_lock:
                if trace_id not in self.queue_manager.task_map:
                    self.logger.warning(f"找不到要停止的任务: {trace_id}")
                    return False
                
                task = self.queue_manager.task_map[trace_id]
            
            # 取消任务
            if task.cancel():
                self.logger.info(f"已取消任务: {trace_id} - {task.file_name}")
                
                # 添加到结果队列，以便更新统计数据
                task.update_status(VideoTask.STATUS_CANCELLED, error="任务被用户取消")
                self.queue_manager.add_result(task, success=False, stage=self._get_current_stage(task))
                
                # 保存任务记录
                self.statistics.save_upload_record(task)
                
                return True
            else:
                self.logger.warning(f"无法取消任务，任务可能已完成或失败: {trace_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"停止任务时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def stop_account_tasks(self, account_id):
        """停止账号的所有任务
        
        Args:
            account_id: 账号ID
            
        Returns:
            int: 成功停止的任务数量
        """
        try:
            # 找到账号的所有任务
            with self.queue_manager.account_lock:
                if account_id not in self.queue_manager.account_task_map:
                    self.logger.warning(f"找不到账号的任务: {account_id}")
                    return 0
                
                task_ids = self.queue_manager.account_task_map[account_id].copy()
            
            # 取消所有任务
            stopped_count = 0
            for trace_id in task_ids:
                if self.stop_task(trace_id):
                    stopped_count += 1
            
            self.logger.info(f"已停止账号 {account_id} 的 {stopped_count}/{len(task_ids)} 个任务")
            return stopped_count
            
        except Exception as e:
            self.logger.error(f"停止账号任务时出错: {str(e)}")
            traceback.print_exc()
            return 0
    
    def stop_all_tasks(self):
        """停止所有任务
        
        Returns:
            int: 成功停止的任务数量
        """
        try:
            # 获取所有任务
            with self.queue_manager.account_lock:
                task_ids = list(self.queue_manager.task_map.keys())
            
            # 取消所有任务
            stopped_count = 0
            for trace_id in task_ids:
                if self.stop_task(trace_id):
                    stopped_count += 1
            
            self.logger.info(f"已停止所有任务: {stopped_count}/{len(task_ids)}")
            return stopped_count
            
        except Exception as e:
            self.logger.error(f"停止所有任务时出错: {str(e)}")
            traceback.print_exc()
            return 0
    
    def _get_current_stage(self, task):
        """获取当前任务阶段
        
        Args:
            task: VideoTask对象
            
        Returns:
            str: 当前阶段 (upload, process, publish)
        """
        if task.status in [VideoTask.STATUS_UPLOADING, VideoTask.STATUS_UPLOAD_FAILED]:
            return 'upload'
        elif task.status in [VideoTask.STATUS_PROCESSING, VideoTask.STATUS_PROCESS_FAILED]:
            return 'process'
        elif task.status in [VideoTask.STATUS_PUBLISHING, VideoTask.STATUS_PUBLISH_FAILED]:
            return 'publish'
        else:
            return 'unknown'
    
    def add_task(self, account, file_path, cover_path=None, use_random_cover=False, 
                topics=None, schedule_time=None, manual_title=None, manual_desc=None, is_batch=False, art_text_settings=None):
        """添加上传任务
        
        Args:
            account: 账号信息
            file_path: 视频文件路径
            cover_path: 封面图片路径，可选
            use_random_cover: 是否使用随机封面
            topics: 话题列表
            schedule_time: 定时发布时间
            manual_title: 手动设置的标题
            manual_desc: 手动设置的描述
            is_batch: 是否批量任务
            art_text_settings: 艺术字设置，包含文本、样式、颜色等
            
        Returns:
            VideoTask: 创建的任务对象，如果失败则返回None
        """
        try:
            # 检查参数
            if not account:
                self.logger.error("缺少账号信息，无法添加任务")
                return None
            
            # 获取账号ID
            appid = account.get('appid')
            if not appid:
                self.logger.error(f"获取账号ID失败，无法添加任务: {account}")
                return None
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.logger.error(f"文件不存在: {file_path}")
                return None
            
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                self.logger.error(f"文件大小为0: {file_path}")
                return None
            
            # 创建任务
            task = VideoTask(
                account=account,
                file_path=file_path,
                cover_path=cover_path,
                use_random_cover=use_random_cover,
                topics=topics,
                schedule_time=schedule_time,
                manual_title=manual_title,
                manual_desc=manual_desc,
                is_batch=is_batch,
                art_text_settings=art_text_settings
            )
            
            self.logger.info(f"添加任务 {task.trace_id}: {os.path.basename(file_path)}")
            
            # 添加到队列管理器
            self.queue_manager.add_upload_task(task)
            
            # 返回任务对象
            return task
            
        except Exception as e:
            self.logger.error(f"添加任务时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def _main_loop(self):
        """主循环，处理队列和任务分发"""
        self.logger.info("上传处理器主循环已启动")
        
        while not self._stop_event.is_set():
            try:
                # 处理上传队列
                try:
                    self._process_upload_queue()
                except Exception as e:
                    self.logger.error(f"处理上传队列时出错: {str(e)}")
                    traceback.print_exc()
                
                # 处理处理队列
                try:
                    self._process_process_queue()
                except Exception as e:
                    self.logger.error(f"处理处理队列时出错: {str(e)}")
                    traceback.print_exc()
                
                # 处理发布队列
                try:
                    self._process_publish_queue()
                except Exception as e:
                    self.logger.error(f"处理发布队列时出错: {str(e)}")
                    traceback.print_exc()
                
                # 休眠一段时间
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"主循环执行错误: {str(e)}")
                traceback.print_exc()
                time.sleep(1)
        
        self.logger.info("上传处理器主循环已停止")
    
    def _process_upload_queue(self):
        """处理上传队列"""
        try:
            # 获取活跃工作线程数
            active_workers = self.thread_pool.get_active_workers()
            
            # 如果上传线程已满，直接返回
            if active_workers['upload'] >= 3:  # 最大上传线程数
                return
            
            # 从队列获取任务
            task = self.queue_manager.get_upload_task(block=False)
            if not task:
                return
            
            # 检查任务状态
            if task.is_cancelled:
                self.logger.info(f"任务已取消，跳过上传: {task.trace_id} - {task.file_name}")
                self.queue_manager.mark_upload_done()
                return
                
            # 检查账号是否被锁定
            if not self._check_account_lock(task.appid):
                self.logger.info(f"账号 {task.appid} 被锁定，跳过上传: {task.trace_id} - {task.file_name}")
                # 重新放回队列
                self.queue_manager.add_upload_task(task)
                self.queue_manager.mark_upload_done()
                return
                
            # 直接将账号的cookies设置到任务中
            cookies = task.account.get('cookies')
            if cookies:
                task.cookies = cookies
            else:
                self.logger.error(f"账号 {task.appid} 没有提供cookies，跳过任务: {task.trace_id}")
                # 更新任务状态
                task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=f"账号没有提供cookies", stage="upload")
                # 添加到结果队列
                self.queue_manager.add_result(task, success=False, stage="upload")
                # 标记任务完成
                self.queue_manager.mark_upload_done()
                return
            
            # 提交到线程池
            future = self.thread_pool.submit_upload_task(self._upload_worker, task)
            if not future:
                self.logger.error(f"提交上传任务失败: {task.trace_id} - {task.file_name}")
                # 更新任务状态
                task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error="提交上传任务失败", stage="upload")
                # 添加到结果队列
                self.queue_manager.add_result(task, success=False, stage="upload")
            
            # 标记任务完成
            self.queue_manager.mark_upload_done()
        except Exception as e:
            self.logger.error(f"处理上传队列时出错: {str(e)}")
            traceback.print_exc()
            # 如果有异常，确保队列不会阻塞
            try:
                self.queue_manager.mark_upload_done()
            except:
                pass
    
    def _process_process_queue(self):
        """处理处理队列"""
        try:
            # 获取活跃工作线程数
            active_workers = self.thread_pool.get_active_workers()
            
            # 如果处理线程已满，直接返回
            if active_workers['process'] >= 3:  # 最大处理线程数
                return
            
            # 从队列获取任务
            task = self.queue_manager.get_process_task(block=False)
            if not task:
                return
            
            # 检查任务状态
            if task.is_cancelled:
                self.logger.info(f"任务已取消，跳过处理: {task.trace_id} - {task.file_name}")
                self.queue_manager.mark_process_done()
                return
                
            # 检查账号是否被锁定
            if not self._check_account_lock(task.appid):
                # 重新放回队列
                self.queue_manager.add_process_task(task)
                self.queue_manager.mark_process_done()
                return
            
            # 提交到线程池
            future = self.thread_pool.submit_process_task(self._process_worker, task)
            if not future:
                self.logger.error(f"提交处理任务失败: {task.trace_id} - {task.file_name}")
                # 更新任务状态
                task.update_status(VideoTask.STATUS_PROCESS_FAILED, error="提交处理任务失败", stage="process")
                # 添加到结果队列
                self.queue_manager.add_result(task, success=False, stage="process")
            
            # 标记任务完成
            self.queue_manager.mark_process_done()
        except Exception as e:
            self.logger.error(f"处理处理队列时出错: {str(e)}")
            traceback.print_exc()
            # 如果有异常，确保队列不会阻塞
            try:
                self.queue_manager.mark_process_done()
            except:
                pass
    
    def _process_publish_queue(self):
        """处理发布队列"""
        try:
            # 获取活跃工作线程数
            active_workers = self.thread_pool.get_active_workers()
            
            # 如果发布线程已满，直接返回
            if active_workers['publish'] >= 3:  # 最大发布线程数
                return
            
            # 从队列获取任务
            task = self.queue_manager.get_publish_task(block=False)
            if not task:
                return
            
            # 检查任务状态
            if task.is_cancelled:
                self.logger.info(f"任务已取消，跳过发布: {task.trace_id} - {task.file_name}")
                self.queue_manager.mark_publish_done()
                return
                
            # 检查账号是否被锁定
            if not self._check_account_lock(task.appid):
                # 重新放回队列
                self.queue_manager.add_publish_task(task)
                self.queue_manager.mark_publish_done()
                return
            
            # 提交到线程池
            future = self.thread_pool.submit_publish_task(self._publish_worker, task)
            if not future:
                self.logger.error(f"提交发布任务失败: {task.trace_id} - {task.file_name}")
                # 更新任务状态
                task.update_status(VideoTask.STATUS_PUBLISH_FAILED, error="提交发布任务失败", stage="publish")
                # 添加到结果队列
                self.queue_manager.add_result(task, success=False, stage="publish")
            
            # 标记任务完成
            self.queue_manager.mark_publish_done()
        except Exception as e:
            self.logger.error(f"处理发布队列时出错: {str(e)}")
            traceback.print_exc()
            # 如果有异常，确保队列不会阻塞
            try:
                self.queue_manager.mark_publish_done()
            except:
                pass
    
    def _process_results(self):
        """处理结果队列"""
        # 从结果队列获取任务
        task = self.queue_manager.get_result(block=False)
        if not task:
            return
        
        try:
            # 更新统计数据
            account_id = task.appid
            task_status = task.status
            
            self.logger.info(f"处理任务结果: {task.trace_id}, 状态: {task_status}, 账号: {account_id}")
            
            if task.status == VideoTask.STATUS_COMPLETED:
                # 成功完成
                self.statistics.update_account_stat(account_id, success=1)
                
                # 更新内存统计
                with self.stats_lock:
                    self.success_count += 1
                    self.logger.info(f"更新成功计数: {self.success_count}")
                
                # 发送信号
                if self.signals:
                    try:
                        self.signals.upload_success.emit(task.trace_id, task.file_path, task.video_url)
                    except Exception as e:
                        self.logger.warning(f"发送成功信号失败，UI对象可能已关闭: {str(e)}")
                
            elif task.status in [VideoTask.STATUS_FAILED, VideoTask.STATUS_UPLOAD_FAILED, 
                                VideoTask.STATUS_PROCESS_FAILED, VideoTask.STATUS_PUBLISH_FAILED]:
                # 任务失败
                self.statistics.update_account_stat(account_id, failed=1)
                
                # 更新内存统计
                with self.stats_lock:
                    self.failed_count += 1
                    self.logger.info(f"更新失败计数: {self.failed_count}")
                
                # 发送信号
                if self.signals:
                    try:
                        self.signals.upload_failed.emit(task.trace_id, task.file_path, task.error)
                    except Exception as e:
                        self.logger.warning(f"发送失败信号失败，UI对象可能已关闭: {str(e)}")
            
            
            # 输出当前统计数据到日志
            with self.stats_lock:
                pending_count = self.queue_manager.get_queue_sizes()['upload'] + self.queue_manager.get_queue_sizes()['process'] + self.queue_manager.get_queue_sizes()['publish']
                self.logger.info(f"上传统计: 成功 {self.success_count}, 失败 {self.failed_count}, 待处理 {pending_count}")
            
            # 打印详细的队列情况
            with self.queue_manager.account_lock:
                if account_id in self.queue_manager.account_task_map:
                    task_count = len(self.queue_manager.account_task_map[account_id])
                    task_status = {}
                    for trace_id in self.queue_manager.account_task_map[account_id]:
                        if trace_id in self.queue_manager.task_map:
                            task_obj = self.queue_manager.task_map[trace_id]
                            status = task_obj.status
                            if status not in task_status:
                                task_status[status] = 0
                            task_status[status] += 1
                    
                    self.logger.info(f"账号 {account_id} 的任务情况: 总数 {task_count}, 状态分布 {task_status}")
                    
                    # 打印队列大小
                    queue_sizes = self.queue_manager.get_queue_sizes()
                    active_workers = self.thread_pool.get_active_workers()
                    self.logger.info(f"队列情况: 上传队列 {queue_sizes['upload']}, 处理队列 {queue_sizes['process']}, 发布队列 {queue_sizes['publish']}")
                    self.logger.info(f"活跃线程: 上传线程 {active_workers['upload']}, 处理线程 {active_workers['process']}, 发布线程 {active_workers['publish']}")
            
            # 检查账号是否还有待处理任务
            if not self.queue_manager.is_account_has_pending_tasks(account_id):
                # 解锁账号
                self._unlock_account(account_id)
                
                # 清理已完成的任务
                self.queue_manager.clear_account_completed_tasks(account_id)
                
                # 发送账号完成信号
                if self.signals:
                    try:
                        self.signals.account_finished.emit(account_id)
                        # 触发UI更新统计数据
                        self.signals.stats_updated.emit()
                        self.logger.info(f"已发送账号完成和统计更新信号, 账号: {account_id}")
                    except Exception as e:
                        self.logger.warning(f"发送账号完成信号失败，UI对象可能已关闭: {str(e)}")
            
            # 无论如何都需要更新统计数据
            if self.signals:
                try:
                    # 在每个任务处理完毕后发送更新统计数据的信号
                    self.signals.stats_updated.emit()
                    self.logger.info("已发送统计更新信号")
                except Exception as e:
                    self.logger.warning(f"发送统计更新信号失败: {str(e)}")
            
            # 标记结果处理完成
            self.queue_manager.mark_result_done()
            
        except Exception as e:
            self.logger.error(f"处理结果时出错: {str(e)}")
            traceback.print_exc()
            
            # 标记结果处理完成
            self.queue_manager.mark_result_done()
    
    def _upload_worker(self, task):
        """上传线程工作函数
        
        Args:
            task: VideoTask对象
            
        Returns:
            bool: 是否成功
        """
        try:
            # 检查任务状态
            if task.is_cancelled:
                self.logger.info(f"任务已取消，跳过上传: {task.trace_id} - {task.file_name}")
                return False
                
            # 更新任务状态
            task.update_status(VideoTask.STATUS_UPLOADING, stage="upload")
            self.logger.info(f"开始上传任务 {task.trace_id}: {task.file_name}")
            
            # 文件校验
            try:
                # 检查文件是否存在
                if not os.path.exists(task.file_path):
                    error_msg = f"文件不存在: {task.file_path}"
                    self.logger.error(error_msg)
                    task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
                    return False
                    
                # 检查文件大小
                file_size = os.path.getsize(task.file_path)
                if file_size <= 0:
                    error_msg = f"文件大小为0或无效: {task.file_path}"
                    self.logger.error(error_msg)
                    task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
                    return False
                
                self.logger.info(f"文件大小: {file_size} 字节")
            except Exception as e:
                error_msg = f"文件验证失败: {str(e)}"
                self.logger.error(error_msg)
                traceback.print_exc()
                task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
                return False
            
            # 获取MT令牌
            try:
                if not task.mt:
                    task.mt = self.api_client.get_mt(task.cookies)
                    if not task.mt:
                        error_msg = "获取MT令牌失败"
                        self.logger.error(error_msg)
                        task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
                        return False
            except Exception as e:
                error_msg = f"获取MT令牌时出错: {str(e)}"
                self.logger.error(error_msg)
                traceback.print_exc()
                task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
                return False
            
            # 发送进度更新
            self._update_upload_progress(task, 5)
            
            # 上传视频
            try:
                if file_size < 4 * 1024 * 1024:  # 小于4MB
                    # 使用普通上传
                    task.file_id = self.api_client.upload_4m_video(task.mt, task.file_path)
                else:
                    # 使用分片上传
                    upload_result = self.api_client.upload_large_video(task.mt, task.file_path, file_size)
                    if isinstance(upload_result, tuple) and len(upload_result) == 2:
                        task.file_id, task.file_name = upload_result
                    else:
                        task.file_id = upload_result
                
                # 检查上传结果
                if not task.file_id:
                    error_msg = "上传视频失败，未获取到文件ID"
                    self.logger.error(error_msg)
                    task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
                    return False
            except Exception as e:
                error_msg = f"上传视频时出错: {str(e)}"
                self.logger.error(error_msg)
                traceback.print_exc()
                task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
                return False
                
            # 发送进度更新
            self._update_upload_progress(task, 50)
            
            # 上传封面
            try:
                if not task.use_random_cover and task.cover_path and os.path.exists(task.cover_path):
                    # 使用自定义封面
                    if task.art_text_settings and task.art_text_settings.get("enabled", False):
                        # 创建带艺术字的封面
                        temp_cover_path = self._create_art_text_cover(task)
                        if temp_cover_path:
                            task.cover_url = self.api_client.upload_pic(task.cookies, temp_cover_path)
                            # 清理临时文件
                            try:
                                os.remove(temp_cover_path)
                            except Exception as e:
                                self.logger.warning(f"删除临时封面文件失败: {str(e)}")
                        else:
                            # 如果创建失败，使用原始封面
                            task.cover_url = self.api_client.upload_pic(task.cookies, task.cover_path)
                    else:
                        # 使用原始封面
                        task.cover_url = self.api_client.upload_pic(task.cookies, task.cover_path)
                else:
                    # 从视频中创建封面
                    temp_cover_path = self._create_cover_from_video(task.file_path)
                    
                    if temp_cover_path and os.path.exists(temp_cover_path):
                        # 如果需要添加艺术字
                        if task.art_text_settings and task.art_text_settings.get("enabled", False):
                            # 创建带艺术字的封面
                            art_text_cover_path = self._create_art_text_cover(task, temp_cover_path)
                            if art_text_cover_path:
                                task.cover_url = self.api_client.upload_pic(task.cookies, art_text_cover_path)
                                # 清理临时文件
                                try:
                                    if art_text_cover_path != temp_cover_path:  # 避免重复删除
                                        os.remove(art_text_cover_path)
                                except Exception as e:
                                    self.logger.warning(f"删除临时艺术字封面文件失败: {str(e)}")
                            else:
                                # 如果创建失败，使用生成的原始封面
                                task.cover_url = self.api_client.upload_pic(task.cookies, temp_cover_path)
                        else:
                            # 使用生成的原始封面
                            task.cover_url = self.api_client.upload_pic(task.cookies, temp_cover_path)
                        
                        # 清理临时文件
                        try:
                            os.remove(temp_cover_path)
                        except Exception as e:
                            self.logger.warning(f"删除临时封面文件失败: {str(e)}")
            except Exception as e:
                self.logger.warning(f"处理封面时出错: {str(e)}")
                traceback.print_exc()
                # 不中断上传，继续处理
            
            # 发送进度更新
            self._update_upload_progress(task, 90)
            
            # 上传完成
            self.logger.info(f"视频上传完成: {task.file_name}, fileId: {task.file_id}")
            task.update_status(VideoTask.STATUS_COMPLETED, stage="upload")
            
            # 添加到处理队列
            self.queue_manager.add_process_task(task)
            
            return True
            
        except Exception as e:
            # 记录错误
            error_msg = f"上传过程出错: {str(e)}"
            self.logger.error(error_msg)
            traceback.print_exc()
            task.update_status(VideoTask.STATUS_UPLOAD_FAILED, error=error_msg, stage="upload")
            
            # 判断是否需要重试
            if task.should_retry("upload"):
                task.increment_retry("upload")
                self.logger.info(f"准备重试上传任务 ({task.retry_count['upload']}/{task.max_retries['upload']}): {task.file_name}")
                self.queue_manager.add_upload_task(task)
                return False
            else:
                # 达到最大重试次数
                task.update_status(VideoTask.STATUS_FAILED, error=f"上传失败，已重试{task.retry_count['upload']}次", stage="upload")
                return False
    
    def _create_cover_from_video(self, video_path, output_path=None):
        """从视频中创建封面图片
        
        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径，可选
            
        Returns:
            str: 创建的封面图片路径，失败则返回None
        """
        try:
            import cv2
            from PIL import Image
            import tempfile
            
            video_path = video_path.replace('\\', '/')
            
            # 检查是否已存在同名jpg文件
            default_jpg = os.path.splitext(video_path)[0] + '.jpg'
            if os.path.exists(default_jpg):
                self.logger.info(f"使用已存在的封面图: {default_jpg}")
                return default_jpg

            if not os.path.exists(video_path):
                self.logger.info(f"视频文件不存在: {video_path}")
                return None

            if output_path is None:
                # 创建临时文件
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                output_path = temp_file.name
                temp_file.close()

            output_path = output_path.replace('\\', '/')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 打开视频文件
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.logger.info(f"无法打开视频文件: {video_path}")
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
                    self.logger.info(f"无法读取指定帧: {video_path}")
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
                resize_img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # 居中裁剪
                left = (new_width - target_width) // 2
                top = (new_height - target_height) // 2
                right = left + target_width
                bottom = top + target_height
                
                # 裁剪到目标尺寸
                final_img = resize_img.crop((left, top, right, bottom))
                
                # 保存图片
                final_img.save(output_path, "JPEG", quality=95)
                self.logger.info(f"成功生成封面图: {output_path}")

                # 验证文件是否成功生成
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return output_path
                return None

            finally:
                cap.release()

        except Exception as e:
            self.logger.error(f"创建封面图过程发生异常: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def _create_art_text_cover(self, task, cover_path=None):
        """创建带艺术字的封面图片
        
        Args:
            task: VideoTask对象
            cover_path: 封面图片路径，如果为None则使用task.cover_path
            
        Returns:
            str: 创建的封面图片路径，失败则返回None
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            import tempfile
            import os.path
            
            # 使用提供的封面路径或任务中的封面路径
            image_path = cover_path or task.cover_path
            if not image_path or not os.path.exists(image_path):
                self.logger.warning(f"封面图片不存在，无法添加艺术字: {image_path}")
                return None
                
            # 检查设置是否有效
            if not task.art_text_settings or not task.art_text_settings.get("text"):
                self.logger.warning(f"艺术字设置无效，使用原始封面: {task.trace_id}")
                return image_path
                
            # 获取设置
            text = task.art_text_settings.get("text", "")
            style = task.art_text_settings.get("style", "标准")
            font_size = task.art_text_settings.get("font_size", 36)
            color_name = task.art_text_settings.get("color", "白色")
            position = task.art_text_settings.get("position", "底部居中")
            
            # 颜色映射
            color_map = {
                "白色": (255, 255, 255),
                "黑色": (0, 0, 0),
                "红色": (255, 0, 0),
                "蓝色": (0, 0, 255),
                "绿色": (0, 255, 0),
                "黄色": (255, 255, 0),
                "粉色": (255, 192, 203),
                "紫色": (128, 0, 128),
                "橙色": (255, 165, 0)
            }
            text_color = color_map.get(color_name, (255, 255, 255))
            
            # 打开原始图像
            image = Image.open(image_path)
            draw = ImageDraw.Draw(image)
            
            # 字体映射
            font_map = {
                "标准": "arial.ttf",
                "艺术风格一": "arialbd.ttf",  # 加粗Arial
                "艺术风格二": "timesi.ttf",   # 斜体Times
                "霓虹灯": "impact.ttf",      # Impact
                "复古": "georgia.ttf",       # Georgia
                "水墨风": "simkai.ttf",      # 楷体
                "书法": "simli.ttf",         # 隶书
                "华丽花体": "stxingka.ttf"   # 行楷
            }
            
            # 尝试加载字体
            font_file = font_map.get(style, "arial.ttf")
            try:
                font = ImageFont.truetype(font_file, font_size)
            except:
                # 如果字体加载失败，使用默认字体
                self.logger.warning(f"无法加载字体 {font_file}，使用默认字体")
                font = ImageFont.load_default()
            
            # 获取文本尺寸
            text_width, text_height = draw.textsize(text, font=font)
            
            # 图像尺寸
            img_width, img_height = image.size
            
            # 计算文本位置
            if position == "顶部居中":
                text_position = ((img_width - text_width) // 2, 10)
            elif position == "底部居中":
                text_position = ((img_width - text_width) // 2, img_height - text_height - 10)
            elif position == "左上":
                text_position = (10, 10)
            elif position == "右上":
                text_position = (img_width - text_width - 10, 10)
            elif position == "左下":
                text_position = (10, img_height - text_height - 10)
            elif position == "右下":
                text_position = (img_width - text_width - 10, img_height - text_height - 10)
            elif position == "居中":
                text_position = ((img_width - text_width) // 2, (img_height - text_height) // 2)
            else:
                # 默认底部居中
                text_position = ((img_width - text_width) // 2, img_height - text_height - 10)
                
            # 特殊效果处理
            if style == "霓虹灯":
                # 添加发光边缘
                shadow_color = (*text_color, 128)  # 半透明颜色
                draw.text((text_position[0]-1, text_position[1]-1), text, font=font, fill=shadow_color)
                draw.text((text_position[0]+1, text_position[1]-1), text, font=font, fill=shadow_color)
                draw.text((text_position[0]-1, text_position[1]+1), text, font=font, fill=shadow_color)
                draw.text((text_position[0]+1, text_position[1]+1), text, font=font, fill=shadow_color)
            
            # 绘制文本
            draw.text(text_position, text, font=font, fill=text_color)
            
            # 保存到临时文件
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.close()
            image.save(temp_file.name, quality=95)
            
            self.logger.info(f"成功生成带艺术字的封面: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            self.logger.error(f"生成艺术字封面时出错: {str(e)}")
            traceback.print_exc()
            # 如果出错，返回原始封面路径
            return cover_path
    
    def _process_worker(self, task):
        """处理工作线程函数
        
        Args:
            task: VideoTask对象
            
        Returns:
            bool: 是否成功处理
        """
        try:
            # 检查任务是否被取消
            if task.is_cancelled:
                self.logger.info(f"任务已被取消，跳过处理: {task.trace_id} - {task.file_name}")
                return False
            
            # 更新任务状态
            task.update_status(VideoTask.STATUS_PROCESSING, stage='process')
            
            # 如果需要，切换到指定账号
            if not self._switch_account_if_needed(task):
                error_msg = f"切换到账号失败: {task.appid}"
                self.logger.error(error_msg)
                task.update_status(VideoTask.STATUS_PROCESS_FAILED, error=error_msg, stage='process')
                task.update_error_detail(traceback.format_exc())
                self.queue_manager.add_result(task, success=False, stage='process')
                return False
            
            # 更新进度
            task.update_progress('process', 10)
            self._send_progress_signal(task)
            
            # 调用API获取视频URL
            video_url = self.api_client.get_video_url(
                file_id=task.file_id,
                cookies=task.cookies,
                appid=task.appid,
                mt=task.mt
            )
            
            if not video_url:
                # 尝试轮询获取视频URL
                max_retries = 10
                retry_interval = 3  # 秒
                
                for i in range(max_retries):
                    # 更新进度
                    progress = 10 + (i + 1) * 80 / max_retries
                    task.update_progress('process', progress)
                    self._send_progress_signal(task)
                    
                    # 等待一段时间
                    time.sleep(retry_interval)
                    
                    # 再次尝试获取视频URL
                    video_url = self.api_client.get_video_url(
                        file_id=task.file_id,
                        cookies=task.cookies,
                        appid=task.appid,
                        mt=task.mt
                    )
                    
                    if video_url:
                        break
            
            if not video_url:
                error_msg = "处理视频失败，未获取到有效的视频URL"
                task.update_status(VideoTask.STATUS_PROCESS_FAILED, error=error_msg, stage='process')
                task.update_error_detail(traceback.format_exc())
                self.queue_manager.add_result(task, success=False, stage='process')
                return False
            
            # 更新任务信息
            task.video_url = video_url
            
            # 更新任务进度
            task.update_progress('process', 100)
            self._send_progress_signal(task)
            
            # 将任务添加到发布队列
            self.queue_manager.add_publish_task(task)
            
            # 添加结果
            self.queue_manager.add_result(task, success=True, stage='process')
            
            return True
            
        except Exception as e:
            error_msg = f"处理视频时出错: {str(e)}"
            self.logger.error(error_msg)
            traceback.print_exc()
            
            # 判断是否需要重试
            if task.should_retry('process'):
                # 增加重试次数
                retry_count = task.increment_retry('process')
                
                # 重新添加到处理队列
                self.queue_manager.add_process_task(task)
                
                # 更新状态
                task.update_status(
                    VideoTask.STATUS_UPLOADING, 
                    error=f"处理失败，准备第{retry_count}次重试"
                )
                
            else:
                # 更新状态为失败
                task.update_status(
                    VideoTask.STATUS_PROCESS_FAILED,
                    error=error_msg,
                    stage='process'
                )
                task.update_error_detail(traceback.format_exc())
                
                # 添加结果
                self.queue_manager.add_result(task, success=False, stage='process')
            
            return False
    
    def _publish_worker(self, task):
        """发布工作线程函数
        
        Args:
            task: VideoTask对象
            
        Returns:
            bool: 是否成功发布
        """
        try:
            # 检查任务是否被取消
            if task.is_cancelled:
                self.logger.info(f"任务已被取消，跳过发布: {task.trace_id} - {task.file_name}")
                return False
            
            # 更新任务状态
            task.update_status(VideoTask.STATUS_PUBLISHING, stage='publish')
            
            # 如果需要，切换到指定账号
            if not self._switch_account_if_needed(task):
                error_msg = f"切换到账号失败: {task.appid}"
                self.logger.error(error_msg)
                task.update_status(VideoTask.STATUS_PUBLISH_FAILED, error=error_msg, stage='publish')
                task.update_error_detail(traceback.format_exc())
                self.queue_manager.add_result(task, success=False, stage='publish')
                return False
            
            # 更新进度
            task.update_progress('publish', 10)
            self._send_progress_signal(task)
            
            # 准备话题
            topics = task.topics
            self.logger.info(f"原始话题数据: {topics}")
            
            # 使用修改后的format_topic_for_publish方法处理话题
            formatted_topics = self.api_client.format_topic_for_publish(topics)
            self.logger.info(f"格式化后的话题数据: {formatted_topics}")
            
            # 上传封面图片（如果有）
            cover_id = None
            if task.use_random_cover:
                # 使用随机封面
                pass
            elif task.cover_path and os.path.exists(task.cover_path):
                # 更新进度
                task.update_progress('publish', 30)
                self._send_progress_signal(task)
                
                # 上传自定义封面
                cover_id = self.api_client.upload_cover(
                    cookies=task.cookies,
                    cover_path=task.cover_path,
                    appid=task.appid
                )
                
                if not cover_id:
                    self.logger.warning(f"上传封面失败，将使用默认封面: {task.cover_path}")
            
            # 更新任务封面ID
            task.cover_id = cover_id
            
            # 更新进度
            task.update_progress('publish', 60)
            self._send_progress_signal(task)
            
            # 准备发布参数
            publish_params = {
                'loginPublicId': task.appid,
                'videoId': task.file_id,
                'videoFile': task.file_path,
                'videoFileName': task.file_name,
                'extProperty': task.cover_url if hasattr(task, 'cover_url') and task.cover_url else {},  # task.cover_url已经是包含djangoId、filePath等的字典
                'mt': task.mt,
                'scheduleTime': task.schedule_time,
                'title': task.manual_title or os.path.splitext(task.file_name)[0],
                'cookies': task.cookies,
                'topics': formatted_topics
            }
            
            # 移除不需要的参数
            if cover_id:
                # 这里不需要单独设置cover_id，因为extProperty已经包含封面信息
                pass
            
            # 调用API发布视频
            publish_result = self.api_client.publish(**publish_params)
            
            if not publish_result:
                error_msg = "发布视频失败，未获取到有效的发布结果"
                task.update_status(VideoTask.STATUS_PUBLISH_FAILED, error=error_msg, stage='publish')
                task.update_error_detail(traceback.format_exc())
                self.queue_manager.add_result(task, success=False, stage='publish')
                return False
            
            # 更新任务信息
            task.publish_id = publish_result.get('id')
            
            # 更新任务状态
            task.update_status(VideoTask.STATUS_COMPLETED, stage='publish')
            
            # 更新任务进度
            task.update_progress('publish', 100)
            self._send_progress_signal(task)
            
            # 添加结果
            self.queue_manager.add_result(task, success=True, stage='publish')
            
            return True
            
        except Exception as e:
            error_msg = f"发布视频时出错: {str(e)}"
            self.logger.error(error_msg)
            traceback.print_exc()
            
            # 判断是否需要重试
            if task.should_retry('publish'):
                # 增加重试次数
                retry_count = task.increment_retry('publish')
                
                # 重新添加到发布队列
                self.queue_manager.add_publish_task(task)
                
                # 更新状态
                task.update_status(
                    VideoTask.STATUS_PROCESSING, 
                    error=f"发布失败，准备第{retry_count}次重试"
                )
                
            else:
                # 更新状态为失败
                task.update_status(
                    VideoTask.STATUS_PUBLISH_FAILED,
                    error=error_msg,
                    stage='publish'
                )
                task.update_error_detail(traceback.format_exc())
                
                # 添加结果
                self.queue_manager.add_result(task, success=False, stage='publish')
            
            return False
    
    def _update_upload_progress(self, task, progress):
        """更新上传进度
        
        Args:
            task: VideoTask对象
            progress: 进度值(0-100)
        """
        # 更新任务进度
        task.update_progress('upload', progress)
        
        # 发送进度信号
        self._send_progress_signal(task)
    
    def _send_progress_signal(self, task):
        """发送进度信号
        
        Args:
            task: VideoTask对象
        """
        if self.signals:
            try:
                self.signals.upload_progress.emit(
                    task.trace_id,
                    task.file_path,
                    task.progress['total'],
                    task.status
                )
            except Exception as e:
                # 避免Qt对象已删除错误导致程序崩溃
                self.logger.warning(f"发送进度信号失败，UI对象可能已关闭: {str(e)}")
                # 不抛出异常，允许后台任务继续执行
    
    def _lock_account(self, account_id):
        """锁定账号，防止其他任务使用
        
        Args:
            account_id: 账号ID
            
        Returns:
            bool: 是否成功锁定
        """
        with self.account_lock:
            if account_id not in self.account_locks:
                self.account_locks[account_id] = {
                    'lock': threading.RLock(),
                    'count': 0
                }
            
            # 增加锁定计数
            self.account_locks[account_id]['count'] += 1
            
            return True
    
    def _unlock_account(self, account_id):
        """解锁账号
        
        Args:
            account_id: 账号ID
            
        Returns:
            bool: 是否成功解锁
        """
        with self.account_lock:
            if account_id not in self.account_locks:
                return False
            
            # 减少锁定计数
            self.account_locks[account_id]['count'] -= 1
            
            # 如果计数为0，移除锁
            if self.account_locks[account_id]['count'] <= 0:
                self.account_locks.pop(account_id, None)
                
                # 清除当前账号信息（如果是该账号）
                with self.account_cookies_lock:
                    if self.current_account == account_id:
                        self.logger.info(f"清除账号 {account_id} 的cookies信息")
                        self.current_account = None
                        self.current_cookies = None
            
            return True
    
    def _check_account_lock(self, account_id):
        """检查账号是否可用
        
        Args:
            account_id: 账号ID
            
        Returns:
            bool: 是否可用
        """
        with self.account_lock:
            # 如果账号不在锁字典中，表示账号可用
            if account_id not in self.account_locks:
                # 锁定账号以供使用（创建锁）
                self._lock_account(account_id)
                return True
            
            # 尝试获取锁
            lock = self.account_locks[account_id]['lock']
            if lock.acquire(blocking=False):
                # 获取锁成功，立即释放
                lock.release()
                return True
            
            return False
    
    def _switch_account_if_needed(self, task):
        """如果需要切换账号，则执行切换
        
        Args:
            task: VideoTask对象
            
        Returns:
            bool: 是否成功切换账号或已经是当前账号
        """
        with self.account_cookies_lock:
            # 检查是否需要切换账号
            if self.current_account == task.appid and self.current_cookies:
                # 已经是当前账号，无需切换
                self.logger.info(f"当前已是账号 {task.appid}，无需切换")
                task.cookies = self.current_cookies
                return True
                
            # 需要切换到新账号
            self.logger.info(f"需要切换到账号: {task.appid}")
            
            if not task.cookies:
                self.logger.error(f"无法切换账号，cookies不存在: {task.appid}")
                return False
                
            # 使用账号cookies切换
            sub_cookies = self.api_client.get_sub_cookies(task.cookies, task.appid)
            if sub_cookies:
                # 更新当前账号信息
                self.current_account = task.appid
                self.current_cookies = sub_cookies
                
                # 更新任务cookies
                task.cookies = sub_cookies
                
                self.logger.info(f"成功切换到账号: {task.appid}")
                return True
            else:
                self.logger.error(f"切换到账号失败: {task.appid}")
                return False
    
    def get_status(self):
        """获取上传处理器状态
        
        Returns:
            dict: 状态信息
        """
        queue_sizes = self.queue_manager.get_queue_sizes()
        active_workers = self.thread_pool.get_active_workers()
        stats = self.queue_manager.get_stats()
        
        with self.account_lock:
            accounts = list(self.account_locks.keys())
        
        with self.stats_lock:
            session_stats = {
                'success': self.success_count,
                'failed': self.failed_count,
                'total': self.success_count + self.failed_count
            }
        
        return {
            'is_running': self._is_running,
            'queue_sizes': queue_sizes,
            'active_workers': active_workers,
            'stats': stats,
            'locked_accounts': accounts,
            'session_stats': session_stats
        }
    
    def get_account_stats(self, account_id):
        """获取账号统计信息
        
        Args:
            account_id: 账号ID
            
        Returns:
            dict: 账号统计信息
        """
        return self.statistics.get_account_stats(account_id)
    
    def close(self):
        """关闭上传处理器"""
        # 停止处理器
        self.stop()
        
        # 关闭统计管理器
        self.statistics.close() 