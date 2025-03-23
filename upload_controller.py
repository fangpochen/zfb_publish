#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import traceback
import time
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication, QMainWindow, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox, QDateTimeEdit, QDialog, QVBoxLayout, QHBoxLayout, QListView
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, QSize, QSettings, QTimer
from PyQt5.QtGui import QBrush, QColor

# 导入新的上传处理系统
from utils.upload_processor import UploadProcessor
from utils.video_task import VideoTask

from api_client import ApiClient

# 旧的上传UI
from upload_ui import UploadUI

# 信号类定义
class UploadSignals(QObject):
    """上传信号类，处理上传过程中的各种信号通知"""
    
    # 进度信号：trace_id, 文件路径, 进度百分比, 状态描述
    upload_progress = pyqtSignal(str, str, int, str)
    
    # 成功信号：trace_id, 文件路径, 视频URL
    upload_success = pyqtSignal(str, str, str)
    
    # 失败信号：trace_id, 文件路径, 错误信息
    upload_failed = pyqtSignal(str, str, str)
    
    # 账号完成信号：账号ID
    account_finished = pyqtSignal(str)
    
    # 统计数据更新信号
    stats_updated = pyqtSignal()

class UploadController:
    """上传控制器类，连接UI和上传处理器"""
    
    def __init__(self, parent=None, ui=None, account_manager=None, log_callback=None):
        """初始化上传控制器
        
        Args:
            parent: 父窗口
            ui: 主界面UI对象
            account_manager: 账号管理器
            log_callback: 日志回调函数
        """
        self.parent = parent
        self.ui = ui
        self.account_manager = account_manager
        self.log_callback = log_callback or print
        
        # 获取数据库引用
        self.db = None
        if account_manager and hasattr(account_manager, 'db'):
            self.db = account_manager.db
        
        # 创建API客户端
        self.api_client = ApiClient(log_callback=log_callback)
        
        # 创建信号对象
        self.signals = UploadSignals()
        
        # 创建上传UI
        self.upload_ui = UploadUI(parent=parent)
        
        # 创建上传处理器
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'upload_stats.db')
        # 确保data目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.upload_processor = UploadProcessor(
            api_client=self.api_client,
            upload_workers=3,
            process_workers=3,
            publish_workers=3,
            db_path=self.db_path,
            signals=self.signals
        )
        
        # 初始化上传标签页
        if hasattr(ui, 'tabWidget') and hasattr(ui, 'uploadTab'):
            # 如果已有上传标签页，添加上传UI到标签页
            upload_tab_index = ui.tabWidget.indexOf(ui.uploadTab)
            if upload_tab_index != -1:
                # 找到uploadTab，设置上传UI
                layout = ui.uploadTab.layout()
                if layout:
                    layout.addWidget(self.upload_ui)
                else:
                    self.log_message("上传标签页没有布局")
            else:
                self.log_message("未找到上传标签页")
        
        # 连接信号
        self.connect_signals()
        
        # 任务统计刷新定时器
        self.stats_timer = QTimer()
        self.stats_timer.setInterval(3000)  # 3秒更新一次
        self.stats_timer.timeout.connect(self.update_task_stats)
        
        # 记录当前添加的任务
        self.tasks = []
    
    def log_message(self, message):
        """记录日志消息
        
        Args:
            message: 日志消息
        """
        if self.log_callback:
            self.log_callback(message)
    
    def connect_signals(self):
        """连接各种信号"""
        try:
            # 上传UI的信号
            if hasattr(self.upload_ui, 'start_upload_button'):
                self.upload_ui.start_upload_button.clicked.connect(self.start_upload)
                
            if hasattr(self.upload_ui, 'stop_upload_button'):
                self.upload_ui.stop_upload_button.clicked.connect(self.stop_upload)
                
            if hasattr(self.upload_ui, 'batch_settings_button'):
                self.upload_ui.batch_settings_button.clicked.connect(self.batch_set_topics)
                
            if hasattr(self.upload_ui, 'topic_search_button'):
                self.upload_ui.topic_search_button.clicked.connect(self.search_topics)
                
            if hasattr(self.upload_ui, 'batch_upload_button'):
                self.upload_ui.batch_upload_button.clicked.connect(self.batch_set_upload_count)
            
            # 上传处理器的信号
            self.signals.upload_progress.connect(self.update_upload_progress)
            self.signals.upload_success.connect(self.on_upload_success)
            self.signals.upload_failed.connect(self.on_upload_failed)
            self.signals.account_finished.connect(self.on_account_finished)
            self.signals.stats_updated.connect(self.update_task_stats)
                
        except Exception as e:
            self.log_message(f"连接信号时出错: {str(e)}")
            traceback.print_exc()
    
    def start_upload(self):
        """开始上传视频"""
        try:
            if not self.account_manager:
                self.log_message("账号管理器未初始化")
                return
                
            # 获取选中的账号和文件夹
            account_folders = self.account_manager.get_selected_accounts_with_folders()
            if not account_folders:
                QMessageBox.warning(self.parent, "上传提示", "未选择账号或账号未绑定文件夹")
                return
                
            # 获取上传设置
            settings = self.upload_ui.get_upload_settings()
            
            # 设置线程数
            upload_workers = settings.get('thread_count', 3)
            self.upload_processor.thread_pool.resize_pools(
                upload_workers=upload_workers,
                process_workers=upload_workers,
                publish_workers=upload_workers
            )
            
            # 显示上传确认对话框
            account_count = len(account_folders)
            
            # 添加封面信息到提示
            cover_info = "使用随机封面" if settings.get('use_random_cover') else f"使用自定义封面: {os.path.basename(settings.get('cover_path', ''))}"
            
            # 添加艺术字信息到提示
            art_text_settings = settings.get('art_text', {})
            art_text_info = ""
            if art_text_settings and art_text_settings.get('enabled', False):
                art_text_info = f"\n艺术字: \"{art_text_settings.get('text', '')}\" (样式: {art_text_settings.get('style', '标准')}, 颜色: {art_text_settings.get('color', '白色')})"
            
            reply = QMessageBox.question(
                self.parent, 
                "确认上传", 
                f"将为{account_count}个账号上传视频，每个账号最多上传{settings.get('max_uploads', 10)}个视频。\n"
                f"{cover_info}{art_text_info}\n"
                f"是否继续？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
                
            # 开始上传
            topics = self.get_topics()
            
            # 启动上传处理器
            if not self.upload_processor._is_running:
                self.upload_processor.start()
                self.stats_timer.start()
            
            # 添加任务
            self.tasks = []
            for account_info in account_folders:
                account = account_info.get('account')
                folders = account_info.get('folders', [])
                
                if not account or not folders:
                    continue
                
                for folder in folders:
                    folder_path = folder.get('path')
                    limit = folder.get('limit', settings.get('max_uploads', 10))
                    
                    # 检查folder_path是否为字典类型，并提取实际路径
                    if isinstance(folder_path, dict):
                        actual_path = folder_path.get('folder_path') or folder_path.get('path', '')
                        folder_path = actual_path
                    
                    if not folder_path or not os.path.exists(folder_path):
                        self.log_message(f"文件夹不存在: {folder_path}")
                        continue
                    
                    # 获取文件夹中的视频文件
                    video_files = []
                    for file_name in os.listdir(folder_path):
                        if file_name.lower().endswith(('.mp4', '.mov', '.avi')):
                            video_files.append(os.path.join(folder_path, file_name))
                    
                    # 限制上传数量
                    video_files = video_files[:limit]
                    
                    # 添加任务
                    for video_file in video_files:
                        task = self.upload_processor.add_task(
                            account=account,
                            file_path=video_file,
                            cover_path=settings.get('cover_path'),
                            use_random_cover=settings.get('use_random_cover', True),
                            topics=topics,
                            schedule_time=settings.get('schedule_time'),
                            art_text_settings=settings.get('art_text')
                        )
                        
                        if task:
                            self.tasks.append(task)
                            self.log_message(f"添加上传任务: {task.trace_id} - {os.path.basename(video_file)}")
            
            if self.tasks:
                self.upload_ui.set_upload_in_progress(True)
                self.log_message(f"开始上传 {len(self.tasks)} 个视频")
            else:
                self.log_message("未添加任何上传任务")
                
        except Exception as e:
            self.log_message(f"开始上传时出错: {str(e)}")
            traceback.print_exc()
    
    def stop_upload(self):
        """停止上传"""
        try:
            reply = QMessageBox.question(
                self.parent, 
                "确认停止", 
                "确定要停止上传任务吗？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 停止所有任务
                stopped_count = self.upload_processor.stop_all_tasks()
                
                # 停止处理器
                self.upload_processor.stop()
                self.stats_timer.stop()
                
                self.upload_ui.set_upload_in_progress(False)
                self.log_message(f"已停止所有上传任务，共停止 {stopped_count} 个任务")
                
        except Exception as e:
            self.log_message(f"停止上传时出错: {str(e)}")
            traceback.print_exc()
    
    def batch_set_topics(self):
        """批量设置话题"""
        try:
            # 打开文件选择对话框
            topic_file, _ = QFileDialog.getOpenFileName(
                self.parent,
                "选择话题配置文件",
                "",
                "JSON文件 (*.json);;文本文件 (*.txt);;所有文件 (*)"
            )
            
            if not topic_file:
                return
                
            # 读取话题
            topics = self.load_topics_from_file(topic_file)
            if not topics:
                QMessageBox.warning(self.parent, "话题设置", "未能读取话题，请检查文件格式")
                return
                
            # 设置话题
            self.set_topics(topics)
            self.log_message(f"已加载 {len(topics)} 个话题")
            
        except Exception as e:
            self.log_message(f"批量设置话题时出错: {str(e)}")
            traceback.print_exc()
    
    def load_topics_from_file(self, file_path):
        """从文件加载话题
        
        Args:
            file_path: 文件路径
            
        Returns:
            list: 话题列表
        """
        try:
            if not os.path.exists(file_path):
                return []
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            # 尝试解析为JSON
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'topics' in data:
                    return data['topics']
                else:
                    return []
            except json.JSONDecodeError:
                # 不是JSON，尝试解析为行分隔的文本
                lines = content.split('\n')
                return [line.strip() for line in lines if line.strip()]
                
        except Exception as e:
            self.log_message(f"加载话题文件失败: {str(e)}")
            traceback.print_exc()
            return []
    
    def get_topics(self):
        """获取当前设置的话题
        
        Returns:
            list: 话题列表或话题信息对象
        """
        # 尝试从主窗口获取完整的话题信息
        from PyQt5.QtWidgets import QApplication
        if QApplication.instance() and QApplication.instance().activeWindow():
            main_window = QApplication.instance().activeWindow()
            if hasattr(main_window, 'current_topic_info'):
                topics_info = main_window.current_topic_info
                if topics_info:
                    self.log_message(f"使用主窗口中的话题信息: {topics_info}")
                    return topics_info
        
        # 如果没有从主窗口获取到话题信息，则从UI获取文本形式的话题
        if hasattr(self.upload_ui, 'topic_search_input'):
            topic_text = self.upload_ui.topic_search_input.text().strip()
            if topic_text:
                # 分割话题并保留#符号
                topics = []
                for topic in topic_text.split(','):
                    topic = topic.strip()
                    if not topic:
                        continue
                    # 确保话题格式正确（前后都有#号）
                    if not topic.startswith('#'):
                        topic = '#' + topic
                    if not topic.endswith('#'):
                        topic = topic + '#'
                    topics.append(topic)
                
                self.log_message(f"使用文本输入框的话题列表: {topics}")
                return topics
        
        return []
    
    def set_topics(self, topics):
        """设置话题到UI
        
        Args:
            topics: 话题列表
        """
        if hasattr(self.upload_ui, 'topic_search_input'):
            if topics:
                if isinstance(topics, dict) and 'topicInfoVOList' in topics:
                    # 这是从main_window.current_topic_info获取的完整话题信息
                    topic_text = ','.join([t.get('topicName', '') for t in topics['topicInfoVOList'] if t.get('topicName')])
                    self.upload_ui.topic_search_input.setText(topic_text)
                    return
                    
                if isinstance(topics[0], dict):
                    # 字典格式的话题
                    if 'display' in topics[0]:
                        # 如果有display字段（包含完整的格式，如#话题#），使用它
                        topic_text = ','.join([t.get('display', '') for t in topics if t.get('display')])
                    elif 'topicName' in topics[0]:
                        # 如果有topicName字段，使用它（支持API格式）
                        topic_text = ','.join([t.get('topicName', '') for t in topics if t.get('topicName')])
                    else:
                        # 如果只有name字段
                        topic_text = ','.join([f"#{t.get('name', '')}#" for t in topics if t.get('name')])
                else:
                    # 字符串格式的话题，确保每个话题都有#前缀和后缀
                    formatted_topics = []
                    for topic in topics:
                        topic = topic.strip()
                        if not topic:
                            continue
                        # 确保话题有正确的格式（前后都有#号）
                        if not topic.startswith('#'):
                            topic = '#' + topic
                        if not topic.endswith('#'):
                            topic = topic + '#'
                        formatted_topics.append(topic)
                    topic_text = ','.join(formatted_topics)
                
                self.upload_ui.topic_search_input.setText(topic_text)
                self.log_message(f"设置话题: {topic_text}")
    
    def search_topics(self):
        """搜索话题"""
        try:
            # 获取搜索关键词
            if not hasattr(self.upload_ui, 'topic_search_input') or not self.account_manager:
                return
                
            keyword = self.upload_ui.topic_search_input.text().strip()
            if not keyword:
                QMessageBox.information(self.parent, "话题搜索", "请输入搜索关键词")
                return
                
            # 获取选中的账号
            selected_accounts = self.account_manager.get_selected_accounts()
            if not selected_accounts:
                QMessageBox.warning(self.parent, "话题搜索", "请先选择账号")
                return
                
            # 使用第一个账号搜索话题
            account = selected_accounts[0]
            appid = account.get('appid')
            
            if not appid:
                QMessageBox.warning(self.parent, "话题搜索", "账号ID不存在")
                return
                
            # 使用account_manager获取cookies
            cookies = self.account_manager.get_account_cookies(appid)
            
            if not cookies:
                QMessageBox.warning(self.parent, "话题搜索", "无法获取账号cookies，请重新登录账号")
                return
                
            # 确保cookies是字典格式
            if isinstance(cookies, str):
                try:
                    cookies = json.loads(cookies)
                except Exception as e:
                    self.log_message(f"解析cookies失败: {str(e)}")
                    QMessageBox.warning(self.parent, "话题搜索", "账号cookies格式错误，请重新登录账号")
                    return
                
            # 搜索话题 - 直接调用API
            self.log_message(f"正在搜索话题: {keyword}")
            
            try:
                topics = self.api_client.search_topics(cookies, appid, keyword)
                
                if topics is not None:
                    self.log_message(f"搜索到 {len(topics)} 个话题")
                    self.show_topic_selection_dialog(topics)
                else:
                    QMessageBox.warning(self.parent, "话题搜索", "未找到相关话题或搜索失败")
                    
            except Exception as e:
                self.log_message(f"搜索话题时发生错误: {str(e)}")
                traceback.print_exc()
                QMessageBox.warning(self.parent, "话题搜索", f"搜索话题失败: {str(e)}")
                
        except Exception as e:
            self.log_message(f"搜索话题时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self.parent, "搜索话题", f"搜索话题过程中出现错误: {str(e)}")
    
    def show_topic_selection_dialog(self, topics):
        """显示话题选择对话框
        
        Args:
            topics: 话题列表
        """
        try:
            if not topics:
                QMessageBox.information(self.parent, "话题搜索", "未找到相关话题")
                return
                
            # 创建对话框
            dialog = QDialog(self.parent)
            dialog.setWindowTitle("选择话题")
            dialog.setMinimumWidth(400)
            dialog.setMinimumHeight(300)
            
            # 创建布局
            layout = QVBoxLayout(dialog)
            
            # 创建列表控件
            label = QLabel("请选择要添加的话题:")
            layout.addWidget(label)
            
            topic_list = QListWidget()
            for topic in topics:
                topic_name = topic.get('name', '')
                topic_display = topic.get('display', f"#{topic_name}#")
                if topic_name:
                    item = QListWidgetItem(topic_display)
                    item.setData(Qt.UserRole, topic)
                    topic_list.addItem(item)
            
            layout.addWidget(topic_list)
            
            # 创建按钮
            button_layout = QHBoxLayout()
            ok_button = QPushButton("确定")
            cancel_button = QPushButton("取消")
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # 选择话题的回调
            selected_topics = []
            
            def on_topic_selected(item):
                topic = item.data(Qt.UserRole)
                if topic:
                    selected_topics.append(topic)
                    # 打印选择的话题原始信息
                    self.log_message(f"选择了话题: {json.dumps(topic, ensure_ascii=False)}")
            
            def on_accept():
                # 将选中的话题添加到UI（替换原有话题）
                current_topics = []  # 清空原有话题列表
                
                # 如果有通过点击选择的话题
                if selected_topics:
                    # 记录原始选择的话题
                    self.log_message(f"选择话题的原始信息: {json.dumps(selected_topics, ensure_ascii=False)}")
                    
                    # 创建完整的话题信息对象，供API使用
                    topic_info_list = []
                    for topic in selected_topics:
                        topic_display = topic.get('display', '')  # 显示用
                        topic_id = topic.get('topicId', '')  # 保存topicId
                        topic_name = topic.get('name', '')
                        
                        # 记录话题的不同格式
                        self.log_message(f"话题处理细节 - display: '{topic_display}', topicId: '{topic_id}', name: '{topic_name}'")
                        
                        if not topic_display and topic_name:
                            topic_display = f"#{topic_name}#"
                        
                        if topic_display:
                            # 添加到UI显示列表
                            if topic_display not in current_topics:
                                current_topics.append(topic_display)
                            
                            # 添加到完整话题信息，包含topicId
                            topic_info = {
                                "topicName": topic_display,
                                "topicId": topic_id,
                                "topicType": "NORMAL"
                            }
                            topic_info_list.append(topic_info)
                            self.log_message(f"添加话题信息: {json.dumps(topic_info, ensure_ascii=False)}")
                    
                    # 更新UI显示
                    self.set_topics(current_topics)
                    
                    # 保存完整话题信息到主窗口
                    from PyQt5.QtWidgets import QApplication
                    if QApplication.instance() and QApplication.instance().activeWindow():
                        main_window = QApplication.instance().activeWindow()
                        topic_info_obj = {
                            'topicInfoVOList': topic_info_list
                        }
                        main_window.current_topic_info = topic_info_obj
                        self.log_message(f"已保存完整话题信息到主窗口: {json.dumps(topic_info_obj, ensure_ascii=False)}")
                    
                    self.log_message(f"已选择 {len(selected_topics)} 个话题: {current_topics}")
                else:
                    # 如果没有通过点击选择话题，尝试获取当前选中的项
                    items = topic_list.selectedItems()
                    if items:
                        self.log_message(f"通过选中项选择了 {len(items)} 个话题")
                        
                        # 创建完整的话题信息对象，供API使用
                        topic_info_list = []
                        
                        for item in items:
                            topic = item.data(Qt.UserRole)
                            if topic:
                                self.log_message(f"选中项话题原始信息: {json.dumps(topic, ensure_ascii=False)}")
                                
                                topic_display = topic.get('display', '')
                                topic_id = topic.get('id', '')  # 保存topicId
                                topic_name = topic.get('name', '')
                                
                                # 记录话题的不同格式
                                self.log_message(f"话题项处理细节 - display: '{topic_display}', topicId: '{topic_id}', name: '{topic_name}'")
                                
                                if not topic_display and topic_name:
                                    topic_display = f"#{topic_name}#"
                                
                                if topic_display:
                                    # 添加到UI显示列表
                                    if topic_display not in current_topics:
                                        current_topics.append(topic_display)
                                    
                                    # 添加到完整话题信息，包含topicId
                                    topic_info = {
                                        "topicName": topic_display,
                                        "topicId": topic_id,
                                        "topicType": "NORMAL"
                                    }
                                    topic_info_list.append(topic_info)
                                    self.log_message(f"添加选中项话题信息: {json.dumps(topic_info, ensure_ascii=False)}")
                        
                        # 更新UI显示
                        self.set_topics(current_topics)
                        
                        # 保存完整话题信息到主窗口
                        from PyQt5.QtWidgets import QApplication
                        if QApplication.instance() and QApplication.instance().activeWindow():
                            main_window = QApplication.instance().activeWindow()
                            topic_info_obj = {
                                'topicInfoVOList': topic_info_list
                            }
                            main_window.current_topic_info = topic_info_obj
                            self.log_message(f"已保存选中项话题信息到主窗口: {json.dumps(topic_info_obj, ensure_ascii=False)}")
                        
                        self.log_message(f"已选择 {len(items)} 个话题: {current_topics}")
                
                dialog.accept()
            
            def on_cancel():
                dialog.reject()
            
            # 连接信号
            topic_list.itemClicked.connect(on_topic_selected)
            ok_button.clicked.connect(on_accept)
            cancel_button.clicked.connect(on_cancel)
            
            # 显示对话框
            dialog.exec_()
            
        except Exception as e:
            self.log_message(f"显示话题选择对话框时出错: {str(e)}")
            traceback.print_exc()
    
    def batch_set_upload_count(self):
        """批量设置上传数量"""
        try:
            # 获取UI控件
            if not hasattr(self.upload_ui, 'upload_count_input'):
                return
                
            # 创建对话框
            dialog = QDialog(self.parent)
            dialog.setWindowTitle("批量设置上传数量")
            dialog.setMinimumWidth(300)
            
            # 创建布局
            layout = QVBoxLayout(dialog)
            
            # 创建数量输入控件
            label = QLabel("每个账号上传数量:")
            layout.addWidget(label)
            
            spin_box = QSpinBox()
            spin_box.setMinimum(1)
            spin_box.setMaximum(100)
            spin_box.setValue(self.upload_ui.upload_count_input.value())
            layout.addWidget(spin_box)
            
            # 创建按钮
            button_layout = QHBoxLayout()
            ok_button = QPushButton("确定")
            cancel_button = QPushButton("取消")
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # 按钮回调
            def on_accept():
                # 更新UI值
                new_limit = spin_box.value()
                self.upload_ui.upload_count_input.setValue(new_limit)
                
                # 获取选中的账号
                if not self.account_manager:
                    self.log_message("账号管理器未初始化，无法批量设置")
                    dialog.accept()
                    return
                    
                account_folders = self.account_manager.get_selected_accounts_with_folders()
                if not account_folders:
                    QMessageBox.warning(self.parent, "提示", "未选择账号或账号未绑定文件夹")
                    dialog.accept()
                    return
                
                # 获取数据库引用
                if hasattr(self.account_manager, 'db'):
                    self.db = self.account_manager.db
                    
                # 检查数据库引用是否可用
                if not hasattr(self, 'db') or not self.db:
                    self.log_message("数据库未初始化，无法更新设置")
                    dialog.accept()
                    return
                    
                # 更新数据库
                success_count = 0
                updated_appids = []
                for account_info in account_folders:
                    account = account_info.get('account')
                    if not account:
                        continue
                        
                    appid = account.get('appid')
                    updated_appids.append(appid)
                    
                    # 获取账号的所有文件夹设置
                    if hasattr(self.db, 'get_folder_settings'):
                        folder_settings = self.db.get_folder_settings(appid)
                        for folder in folder_settings:
                            folder_id = folder.get('id')
                            # 更新文件夹上传限制
                            if hasattr(self.db, 'update_folder_limit'):
                                if self.db.update_folder_limit(folder_id, new_limit):
                                    success_count += 1
                                    self.log_message(f"已更新文件夹ID {folder_id} 的上传数量限制为 {new_limit}")
                                else:
                                    self.log_message(f"更新文件夹ID {folder_id} 的上传限制失败")
                            else:
                                self.log_message("数据库管理器缺少update_folder_limit方法")
                
                self.log_message(f"已为 {success_count} 个文件夹设置最大上传数量: {new_limit}")
                
                # 重新加载账号数据以刷新表格显示
                if hasattr(self.account_manager, 'load_accounts'):
                    self.account_manager.load_accounts()
                    self.log_message("已刷新账号表格显示")
                
                dialog.accept()
            
            def on_cancel():
                dialog.reject()
            
            # 连接信号
            ok_button.clicked.connect(on_accept)
            cancel_button.clicked.connect(on_cancel)
            
            # 显示对话框
            dialog.exec_()
            
        except Exception as e:
            self.log_message(f"批量设置上传数量时出错: {str(e)}")
            traceback.print_exc()
    
    def update_upload_progress(self, trace_id, file_path, progress, status):
        """更新上传进度
        
        Args:
            trace_id: 任务ID
            file_path: 文件路径
            progress: 进度百分比
            status: 状态描述
        """
        try:
            file_name = os.path.basename(file_path)
            self.log_message(f"上传进度: {file_name} - {progress}% - {status}")
            
            # 更新UI进度条
            if hasattr(self.upload_ui, 'update_progress_bar'):
                self.upload_ui.update_progress_bar(file_name, progress, status)
                
        except Exception as e:
            self.log_message(f"更新上传进度时出错: {str(e)}")
    
    def on_upload_success(self, trace_id, file_path, video_url):
        """上传成功回调
        
        Args:
            trace_id: 任务ID
            file_path: 文件路径
            video_url: 视频URL
        """
        try:
            file_name = os.path.basename(file_path)
            self.log_message(f"上传成功: {file_name} - {video_url}")
            
            # 更新UI
            if hasattr(self.upload_ui, 'update_upload_success'):
                self.upload_ui.update_upload_success(file_name)
                
        except Exception as e:
            self.log_message(f"处理上传成功时出错: {str(e)}")
    
    def on_upload_failed(self, trace_id, file_path, error):
        """上传失败回调
        
        Args:
            trace_id: 任务ID
            file_path: 文件路径
            error: 错误信息
        """
        try:
            file_name = os.path.basename(file_path)
            self.log_message(f"上传失败: {file_name} - {error}")
            
            # 更新UI
            if hasattr(self.upload_ui, 'update_upload_failed'):
                self.upload_ui.update_upload_failed(file_name, error)
                
        except Exception as e:
            self.log_message(f"处理上传失败时出错: {str(e)}")
    
    def on_account_finished(self, account_id):
        """账号任务完成回调
        
        Args:
            account_id: 账号ID
        """
        try:
            self.log_message(f"账号 {account_id} 的任务已全部完成")
            
            # 更新UI
            if hasattr(self.upload_ui, 'update_account_finished'):
                self.upload_ui.update_account_finished(account_id)
                
        except Exception as e:
            self.log_message(f"处理账号完成时出错: {str(e)}")
    
    def update_task_stats(self):
        """更新任务统计信息"""
        if not self.upload_processor:
            return
            
        try:
            # 获取处理器状态
            status = self.upload_processor.get_status()
            if not status:
                return
                
            # 检查上传处理器是否运行中
            is_running = status.get('is_running', False)
            
            # 获取队列大小和正在处理的任务数
            queue_sizes = status.get('queue_sizes', {})
            active_workers = status.get('active_workers', {})
            
            # 计算任务数
            upload_queue = queue_sizes.get('upload', 0)
            process_queue = queue_sizes.get('process', 0)
            publish_queue = queue_sizes.get('publish', 0)
            
            active_upload = active_workers.get('upload', 0)
            active_process = active_workers.get('process', 0)
            active_publish = active_workers.get('publish', 0)
            
            total_queue = upload_queue + process_queue + publish_queue
            total_active = active_upload + active_process + active_publish
            
            # 更新UI显示
            if hasattr(self.upload_ui, 'update_task_stats') and callable(self.upload_ui.update_task_stats):
                self.upload_ui.update_task_stats(
                    upload_queue, process_queue, publish_queue,
                    active_upload, active_process, active_publish
                )
            
            # 获取会话统计数据 - 直接使用内存中的计数
            with self.upload_processor.stats_lock:
                total_success = self.upload_processor.success_count
                total_failed = self.upload_processor.failed_count
            
            pending_count = total_queue + total_active
            
            # 获取账号级别的统计数据
            account_stats = {}
            
            # 直接从UploadProcessor的结果队列中获取任务状态
            if hasattr(self.upload_processor, 'queue_manager') and hasattr(self.upload_processor.queue_manager, 'task_map'):
                with self.upload_processor.queue_manager.account_lock:
                    # 初始化所有账号的统计数据
                    for task_id, task in self.upload_processor.queue_manager.task_map.items():
                        appid = task.appid
                        if appid not in account_stats:
                            account_stats[appid] = {'success': 0, 'failed': 0}
                        
                        # 这里需要处理任务状态名称的匹配问题
                        # 任务状态可能是VideoTask的常量，也可能是字符串形式
                        if task.status == VideoTask.STATUS_COMPLETED or task.status == 'completed':
                            account_stats[appid]['success'] += 1
                        elif (task.status in [VideoTask.STATUS_FAILED, VideoTask.STATUS_UPLOAD_FAILED, 
                                            VideoTask.STATUS_PROCESS_FAILED, VideoTask.STATUS_PUBLISH_FAILED] or
                              task.status in ['failed', 'upload_failed', 'process_failed', 'publish_failed']):
                            account_stats[appid]['failed'] += 1
            
            self.log_message(f"当前任务统计数据: {account_stats}")
            
            # 获取表格对象和列索引
            if hasattr(self.account_manager, 'ui') and hasattr(self.account_manager.ui, 'accountTable'):
                table = self.account_manager.ui.accountTable
                
                # 获取列数并确保有当前成功和当前失败列
                success_col_index = -1
                failed_col_index = -1
                
                # 查找列标题
                if table.columnCount() >= 10:
                    for col in range(table.columnCount()):
                        header_item = table.horizontalHeaderItem(col)
                        if header_item:
                            header_text = header_item.text()
                            if "当前成功" in header_text:
                                success_col_index = col
                            elif "当前失败" in header_text:
                                failed_col_index = col
                
                # 如果没有找到列标题，使用默认索引
                if success_col_index == -1:
                    success_col_index = 10  # 默认当前成功列索引
                if failed_col_index == -1:
                    failed_col_index = 11  # 默认当前失败列索引
                
                self.log_message(f"使用列索引 - 成功: {success_col_index}, 失败: {failed_col_index}")
                
                # 确保列索引有效
                if success_col_index >= 0 and failed_col_index >= 0 and success_col_index < table.columnCount() and failed_col_index < table.columnCount():
                    # 更新每个账号的统计数据
                    for row in range(table.rowCount()):
                        # 获取当前行的账号ID - 索引为1，因为第一列是序号，第二列(索引1)是账号ID
                        account_id_item = table.item(row, 1) 
                        if account_id_item:
                            account_id = account_id_item.text()
                            
                            # 获取账号的统计数据
                            account_success = 0
                            account_failed = 0
                            
                            if account_id in account_stats:
                                account_success = account_stats[account_id]['success']
                                account_failed = account_stats[account_id]['failed']
                            
                            # 设置当前成功数
                            success_item = QTableWidgetItem(str(account_success))
                            success_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                            table.setItem(row, success_col_index, success_item)
                            
                            # 设置当前失败数
                            failed_item = QTableWidgetItem(str(account_failed))
                            failed_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                            table.setItem(row, failed_col_index, failed_item)
                
                    # 强制刷新表格显示
                    table.viewport().update()
                    table.update()
                
                else:
                    self.log_message(f"列索引无效: 成功({success_col_index}), 失败({failed_col_index}), 总列数({table.columnCount()})")
            
            # 更新状态栏显示
            status_text = f"上传统计: 成功 {total_success}, 失败 {total_failed}, 待处理 {pending_count}"
            if hasattr(self.upload_ui, 'set_status_message') and callable(self.upload_ui.set_status_message):
                self.upload_ui.set_status_message(status_text)
            
            # 检查是否所有任务都已完成
            is_empty = total_queue == 0
            is_idle = total_active == 0
            
            if is_empty and is_idle and is_running:
                self.log_message("所有上传任务已完成")
                
                # 显示统计信息
                self.log_message(f"上传统计: 成功 {total_success}, 失败 {total_failed}, 待处理 {pending_count}")
                
                # 更新UI状态
                if hasattr(self.upload_ui, 'set_upload_in_progress'):
                    self.upload_ui.set_upload_in_progress(False)
                
                # 在完成时强制刷新表格以确保显示最终状态
                if hasattr(self.account_manager, 'ui') and hasattr(self.account_manager.ui, 'accountTable'):
                    self.account_manager.ui.accountTable.update()
                    
                if hasattr(self, 'stats_timer') and self.stats_timer.isActive():
                    self.stats_timer.stop()
                
        except Exception as e:
            self.log_message(f"更新任务统计时出错: {str(e)}")
            traceback.print_exc()
    
    def test_batch_set_upload_count(self):
        """测试批量设置上传数量功能
        
        用于验证批量设置上传数量功能是否正确保存到数据库
        """
        try:
            # 检查数据库引用
            if not self.db:
                self.log_message("数据库未初始化，无法测试")
                return False
                
            # 获取选中的账号
            if not self.account_manager:
                self.log_message("账号管理器未初始化，无法测试")
                return False
                
            # 获取选中的账号和文件夹
            account_folders = self.account_manager.get_selected_accounts_with_folders()
            if not account_folders:
                self.log_message("未选择账号或账号未绑定文件夹，无法测试")
                return False
            
            # 新的上传限制值
            new_limit = 20
            
            # 更新数据库
            success_count = 0
            for account_info in account_folders:
                account = account_info.get('account')
                if not account:
                    continue
                    
                appid = account.get('appid')
                
                # 获取账号的所有文件夹设置
                if hasattr(self.db, 'get_folder_settings'):
                    before_settings = self.db.get_folder_settings(appid)
                    
                    for folder in before_settings:
                        folder_id = folder.get('id')
                        old_limit = folder.get('max_uploads')
                        
                        # 更新文件夹上传限制
                        if hasattr(self.db, 'update_folder_limit'):
                            if self.db.update_folder_limit(folder_id, new_limit):
                                success_count += 1
                                self.log_message(f"更新ID为{folder_id}的文件夹限制从{old_limit}到{new_limit}")
                
            # 验证更新
            verification_results = []
            for account_info in account_folders:
                account = account_info.get('account')
                if not account:
                    continue
                    
                appid = account.get('appid')
                
                # 获取更新后的设置
                if hasattr(self.db, 'get_folder_settings'):
                    after_settings = self.db.get_folder_settings(appid)
                    
                    for folder in after_settings:
                        folder_id = folder.get('id')
                        current_limit = folder.get('max_uploads')
                        
                        if current_limit == new_limit:
                            verification_results.append(True)
                            self.log_message(f"验证成功: ID为{folder_id}的文件夹限制已更新为{new_limit}")
                        else:
                            verification_results.append(False)
                            self.log_message(f"验证失败: ID为{folder_id}的文件夹限制为{current_limit}，应为{new_limit}")
            
            if all(verification_results) and verification_results:
                self.log_message("测试成功: 所有文件夹的上传限制都已正确更新")
                return True
            else:
                self.log_message("测试失败: 部分或全部文件夹的上传限制未正确更新")
                return False
                
        except Exception as e:
            self.log_message(f"测试批量设置上传数量时出错: {str(e)}")
            traceback.print_exc()
            return False 