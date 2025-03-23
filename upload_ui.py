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
        
        # 加载自定义字体
        self.load_custom_fonts()
        
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
    
    def create_cover_group(self):
        """创建封面自定义设置组
        
        Returns:
            QGroupBox: 封面设置组
        """
        # 创建封面组
        cover_group = QGroupBox("封面设置")
        cover_layout = QVBoxLayout()
        
        # 添加使用艺术字勾选框
        use_art_text_layout = QHBoxLayout()
        self.use_art_text_checkbox = QCheckBox("使用艺术字")
        self.use_art_text_checkbox.setChecked(False)
        self.use_art_text_checkbox.toggled.connect(self.toggle_art_text_settings)
        use_art_text_layout.addWidget(self.use_art_text_checkbox)
        cover_layout.addLayout(use_art_text_layout)
        
        # 添加艺术字设置区域
        self.art_text_group = QGroupBox("艺术字设置")
        art_text_layout = QVBoxLayout()
        
        # 艺术字文本输入
        text_input_layout = QHBoxLayout()
        text_input_layout.addWidget(QLabel("文本内容:"))
        self.art_text_input = QLineEdit()
        self.art_text_input.setPlaceholderText("输入要添加的艺术字...(留空则使用视频文件名)")
        text_input_layout.addWidget(self.art_text_input)
        art_text_layout.addLayout(text_input_layout)
        
        # 添加提示标签
        tip_label = QLabel("提示: 留空将自动使用视频文件名作为艺术字")
        tip_label.setStyleSheet("color: #888; font-size: 11px;")
        tip_label.setAlignment(Qt.AlignRight)
        art_text_layout.addWidget(tip_label)
        
        # 艺术字样式选择
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("字体样式:"))
        self.art_style_combo = QComboBox()
        
        # 先检查并打印字体列表状态
        if hasattr(self, 'font_list'):
            print(f"字体列表状态: {self.font_list}")
        else:
            print("字体列表未初始化")
        
        # 添加字体到下拉菜单
        default_fonts = ["标准", "艺术风格一", "艺术风格二", "霓虹灯", "复古", "水墨风", "书法", "华丽花体"]
        
        # 强制添加三个自定义字体的名称
        force_custom_fonts = ["子魂变体字", "华光刚黑体", "青鸟华光行楷"]
        print(f"强制添加自定义字体: {force_custom_fonts}")
        self.art_style_combo.addItems(force_custom_fonts)
        
        # 再添加默认字体选项
        print("添加默认字体选项")
        self.art_style_combo.addItems(default_fonts)
        
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
        self.text_position_combo.addItems(["顶部居中", "底部居中", "居中"])
        self.text_position_combo.setCurrentText("底部居中")  # 默认底部居中
        position_layout.addWidget(self.text_position_combo)
        art_text_layout.addLayout(position_layout)
        
        # 添加预览艺术字按钮
        preview_button_layout = QHBoxLayout()
        self.preview_art_text_button = QPushButton("预览艺术字效果")
        self.preview_art_text_button.setProperty("type", "info")
        self.preview_art_text_button.clicked.connect(self.preview_art_text)
        preview_button_layout.addWidget(self.preview_art_text_button)
        art_text_layout.addLayout(preview_button_layout)
        
        # 设置艺术字组布局
        self.art_text_group.setLayout(art_text_layout)
        cover_layout.addWidget(self.art_text_group)
        
        # 预览区域
        self.preview_label = QLabel("封面预览区域")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #f5f5f5; border: 1px dashed #dcdfe6; min-height: 180px;")
        self.preview_label.setMinimumSize(320, 180)  # 设置一个合适的预览大小
        cover_layout.addWidget(self.preview_label)
        
        cover_group.setLayout(cover_layout)
        
        # 初始状态下禁用艺术字设置
        self.toggle_art_text_settings(False)
        
        # 打印下拉菜单中的所有选项
        items = []
        for i in range(self.art_style_combo.count()):
            items.append(self.art_style_combo.itemText(i))
        print(f"下拉菜单中的所有选项: {items}")
        
        return cover_group
        
    def toggle_art_text_settings(self, enabled):
        """根据是否使用艺术字切换设置区域的启用状态
        
        Args:
            enabled: 是否启用艺术字设置
        """
        self.art_text_group.setEnabled(enabled)
        self.preview_label.setEnabled(enabled)
        self.preview_art_text_button.setEnabled(enabled)

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
        
        # 艺术字设置
        use_art_text = self.use_art_text_checkbox.isChecked()
        art_text_settings = None
        if use_art_text:
            art_text_settings = self.get_art_text_settings()
        
        return {
            "max_uploads": self.upload_count_input.value(),
            "thread_count": self.thread_count_input.value(),
            "delete_original": self.delete_original_checkbox.isChecked(),
            "schedule_type": schedule_type,
            "schedule_time": schedule_time,
            "use_random_cover": True,  # 默认使用随机封面
            "cover_path": None,  # 不使用自定义封面
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
        
        # 禁用/启用艺术字设置控件
        self.use_art_text_checkbox.setEnabled(not in_progress)
        if not in_progress:
            # 如果不是上传中，根据勾选状态设置艺术字控件可用性
            self.toggle_art_text_settings(self.use_art_text_checkbox.isChecked())
        else:
            # 如果正在上传，禁用所有艺术字控件
            self.art_text_group.setEnabled(False)

    def fill_current_time(self):
        """自动填入当前时间到Web定时发布时间输入框"""
        now = datetime.datetime.now()
        formatted_time = now.strftime("%Y-%m-%d %H:%M")
        self.web_schedule_datetime.setText(formatted_time)
        # 自动选中Web定时发布选项
        self.web_schedule_radio.setChecked(True)

    def get_art_text_settings(self):
        """获取艺术字设置
        
        Returns:
            dict: 艺术字设置字典
        """
        if not self.use_art_text_checkbox.isChecked():
            return {"enabled": False}
        
        # 获取用户输入的文本，如果为空则设置标志让上传时使用文件名
        text = self.art_text_input.text()
        
        return {
            "enabled": True,
            "text": text,  # 可以为空，上传时会自动替换为文件名
            "use_filename_if_empty": text == "",  # 标记是否使用文件名
            "style": self.art_style_combo.currentText(),
            "font_size": self.font_size_spin.value(),
            "color": self.text_color_combo.currentText(),
            "position": self.text_position_combo.currentText()
        }

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
        
        # 根据位置设置坐标 - 只支持上中下三个位置
        if position == "顶部居中":
            x = (img_width - text_width) // 2
            y = text_height + 10
        elif position == "底部居中":
            x = (img_width - text_width) // 2
            # 修复：y值应该是(图像高度 - 文本高度的一部分)，确保文本完全可见
            y = img_height - (text_height // 2)
        elif position == "居中":
            x = (img_width - text_width) // 2
            y = (img_height + text_height) // 2
        else:
            # 默认底部居中
            x = (img_width - text_width) // 2
            # 使用同样修复的计算方式
            y = img_height - (text_height // 2)
            
        return x, y

    def preview_art_text(self):
        """预览添加艺术字效果"""
        try:
            # 获取艺术字设置
            text = self.art_text_input.text()
            if not text:
                # 使用默认文本作为示例
                text = "视频文件名示例.mp4"
                QMessageBox.information(self.parent, "预览提示", "文本内容为空，上传时会自动使用视频文件名。预览将使用示例文件名。")
            
            # 生成预览图像
            preview_image = self.generate_art_text_preview(text)
            if preview_image:
                # 显示预览图像
                self.show_preview_image(preview_image)
            else:
                QMessageBox.warning(self.parent, "预览失败", "生成预览图像失败")
        except Exception as e:
            print(f"预览艺术字效果时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.parent, "预览错误", f"预览过程中发生错误: {str(e)}")

    def generate_art_text_preview(self, text):
        """生成添加艺术字的预览图像
        
        Args:
            text: 文本内容
            
        Returns:
            QPixmap: 生成的预览图像
        """
        try:
            # 创建一个空白图像作为预览背景
            width, height = 400, 240
            pixmap = QPixmap(width, height)
            pixmap.fill(QColor("#2c3e50"))  # 深蓝色背景
            
            # 创建绘图对象
            painter = QPainter(pixmap)
            
            # 获取艺术字设置
            font_style = self.art_style_combo.currentText()
            font_size = self.font_size_spin.value()
            color_name = self.text_color_combo.currentText()
            position = self.text_position_combo.currentText()
            
            print(f"预览艺术字: {text}, 样式: {font_style}, 大小: {font_size}")
            
            # 设置字体
            font = QFont()
            
            # 字体映射：自定义字体与文件映射
            custom_font_map = {
                "子魂变体字": "ZiHunBianTaoTi-2.ttf",
                "华光刚黑体": "HuaGuangGangHeiTi-2.ttf",
                "青鸟华光行楷": "QingNiaoHuaGuangXingKai-2.ttf"
            }
            
            # 使用当前工作目录
            font_dir = os.path.join(os.getcwd(), 'fonts')
            print(f"字体目录: {font_dir}")
            
            # 检查所选字体是否是我们的自定义字体
            if font_style in custom_font_map:
                # 使用选择的自定义字体
                font_file = custom_font_map[font_style]
                font_path = os.path.join(font_dir, font_file)
                
                print(f"尝试使用字体文件: {font_path}")
                
                if os.path.exists(font_path):
                    print(f"✅ 字体文件存在: {font_path}")
                    # 尝试直接加载字体
                    font_id = QFontDatabase.addApplicationFont(font_path)
                    if font_id != -1:
                        font_families = QFontDatabase.applicationFontFamilies(font_id)
                        if font_families:
                            font.setFamily(font_families[0])
                            print(f"已设置字体族: {font_families[0]}")
                        else:
                            # 如果加载失败，使用默认字体
                            font.setFamily("微软雅黑")
                            print(f"自定义字体族读取失败，使用默认字体")
                    else:
                        # 如果加载失败，使用默认字体
                        font.setFamily("微软雅黑")
                        print(f"自定义字体加载失败，使用默认字体")
                else:
                    print(f"❌ 字体文件不存在: {font_path}")
                    
                    # 尝试使用自定义字体映射
                    if hasattr(self, 'custom_fonts') and font_style in self.custom_fonts:
                        font_path = self.custom_fonts[font_style]
                        print(f"尝试从映射获取字体: {font_path}")
                        if os.path.exists(font_path):
                            font_id = QFontDatabase.addApplicationFont(font_path)
                            if font_id != -1:
                                font_families = QFontDatabase.applicationFontFamilies(font_id)
                                if font_families:
                                    font.setFamily(font_families[0])
                                    print(f"从映射成功加载字体: {font_families[0]}")
                                else:
                                    font.setFamily("微软雅黑")
                            else:
                                font.setFamily("微软雅黑")
                        else:
                            font.setFamily("微软雅黑")
            elif hasattr(self, 'custom_fonts') and font_style in self.custom_fonts:
                # 使用选择的自定义字体
                font.setFamily(font_style)
                print(f"使用自定义字体: {font_style}")
            else:
                # 使用默认字体映射
                if font_style == "标准":
                    font.setFamily("微软雅黑")
                elif font_style == "艺术风格一":
                    font.setFamily("华文琥珀")
                    font.setBold(True)
                elif font_style == "艺术风格二":
                    font.setFamily("方正舒体")
                elif font_style == "霓虹灯":
                    font.setFamily("Arial")
                    font.setBold(True)
                elif font_style == "复古":
                    font.setFamily("华文新魏")
                elif font_style == "水墨风":
                    font.setFamily("楷体")
                elif font_style == "书法":
                    font.setFamily("隶书")
                elif font_style == "华丽花体":
                    font.setFamily("华文行楷")
            
            # 设置字体大小
            font.setPointSize(font_size)
            painter.setFont(font)
            print(f"最终设置的字体: {font.family()}, 大小: {font.pointSize()}")
            
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
            
            # 特殊风格处理 - 只对霓虹灯样式应用特效
            if font_style == "霓虹灯":
                # 霓虹灯效果添加发光边缘
                glow_color = QColor(text_color)
                glow_color.setAlpha(80)
                painter.setPen(QPen(glow_color, 4))
                
                # 根据位置计算文本位置并绘制发光效果
                x, y = self.calculate_text_position(pixmap, text, position, painter)
                painter.drawText(x-1, y-1, text)
                painter.drawText(x+1, y-1, text)
                painter.drawText(x-1, y+1, text)
                painter.drawText(x+1, y+1, text)
                
                # 绘制主要文本
                painter.setPen(QPen(text_color, 1))
            else:
                painter.setPen(text_color)
            
            # 计算文本位置并绘制
            x, y = self.calculate_text_position(pixmap, text, position, painter)
            painter.drawText(x, y, text)
            
            # 结束绘制
            painter.end()
            
            return pixmap
            
        except Exception as e:
            print(f"生成艺术字预览时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

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

    def load_custom_fonts(self):
        """加载自定义字体"""
        from PyQt5.QtGui import QFontDatabase
        import os
        
        # 直接使用当前目录下的fonts文件夹
        font_dir = os.path.join(os.getcwd(), 'fonts')
        print(f"字体目录路径: {font_dir}")
        
        # 确保字体目录存在
        if not os.path.exists(font_dir):
            os.makedirs(font_dir)
            print(f"创建字体目录: {font_dir}")
        else:
            print(f"字体目录已存在: {font_dir}")
        
        # 指定要加载的字体文件名
        target_fonts = ["ZiHunBianTaoTi-2.ttf", "HuaGuangGangHeiTi-2.ttf", "QingNiaoHuaGuangXingKai-2.ttf"]
        
        # 检查这些文件是否存在
        font_files = []
        for font_name in target_fonts:
            font_path = os.path.join(font_dir, font_name)
            if os.path.exists(font_path):
                print(f"✅ 找到字体文件: {font_name}")
                font_files.append(font_name)
            else:
                print(f"❌ 未找到字体文件: {font_name}")
        
        print(f"找到可用字体文件: {font_files}")
        
        # 加载目录中的所有字体
        self.custom_fonts = {}  # 存储字体名称和文件的映射
        font_count = 0
        font_list = []
        
        # 手动添加我们知道的字体名称
        known_font_mappings = {
            "ZiHunBianTaoTi-2.ttf": "子魂变体字",
            "HuaGuangGangHeiTi-2.ttf": "华光刚黑体",
            "QingNiaoHuaGuangXingKai-2.ttf": "青鸟华光行楷"
        }
        
        # 先尝试常规加载
        for font_file in font_files:
            try:
                font_path = os.path.join(font_dir, font_file)
                print(f"尝试加载字体: {font_path}")
                
                font_id = QFontDatabase.addApplicationFont(font_path)
                print(f"字体ID: {font_id}")
                
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    print(f"字体族: {font_families}")
                    
                    if font_families:
                        for family in font_families:
                            self.custom_fonts[family] = font_path
                            font_list.append(family)
                            font_count += 1
                            print(f"成功加载字体: {family} 从 {font_file}")
                    else:
                        # 如果无法读取字体族，使用我们预先知道的名称
                        if font_file in known_font_mappings:
                            family = known_font_mappings[font_file]
                            self.custom_fonts[family] = font_path
                            font_list.append(family)
                            font_count += 1
                            print(f"使用预设名称加载字体: {family} 从 {font_file}")
                else:
                    # 如果无法加载字体，使用预设名称
                    if font_file in known_font_mappings:
                        family = known_font_mappings[font_file]
                        self.custom_fonts[family] = font_path
                        font_list.append(family)
                        font_count += 1
                        print(f"字体无法加载但使用预设名称: {family} 从 {font_file}")
            except Exception as e:
                print(f"加载字体时出错: {font_file} - {str(e)}")
                # 出错也使用预设名称
                if font_file in known_font_mappings:
                    family = known_font_mappings[font_file]
                    self.custom_fonts[family] = font_path
                    font_list.append(family)
                    font_count += 1
                    print(f"加载出错但使用预设名称: {family} 从 {font_file}")
                import traceback
                traceback.print_exc()
        
        # 添加预设名称
        if not font_list:
            # 如果上面的方法都失败了，直接使用预设名称
            for font_file, family in known_font_mappings.items():
                font_path = os.path.join(font_dir, font_file)
                if os.path.exists(font_path):
                    print(f"直接使用预设名称: {family}")
                    self.custom_fonts[family] = font_path
                    font_list.append(family)
                    font_count += 1
        
        # 保存字体列表用于UI显示
        self.font_list = font_list
        print(f"共加载 {font_count} 个自定义字体: {font_list}")
        
        # 打印系统中所有可用字体
        all_fonts = QFontDatabase().families()
        print(f"系统中所有可用字体: {all_fonts}")
        
        # 返回字体列表供UI使用
        return font_list 