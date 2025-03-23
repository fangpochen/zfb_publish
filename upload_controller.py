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
        
        # 保存主窗口引用，避免跨方法引用不一致
        self.main_window = None
        if QApplication.instance() and QApplication.instance().activeWindow():
            self.main_window = QApplication.instance().activeWindow()
        
        # 创建自己的话题信息存储，避免依赖主窗口
        self.current_topic_info = None
        
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
                
        # 添加刷新统计按钮到UI
        self.add_refresh_button_to_ui()
        
        # 连接信号
        self.connect_signals()
        
        # 任务统计刷新定时器
        self.stats_timer = QTimer()
        self.stats_timer.setInterval(3000)  # 3秒更新一次
        self.stats_timer.timeout.connect(self.update_task_stats)
        
        # 记录当前添加的任务
        self.tasks = []
    
    def add_refresh_button_to_ui(self):
        """添加刷新统计按钮到上传UI"""
        try:
            # 检查上传UI是否已有刷新按钮
            if hasattr(self.upload_ui, 'refresh_stats_button'):
                self.log_message("上传UI已有刷新统计按钮")
                return
                
            # 检查是否有设置区域
            if hasattr(self.upload_ui, 'settings_layout'):
                # 创建刷新按钮
                self.upload_ui.refresh_stats_button = QPushButton("刷新统计")
                self.upload_ui.refresh_stats_button.setToolTip("手动刷新上传统计数据")
                self.upload_ui.refresh_stats_button.clicked.connect(self.manual_refresh_stats)
                
                # 添加到设置布局
                self.upload_ui.settings_layout.addWidget(self.upload_ui.refresh_stats_button)
                self.log_message("成功添加刷新统计按钮到上传UI")
            elif hasattr(self.account_manager, 'ui') and hasattr(self.account_manager.ui, 'accountTab'):
                # 创建刷新按钮并添加到账号标签页
                from PyQt5.QtWidgets import QHBoxLayout
                
                # 检查是否已有按钮布局
                button_layout = None
                if hasattr(self.account_manager.ui, 'account_button_layout'):
                    button_layout = self.account_manager.ui.account_button_layout
                else:
                    # 创建新的按钮布局
                    button_layout = QHBoxLayout()
                    self.account_manager.ui.account_button_layout = button_layout
                    
                    # 获取账号标签页布局
                    account_tab_layout = self.account_manager.ui.accountTab.layout()
                    if account_tab_layout:
                        account_tab_layout.addLayout(button_layout)
                
                # 创建并添加刷新按钮
                if button_layout:
                    refresh_button = QPushButton("刷新统计")
                    refresh_button.setToolTip("手动刷新上传统计数据")
                    refresh_button.clicked.connect(self.manual_refresh_stats)
                    
                    # 保存引用
                    self.upload_ui.refresh_stats_button = refresh_button
                    
                    # 添加到布局
                    button_layout.addWidget(refresh_button)
                    self.log_message("成功添加刷新统计按钮到账号标签页")
            else:
                self.log_message("未找到合适的位置添加刷新统计按钮")
                
        except Exception as e:
            self.log_message(f"添加刷新统计按钮时出错: {str(e)}")
            traceback.print_exc()
    
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
                
            # 获取话题信息，并进行验证
            try:
                topics = self.get_topics()
                
                if not topics:
                    QMessageBox.warning(self.parent, "上传提示", "未设置话题，请先搜索并选择话题")
                    return
                
                # 打印话题信息进行调试
                if isinstance(topics, dict) and 'topicInfoVOList' in topics:
                    topic_count = len(topics['topicInfoVOList'])
                    topic_names = [t.get('topicName', '') for t in topics['topicInfoVOList']]
                    self.log_message(f"上传将使用 {topic_count} 个话题: {topic_names}")
                else:
                    self.log_message(f"上传将使用话题: {topics}")
                
            except Exception as e:
                # 话题验证失败，显示友好的错误提示
                QMessageBox.warning(self.parent, "上传提示", f"话题数据验证失败: {str(e)}\n请先搜索并选择有效的话题")
                self.log_message(f"话题验证失败: {str(e)}")
                return
            
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
                
                # 上传开始后强制刷新一次表格
                QTimer.singleShot(1000, self.force_update_stats)
            else:
                self.log_message("未添加任何上传任务")
                
        except Exception as e:
            self.log_message(f"开始上传时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self.parent, "上传错误", f"开始上传时出错: {str(e)}")
    
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
            
        Raises:
            Exception: 如果无法获取有效的话题ID则抛出异常
        """
        # 首先检查控制器自己存储的话题信息
        if self.current_topic_info and 'topicInfoVOList' in self.current_topic_info:
            # 验证话题ID是否存在且不为空
            for topic in self.current_topic_info['topicInfoVOList']:
                if 'topicId' not in topic or not topic['topicId'].strip():
                    raise Exception("话题信息中缺少有效的topicId，请重新搜索并选择话题")
            self.log_message(f"使用控制器中保存的话题信息: {self.current_topic_info}")
            return self.current_topic_info
        
        # 如果控制器没有保存，尝试从主窗口获取
        # 先使用初始化时保存的主窗口引用
        if self.main_window and hasattr(self.main_window, 'current_topic_info'):
            topics_info = self.main_window.current_topic_info
            if topics_info and 'topicInfoVOList' in topics_info:
                # 验证话题ID是否存在且不为空
                for topic in topics_info['topicInfoVOList']:
                    if 'topicId' not in topic or not topic['topicId'].strip():
                        raise Exception("话题信息中缺少有效的topicId，请重新搜索并选择话题")
                # 同时保存到控制器自己的存储中，确保一致性
                self.current_topic_info = topics_info
                self.log_message(f"使用保存的主窗口中的话题信息: {topics_info}")
                return topics_info
        
        # 如果保存的主窗口引用无效，尝试重新获取主窗口
        from PyQt5.QtWidgets import QApplication
        if QApplication.instance() and QApplication.instance().activeWindow():
            main_window = QApplication.instance().activeWindow()
            # 更新主窗口引用
            self.main_window = main_window
            if hasattr(main_window, 'current_topic_info'):
                topics_info = main_window.current_topic_info
                if topics_info and 'topicInfoVOList' in topics_info:
                    # 验证话题ID是否存在且不为空
                    for topic in topics_info['topicInfoVOList']:
                        if 'topicId' not in topic or not topic['topicId'].strip():
                            raise Exception("话题信息中缺少有效的topicId，请重新搜索并选择话题")
                    # 保存到控制器自己的存储中
                    self.current_topic_info = topics_info
                    self.log_message(f"使用重新获取主窗口中的话题信息: {topics_info}")
                    return topics_info
        
        # 如果没有从任何地方获取到话题信息，则从UI获取文本形式的话题
        if hasattr(self.upload_ui, 'topic_search_input'):
            topic_text = self.upload_ui.topic_search_input.text().strip()
            if topic_text:
                # 这种情况下没有话题ID，需要提示用户执行搜索
                raise Exception("找不到话题ID信息，请先点击'搜索'按钮搜索并选择话题")
        
        raise Exception("未设置任何话题，请先搜索并选择话题")
    
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
        """搜索话题并保存到内存中供发布使用"""
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
                
                if topics is not None and len(topics) > 0:
                    # 验证返回的话题是否包含必要的ID信息
                    has_valid_id = False
                    for topic in topics:
                        if topic.get('topicId') or topic.get('id'):
                            has_valid_id = True
                            break
                    
                    if not has_valid_id:
                        QMessageBox.warning(self.parent, "话题搜索", "API返回的话题数据中缺少话题ID信息")
                        return
                        
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
    
    def force_update_stats(self):
        """强制刷新统计数据和表格显示"""
        try:
            # 直接更新表格 - 强制刷新
            if hasattr(self.account_manager, 'ui') and hasattr(self.account_manager.ui, 'accountTable'):
                table = self.account_manager.ui.accountTable
                if table:
                    # 更新表格显示
                    table.viewport().update()
                    table.update()
                    self.log_message("已强制刷新账号表格")
                    
                    # 尝试更新tab页
                    if hasattr(self.account_manager.ui, 'accountTab'):
                        self.account_manager.ui.accountTab.update()
                    
                    # 尝试刷新整个窗口
                    if self.parent:
                        self.parent.update()
                    
                    # 尝试应用样式
                    if hasattr(self.account_manager, 'refresh_account_table'):
                        self.account_manager.refresh_account_table()
                        self.log_message("已调用账号管理器的刷新方法")
                    
                    # 更新统计数据
                    self.update_task_stats()
                    
                    # 尝试重新加载账号
                    if hasattr(self.account_manager, 'load_accounts'):
                        self.account_manager.load_accounts()
                        self.log_message("已重新加载账号数据")
            
        except Exception as e:
            self.log_message(f"强制刷新统计数据时出错: {str(e)}")
            traceback.print_exc()

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
                        topic_id = topic.get('topicId', '') or topic.get('id', '')  # 优先使用topicId，否则使用id
                        topic_name = topic.get('name', '')
                        
                        # 记录话题的不同格式
                        self.log_message(f"话题处理细节 - display: '{topic_display}', topicId: '{topic_id}', name: '{topic_name}'")
                        
                        if not topic_display and topic_name:
                            topic_display = f"#{topic_name}#"
                        
                        # 验证话题ID是否有效
                        if not topic_id.strip():
                            QMessageBox.warning(self.parent, "话题选择", f"话题 '{topic_display}' 缺少有效的ID，无法添加")
                            continue
                        
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
                    
                    # 检查是否有有效话题被添加
                    if not topic_info_list:
                        QMessageBox.warning(self.parent, "话题选择", "未能添加任何有效话题，请重新选择")
                        return
                    
                    # 更新UI显示
                    self.set_topics(current_topics)
                    
                    # 保存完整话题信息到主窗口
                    topic_info_obj = {
                        'topicInfoVOList': topic_info_list
                    }
                    
                    # 首先保存到控制器自己的存储中
                    self.current_topic_info = topic_info_obj
                    
                    # 尝试保存到主窗口
                    from PyQt5.QtWidgets import QApplication
                    if QApplication.instance() and QApplication.instance().activeWindow():
                        main_window = QApplication.instance().activeWindow()
                        self.main_window = main_window  # 更新主窗口引用
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
                                topic_id = topic.get('id', '') or topic.get('topicId', '')  # 优先使用id，否则使用topicId
                                topic_name = topic.get('name', '')
                                
                                # 记录话题的不同格式
                                self.log_message(f"话题项处理细节 - display: '{topic_display}', topicId: '{topic_id}', name: '{topic_name}'")
                                
                                if not topic_display and topic_name:
                                    topic_display = f"#{topic_name}#"
                                
                                # 验证话题ID是否有效
                                if not topic_id.strip():
                                    QMessageBox.warning(self.parent, "话题选择", f"话题 '{topic_display}' 缺少有效的ID，无法添加")
                                    continue
                                    
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
                        
                        # 检查是否有有效话题被添加
                        if not topic_info_list:
                            QMessageBox.warning(self.parent, "话题选择", "未能添加任何有效话题，请重新选择")
                            return
                            
                        # 更新UI显示
                        self.set_topics(current_topics)
                        
                        # 保存完整话题信息
                        topic_info_obj = {
                            'topicInfoVOList': topic_info_list
                        }
                        
                        # 首先保存到控制器自己的存储中
                        self.current_topic_info = topic_info_obj
                        self.log_message(f"已保存选中项话题信息到控制器: {json.dumps(topic_info_obj, ensure_ascii=False)}")
                        
                        # 尝试保存到主窗口
                        from PyQt5.QtWidgets import QApplication
                        if QApplication.instance() and QApplication.instance().activeWindow():
                            main_window = QApplication.instance().activeWindow()
                            self.main_window = main_window  # 更新主窗口引用
                            main_window.current_topic_info = topic_info_obj
                            self.log_message(f"已保存选中项话题信息到主窗口: {json.dumps(topic_info_obj, ensure_ascii=False)}")
                        
                        self.log_message(f"已选择 {len(items)} 个话题: {current_topics}")
                
                # 强制刷新统计数据和表格显示
                QTimer.singleShot(500, self.force_update_stats)
                
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
            
            # 更新UI进度条
            if hasattr(self.upload_ui, 'update_progress_bar'):
                self.upload_ui.update_progress_bar(file_name, progress, status)
                
        except Exception as e:
            self.log_message(f"更新上传进度时出错: {str(e)}")
    
    def update_account_row_stats(self, account_id, success_count=0, failed_count=0, set_value=False, success_value=0, failed_value=0):
        """直接更新指定账号的统计数据到表格
        
        Args:
            account_id: 账号ID
            success_count: 成功数量
            failed_count: 失败数量
            set_value: 是否设置为新值
            success_value: 成功值
            failed_value: 失败值
        """
        try:
            self.log_message(f"直接更新账号 {account_id} 的统计: {'设置为' if set_value else '增加'} 成功:{success_value if set_value else success_count}, 失败:{failed_value if set_value else failed_count}")
            
            # 确保账号ID是字符串格式
            account_id = str(account_id).strip()
            
            # 获取表格实例
            if not hasattr(self.account_manager, 'ui') or not hasattr(self.account_manager.ui, 'accountTable'):
                self.log_message("无法获取账号表格实例")
                return
                
            table = self.account_manager.ui.accountTable
            if not table:
                self.log_message("账号表格对象为空")
                return
                
            # 查找账号ID对应的行
            found_row = -1
            for row in range(table.rowCount()):
                account_id_item = table.item(row, 2)  # 第3列是账号ID
                if not account_id_item:
                    continue
                    
                table_account_id = account_id_item.text().strip()
                if table_account_id == account_id:
                    found_row = row
                    break
                    
            if found_row == -1:
                self.log_message(f"未在表格中找到账号 {account_id}")
                return
                
            # 找到当前成功和失败列的索引
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
                
            # 确保索引有效
            if success_col_index < 0 or failed_col_index < 0 or success_col_index >= table.columnCount() or failed_col_index >= table.columnCount():
                self.log_message(f"无效的列索引: 成功({success_col_index}), 失败({failed_col_index})")
                return
                
            # 设置表格单元格的值
            # 设置当前成功数
            current_success_item = table.item(found_row, success_col_index)
            current_success = 0
            if current_success_item:
                try:
                    current_success = int(current_success_item.text())
                except (ValueError, TypeError) as e:
                    self.log_message(f"解析成功数量失败: {e}, 使用默认值0")
            
            # 根据模式设置新值
            if set_value:
                new_success = success_value
            else:
                new_success = current_success + success_count
            
            # 创建新表格项
            success_item = QTableWidgetItem(str(new_success))
            success_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
            success_item.setTextAlignment(Qt.AlignCenter)  # 居中对齐
            
            # 直接设置，并立即刷新
            table.setItem(found_row, success_col_index, success_item)
            self.log_message(f"已设置行 {found_row} 列 {success_col_index} 的值为 {new_success}")
            
            # 设置当前失败数
            current_failed_item = table.item(found_row, failed_col_index)
            current_failed = 0
            if current_failed_item:
                try:
                    current_failed = int(current_failed_item.text())
                except (ValueError, TypeError) as e:
                    self.log_message(f"解析失败数量失败: {e}, 使用默认值0")
            
            # 根据模式设置新值
            if set_value:
                new_failed = failed_value
            else:
                new_failed = current_failed + failed_count
            
            # 创建新表格项
            failed_item = QTableWidgetItem(str(new_failed))
            failed_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
            failed_item.setTextAlignment(Qt.AlignCenter)  # 居中对齐
            
            # 直接设置，并立即刷新
            table.setItem(found_row, failed_col_index, failed_item)
            self.log_message(f"已设置行 {found_row} 列 {failed_col_index} 的值为 {new_failed}")
            
            # 如果有必要，确保单元格可见
            table.scrollToItem(success_item)
            
            # 直接调用QApplication处理所有待处理的事件，确保UI更新
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()
            
            # 强制刷新表格
            table.viewport().update()
            table.update()
            table.updateGeometry()
            table.repaint()
            
            # 尝试刷新单元格
            table.update(table.model().index(found_row, success_col_index))
            table.update(table.model().index(found_row, failed_col_index))
            
            # 触发表格数据变化信号
            if hasattr(table, 'cellChanged'):
                table.cellChanged.emit(found_row, success_col_index)
                table.cellChanged.emit(found_row, failed_col_index)
            
            # 确保主窗口也刷新
            if self.parent:
                self.parent.update()
                self.parent.repaint()
            
            self.log_message(f"已直接更新账号 {account_id} 的统计数据: 成功 {new_success}, 失败 {new_failed}")
            
            # 直接强制修改单元格数据，不依赖Qt信号机制
            self.direct_set_table_cell(table, found_row, success_col_index, str(new_success), "#67C23A")
            self.direct_set_table_cell(table, found_row, failed_col_index, str(new_failed), "#F56C6C")
            
        except Exception as e:
            self.log_message(f"更新账号行统计数据出错: {str(e)}")
            traceback.print_exc()
            
    def direct_set_table_cell(self, table, row, col, value, color_code=None):
        """直接设置表格单元格的值，绕过Qt的信号机制
        
        Args:
            table: QTableWidget对象
            row: 行索引
            col: 列索引
            value: 单元格值
            color_code: 文本颜色代码，如"#FF0000"为红色
        """
        try:
            # 先检查表格和索引是否有效
            if not table or row < 0 or col < 0 or row >= table.rowCount() or col >= table.columnCount():
                return False
                
            # 获取现有的单元格项目
            item = table.item(row, col)
            
            # 如果单元格项目不存在，创建一个新的
            if not item:
                item = QTableWidgetItem()
                table.setItem(row, col, item)
            
            # 设置单元格文本和对齐方式
            item.setText(str(value))
            item.setTextAlignment(Qt.AlignCenter)
            
            # 如果指定了颜色，设置文本颜色
            if color_code:
                item.setForeground(QBrush(QColor(color_code)))
            
            # 更新单元格
            table.viewport().update()
            
            # 直接处理事件
            QApplication.processEvents()
            
            return True
        except Exception as e:
            self.log_message(f"直接设置表格单元格时出错: {str(e)}")
            return False
            
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
                
                if hasattr(self, 'stats_timer') and self.stats_timer.isActive():
                    self.stats_timer.stop()
                
        except Exception as e:
            self.log_message(f"更新任务统计时出错: {str(e)}")
            traceback.print_exc()
    
    def manual_refresh_stats(self):
        """手动刷新统计数据按钮的回调函数"""
        try:
            self.log_message("手动刷新统计数据...")
            
            # 避免循环调用，不再调用update_task_stats
            # self.update_task_stats()
            
            # 获取账号表格
            if not hasattr(self.account_manager, 'ui') or not hasattr(self.account_manager.ui, 'accountTable'):
                self.log_message("无法获取账号表格实例")
                return
                
            table = self.account_manager.ui.accountTable
            if not table:
                self.log_message("账号表格对象为空")
                return
                
            # 直接按行更新表格
            if hasattr(self.upload_processor, 'queue_manager'):
                # 获取账号统计数据
                account_stats = {}
                
                with self.upload_processor.queue_manager.account_lock:
                    for task_id, task in self.upload_processor.queue_manager.task_map.items():
                        appid = task.appid
                        if not appid:
                            continue
                            
                        # 确保appid是字符串类型
                        appid = str(appid).strip()
                        
                        if appid not in account_stats:
                            account_stats[appid] = {'success': 0, 'failed': 0}
                        
                        # 处理任务状态
                        if task.status == VideoTask.STATUS_COMPLETED or task.status == 'completed':
                            account_stats[appid]['success'] += 1
                        elif (task.status in [VideoTask.STATUS_FAILED, VideoTask.STATUS_UPLOAD_FAILED, 
                                            VideoTask.STATUS_PROCESS_FAILED, VideoTask.STATUS_PUBLISH_FAILED] or
                              task.status in ['failed', 'upload_failed', 'process_failed', 'publish_failed']):
                            account_stats[appid]['failed'] += 1
                
                # 更新表格数据
                for row in range(table.rowCount()):
                    # 获取账号ID
                    account_id_item = table.item(row, 2)  # 第3列是账号ID
                    if not account_id_item:
                        continue
                        
                    account_id = account_id_item.text().strip()
                    if not account_id:
                        continue
                        
                    # 找到成功和失败列索引
                    success_col = -1
                    failed_col = -1
                    
                    for col in range(table.columnCount()):
                        header = table.horizontalHeaderItem(col)
                        if header:
                            header_text = header.text()
                            if "当前成功" in header_text:
                                success_col = col
                            elif "当前失败" in header_text:
                                failed_col = col
                    
                    if success_col == -1 or failed_col == -1:
                        success_col = 10  # 默认值
                        failed_col = 11   # 默认值
                    
                    # 设置统计数据
                    success_count = 0
                    failed_count = 0
                    
                    if account_id in account_stats:
                        success_count = account_stats[account_id]['success']
                        failed_count = account_stats[account_id]['failed']
                    
                    # 直接设置单元格值
                    self.direct_set_table_cell(table, row, success_col, str(success_count), "#67C23A")
                    self.direct_set_table_cell(table, row, failed_col, str(failed_count), "#F56C6C")
            
            # 强制刷新表格
            table.viewport().update()
            table.update()
            table.updateGeometry()
            table.repaint()
            
            # 确保主窗口也刷新
            if self.parent:
                self.parent.update()
                self.parent.repaint()
                
            self.log_message("统计数据手动刷新完成")
            
        except Exception as e:
            self.log_message(f"手动刷新统计数据时出错: {str(e)}")
            traceback.print_exc()

    def on_upload_success(self, trace_id, file_path, video_url):
        """处理上传成功信号
        
        Args:
            trace_id: 追踪ID
            file_path: 文件路径
            video_url: 视频URL
        """
        try:
            # 日志记录
            self.log_message(f"上传成功 - 文件: {os.path.basename(file_path)}, URL: {video_url}")
            
            # 将进度条设置为100%并显示"已完成"
            self.update_upload_progress(trace_id, file_path, 100, "已完成")
            
            # 获取任务状态，只有状态为completed时才增加成功计数
            if self.upload_processor and trace_id in self.upload_processor.queue_manager.task_map:
                task = self.upload_processor.queue_manager.task_map[trace_id]
                if task:
                    # 确保appid是字符串类型
                    appid = str(task.appid).strip() if task.appid else ""
                    
                    # 检查任务状态，只有真正完成才算成功
                    if task.status == VideoTask.STATUS_COMPLETED or task.status == 'completed':
                        # 增加成功计数 - 直接++
                        self.update_account_row_stats(appid, success_count=1)
                        self.log_message(f"任务 {trace_id} 完成状态为 {task.status}，已增加成功计数")
                    else:
                        # 记录当前状态但不更新计数
                        self.log_message(f"任务 {trace_id} 上传成功，当前状态为 {task.status}，等待最终发布完成")
            
        except Exception as e:
            self.log_message(f"处理上传成功信号时出错: {str(e)}")
            traceback.print_exc()
    
    def on_upload_failed(self, trace_id, file_path, error):
        """处理上传失败信号
        
        Args:
            trace_id: 追踪ID
            file_path: 文件路径
            error: 错误信息
        """
        try:
            # 日志记录
            file_name = os.path.basename(file_path)
            self.log_message(f"上传失败 - 文件: {file_name}, 错误: {error}")
            
            # 设置进度条为失败状态
            self.update_upload_progress(trace_id, file_path, 0, f"失败: {error}")
            
            # 直接增加失败计数
            if self.upload_processor and trace_id in self.upload_processor.queue_manager.task_map:
                task = self.upload_processor.queue_manager.task_map[trace_id]
                if task:
                    # 确保appid是字符串类型
                    appid = str(task.appid).strip() if task.appid else ""
                    
                    # 增加失败计数 - 直接++
                    self.update_account_row_stats(appid, failed_count=1)
                    self.log_message(f"任务 {trace_id} 失败状态为 {task.status}，已增加失败计数")
            
        except Exception as e:
            self.log_message(f"处理上传失败信号时出错: {str(e)}")
            traceback.print_exc()
    
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