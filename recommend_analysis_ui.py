#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QPushButton, QComboBox, QTableWidget, 
                           QTableWidgetItem, QDateEdit, QSpinBox, QLineEdit,
                           QTabWidget, QTextBrowser, QHeaderView,
                           QFileDialog, QAbstractItemView, QCheckBox,
                           QStatusBar, QMessageBox, QSplitter)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QBrush

class RecommendAnalysisUI(object):
    """推荐测评分析系统UI界面类"""
    
    def setupUi(self, MainWindow):
        # 设置主窗口基本属性
        MainWindow.setObjectName("RecommendAnalysisWindow")
        MainWindow.resize(1400, 900)  # 增加初始窗口大小
        MainWindow.setWindowTitle("作品推荐测评分析系统")
        
        # 创建中央控件
        self.centralwidget = QWidget(MainWindow)
        
        # 设置全局样式表
        self.centralwidget.setStyleSheet("""
            /* 基础按钮样式 */
            QPushButton {
                height: 30px;
                min-width: 90px;
                max-width: 120px;
                padding: 0 10px;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                background-color: white;
                color: #606266;
            }
            QPushButton:hover {
                background-color: #ecf5ff;
                border-color: #c6e2ff;
                color: #409eff;
            }
            QPushButton:pressed {
                background-color: #409eff;
                color: white;
                border-color: #409eff;
            }
            
            /* 主要按钮样式 */
            QPushButton[type="primary"] {
                background-color: #409eff;
                color: white;
                border-color: #409eff;
            }
            QPushButton[type="primary"]:hover {
                background-color: #66b1ff;
                border-color: #66b1ff;
                color: white;
            }
            QPushButton[type="primary"]:pressed {
                background-color: #3a8ee6;
                border-color: #3a8ee6;
            }
            
            /* 成功按钮样式 */
            QPushButton[type="success"] {
                background-color: #67c23a;
                color: white;
                border-color: #67c23a;
            }
            QPushButton[type="success"]:hover {
                background-color: #85ce61;
                border-color: #85ce61;
                color: white;
            }
            QPushButton[type="success"]:pressed {
                background-color: #5daf34;
                border-color: #5daf34;
            }
            
            /* 警告按钮样式 */
            QPushButton[type="warning"] {
                background-color: #e6a23c;
                color: white;
                border-color: #e6a23c;
            }
            QPushButton[type="warning"]:hover {
                background-color: #ebb563;
                border-color: #ebb563;
                color: white;
            }
            QPushButton[type="warning"]:pressed {
                background-color: #cf9236;
                border-color: #cf9236;
            }
            
            /* 危险按钮样式 */
            QPushButton[type="danger"] {
                background-color: #f56c6c;
                color: white;
                border-color: #f56c6c;
            }
            QPushButton[type="danger"]:hover {
                background-color: #f78989;
                border-color: #f78989;
                color: white;
            }
            QPushButton[type="danger"]:pressed {
                background-color: #dd6161;
                border-color: #dd6161;
            }
            
            /* 信息按钮样式 */
            QPushButton[type="info"] {
                background-color: #909399;
                color: white;
                border-color: #909399;
            }
            QPushButton[type="info"]:hover {
                background-color: #a6a9ad;
                border-color: #a6a9ad;
                color: white;
            }
            QPushButton[type="info"]:pressed {
                background-color: #82848a;
                border-color: #82848a;
            }
            
            /* 小按钮样式 */
            QPushButton[size="small"] {
                height: 24px;
                min-width: 60px;
                max-width: 80px;
                font-size: 11px;
                padding: 0 8px;
            }
            
            /* 标签页工具栏按钮 */
            QTabWidget QPushButton {
                height: 26px;
                min-width: 80px;
            }
            
            /* 表单控件样式 */
            QComboBox, QLineEdit, QDateEdit, QSpinBox {
                height: 30px;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 0 10px;
            }
            
            /* 标签样式 */
            QLabel {
                font-size: 12pt;
            }
            
            /* 表格样式 */
            QTableWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                gridline-color: #f2f2f2;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #ecf5ff;
                color: #409eff;
            }
            
            /* 文件夹按钮样式 */
            QPushButton[objectName="folderButton"] {
                height: 28px;
                min-width: 90px;
                max-width: 90px;
                background-color: #409eff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0;
                font-size: 12px;
            }
            QPushButton[objectName="folderButton"]:hover {
                background-color: #66b1ff;
            }
            QPushButton[objectName="folderButton"]:pressed {
                background-color: #3a8ee6;
            }
            
            /* 文件夹信息样式 */
            QLabel[objectName="folderLabel"] {
                font-size: 11px;
                color: #606266;
            }
            QLabel[objectName="folderCount"] {
                font-size: 11px;
                color: #409eff;
                font-weight: bold;
            }
        """)
        
        # 创建主布局
        self.mainLayout = QVBoxLayout(self.centralwidget)
        self.mainLayout.setContentsMargins(5, 5, 5, 5)  # 减小主布局边距
        self.mainLayout.setSpacing(5)  # 减小主布局间距
        
        # === 顶部工具栏 ===
        self.toolbarLayout = QHBoxLayout()
        self.toolbarLayout.setContentsMargins(0, 0, 0, 0)  # 减小边距
        self.toolbarLayout.setSpacing(8)  # 减小控件间距
        
        # 搜索框
        self.searchLabel = QLabel("搜索:")
        self.toolbarLayout.addWidget(self.searchLabel)
        
        self.searchInput = QLineEdit()
        self.searchInput.setPlaceholderText("输入昵称或appId进行搜索...")
        self.searchInput.setMinimumWidth(300)  # 加宽搜索框以便显示更多文字
        self.toolbarLayout.addWidget(self.searchInput)
        
        # 登录按钮
        self.loginButton = QPushButton("登录新账号")
        self.loginButton.setProperty("type", "primary")
        self.toolbarLayout.addWidget(self.loginButton)
        
        # 读取子账号按钮
        self.subAccountButton = QPushButton("读取子账号")
        self.subAccountButton.setProperty("type", "info")
        self.toolbarLayout.addWidget(self.subAccountButton)
        
        # 清除选中按钮
        self.clearSelectedButton = QPushButton("清除选中")
        self.clearSelectedButton.setProperty("type", "danger")
        self.toolbarLayout.addWidget(self.clearSelectedButton)
        
        # 全选按钮
        self.selectAllButton = QPushButton("全选")
        self.selectAllButton.setProperty("type", "primary")
        self.selectAllButton.setProperty("size", "small")
        self.selectAllButton.setFixedWidth(70)
        self.toolbarLayout.addWidget(self.selectAllButton)
        
        # 全不选按钮
        self.deselectAllButton = QPushButton("全不选")
        self.deselectAllButton.setProperty("type", "info")
        self.deselectAllButton.setProperty("size", "small")
        self.deselectAllButton.setFixedWidth(70)
        self.toolbarLayout.addWidget(self.deselectAllButton)
        
        # 清空所有数据按钮
        self.clearAllDataButton = QPushButton("清空所有数据")
        self.clearAllDataButton.setProperty("type", "danger")
        self.toolbarLayout.addWidget(self.clearAllDataButton)
        
        # 保持登录选项
        self.keepLoginCheck = QCheckBox("是否保持登入")
        self.keepLoginCheck.setChecked(True)
        self.toolbarLayout.addWidget(self.keepLoginCheck)
        
        self.mainLayout.addLayout(self.toolbarLayout)
        
        # 使用垂直拆分器，让账号表和下面的选项卡可以调整大小
        self.mainSplitter = QSplitter(Qt.Vertical)
        self.mainSplitter.setChildrenCollapsible(False)
        
        # === 账号表格 ===
        self.accountTable = QTableWidget()
        self.accountTable.setColumnCount(16)  # 增加列数，分开显示文件夹路径和视频数量
        self.accountTable.setHorizontalHeaderLabels([
            "选择", "序号", "appId", "账号名称", "今日视频数量", "今日推荐数量", 
            "今日播放量", "是否过画风", "Cookie状态", "上传总数", "话题设置", "文件配置",
            "文字配置", "文件夹路径", "视频数量", "操作"
        ])
        
        # 设置账号表格属性
        self.accountTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.accountTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.accountTable.setAlternatingRowColors(True)
        self.accountTable.verticalHeader().setVisible(False)
        self.accountTable.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.accountTable.horizontalHeader().setStretchLastSection(True)
        self.accountTable.setMinimumHeight(700)  # 增加最小高度，确保显示更多行
        
        # 设置列宽
        self.accountTable.setColumnWidth(0, 50)   # 选择
        self.accountTable.setColumnWidth(1, 50)   # 序号
        self.accountTable.setColumnWidth(2, 150)  # appId
        self.accountTable.setColumnWidth(3, 120)  # 账号名称
        self.accountTable.setColumnWidth(4, 90)   # 今日视频数量
        self.accountTable.setColumnWidth(5, 90)   # 今日推荐数量
        self.accountTable.setColumnWidth(6, 80)   # 今日播放量
        self.accountTable.setColumnWidth(7, 80)   # 是否过画风
        self.accountTable.setColumnWidth(8, 90)   # Cookie状态
        self.accountTable.setColumnWidth(9, 80)   # 上传总数
        self.accountTable.setColumnWidth(10, 80)  # 话题设置
        self.accountTable.setColumnWidth(11, 80)  # 文件配置
        self.accountTable.setColumnWidth(12, 80)  # 文字配置
        self.accountTable.setColumnWidth(13, 250) # 文件夹路径，增加宽度以显示完整路径
        self.accountTable.setColumnWidth(14, 80)  # 视频数量
        self.accountTable.setColumnWidth(15, 100) # 操作
        
        # 添加账号表格到拆分器
        self.mainSplitter.addWidget(self.accountTable)
        
        # === 选项卡 ===
        self.tabWidget = QTabWidget()
        
        # 创建标签页
        self.createAnalysisTab()  # 创建作品分析标签页
        self.createUploadTab()    # 创建上传标签页
        self.createManageTab()    # 创建测试管理标签页
        self.createLogTab()       # 创建日志标签页
        
        # 添加选项卡到拆分器
        self.mainSplitter.addWidget(self.tabWidget)
        
        # 设置拆分比例，使账号表格占更多空间
        self.mainSplitter.setSizes([800, 200])
        
        # 将拆分器添加到主布局
        self.mainLayout.addWidget(self.mainSplitter)
        
        # 设置中央控件
        MainWindow.setCentralWidget(self.centralwidget)
        
        # 创建状态栏
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.showMessage("作品推荐测评分析系统 - 就绪")
        MainWindow.setStatusBar(self.statusbar)
        
    def createUploadTab(self):
        """创建上传标签页"""
        # 创建上传标签页
        self.uploadTab = QWidget()
        self.uploadTabLayout = QVBoxLayout(self.uploadTab)
        self.uploadTabLayout.setContentsMargins(8, 8, 8, 8)  # 减小边距
        self.uploadTabLayout.setSpacing(8)  # 减小控件间距
        
        # 添加标题标签
        uploadLabel = QLabel("上传管理")
        uploadLabel.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 15px;")
        self.uploadTabLayout.addWidget(uploadLabel)
        
        # 添加描述
        descLabel = QLabel("在此页面可以管理账号的上传任务、设置话题和批量上传视频。")
        descLabel.setStyleSheet("font-size: 11pt; color: #606266; margin-bottom: 10px;")
        self.uploadTabLayout.addWidget(descLabel)
        
        # 添加说明
        self.uploadTabLayout.addWidget(QLabel("请先在账号列表中为账号绑定上传文件夹，然后在此页面设置上传参数。"))
        
        # 添加上传标签页到标签组件
        self.tabWidget.addTab(self.uploadTab, "上传管理")
        
    def log_message(self, message):
        """添加日志消息到日志框"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        self.logTextBrowser.append(log_line)
        self.logTextBrowser.verticalScrollBar().setValue(
            self.logTextBrowser.verticalScrollBar().maximum()
        ) 

    # --- 测试管理标签页 ---
    def createManageTab(self):
        """创建测试管理标签页"""
        self.manageTab = QWidget()
        self.manageLayout = QVBoxLayout(self.manageTab)
        self.manageLayout.setContentsMargins(8, 8, 8, 8)  # 减小边距
        self.manageLayout.setSpacing(8)  # 减小控件间距

        # 文件夹管理工具栏
        self.folderToolbar = QHBoxLayout()
        self.folderToolbar.setContentsMargins(0, 0, 0, 0)  # 减小边距
        self.folderToolbar.setSpacing(8)  # 减小控件间距
        
        self.addFolderButton = QPushButton("添加文件夹")
        self.addFolderButton.setProperty("type", "success")
        self.folderToolbar.addWidget(self.addFolderButton)

        self.removeFolderButton = QPushButton("删除文件夹")
        self.removeFolderButton.setProperty("type", "danger")
        self.folderToolbar.addWidget(self.removeFolderButton)

        self.editFolderButton = QPushButton("修改上限")
        self.editFolderButton.setProperty("type", "warning")
        self.folderToolbar.addWidget(self.editFolderButton)

        self.refreshFolderButton = QPushButton("刷新列表")
        self.refreshFolderButton.setProperty("type", "info")
        self.folderToolbar.addWidget(self.refreshFolderButton)

        self.viewLogButtonTest = QPushButton("查看日志")
        self.viewLogButtonTest.setProperty("type", "info")
        self.folderToolbar.addWidget(self.viewLogButtonTest)

        self.folderToolbar.addStretch()
        self.manageLayout.addLayout(self.folderToolbar)

        # 创建管理标签页的拆分器
        self.manageSplitter = QSplitter(Qt.Vertical)
        self.manageSplitter.setChildrenCollapsible(False)

        # 文件夹表格
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

        # 添加文件夹表格到拆分器
        self.manageSplitter.addWidget(self.folderTableWidget)

        # 创建测试控制面板
        self.testControlPanel = QWidget()
        self.testControlLayout = QVBoxLayout(self.testControlPanel)
        self.testControlLayout.setContentsMargins(0, 10, 0, 0)

        # 测试控制布局
        self.testControlLayout.addWidget(QLabel("测试控制:"))
        self.testButtonLayout = QHBoxLayout()

        self.uploadIntervalLabel = QLabel("上传间隔(分钟):")
        self.testButtonLayout.addWidget(self.uploadIntervalLabel)

        self.uploadIntervalSpinBox = QSpinBox()
        self.uploadIntervalSpinBox.setMinimum(1)
        self.uploadIntervalSpinBox.setMaximum(60)
        self.uploadIntervalSpinBox.setValue(5)
        self.testButtonLayout.addWidget(self.uploadIntervalSpinBox)

        self.startTestButton = QPushButton("开始测评")
        self.startTestButton.setProperty("type", "success")
        self.startTestButton.setFixedWidth(100)
        self.testButtonLayout.addWidget(self.startTestButton)

        self.stopTestButton = QPushButton("停止测评")
        self.stopTestButton.setEnabled(False)
        self.stopTestButton.setProperty("type", "danger")
        self.stopTestButton.setFixedWidth(100)
        self.testButtonLayout.addWidget(self.stopTestButton)

        self.testButtonLayout.addStretch()
        self.testControlLayout.addLayout(self.testButtonLayout)

        # 添加测试控制面板到拆分器
        self.manageSplitter.addWidget(self.testControlPanel)

        # 设置拆分器比例
        self.manageSplitter.setSizes([700, 100])

        # 将拆分器添加到布局
        self.manageLayout.addWidget(self.manageSplitter)

        # 添加测试管理标签页到选项卡
        self.tabWidget.addTab(self.manageTab, "测试管理") 

    def createAnalysisTab(self):
        """创建作品分析标签页"""
        self.analysisTab = QWidget()
        self.analysisLayout = QVBoxLayout(self.analysisTab)
        self.analysisLayout.setContentsMargins(8, 8, 8, 8)  # 减小边距
        self.analysisLayout.setSpacing(8)  # 减小控件间距
        
        # 查询条件工具栏
        self.queryToolbar = QHBoxLayout()
        self.queryToolbar.setContentsMargins(0, 0, 0, 0)  # 减小边距
        self.queryToolbar.setSpacing(8)  # 减小控件间距
        
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
        self.queryButton.setProperty("type", "success")
        self.queryToolbar.addWidget(self.queryButton)
        
        # 导出按钮
        self.exportButton = QPushButton("导出数据")
        self.exportButton.setProperty("type", "primary")
        self.queryToolbar.addWidget(self.exportButton)
        
        # 查看日志按钮
        self.viewLogButton = QPushButton("查看日志")
        self.viewLogButton.setProperty("type", "info")
        self.queryToolbar.addWidget(self.viewLogButton)
        
        self.queryToolbar.addStretch()
        
        self.analysisLayout.addLayout(self.queryToolbar)
        
        # 创建水平拆分器
        self.analysisSplitter = QSplitter(Qt.Vertical)
        self.analysisSplitter.setChildrenCollapsible(False)
        
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
        
        # 添加数据表格到拆分器
        self.analysisSplitter.addWidget(self.dataTableWidget)
        
        # 创建统计信息面板
        self.statsPanel = QWidget()
        self.statsPanelLayout = QVBoxLayout(self.statsPanel)
        self.statsPanelLayout.setContentsMargins(0, 0, 0, 0)
        
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
        
        self.statsPanelLayout.addLayout(self.statsLayout)
        
        # 添加统计面板到拆分器
        self.analysisSplitter.addWidget(self.statsPanel)
        
        # 设置拆分器比例
        self.analysisSplitter.setSizes([700, 100])
        
        # 将拆分器添加到布局
        self.analysisLayout.addWidget(self.analysisSplitter)
        
        # 添加分析标签页到选项卡
        self.tabWidget.addTab(self.analysisTab, "作品分析")

    def createLogTab(self):
        """创建运行日志标签页"""
        self.logTab = QWidget()
        self.logLayout = QVBoxLayout(self.logTab)
        self.logLayout.setContentsMargins(8, 8, 8, 8)  # 减小边距
        self.logLayout.setSpacing(8)  # 减小控件间距
        
        # 日志工具栏
        self.logToolbar = QHBoxLayout()
        self.logToolbar.setContentsMargins(0, 0, 0, 0)  # 减小边距
        self.logToolbar.setSpacing(8)  # 减小控件间距
        
        self.clearLogButton = QPushButton("清空日志")
        self.clearLogButton.setProperty("type", "danger")
        self.clearLogButton.setFixedWidth(100)
        self.logToolbar.addWidget(self.clearLogButton)
        
        self.saveLogButton = QPushButton("保存日志")
        self.saveLogButton.setProperty("type", "success")
        self.saveLogButton.setFixedWidth(100)
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