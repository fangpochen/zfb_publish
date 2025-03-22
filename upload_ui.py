#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QRadioButton, QButtonGroup, QTimeEdit, QSpinBox, QCheckBox, QGroupBox,
    QFileDialog, QListWidget, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QTime, QSize
from PyQt5.QtGui import QIcon
import datetime

class UploadUI(QWidget):
    """视频上传界面UI类"""
    
    def __init__(self, parent=None):
        """初始化上传界面
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        
    def init_ui(self):
        """初始化UI界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 创建上传设置区域
        upload_group = self.create_upload_settings_group()
        main_layout.addWidget(upload_group)
        
        # 创建定时发布设置区域
        schedule_group = self.create_schedule_group()
        main_layout.addWidget(schedule_group)
        
        # 创建话题和封面区域 - 使用水平分割器
        topic_cover_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧话题设置区域
        topic_group = self.create_topic_group()
        topic_cover_splitter.addWidget(topic_group)
        
        # 右侧封面设置区域
        cover_group = self.create_cover_group()
        topic_cover_splitter.addWidget(cover_group)
        
        # 设置分割器比例
        topic_cover_splitter.setSizes([int(self.width() * 0.5), int(self.width() * 0.5)])
        main_layout.addWidget(topic_cover_splitter)
        
        # 创建上传控制区域
        upload_control = self.create_upload_control()
        main_layout.addLayout(upload_control)
        
        # 设置布局
        self.setLayout(main_layout)
        
    def create_topic_group(self):
        """创建话题设置组
        
        Returns:
            QGroupBox: 话题设置组
        """
        # 创建话题组
        topic_group = QGroupBox("话题设置")
        topic_layout = QVBoxLayout()
        
        # 话题搜索框
        topic_search_layout = QHBoxLayout()
        topic_search_layout.addWidget(QLabel("话题："))
        self.topic_search_input = QLineEdit()
        self.topic_search_input.setPlaceholderText("输入关键词搜索...")
        topic_search_layout.addWidget(self.topic_search_input)
        self.topic_search_button = QPushButton("搜索话题")
        self.topic_search_button.setProperty("type", "primary")
        topic_search_layout.addWidget(self.topic_search_button)
        topic_layout.addLayout(topic_search_layout)
        
        # 批量设置按钮
        batch_settings_layout = QHBoxLayout()
        self.batch_settings_button = QPushButton("批量设置")
        self.batch_settings_button.setProperty("type", "success")
        batch_settings_layout.addWidget(self.batch_settings_button)
        topic_layout.addLayout(batch_settings_layout)
        
        topic_group.setLayout(topic_layout)
        return topic_group
        
    def create_upload_settings_group(self):
        """创建上传设置组
        
        Returns:
            QGroupBox: 上传设置组
        """
        # 创建上传设置组
        upload_group = QGroupBox("上传设置")
        upload_layout = QVBoxLayout()
        
        # 上传总数设置
        upload_count_layout = QHBoxLayout()
        upload_count_layout.addWidget(QLabel("上传总数："))
        self.upload_count_input = QSpinBox()
        self.upload_count_input.setRange(1, 1000)
        self.upload_count_input.setValue(10)
        upload_count_layout.addWidget(self.upload_count_input)
        self.batch_upload_button = QPushButton("批量设置")
        self.batch_upload_button.setProperty("type", "success")
        upload_count_layout.addWidget(self.batch_upload_button)
        upload_layout.addLayout(upload_count_layout)
        
        # 线程数设置
        thread_count_layout = QHBoxLayout()
        thread_count_layout.addWidget(QLabel("线程数量："))
        self.thread_count_input = QSpinBox()
        self.thread_count_input.setRange(1, 100)
        self.thread_count_input.setValue(50)  # 默认50线程
        thread_count_layout.addWidget(self.thread_count_input)
        upload_layout.addLayout(thread_count_layout)
        
        # 上传后删除原视频设置
        delete_original_layout = QHBoxLayout()
        self.delete_original_checkbox = QCheckBox("上传后删除原视频")
        delete_original_layout.addWidget(self.delete_original_checkbox)
        upload_layout.addLayout(delete_original_layout)
        
        upload_group.setLayout(upload_layout)
        return upload_group
        
    def create_schedule_group(self):
        """创建定时发布设置组
        
        Returns:
            QGroupBox: 定时发布设置组
        """
        # 创建定时发布组
        schedule_group = QGroupBox("设置定时发布")
        schedule_layout = QVBoxLayout()
        
        # 软件定时发布选项
        self.soft_schedule_radio = QRadioButton("软件定时发布时间每天：")
        self.soft_schedule_time = QTimeEdit()
        self.soft_schedule_time.setTime(QTime(0, 0, 0))  # 默认00:00:00
        soft_schedule_layout = QHBoxLayout()
        soft_schedule_layout.addWidget(self.soft_schedule_radio)
        soft_schedule_layout.addWidget(self.soft_schedule_time)
        schedule_layout.addLayout(soft_schedule_layout)
        
        # Web定时发布选项
        self.web_schedule_radio = QRadioButton("Web定时发布时间：")
        self.web_schedule_datetime = QLineEdit()
        self.web_schedule_datetime.setPlaceholderText("YYYY-MM-DD HH:MM")
        
        # 创建一个填入当前时间的按钮
        self.current_time_button = QPushButton("当前时间")
        self.current_time_button.setProperty("type", "info")
        self.current_time_button.setProperty("size", "small")
        self.current_time_button.setFixedWidth(80)
        self.current_time_button.clicked.connect(self.fill_current_time)
        
        web_schedule_layout = QHBoxLayout()
        web_schedule_layout.addWidget(self.web_schedule_radio)
        web_schedule_layout.addWidget(self.web_schedule_datetime)
        web_schedule_layout.addWidget(self.current_time_button)
        schedule_layout.addLayout(web_schedule_layout)
        
        # 不定时选项
        self.no_schedule_radio = QRadioButton("不定时")
        self.no_schedule_radio.setChecked(True)  # 默认选中不定时
        schedule_layout.addWidget(self.no_schedule_radio)
        
        # 添加按钮组
        self.schedule_button_group = QButtonGroup()
        self.schedule_button_group.addButton(self.soft_schedule_radio, 1)
        self.schedule_button_group.addButton(self.web_schedule_radio, 2)
        self.schedule_button_group.addButton(self.no_schedule_radio, 3)
        
        schedule_group.setLayout(schedule_layout)
        return schedule_group
        
    def create_upload_control(self):
        """创建上传控制区域
        
        Returns:
            QHBoxLayout: 上传控制布局
        """
        # 创建上传控制布局
        upload_control_layout = QHBoxLayout()
        
        # 开始上传按钮
        self.start_upload_button = QPushButton("开始上传")
        self.start_upload_button.setProperty("type", "success")
        self.start_upload_button.setMinimumHeight(40)
        upload_control_layout.addWidget(self.start_upload_button)
        
        # 停止按钮
        self.stop_upload_button = QPushButton("停止")
        self.stop_upload_button.setProperty("type", "danger")
        self.stop_upload_button.setMinimumHeight(40)
        self.stop_upload_button.setEnabled(False)  # 初始禁用
        upload_control_layout.addWidget(self.stop_upload_button)
        
        return upload_control_layout
    
    def get_upload_settings(self):
        """获取上传设置
        
        Returns:
            dict: 上传设置字典
        """
        schedule_type = self.schedule_button_group.checkedId()
        schedule_time = None
        
        if schedule_type == 1:  # 软件定时
            schedule_time = self.soft_schedule_time.time().toString("HH:mm:ss")
        elif schedule_type == 2:  # Web定时
            schedule_time = self.web_schedule_datetime.text()
        
        # 获取封面设置
        use_random_cover = self.random_cover_checkbox.isChecked()
        cover_path = None if use_random_cover else self.cover_path_input.text()
        
        return {
            "max_uploads": self.upload_count_input.value(),
            "thread_count": self.thread_count_input.value(),
            "delete_original": self.delete_original_checkbox.isChecked(),
            "schedule_type": schedule_type,
            "schedule_time": schedule_time,
            "use_random_cover": use_random_cover,
            "cover_path": cover_path
        }
    
    def set_upload_in_progress(self, in_progress):
        """设置上传进行中状态
        
        Args:
            in_progress: 是否正在上传
        """
        self.start_upload_button.setEnabled(not in_progress)
        self.stop_upload_button.setEnabled(in_progress)
        
        # 禁用/启用设置控件
        self.upload_count_input.setEnabled(not in_progress)
        self.thread_count_input.setEnabled(not in_progress)
        self.delete_original_checkbox.setEnabled(not in_progress)
        self.soft_schedule_radio.setEnabled(not in_progress)
        self.soft_schedule_time.setEnabled(not in_progress)
        self.web_schedule_radio.setEnabled(not in_progress)
        self.web_schedule_datetime.setEnabled(not in_progress)
        self.current_time_button.setEnabled(not in_progress)
        self.no_schedule_radio.setEnabled(not in_progress)
        
        # 禁用/启用话题设置控件
        self.topic_search_input.setEnabled(not in_progress)
        self.topic_search_button.setEnabled(not in_progress)
        self.batch_settings_button.setEnabled(not in_progress)
        
        # 禁用/启用封面设置控件
        self.cover_path_input.setEnabled(not in_progress)
        self.select_cover_button.setEnabled(not in_progress)
        self.random_cover_checkbox.setEnabled(not in_progress)
        
    def fill_current_time(self):
        """自动填入当前时间到Web定时发布时间输入框"""
        now = datetime.datetime.now()
        formatted_time = now.strftime("%Y-%m-%d %H:%M")
        self.web_schedule_datetime.setText(formatted_time)
        # 自动选中Web定时发布选项
        self.web_schedule_radio.setChecked(True)

    def create_cover_group(self):
        """创建封面自定义设置组
        
        Returns:
            QGroupBox: 封面设置组
        """
        # 创建封面组
        cover_group = QGroupBox("封面自定义设置")
        cover_layout = QVBoxLayout()
        
        # 添加封面选择按钮
        select_cover_layout = QHBoxLayout()
        self.cover_path_input = QLineEdit()
        self.cover_path_input.setPlaceholderText("点击选择自定义封面图片...")
        self.cover_path_input.setReadOnly(True)
        select_cover_layout.addWidget(self.cover_path_input)
        
        self.select_cover_button = QPushButton("选择图片")
        self.select_cover_button.setProperty("type", "primary")
        self.select_cover_button.clicked.connect(self.select_cover_image)
        select_cover_layout.addWidget(self.select_cover_button)
        
        cover_layout.addLayout(select_cover_layout)
        
        # 添加预览区域（后续可添加图片预览功能）
        preview_label = QLabel("封面预览区域")
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setStyleSheet("background-color: #f5f5f5; border: 1px dashed #dcdfe6; min-height: 150px;")
        cover_layout.addWidget(preview_label)
        
        # 添加使用随机封面选项
        random_cover_layout = QHBoxLayout()
        self.random_cover_checkbox = QCheckBox("使用随机封面")
        self.random_cover_checkbox.setChecked(True)
        random_cover_layout.addWidget(self.random_cover_checkbox)
        cover_layout.addLayout(random_cover_layout)
        
        cover_group.setLayout(cover_layout)
        return cover_group
        
    def select_cover_image(self):
        """选择封面图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            "选择封面图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.gif);;所有文件 (*)"
        )
        
        if file_path:
            self.cover_path_input.setText(file_path)
            self.random_cover_checkbox.setChecked(False)
            # TODO: 显示图片预览 