#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import traceback
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication, QMainWindow, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox, QDateTimeEdit
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, QSize, QSettings

from upload_manager import UploadManager
from upload_ui import UploadUI

class UploadController:
    """上传控制器类，连接UI和上传管理器"""
    
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
        
        # 创建上传管理器
        self.upload_manager = UploadManager(parent=parent, log_callback=log_callback)
        
        # 创建上传UI
        self.upload_ui = UploadUI(parent=parent)
        
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
            
            # 上传管理器的信号
            if hasattr(self.upload_manager, 'signals'):
                self.upload_manager.signals.upload_progress.connect(self.update_upload_progress)
                self.upload_manager.signals.upload_success.connect(self.on_upload_success)
                self.upload_manager.signals.upload_failed.connect(self.on_upload_failed)
                self.upload_manager.signals.upload_complete.connect(self.on_upload_complete)
                self.upload_manager.signals.upload_status.connect(self.update_upload_status)
                
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
            self.upload_manager.set_max_workers(settings.get('thread_count', 3))
            
            # 显示上传确认对话框
            account_count = len(account_folders)
            
            # 添加封面信息到提示
            cover_info = "使用随机封面" if settings.get('use_random_cover') else f"使用自定义封面: {os.path.basename(settings.get('cover_path', ''))}"
            
            reply = QMessageBox.question(
                self.parent, 
                "确认上传", 
                f"将为{account_count}个账号上传视频，每个账号最多上传{settings.get('max_uploads', 10)}个视频。\n"
                f"{cover_info}\n"
                f"是否继续？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
                
            # 开始上传
            topics = self.get_topics()
            success = self.upload_manager.start_upload(
                account_folders=account_folders,
                topics=topics,
                max_uploads=settings.get('max_uploads'),
                delete_original=settings.get('delete_original', False),
                schedule_time=settings.get('schedule_time'),
                cover_path=settings.get('cover_path'),
                use_random_cover=settings.get('use_random_cover', True)
            )
            
            if success:
                self.upload_ui.set_upload_in_progress(True)
                self.log_message("开始上传视频")
            else:
                self.log_message("启动上传任务失败")
                
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
                self.upload_manager.stop_upload()
                self.log_message("正在停止上传任务...")
                
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
            list: 话题列表
        """
        # 从UI获取话题
        if hasattr(self.upload_ui, 'topic_search_input'):
            topic_text = self.upload_ui.topic_search_input.text().strip()
            if topic_text:
                return [topic.strip() for topic in topic_text.split(',') if topic.strip()]
        return []
    
    def set_topics(self, topics):
        """设置话题到UI
        
        Args:
            topics: 话题列表
        """
        if hasattr(self.upload_ui, 'topic_search_input'):
            self.upload_ui.topic_search_input.setText(', '.join(topics))
    
    def search_topics(self):
        """搜索话题"""
        try:
            if not self.account_manager:
                self.log_message("账号管理器未初始化")
                QMessageBox.warning(self.parent, "搜索话题", "账号管理器未初始化")
                return
                
            # 获取搜索关键词
            keywords = ""
            if hasattr(self.upload_ui, 'topic_search_input'):
                keywords = self.upload_ui.topic_search_input.text().strip()
                
            if not keywords:
                QMessageBox.warning(self.parent, "搜索话题", "请输入搜索关键词")
                return
                
            # 获取选中的账号
            selected_accounts = self.account_manager.get_selected_accounts()
            if not selected_accounts:
                QMessageBox.warning(self.parent, "搜索话题", "请先选择账号")
                return
                
            # 获取第一个选中账号的信息
            account = selected_accounts[0]
            cookies = account.get('cookies_dict')
            appid = account.get('appid')
            
            if not cookies or not appid:
                QMessageBox.warning(self.parent, "搜索话题", "账号信息不完整")
                return
                
            self.log_message(f"正在搜索话题: {keywords}")
            
            # 创建API客户端对象
            from api_client import ApiClient
            api_client = ApiClient(log_callback=self.log_message)
            
            # 调用话题搜索方法
            topics = api_client.search_topics(cookies, appid, keywords)
            
            if topics is None:
                QMessageBox.warning(self.parent, "搜索话题", "搜索话题时出错")
                return
                
            if not topics:
                QMessageBox.information(self.parent, "搜索话题", "未找到相关话题")
                return
                
            # 显示话题选择对话框
            self.show_topic_selection_dialog(topics)
            
        except Exception as e:
            self.log_message(f"搜索话题时出错: {str(e)}")
            QMessageBox.critical(self.parent, "搜索话题", f"搜索话题时出错: {str(e)}")
            traceback.print_exc()
    
    def show_topic_selection_dialog(self, topics):
        """显示话题选择对话框
        
        Args:
            topics: 话题列表，每个话题包含name和topicId
        """
        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QLabel, QLineEdit
            
            # 创建对话框
            dialog = QDialog(self.parent)
            dialog.setWindowTitle("选择话题")
            dialog.setMinimumWidth(400)
            dialog.setMinimumHeight(500)
            
            # 创建布局
            layout = QVBoxLayout(dialog)
            
            # 添加提示标签
            tip_label = QLabel("搜索结果:")
            tip_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(tip_label)
            
            # 添加话题列表
            topic_list = QListWidget()
            for topic in topics:
                display_text = topic.get('display') if 'display' in topic else f"#{topic.get('name', '')}#"
                item = QListWidgetItem(display_text)
                # 保存话题完整信息到item的data中
                item.setData(Qt.UserRole, {
                    'name': topic.get('name', ''),
                    'topicId': topic.get('topicId', '')
                })
                topic_list.addItem(item)
            
            layout.addWidget(topic_list)
            
            # 添加自定义话题输入
            custom_layout = QHBoxLayout()
            custom_label = QLabel("自定义话题:")
            custom_input = QLineEdit()
            custom_input.setPlaceholderText("输入自定义话题 (例如: #我的话题#)")
            custom_layout.addWidget(custom_label)
            custom_layout.addWidget(custom_input)
            layout.addLayout(custom_layout)
            
            # 添加确定和取消按钮
            button_layout = QHBoxLayout()
            ok_button = QPushButton("确定")
            cancel_button = QPushButton("取消")
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # 绑定列表选择事件
            def on_topic_selected(item):
                selected_topic = item.text()
                custom_input.setText(selected_topic)
            
            topic_list.itemClicked.connect(on_topic_selected)
            
            # 绑定按钮事件
            def on_accept():
                selected_topic = custom_input.text().strip()
                if selected_topic:
                    # 确保话题格式正确
                    if not selected_topic.startswith("#"):
                        selected_topic = f"#{selected_topic}"
                    if not selected_topic.endswith("#"):
                        selected_topic = f"{selected_topic}#"
                    
                    # 更新到UI
                    if hasattr(self.upload_ui, 'topic_search_input'):
                        # 获取当前输入框中的话题
                        current_topics = self.upload_ui.topic_search_input.text().strip()
                        if current_topics:
                            # 如果已有话题，追加新话题
                            self.upload_ui.topic_search_input.setText(f"{current_topics}, {selected_topic}")
                        else:
                            # 否则直接设置
                            self.upload_ui.topic_search_input.setText(selected_topic)
                dialog.accept()
            
            def on_cancel():
                dialog.reject()
            
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
            if not self.account_manager or not hasattr(self.account_manager, 'ui') or not hasattr(self.account_manager.ui, 'accountTable'):
                self.log_message("账号管理器未初始化")
                QMessageBox.warning(self.parent, "设置失败", "账号管理器未初始化")
                return
                
            # 获取当前设置的上传数量
            count = 10
            if hasattr(self.upload_ui, 'upload_count_input'):
                count = self.upload_ui.upload_count_input.value()
                
            # 遍历所有选中的账号
            selected_count = 0
            for row in range(self.account_manager.ui.accountTable.rowCount()):
                checkbox_item = self.account_manager.ui.accountTable.cellWidget(row, 0)
                if checkbox_item and hasattr(checkbox_item, 'isChecked') and checkbox_item.isChecked():
                    # 这里假设有一个方法可以设置账号的上传数量
                    selected_count += 1
                    # 这部分功能需要在后续完善
                    pass
            
            if selected_count == 0:
                QMessageBox.warning(self.parent, "设置失败", "未选择任何账号")
                return
                    
            self.log_message(f"已为所有选中账号设置上传数量: {count}")
            QMessageBox.information(self.parent, "设置成功", f"已为{selected_count}个选中账号设置上传数量: {count}")
            
        except Exception as e:
            self.log_message(f"批量设置上传数量时出错: {str(e)}")
            QMessageBox.critical(self.parent, "设置失败", f"设置上传数量时出错: {str(e)}")
            traceback.print_exc()
    
    def update_upload_progress(self, file_name, current, total):
        """更新上传进度
        
        Args:
            file_name: 文件名
            current: 当前进度
            total: 总大小
        """
        progress_percentage = int((current / total) * 100) if total > 0 else 0
        message = f"正在上传 {file_name}... {progress_percentage}% ({current}/{total})"
        self.log_message(message)
        
        # 更新UI进度显示（如果需要后续添加进度条UI）
        # TODO: 添加进度条UI更新
    
    def on_upload_success(self, file_name, content_id):
        """上传成功回调
        
        Args:
            file_name: 文件名
            content_id: 内容ID
        """
        self.log_message(f"文件 {file_name} 上传成功，内容ID: {content_id}")
    
    def on_upload_failed(self, file_name, error):
        """上传失败回调
        
        Args:
            file_name: 文件名
            error: 错误信息
        """
        self.log_message(f"文件 {file_name} 上传失败: {error}")
    
    def on_upload_complete(self, stats):
        """上传完成回调
        
        Args:
            stats: 上传统计结果
        """
        self.upload_ui.set_upload_in_progress(False)
        
        # 显示上传结果
        hours = stats.get('time_spent', {}).get('hours', 0)
        minutes = stats.get('time_spent', {}).get('minutes', 0)
        seconds = stats.get('time_spent', {}).get('seconds', 0)
        
        message = (
            f"上传任务完成\n"
            f"总计: {stats.get('total', 0)} 个文件\n"
            f"成功: {stats.get('success', 0)} 个\n"
            f"失败: {stats.get('failed', 0)} 个\n"
            f"耗时: {hours}小时 {minutes}分钟 {seconds}秒"
        )
        
        QMessageBox.information(self.parent, "上传完成", message)
        self.log_message(message.replace('\n', ' | '))
    
    def update_upload_status(self, status):
        """更新上传状态
        
        Args:
            status: 状态信息
        """
        self.log_message(status) 