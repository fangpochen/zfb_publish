#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import logging
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 导入API客户端
from api_client import APIClient

# 导入上传处理器
from utils.upload_processor import UploadProcessor

# 模拟信号类
class MockSignals:
    def __init__(self):
        self.logger = logging.getLogger('MockSignals')
    
    def upload_progress(self, trace_id, file_path, progress, status):
        self.logger.info(f"Upload Progress: {file_path} - {progress}% - {status}")
    
    def upload_success(self, trace_id, file_path, video_url):
        self.logger.info(f"Upload Success: {file_path} - {video_url}")
    
    def upload_failed(self, trace_id, file_path, error):
        self.logger.error(f"Upload Failed: {file_path} - {error}")
    
    def account_finished(self, account_id):
        self.logger.info(f"Account Finished: {account_id}")
    
    # 添加emit方法，模拟PyQt信号
    def emit(self, *args, **kwargs):
        pass
    
    # 将方法转换为有emit方法的对象
    @property
    def upload_progress(self):
        return self._create_signal_object(self._upload_progress)
    
    @property
    def upload_success(self):
        return self._create_signal_object(self._upload_success)
    
    @property
    def upload_failed(self):
        return self._create_signal_object(self._upload_failed)
    
    @property
    def account_finished(self):
        return self._create_signal_object(self._account_finished)
    
    def _upload_progress(self, trace_id, file_path, progress, status):
        self.logger.info(f"Upload Progress: {trace_id} - {os.path.basename(file_path)} - {progress}% - {status}")
    
    def _upload_success(self, trace_id, file_path, video_url):
        self.logger.info(f"Upload Success: {trace_id} - {os.path.basename(file_path)} - {video_url}")
    
    def _upload_failed(self, trace_id, file_path, error):
        self.logger.error(f"Upload Failed: {trace_id} - {os.path.basename(file_path)} - {error}")
    
    def _account_finished(self, account_id):
        self.logger.info(f"Account Finished: {account_id}")
    
    def _create_signal_object(self, callback):
        class SignalObject:
            def emit(self, *args, **kwargs):
                callback(*args, **kwargs)
        
        return SignalObject()

def main():
    """测试上传处理器"""
    logger = logging.getLogger("Test")
    
    # 加载配置
    try:
        config_file = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        config = {}
    
    # 创建API客户端
    api_client = APIClient()
    
    # 创建信号对象
    signals = MockSignals()
    
    # 创建上传处理器
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'upload_stats.db')
    processor = UploadProcessor(
        api_client=api_client,
        upload_workers=3,
        process_workers=3,
        publish_workers=3,
        db_path=db_path,
        signals=signals
    )
    
    # 启动处理器
    logger.info("启动上传处理器...")
    processor.start()
    
    # 从配置中获取测试账号
    test_account = config.get('test_account', {})
    if not test_account:
        logger.error("未找到测试账号配置，请检查config.json文件")
        processor.stop()
        return
    
    # 获取测试文件
    test_videos_dir = config.get('test_videos_dir', os.path.join(os.path.dirname(__file__), 'test_videos'))
    test_videos = []
    
    if os.path.exists(test_videos_dir):
        for file_name in os.listdir(test_videos_dir):
            if file_name.lower().endswith(('.mp4', '.mov', '.avi')):
                test_videos.append(os.path.join(test_videos_dir, file_name))
    
    if not test_videos:
        logger.error(f"未找到测试视频文件，请将视频文件放入: {test_videos_dir}")
        processor.stop()
        return
    
    # 添加上传任务
    logger.info(f"添加测试上传任务: {len(test_videos)}个视频")
    tasks = []
    for video_file in test_videos:
        task = processor.add_task(
            account=test_account,
            file_path=video_file,
            use_random_cover=True,
            topics=["测试话题1", "测试话题2"],
            schedule_time=None
        )
        
        if task:
            logger.info(f"成功添加任务: {task.trace_id} - {os.path.basename(video_file)}")
            tasks.append(task)
        else:
            logger.error(f"添加任务失败: {os.path.basename(video_file)}")
    
    # 等待处理完成
    try:
        logger.info("等待所有任务完成...")
        
        # 测试停止功能
        if tasks and len(tasks) >= 3:
            # 等待5秒后停止第一个任务
            time.sleep(5)
            first_task = tasks[0]
            logger.info(f"测试停止单个任务: {first_task.trace_id}")
            
            if processor.stop_task(first_task.trace_id):
                logger.info(f"成功停止任务: {first_task.trace_id}")
            else:
                logger.warning(f"停止任务失败: {first_task.trace_id}")
            
            # 等待5秒后停止所有任务
            time.sleep(5)
            logger.info("测试停止所有任务")
            stopped_count = processor.stop_all_tasks()
            logger.info(f"成功停止 {stopped_count} 个任务")
        
        # 主循环 - 等待剩余任务完成或处理器停止
        while processor._is_running:
            # 获取处理器状态
            status = processor.get_status()
            
            # 检查是否所有队列都为空
            queue_sizes = status.get('queue_sizes', {})
            active_workers = status.get('active_workers', {})
            
            is_empty = all(size == 0 for size in queue_sizes.values())
            is_idle = all(count == 0 for count in active_workers.values())
            
            # 打印当前状态
            logger.info(f"队列大小: {queue_sizes}")
            logger.info(f"活跃线程: {active_workers}")
            logger.info(f"锁定账号: {status.get('locked_accounts', [])}")
            logger.info(f"统计信息: {status.get('stats', {})}")
            
            # 如果所有队列都为空且没有活跃线程，可以退出循环
            if is_empty and is_idle:
                break
            
            # 等待一段时间
            time.sleep(5)
        
        logger.info("所有任务已完成或被取消！")
        
    except KeyboardInterrupt:
        logger.info("用户中断，停止处理器...")
        
        # 停止所有任务
        processor.stop_all_tasks()
    
    # 停止处理器
    processor.stop()
    
    # 打印统计信息
    account_id = test_account.get('appid')
    if account_id:
        stats = processor.get_account_stats(account_id)
        logger.info(f"账号统计: {stats}")
    
    logger.info("测试完成！")

if __name__ == "__main__":
    main() 