import os
import sys
import time
import json
import logging
import traceback
from datetime import datetime

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, Qt, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor, QBrush
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, 
                            QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, 
                            QLabel, QProgressBar, QStatusBar, QLineEdit, QCheckBox, QMessageBox)

from UI.upload_dialog import Ui_UploadDialog
from UI.upload_folder_dialog import Ui_UploadFolderDialog
from UI.topic_dialog import Ui_TopicDialog
from utils.upload_processor import UploadProcessor
from utils.models.video_task import VideoTask

def update_task_stats(self):
    """更新任务统计信息"""
    try:
        # 获取当前统计信息
        if not hasattr(self, 'upload_processor') or not self.upload_processor:
            return
        
        status = self.upload_processor.get_status()
        
        # 计算队列任务数和活跃线程数
        queue_sizes = status.get('queue_sizes', {})
        active_workers = status.get('active_workers', {})
        
        total_queue = sum(queue_sizes.values())
        total_active = sum(active_workers.values())
        
        # 更新UI显示
        if self.ui.uploadProgressBar.maximum() == 0 and total_queue + total_active > 0:
            self.ui.uploadProgressBar.setMaximum(total_queue + total_active)
        
        self.ui.uploadProgressBar.setValue(status.get('success_count', 0) + status.get('failed_count', 0))
        
        # 获取会话统计信息
        session_stats = status.get('session_stats', {})
        success_count = session_stats.get('success_count', 0)
        failed_count = session_stats.get('failed_count', 0)
        
        # 获取任务情况 - 按账号统计
        self.logger.info("开始更新账号任务统计...")
        
        # 确保queue_manager存在
        queue_manager = getattr(self.upload_processor, 'queue_manager', None)
        if not queue_manager:
            self.logger.warning("无法获取任务队列管理器")
            return
            
        # 从任务映射中获取所有任务
        account_tasks = {}
        with queue_manager.account_lock:
            for trace_id, task in queue_manager.task_map.items():
                account_id = task.appid
                if account_id not in account_tasks:
                    account_tasks[account_id] = {'success': 0, 'failed': 0, 'pending': 0}
                
                # 检查任务状态，支持常量和字符串形式
                status = task.status
                if status == VideoTask.STATUS_COMPLETED or status == "completed":
                    account_tasks[account_id]['success'] += 1
                elif status in [VideoTask.STATUS_FAILED, VideoTask.STATUS_UPLOAD_FAILED, 
                                VideoTask.STATUS_PROCESS_FAILED, VideoTask.STATUS_PUBLISH_FAILED] or \
                     status in ["failed", "upload_failed", "process_failed", "publish_failed"]:
                    account_tasks[account_id]['failed'] += 1
                else:
                    account_tasks[account_id]['pending'] += 1
        
        # 打印统计信息到日志
        self.logger.info(f"当前任务统计: {account_tasks}")
        
        # 更新账号表格中的成功和失败计数
        account_table = self.parent.accountManager.ui.accountTable
        if account_table.columnCount() >= 12:  # 确保表格有足够的列
            for row in range(account_table.rowCount()):
                # 获取账号ID (第一列)
                item = account_table.item(row, 0)
                if not item:
                    continue
                
                account_id = item.text()
                if account_id in account_tasks:
                    # 更新成功计数 (第10列)
                    success_item = QTableWidgetItem(str(account_tasks[account_id]['success']))
                    success_item.setForeground(QBrush(QColor(0, 255, 0)))  # 绿色
                    account_table.setItem(row, 10, success_item)
                    
                    # 更新失败计数 (第11列)
                    failed_item = QTableWidgetItem(str(account_tasks[account_id]['failed']))
                    failed_item.setForeground(QBrush(QColor(255, 0, 0)))  # 红色
                    account_table.setItem(row, 11, failed_item)
                    
                    self.logger.info(f"已更新账号 {account_id} 的统计: 成功={account_tasks[account_id]['success']}, 失败={account_tasks[account_id]['failed']}")
            
            # 强制刷新表格
            account_table.viewport().update()
            
        # 更新状态栏消息
        self.status_message.setText(f"上传统计: {success_count}成功, {failed_count}失败, {total_queue}待处理, {total_active}进行中")
        
        # 如果所有上传任务已完成，则停止统计计时器
        if total_queue == 0 and total_active == 0 and (success_count > 0 or failed_count > 0):
            self.logger.info("所有上传任务已完成，停止统计计时器")
            if hasattr(self, 'stat_timer') and self.stat_timer.isActive():
                self.stat_timer.stop()
        
    except Exception as e:
        self.logger.error(f"更新任务统计信息时出错: {str(e)}")
        traceback.print_exc() 