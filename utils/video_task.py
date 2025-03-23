#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import random
import threading
import datetime
import traceback
import uuid
import json

class VideoTask:
    """视频上传任务类，负责跟踪单个视频的上传过程"""
    
    # 状态常量
    STATUS_INIT = "initialized"       # 初始化
    STATUS_UPLOADING = "uploading"    # 上传中
    STATUS_UPLOAD_FAILED = "upload_failed"  # 上传失败
    STATUS_PROCESSING = "processing"  # 处理中
    STATUS_PROCESS_FAILED = "process_failed"  # 处理失败
    STATUS_PUBLISHING = "publishing"  # 发布中
    STATUS_PUBLISH_FAILED = "publish_failed"  # 发布失败
    STATUS_COMPLETED = "completed"    # 完成
    STATUS_FAILED = "failed"          # 失败
    STATUS_CANCELLED = "cancelled"    # 取消
    
    def __init__(self, account, file_path, mt=None, cover_path=None, use_random_cover=False, topics=None, 
                 schedule_time=None, manual_title=None, manual_desc=None, is_batch=False, art_text_settings=None):
        """初始化视频任务
        
        Args:
            account: 账号信息字典，包含appid和cookies
            file_path: 视频文件路径
            mt: MT令牌，如果为None则稍后获取
            cover_path: 封面图片路径，如果为None则使用随机封面
            use_random_cover: 是否使用随机封面
            topics: 话题列表
            schedule_time: 定时发布时间
            manual_title: 手动设置的标题
            manual_desc: 手动设置的描述
            is_batch: 是否批量任务
            art_text_settings: 艺术字设置，包含文本、样式、颜色等
        """
        # 基本信息
        self.account = account
        self.appid = account.get('appid')
        self.cookies = account.get('cookies')
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.file_size = 0
        self.status = self.STATUS_INIT
        self.error = None
        self.error_detail = None  # 添加详细错误信息字段
        
        # 上传参数
        self.mt = mt
        self.cover_path = cover_path
        self.use_random_cover = use_random_cover
        self.topics = topics or []
        self.schedule_time = schedule_time
        self.manual_title = manual_title
        self.manual_desc = manual_desc
        self.is_batch = is_batch
        
        # 艺术字设置
        self.art_text_settings = art_text_settings or {}
        
        # 进度信息
        self.progress = {
            "upload": 0,
            "process": 0,
            "publish": 0,
            "total": 0
        }
        
        # 状态和结果
        self.file_id = None
        self.video_url = None
        self.cover_url = None
        self.content_id = None
        
        # 跟踪和调试信息
        self.trace_id = f"trace_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        self.thread_id = None
        self.create_time = datetime.datetime.now()
        self.upload_start_time = None
        self.upload_end_time = None
        self.process_start_time = None
        self.process_end_time = None
        self.publish_start_time = None
        self.publish_end_time = None
        self.status_history = []
        self.retry_count = {
            "upload": 0,
            "process": 0,
            "publish": 0
        }
        self.max_retries = {
            "upload": 3,
            "process": 5,
            "publish": 2
        }
        
        # 取消标志
        self.is_cancelled = False
        
        # 记录原始话题信息
        self.log_topics_info()
    
    def log_topics_info(self):
        """记录话题详细信息到日志"""
        try:
            import json
            
            # 创建日志条目
            log_entry = {
                "trace_id": self.trace_id,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "topics_info": None
            }
            
            # 记录话题信息
            if self.topics:
                if isinstance(self.topics, dict) and 'topicInfoVOList' in self.topics:
                    log_entry["topics_info"] = {
                        "type": "dict_with_topicInfoVOList",
                        "content": self.topics
                    }
                elif isinstance(self.topics, list):
                    topic_details = []
                    for i, topic in enumerate(self.topics):
                        if isinstance(topic, dict):
                            topic_details.append({
                                "index": i,
                                "type": "dict",
                                "content": topic,
                                "keys": list(topic.keys())
                            })
                        else:
                            topic_details.append({
                                "index": i,
                                "type": type(topic).__name__,
                                "content": str(topic)
                            })
                    
                    log_entry["topics_info"] = {
                        "type": "list",
                        "length": len(self.topics),
                        "details": topic_details
                    }
                else:
                    log_entry["topics_info"] = {
                        "type": type(self.topics).__name__,
                        "content": str(self.topics)
                    }
            
            # 记录到status_history
            self.status_history.append({
                "time": datetime.datetime.now(),
                "status": "topics_info",
                "info": log_entry
            })
            
            # 将结果序列化为JSON并写入日志文件
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, f"topic_info_{self.trace_id}.json")
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            # 记录错误但不影响任务执行
            error_msg = f"记录话题信息时出错: {str(e)}"
            if hasattr(self, 'status_history'):
                self.status_history.append({
                    "time": datetime.datetime.now(),
                    "status": "error",
                    "error": error_msg
                })
    
    def get_topics_detail(self):
        """获取话题的详细信息，用于调试
        
        Returns:
            dict: 话题详细信息
        """
        import json
        
        result = {
            "type": None,
            "content": None,
            "details": None
        }
        
        if not self.topics:
            result["type"] = "empty"
            return result
            
        if isinstance(self.topics, dict):
            result["type"] = "dict"
            result["content"] = json.dumps(self.topics, ensure_ascii=False)
            if 'topicInfoVOList' in self.topics:
                result["details"] = []
                for i, topic in enumerate(self.topics['topicInfoVOList']):
                    topic_detail = {
                        "index": i,
                        "name": topic.get('topicName', ''),
                        "id": topic.get('topicId', ''),
                        "type": topic.get('topicType', ''),
                        "all_keys": list(topic.keys())
                    }
                    result["details"].append(topic_detail)
        elif isinstance(self.topics, list):
            result["type"] = "list"
            result["content"] = json.dumps(self.topics, ensure_ascii=False)
            result["details"] = []
            for i, topic in enumerate(self.topics):
                if isinstance(topic, dict):
                    topic_detail = {
                        "index": i,
                        "type": "dict",
                        "keys": list(topic.keys())
                    }
                    if 'topicName' in topic:
                        topic_detail["name"] = topic['topicName']
                    elif 'name' in topic:
                        topic_detail["name"] = topic['name']
                    elif 'display' in topic:
                        topic_detail["name"] = topic['display']
                        
                    if 'topicId' in topic:
                        topic_detail["id"] = topic['topicId']
                    elif 'id' in topic:
                        topic_detail["id"] = topic['id']
                    
                    result["details"].append(topic_detail)
                else:
                    result["details"].append({
                        "index": i,
                        "type": type(topic).__name__,
                        "content": str(topic)
                    })
        else:
            result["type"] = type(self.topics).__name__
            result["content"] = str(self.topics)
            
        return result
    
    def update_status(self, status, error=None, stage=None):
        """更新任务状态
        
        Args:
            status: 新状态
            error: 错误信息
            stage: 阶段名称
        """
        self.status = status
        if error:
            self.error = error
        
        # 记录状态历史
        timestamp = datetime.datetime.now()
        history_entry = {
            "time": timestamp,
            "status": status,
            "thread_id": threading.get_ident(),
            "stage": stage
        }
        
        if error:
            history_entry["error"] = error
        
        self.status_history.append(history_entry)
        
        # 记录开始时间和结束时间
        if stage == "upload" and status == "uploading" and not self.upload_start_time:
            self.upload_start_time = timestamp
        elif stage == "upload" and (status == "completed" or status == "failed"):
            self.upload_end_time = timestamp
            
        if stage == "process" and status == "processing" and not self.process_start_time:
            self.process_start_time = timestamp
        elif stage == "process" and (status == "completed" or status == "failed"):
            self.process_end_time = timestamp
            
        if stage == "publish" and status == "publishing" and not self.publish_start_time:
            self.publish_start_time = timestamp
        elif stage == "publish" and (status == "completed" or status == "failed"):
            self.publish_end_time = timestamp
    
    def update_error_detail(self, error_detail):
        """更新详细错误信息
        
        Args:
            error_detail: 详细错误信息
        """
        self.error_detail = error_detail
    
    def should_retry(self, stage):
        """检查是否应该重试
        
        Args:
            stage: 阶段名称 (upload, process, publish)
            
        Returns:
            bool: 是否应该重试
        """
        if stage not in self.retry_count:
            return False
            
        return self.retry_count[stage] < self.max_retries[stage]
    
    def increment_retry(self, stage):
        """增加重试计数
        
        Args:
            stage: 阶段名称 (upload, process, publish)
            
        Returns:
            int: 当前重试次数
        """
        if stage in self.retry_count:
            self.retry_count[stage] += 1
            return self.retry_count[stage]
        return 0
    
    def get_stage_duration(self, stage):
        """获取某个阶段的持续时间
        
        Args:
            stage: 阶段名称 (upload, process, publish)
            
        Returns:
            float: 持续时间(秒)
        """
        if stage == "upload" and self.upload_start_time and self.upload_end_time:
            return (self.upload_end_time - self.upload_start_time).total_seconds()
            
        if stage == "process" and self.process_start_time and self.process_end_time:
            return (self.process_end_time - self.process_start_time).total_seconds()
            
        if stage == "publish" and self.publish_start_time and self.publish_end_time:
            return (self.publish_end_time - self.publish_start_time).total_seconds()
            
        return 0
    
    def get_total_duration(self):
        """获取总持续时间
        
        Returns:
            float: 总持续时间(秒)
        """
        end_time = self.publish_end_time or self.process_end_time or self.upload_end_time or datetime.datetime.now()
        return (end_time - self.create_time).total_seconds()
    
    def to_dict(self):
        """将任务转换为字典
        
        Returns:
            dict: 任务字典
        """
        return {
            "trace_id": self.trace_id,
            "account_id": self.appid,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "status": self.status,
            "error": self.error,
            "file_id": self.file_id,
            "video_url": self.video_url,
            "cover_url": self.cover_url,
            "content_id": self.content_id,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "upload_start_time": self.upload_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.upload_start_time else None,
            "upload_end_time": self.upload_end_time.strftime("%Y-%m-%d %H:%M:%S") if self.upload_end_time else None,
            "process_start_time": self.process_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.process_start_time else None,
            "process_end_time": self.process_end_time.strftime("%Y-%m-%d %H:%M:%S") if self.process_end_time else None,
            "publish_start_time": self.publish_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.publish_start_time else None,
            "publish_end_time": self.publish_end_time.strftime("%Y-%m-%d %H:%M:%S") if self.publish_end_time else None,
            "upload_duration": self.get_stage_duration("upload"),
            "process_duration": self.get_stage_duration("process"),
            "publish_duration": self.get_stage_duration("publish"),
            "total_duration": self.get_total_duration(),
            "retry_count": self.retry_count,
        } 
    
    def cancel(self):
        """取消任务
        
        Returns:
            bool: 是否成功取消
        """
        # 设置取消标志
        self.is_cancelled = True
        
        # 如果任务已经完成或失败，无法取消
        if self.status in [self.STATUS_COMPLETED, self.STATUS_FAILED]:
            return False
        
        # 更新任务状态
        self.update_status(self.STATUS_CANCELLED, error="任务被用户取消")
        
        return True
    
    def is_active(self):
        """检查任务是否处于活动状态
        
        Returns:
            bool: 是否活动
        """
        return (not self.is_cancelled and 
                self.status not in [self.STATUS_COMPLETED, self.STATUS_FAILED, self.STATUS_CANCELLED]) 
    
    def update_progress(self, stage, value):
        """更新任务进度
        
        Args:
            stage: 阶段名称 (upload, process, publish)
            value: 进度值 (0-100)
            
        Returns:
            None
        """
        # 确保value在0-100范围内
        value = max(0, min(100, value))
        
        # 更新对应阶段的进度
        if stage in self.progress:
            self.progress[stage] = value
        
        # 更新总进度，按照三个阶段的权重计算
        # 上传权重40%，处理权重30%，发布权重30%
        weights = {
            "upload": 0.4,
            "process": 0.3,
            "publish": 0.3
        }
        
        # 计算总进度
        total_progress = 0
        for s, weight in weights.items():
            total_progress += self.progress.get(s, 0) * weight
        
        self.progress["total"] = round(total_progress)
        
        return self.progress["total"] 