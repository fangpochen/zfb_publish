#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QPushButton, QComboBox, QTableWidget, 
                           QTableWidgetItem, QDateEdit, QSpinBox, QLineEdit,
                           QTabWidget, QTextBrowser, QHeaderView,
                           QFileDialog, QAbstractItemView, QCheckBox,
                           QStatusBar, QMessageBox)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QBrush

class RecommendAnalysisUI(object):
    """推荐测评分析系统UI界面类"""
    
    def setupUi(self, MainWindow):
        # 设置主窗口基本属性
        MainWindow.setObjectName("RecommendAnalysisWindow")
        MainWindow.resize(1200, 800)
        MainWindow.setWindowTitle("作品推荐测评分析系统")
        
        # 创建中央控件
        self.centralwidget = QWidget(MainWindow)
        
        # 设置全局样式表
        self.centralwidget.setStyleSheet("""
            QPushButton {
                height: 30px;
                padding: 0 15px;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ecf5ff;
                border-color: #409eff;
                color: #409eff;
            }
            QComboBox, QLineEdit, QDateEdit, QSpinBox {
                height: 30px;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 0 10px;
            }
            QLabel {
                font-size: 12pt;
            }
        """)
        
        # 创建主布局
        self.mainLayout = QVBoxLayout(self.centralwidget)
        self.mainLayout.setContentsMargins(10, 10, 10, 10)
        self.mainLayout.setSpacing(10)
        
        # === 顶部工具栏 ===
        self.toolbarLayout = QHBoxLayout()
        
        # 搜索框
        self.searchLabel = QLabel("搜索:")
        self.toolbarLayout.addWidget(self.searchLabel)
        
        self.searchInput = QLineEdit()
        self.searchInput.setPlaceholderText("输入昵称或appId进行搜索...")
        self.searchInput.setMinimumWidth(300)  # 加宽搜索框以便显示更多文字
        self.toolbarLayout.addWidget(self.searchInput)
        
        # 登录按钮
        self.loginButton = QPushButton("登录新账号")
        self.loginButton.setStyleSheet("""
            QPushButton {
                background-color: #409eff;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #66b1ff;
                color: white;
            }
        """)
        self.toolbarLayout.addWidget(self.loginButton)
        
        # 读取子账号按钮
        self.subAccountButton = QPushButton("读取子账号")
        self.toolbarLayout.addWidget(self.subAccountButton)
        
        # 清除选中按钮
        self.clearSelectedButton = QPushButton("清除选中")
        self.clearSelectedButton.setStyleSheet("""
            QPushButton {
                background-color: #f56c6c;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f78989;
                color: white;
            }
        """)
        self.toolbarLayout.addWidget(self.clearSelectedButton)
        
        # 全选按钮
        self.selectAllButton = QPushButton("全选")
        self.selectAllButton.setStyleSheet("""
            QPushButton {
                background-color: #409eff;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #66b1ff;
                color: white;
            }
        """)
        self.toolbarLayout.addWidget(self.selectAllButton)
        
        # 全不选按钮
        self.deselectAllButton = QPushButton("全不选")
        self.deselectAllButton.setStyleSheet("""
            QPushButton {
                background-color: #909399;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a6a9ad;
                color: white;
            }
        """)
        self.toolbarLayout.addWidget(self.deselectAllButton)
        
        # 清空所有数据按钮
        self.clearAllDataButton = QPushButton("清空所有数据")
        self.clearAllDataButton.setStyleSheet("""
            QPushButton {
                background-color: #ff4949;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6d6d;
                color: white;
            }
        """)
        self.toolbarLayout.addWidget(self.clearAllDataButton)
        
        # 保持登录选项
        self.keepLoginCheck = QCheckBox("是否保持登入")
        self.keepLoginCheck.setChecked(True)
        self.toolbarLayout.addWidget(self.keepLoginCheck)
        
        self.mainLayout.addLayout(self.toolbarLayout)
        
        # === 账号列表表格 ===
        self.accountTable = QTableWidget()
        self.accountTable.setColumnCount(15)
        self.accountTable.setHorizontalHeaderLabels([
            "选择", "序号", "appId", "账号名称", "今日视频数量", "今日推荐数量", "今日播放量", "是否过画风",
            "Cookie状态", "上传总数", "话题设置", "删除不可推荐", "文件总数",
            "是否是主账号", "操作"
        ])
        # 设置第一列可勾选
        self.accountTable.setColumnWidth(0, 50)  # 设置勾选框列的宽度
        # 设置其他列属性
        self.accountTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.accountTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.accountTable.setAlternatingRowColors(True)
        self.accountTable.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QPushButton {
                min-width: 80px;
                padding: 2px 10px;
                border: none;
                border-radius: 2px;
                color: white;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
        """)
        
        self.mainLayout.addWidget(self.accountTable)
        
        # === 选项卡 ===
        self.tabWidget = QTabWidget()
        
        # --- 作品分析选项卡 ---
        self.analysisTab = QWidget()
        self.analysisLayout = QVBoxLayout(self.analysisTab)
        
        # 查询条件工具栏
        self.queryToolbar = QHBoxLayout()
        
        # 日期选择
        self.dateLabel = QLabel("查询日期:")
        self.queryToolbar.addWidget(self.dateLabel)
        
        self.dateEdit = QDateEdit()
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setDate(QDate.currentDate())
        self.queryToolbar.addWidget(self.dateEdit)
        
        # 删除提示文字
        self.selectionHintLabel = QLabel("")
        # 或者完全隐藏该标签
        self.selectionHintLabel.setVisible(False)
        
        # 查询按钮
        self.queryButton = QPushButton("分析视频")
        self.queryButton.setStyleSheet("""
            QPushButton {
                background-color: #67c23a;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #85ce61;
                color: white;
            }
        """)
        self.queryToolbar.addWidget(self.queryButton)
        
        # 导出按钮
        self.exportButton = QPushButton("导出数据")
        self.exportButton.setStyleSheet("""
            QPushButton {
                background-color: #409EFF;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #66b1ff;
                color: white;
            }
        """)
        self.queryToolbar.addWidget(self.exportButton)
        
        # 查看日志按钮
        self.viewLogButton = QPushButton("查看日志")
        self.viewLogButton.setStyleSheet("""
            QPushButton {
                background-color: #909399;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a6a9ad;
                color: white;
            }
        """)
        self.queryToolbar.addWidget(self.viewLogButton)
        
        self.queryToolbar.addStretch()
        
        self.analysisLayout.addLayout(self.queryToolbar)
        
        # 数据表格
        self.dataTableWidget = QTableWidget()
        self.dataTableWidget.setColumnCount(8)
        self.dataTableWidget.setHorizontalHeaderLabels([
            "作品ID", "标题", "发布时间", "播放量", 
            "点赞数", "评论数", "推荐状态", "异常状态"
        ])
        self.dataTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dataTableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dataTableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dataTableWidget.setAlternatingRowColors(True)
        # 启用排序功能
        self.dataTableWidget.setSortingEnabled(True)
        self.dataTableWidget.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item[recommend="true"] {
                color: #67c23a;  /* 绿色 */
            }
            QTableWidget::item[recommend="false"] {
                color: #f56c6c;  /* 红色 */
            }
            QTableWidget::item[abnormal="true"] {
                background-color: #fef0f0;  /* 浅红色背景 */
            }
        """)
        
        self.analysisLayout.addWidget(self.dataTableWidget)
        
        # 数据统计栏
        self.statsLayout = QHBoxLayout()
        
        self.totalWorksLabel = QLabel("作品总数: 0")
        self.statsLayout.addWidget(self.totalWorksLabel)
        
        self.recommendedLabel = QLabel("推荐作品数: 0")
        self.statsLayout.addWidget(self.recommendedLabel)
        
        self.avgPlayLabel = QLabel("平均播放量: 0")
        self.statsLayout.addWidget(self.avgPlayLabel)
        
        self.avgLikesLabel = QLabel("平均点赞数: 0")
        self.statsLayout.addWidget(self.avgLikesLabel)
        
        self.statsLayout.addStretch()
        
        self.analysisLayout.addLayout(self.statsLayout)
        
        self.tabWidget.addTab(self.analysisTab, "作品分析")
        
        # --- 测评管理选项卡 ---
        self.testTab = QWidget()
        self.testLayout = QVBoxLayout(self.testTab)
        
        # 文件夹管理区域
        self.folderTableWidget = QTableWidget()
        self.folderTableWidget.setColumnCount(6)
        self.folderTableWidget.setHorizontalHeaderLabels([
            "文件夹路径", "视频总数", "已上传/上限", "状态", "上次上传时间", "操作"
        ])
        self.folderTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.folderTableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.folderTableWidget.setAlternatingRowColors(True)
        self.folderTableWidget.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QPushButton {
                min-width: 60px;
                padding: 2px 10px;
            }
        """)
        
        # 文件夹操作工具栏
        self.folderToolbar = QHBoxLayout()
        
        self.addFolderButton = QPushButton("添加文件夹")
        self.addFolderButton.setStyleSheet("""
            QPushButton {
                background-color: #67c23a;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #85ce61;
            }
        """)
        self.folderToolbar.addWidget(self.addFolderButton)
        
        self.removeFolderButton = QPushButton("删除文件夹")
        self.removeFolderButton.setStyleSheet("""
            QPushButton {
                background-color: #f56c6c;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f78989;
            }
        """)
        self.folderToolbar.addWidget(self.removeFolderButton)
        
        self.editFolderButton = QPushButton("修改上限")
        self.folderToolbar.addWidget(self.editFolderButton)
        
        self.refreshFolderButton = QPushButton("刷新列表")
        self.folderToolbar.addWidget(self.refreshFolderButton)
        
        # 查看日志按钮
        self.viewLogButtonTest = QPushButton("查看日志")
        self.viewLogButtonTest.setStyleSheet("""
            QPushButton {
                background-color: #909399;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a6a9ad;
                color: white;
            }
        """)
        self.folderToolbar.addWidget(self.viewLogButtonTest)
        
        self.folderToolbar.addStretch()
        
        # 测评控制区域
        self.testControlLayout = QHBoxLayout()
        
        self.uploadIntervalLabel = QLabel("上传间隔(分钟):")
        self.testControlLayout.addWidget(self.uploadIntervalLabel)
        
        self.uploadIntervalSpinBox = QSpinBox()
        self.uploadIntervalSpinBox.setMinimum(1)
        self.uploadIntervalSpinBox.setMaximum(60)
        self.uploadIntervalSpinBox.setValue(5)
        self.testControlLayout.addWidget(self.uploadIntervalSpinBox)
        
        self.startTestButton = QPushButton("开始测评")
        self.startTestButton.setStyleSheet("""
            QPushButton {
                background-color: #67c23a;
                color: white;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #85ce61;
            }
        """)
        self.testControlLayout.addWidget(self.startTestButton)
        
        self.stopTestButton = QPushButton("停止测评")
        self.stopTestButton.setEnabled(False)
        self.stopTestButton.setStyleSheet("""
            QPushButton {
                background-color: #f56c6c;
                color: white;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #f78989;
            }
        """)
        self.testControlLayout.addWidget(self.stopTestButton)
        
        self.testControlLayout.addStretch()
        
        # 添加所有组件到测评管理布局
        self.testLayout.addLayout(self.folderToolbar)
        self.testLayout.addWidget(self.folderTableWidget)
        self.testLayout.addLayout(self.testControlLayout)
        
        self.tabWidget.addTab(self.testTab, "测评管理")
        
        # --- 运行日志选项卡 ---
        self.logTab = QWidget()
        self.logLayout = QVBoxLayout(self.logTab)
        
        # 日志工具栏
        self.logToolbar = QHBoxLayout()
        
        self.clearLogButton = QPushButton("清空日志")
        self.clearLogButton.setStyleSheet("""
            QPushButton {
                background-color: #f56c6c;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f78989;
            }
        """)
        self.logToolbar.addWidget(self.clearLogButton)
        
        self.saveLogButton = QPushButton("保存日志")
        self.saveLogButton.setStyleSheet("""
            QPushButton {
                background-color: #67c23a;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #85ce61;
            }
        """)
        self.logToolbar.addWidget(self.saveLogButton)
        
        self.logToolbar.addStretch()
        
        self.logLayout.addLayout(self.logToolbar)
        
        # 日志文本区域
        self.logTextBrowser = QTextBrowser()
        self.logTextBrowser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
            }
        """)
        self.logLayout.addWidget(self.logTextBrowser)
        
        self.tabWidget.addTab(self.logTab, "运行日志")
        
        # 将选项卡添加到主布局
        self.mainLayout.addWidget(self.tabWidget)
        
        # 设置中央控件
        MainWindow.setCentralWidget(self.centralwidget)
        
        # 创建状态栏
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.showMessage("作品推荐测评分析系统 - 就绪")
        MainWindow.setStatusBar(self.statusbar)
        
    def log_message(self, message):
        """添加日志消息到日志框"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        self.logTextBrowser.append(log_line)
        self.logTextBrowser.verticalScrollBar().setValue(
            self.logTextBrowser.verticalScrollBar().maximum()
        ) 