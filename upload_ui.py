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
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont, QColor, QPen, QBrush, QFontDatabase
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
        
        # 注册字体(如果需要自定义字体)
        self.available_fonts = []
        font_db = QFontDatabase()
        self.available_fonts = font_db.families()
        
        # 初始化UI
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
        
        # 添加艺术字设置
        art_text_settings = self.get_art_text_settings()
        
        return {
            "max_uploads": self.upload_count_input.value(),
            "thread_count": self.thread_count_input.value(),
            "delete_original": self.delete_original_checkbox.isChecked(),
            "schedule_type": schedule_type,
            "schedule_time": schedule_time,
            "use_random_cover": use_random_cover,
            "cover_path": cover_path,
            "art_text": art_text_settings
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
        
        # 禁用/启用艺术字设置控件
        self.art_text_input.setEnabled(not in_progress)
        self.art_style_combo.setEnabled(not in_progress)
        self.font_size_spin.setEnabled(not in_progress)
        self.text_color_combo.setEnabled(not in_progress)
        self.text_position_combo.setEnabled(not in_progress)
        self.preview_art_text_button.setEnabled(not in_progress)
        
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
        
        # 添加艺术字设置区域
        art_text_group = QGroupBox("艺术字设置")
        art_text_layout = QVBoxLayout()
        
        # 艺术字文本输入
        text_input_layout = QHBoxLayout()
        text_input_layout.addWidget(QLabel("文本内容:"))
        self.art_text_input = QLineEdit()
        self.art_text_input.setPlaceholderText("输入要添加的艺术字...")
        text_input_layout.addWidget(self.art_text_input)
        art_text_layout.addLayout(text_input_layout)
        
        # 艺术字样式选择
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("字体样式:"))
        self.art_style_combo = QComboBox()
        # 添加不同的艺术字样式
        self.art_style_combo.addItems(["标准", "艺术风格一", "艺术风格二", "霓虹灯", "复古", "水墨风", "书法", "华丽花体"])
        style_layout.addWidget(self.art_style_combo)
        art_text_layout.addLayout(style_layout)
        
        # 字体大小选择
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("字体大小:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 72)
        self.font_size_spin.setValue(36)
        self.font_size_spin.setSingleStep(2)
        size_layout.addWidget(self.font_size_spin)
        art_text_layout.addLayout(size_layout)
        
        # 字体颜色选择
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("字体颜色:"))
        self.text_color_combo = QComboBox()
        self.text_color_combo.addItems(["白色", "黑色", "红色", "蓝色", "绿色", "黄色", "粉色", "紫色", "橙色"])
        self.text_color_combo.setCurrentText("白色")  # 默认白色
        color_layout.addWidget(self.text_color_combo)
        art_text_layout.addLayout(color_layout)
        
        # 艺术字位置选择
        position_layout = QHBoxLayout()
        position_layout.addWidget(QLabel("文字位置:"))
        self.text_position_combo = QComboBox()
        self.text_position_combo.addItems(["顶部居中", "底部居中", "左上", "右上", "左下", "右下", "居中"])
        self.text_position_combo.setCurrentText("底部居中")  # 默认底部居中
        position_layout.addWidget(self.text_position_combo)
        art_text_layout.addLayout(position_layout)
        
        # 添加艺术字预览按钮
        preview_button_layout = QHBoxLayout()
        self.preview_art_text_button = QPushButton("预览艺术字效果")
        self.preview_art_text_button.setProperty("type", "info")
        self.preview_art_text_button.clicked.connect(self.preview_art_text)
        preview_button_layout.addWidget(self.preview_art_text_button)
        art_text_layout.addLayout(preview_button_layout)
        
        art_text_group.setLayout(art_text_layout)
        cover_layout.addWidget(art_text_group)
        
        # 添加预览区域
        self.preview_label = QLabel("封面预览区域")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #f5f5f5; border: 1px dashed #dcdfe6; min-height: 180px;")
        self.preview_label.setMinimumSize(320, 180)  # 设置一个合适的预览大小
        cover_layout.addWidget(self.preview_label)
        
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
            
            # 显示图片预览
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    # 如果已有艺术字文本，则显示带艺术字的预览
                    text = self.art_text_input.text()
                    if text:
                        preview_image = self.generate_art_text_preview(file_path, text)
                        if preview_image:
                            self.show_preview_image(preview_image)
                            return
                    
                    # 否则只显示原图预览
                    self.show_preview_image(pixmap)
                else:
                    self.preview_label.clear()
                    self.preview_label.setText("封面预览区域")
                    QMessageBox.warning(self.parent, "预览提示", "无法加载图片，请检查图片格式！")
            except Exception as e:
                print(f"预览图片时出错: {str(e)}")
                self.preview_label.clear()
                self.preview_label.setText("封面预览区域")

    def preview_art_text(self):
        """预览添加艺术字效果的封面"""
        try:
            # 检查是否选择了封面图片
            cover_path = self.cover_path_input.text()
            if not cover_path or not os.path.exists(cover_path):
                QMessageBox.warning(self.parent, "预览提示", "请先选择封面图片！")
                return
                
            # 获取艺术字设置
            text = self.art_text_input.text()
            if not text:
                QMessageBox.warning(self.parent, "预览提示", "请输入艺术字文本！")
                return
                
            # 生成艺术字预览图像
            preview_image = self.generate_art_text_preview(cover_path, text)
            if preview_image:
                # 显示预览图像
                self.show_preview_image(preview_image)
            else:
                QMessageBox.warning(self.parent, "预览失败", "生成预览图像失败，请检查图片格式！")
        except Exception as e:
            print(f"预览艺术字效果时出错: {str(e)}")
            QMessageBox.critical(self.parent, "预览错误", f"预览过程中发生错误: {str(e)}")
            
    def generate_art_text_preview(self, image_path, text):
        """生成添加艺术字的预览图像
        
        Args:
            image_path: 图片路径
            text: 文本内容
            
        Returns:
            QPixmap: 生成的预览图像
        """
        try:
            # 加载原始图像
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                return None
                
            # 创建副本用于绘制
            preview = pixmap.copy()
            
            # 创建绘图对象
            painter = QPainter(preview)
            
            # 获取艺术字设置
            style = self.art_style_combo.currentText()
            font_size = self.font_size_spin.value()
            color_name = self.text_color_combo.currentText()
            position = self.text_position_combo.currentText()
            
            # 设置字体
            font = QFont()
            # 根据选择的样式设置不同的字体
            if style == "标准":
                font.setFamily("微软雅黑")
            elif style == "艺术风格一":
                font.setFamily("华文琥珀")
                font.setBold(True)
            elif style == "艺术风格二":
                font.setFamily("方正舒体")
            elif style == "霓虹灯":
                font.setFamily("Arial")
                font.setBold(True)
            elif style == "复古":
                font.setFamily("华文新魏")
            elif style == "水墨风":
                font.setFamily("楷体")
            elif style == "书法":
                font.setFamily("隶书")
            elif style == "华丽花体":
                font.setFamily("华文行楷")
                
            font.setPointSize(font_size)
            painter.setFont(font)
            
            # 设置颜色
            color_map = {
                "白色": QColor(255, 255, 255),
                "黑色": QColor(0, 0, 0),
                "红色": QColor(255, 0, 0),
                "蓝色": QColor(0, 0, 255),
                "绿色": QColor(0, 255, 0),
                "黄色": QColor(255, 255, 0),
                "粉色": QColor(255, 192, 203),
                "紫色": QColor(128, 0, 128),
                "橙色": QColor(255, 165, 0)
            }
            text_color = color_map.get(color_name, QColor(255, 255, 255))
            
            # 特殊风格处理
            if style == "霓虹灯":
                # 霓虹灯效果添加发光边缘
                glow_color = QColor(text_color)
                glow_color.setAlpha(80)
                painter.setPen(QPen(glow_color, 4))
                
                # 根据位置计算文本位置并绘制发光效果
                x, y = self.calculate_text_position(preview, text, position, painter)
                painter.drawText(x-1, y-1, text)
                painter.drawText(x+1, y-1, text)
                painter.drawText(x-1, y+1, text)
                painter.drawText(x+1, y+1, text)
                
                # 绘制主要文本
                painter.setPen(QPen(text_color, 1))
            else:
                painter.setPen(text_color)
            
            # 计算文本位置并绘制
            x, y = self.calculate_text_position(preview, text, position, painter)
            painter.drawText(x, y, text)
            
            # 结束绘制
            painter.end()
            
            return preview
            
        except Exception as e:
            print(f"生成艺术字预览时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
            
    def calculate_text_position(self, pixmap, text, position, painter):
        """计算文本在图像上的位置
        
        Args:
            pixmap: 图像
            text: 文本内容
            position: 位置描述
            painter: 绘图对象
            
        Returns:
            tuple: (x, y) 文本位置坐标
        """
        # 获取文本矩形
        text_rect = painter.fontMetrics().boundingRect(text)
        text_width = text_rect.width()
        text_height = text_rect.height()
        
        # 图像尺寸
        img_width = pixmap.width()
        img_height = pixmap.height()
        
        # 根据位置设置坐标
        if position == "顶部居中":
            x = (img_width - text_width) // 2
            y = text_height + 10
        elif position == "底部居中":
            x = (img_width - text_width) // 2
            y = img_height - 10
        elif position == "左上":
            x = 10
            y = text_height + 10
        elif position == "右上":
            x = img_width - text_width - 10
            y = text_height + 10
        elif position == "左下":
            x = 10
            y = img_height - 10
        elif position == "右下":
            x = img_width - text_width - 10
            y = img_height - 10
        elif position == "居中":
            x = (img_width - text_width) // 2
            y = (img_height + text_height) // 2
        else:
            # 默认底部居中
            x = (img_width - text_width) // 2
            y = img_height - 10
            
        return x, y
            
    def show_preview_image(self, pixmap):
        """在预览标签中显示图像
        
        Args:
            pixmap: 预览图像
        """
        if pixmap:
            # 调整图像大小以适应预览区域
            preview_size = self.preview_label.size()
            scaled_pixmap = pixmap.scaled(
                preview_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            # 显示预览图像
            self.preview_label.setPixmap(scaled_pixmap)
        else:
            # 清除预览
            self.preview_label.clear()
            self.preview_label.setText("封面预览区域")
            
    def get_art_text_settings(self):
        """获取艺术字设置
        
        Returns:
            dict: 艺术字设置字典
        """
        return {
            "enabled": bool(self.art_text_input.text()),
            "text": self.art_text_input.text(),
            "style": self.art_style_combo.currentText(),
            "font_size": self.font_size_spin.value(),
            "color": self.text_color_combo.currentText(),
            "position": self.text_position_combo.currentText()
        } 