#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QSplashScreen, QTableWidget
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QPixmap
from datetime import datetime

from recommend_analysis_ui import RecommendAnalysisUI
from account_manager import AccountManager
from folder_manager import FolderManager
from video_analyzer import VideoAnalyzer
from chart_manager import ChartManager
from database import db_manager

class RecommendAnalysis(QMainWindow):
    """支付宝上传和分析工具主窗口类"""
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化数据库
        try:
            if hasattr(db_manager, 'initialize_database'):
                db_manager.initialize_database()
            else:
                print("错误：数据库管理器缺少initialize_database方法")
        except Exception as e:
            print(f"数据库初始化失败: {str(e)}")
            traceback.print_exc()
        
        # 初始化UI
        self.ui = RecommendAnalysisUI()
        self.ui.setupUi(self)
        self.setWindowTitle("支付宝上传和分析工具")
        
        # 设置初始UI状态
        self.setup_initial_ui()
        
        # 初始化功能模块
        self.account_manager = AccountManager(
            ui=self.ui, 
            parent=self, 
            log_callback=self.log_message
        )
        
        self.folder_manager = FolderManager(
            ui=self.ui, 
            parent=self, 
            log_callback=self.log_message
        )
        
        self.video_analyzer = VideoAnalyzer(
            ui=self.ui, 
            parent=self, 
            log_callback=self.log_message
        )
        
        self.chart_manager = ChartManager(
            parent=self, 
            log_callback=self.log_message
        )
        
        # 连接信号
        self.setup_signals()
        
        # 加载数据
        try:
            if hasattr(self.account_manager, 'load_accounts'):
                self.account_manager.load_accounts()
            else:
                print("错误：account_manager缺少load_accounts方法")
        except Exception as e:
            print(f"加载账号数据失败: {str(e)}")
            traceback.print_exc()
        
        # 显示欢迎信息
        self.log_message("欢迎使用支付宝上传和分析工具")
        
        # 记录是否有正在运行的任务
        self.running_tasks = False
        
        # 选中默认标签页
        self.ui.tabWidget.setCurrentIndex(0)
        
        # 自动加载今日视频数据
        self.refresh_all_data()
    
    def safe_log(self, message):
        """安全的日志记录方法，不依赖UI
        
        Args:
            message: 日志消息
        """
        print(message)  # 始终打印到控制台
        if hasattr(self, 'ui') and hasattr(self.ui, 'logTextBrowser'):
            self.ui.logTextBrowser.append(message)
            # 滚动到底部
            self.ui.logTextBrowser.verticalScrollBar().setValue(
                self.ui.logTextBrowser.verticalScrollBar().maximum()
            )
    
    def init_database(self):
        """初始化数据库"""
        try:
            # 确保数据库表已创建
            if hasattr(db_manager, 'initialize_database'):
                db_manager.initialize_database()
                self.safe_log("数据库初始化成功")
            else:
                self.safe_log("警告：数据库管理器缺少initialize_database方法")
        except Exception as e:
            self.safe_log(f"数据库初始化失败: {str(e)}")
            traceback.print_exc()
    
    def refresh_all_data(self):
        """刷新所有数据显示"""
        try:
            # 加载账号列表
            if hasattr(self.account_manager, 'load_accounts'):
                self.account_manager.load_accounts()
            
            # 加载视频数据
            today_date = self.ui.dateEdit.date().toString('yyyy-MM-dd') if hasattr(self.ui, 'dateEdit') else None
            
            if not today_date:
                today_date = datetime.now().strftime('%Y-%m-%d')
            
            try:
                # 1. 首先尝试使用send_time查询今日发布的视频
                if hasattr(db_manager, 'get_today_published_videos'):
                    videos = db_manager.get_today_published_videos()
                    if not videos:
                        # 2. 如果没有今日发布的视频，尝试使用指定日期查询
                        if hasattr(db_manager, 'get_videos_by_date'):
                            videos = db_manager.get_videos_by_date(today_date)
                            if not videos:
                                # 3. 如果指定日期没有视频，尝试获取今日视频
                                videos = db_manager.get_today_videos()
                        else:
                            # 回退到只获取今日视频
                            videos = db_manager.get_today_videos()
                else:
                    # 回退到其他查询方式
                    if hasattr(db_manager, 'get_videos_by_date'):
                        videos = db_manager.get_videos_by_date(today_date)
                        if not videos:
                            videos = db_manager.get_today_videos()
                    else:
                        videos = db_manager.get_today_videos()
                
                if videos:
                    # 显示视频数据到UI
                    if hasattr(self.video_analyzer, 'update_data_table'):
                        self.video_analyzer.update_data_table(videos)
                        self.log_message(f"成功加载 {len(videos)} 条视频数据")
                    else:
                        self.log_message("无法更新视频数据表格")
                else:
                    # 清空表格
                    if hasattr(self.ui, 'dataTableWidget') and hasattr(self.ui.dataTableWidget, 'setRowCount'):
                        self.ui.dataTableWidget.setRowCount(0)
                        self.log_message("没有找到视频数据，已清空数据表格")
            except Exception as e:
                self.log_message(f"加载视频数据时出错: {str(e)}")
                traceback.print_exc()

        except Exception as e:
            self.log_message(f"刷新数据时出错: {str(e)}")
            traceback.print_exc()
    
    def setup_initial_ui(self):
        """设置初始UI状态"""
        try:
            # 设置日期选择器的范围
            today = QDate.currentDate()
            last_month = today.addMonths(-1)
            
            if hasattr(self.ui, 'dateEdit'):
                self.ui.dateEdit.setDate(today)
            
            # 设置表格属性
            for table_name in ['accountTable', 'dataTableWidget', 'folderTableWidget']:
                if hasattr(self.ui, table_name):
                    table = getattr(self.ui, table_name)
                    # 设置交替行颜色
                    table.setAlternatingRowColors(True)
            
            # 设置日志文本框
            if hasattr(self.ui, 'logTextBrowser'):
                self.ui.logTextBrowser.document().setMaximumBlockCount(1000)  # 限制最大行数
                
        except Exception as e:
            print(f"设置初始UI状态时出错: {str(e)}")
            traceback.print_exc()
    
    def setup_signals(self):
        """连接信号和槽"""
        try:
            # 查询按钮
            if hasattr(self.ui, 'queryButton'):
                self.ui.queryButton.clicked.connect(self.video_analyzer.query_selected_accounts)
            
            # 登录新账号按钮
            if hasattr(self.ui, 'loginButton'):
                self.ui.loginButton.clicked.connect(self.account_manager.login_new_account)
            
            # 读取子账号按钮
            if hasattr(self.ui, 'subAccountButton'):
                self.ui.subAccountButton.clicked.connect(self.account_manager.fetch_sub_accounts)
            
            # 文件夹管理按钮
            if hasattr(self.ui, 'addFolderButton'):
                self.ui.addFolderButton.clicked.connect(self.folder_manager.add_folder)
            
            if hasattr(self.ui, 'removeFolderButton'):
                self.ui.removeFolderButton.clicked.connect(self.folder_manager.remove_folder)
            
            if hasattr(self.ui, 'editFolderButton'):
                self.ui.editFolderButton.clicked.connect(self.folder_manager.edit_folder_limit)
            
            if hasattr(self.ui, 'refreshFolderButton'):
                self.ui.refreshFolderButton.clicked.connect(self.folder_manager.view_folders)
            
            # 视频数据刷新按钮
            if hasattr(self.ui, 'refreshDataButton'):
                self.ui.refreshDataButton.clicked.connect(self.refresh_all_data)
            
            # 账号列表选择变化事件
            if hasattr(self.ui, 'accountTable'):
                self.ui.accountTable.itemSelectionChanged.connect(
                    lambda: self.folder_manager.view_folders() if hasattr(self.folder_manager, 'view_folders') else None
                )
            
            # 日志清空按钮
            if hasattr(self.ui, 'clearLogButton'):
                self.ui.clearLogButton.clicked.connect(
                    lambda: self.ui.logTextBrowser.clear() if hasattr(self.ui, 'logTextBrowser') else None
                )
            
            # 全选/全不选按钮
            if hasattr(self.ui, 'selectAllButton'):
                self.ui.selectAllButton.clicked.connect(
                    lambda: self.account_manager.select_all_accounts() if hasattr(self.account_manager, 'select_all_accounts') else None
                )
            
            if hasattr(self.ui, 'deselectAllButton'):
                self.ui.deselectAllButton.clicked.connect(
                    lambda: self.account_manager.deselect_all_accounts() if hasattr(self.account_manager, 'deselect_all_accounts') else None
                )
            
            # 清空所有数据按钮
            if hasattr(self.ui, 'clearAllDataButton'):
                self.ui.clearAllDataButton.clicked.connect(
                    lambda: self.account_manager.clear_account_data(clear_all=True) if hasattr(self.account_manager, 'clear_account_data') else None
                )
            
        except Exception as e:
            print(f"连接信号时出错: {str(e)}")
            traceback.print_exc()
    
    def log_message(self, message):
        """记录日志消息
        
        Args:
            message: 日志消息
        """
        try:
            if hasattr(self.ui, 'logTextBrowser'):
                self.ui.logTextBrowser.append(message)
                # 滚动到底部
                self.ui.logTextBrowser.verticalScrollBar().setValue(
                    self.ui.logTextBrowser.verticalScrollBar().maximum()
                )
            # 同时打印到控制台
            print(message)
        except Exception as e:
            print(f"记录日志时出错: {str(e)}")
            traceback.print_exc()
    
    def closeEvent(self, event):
        """窗口关闭事件处理
        
        Args:
            event: 关闭事件
        """
        try:
            # 检查是否有正在运行的任务
            if self.running_tasks:
                reply = QMessageBox.question(
                    self, "确认退出", 
                    "当前有任务正在运行，确定要退出吗？",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    event.ignore()
                    return
            
            # 确认退出
            reply = QMessageBox.question(
                self, "确认退出", 
                "确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 关闭所有线程
                if hasattr(self.video_analyzer, 'query_threads'):
                    for thread in self.video_analyzer.query_threads:
                        if thread.isRunning():
                            thread.terminate()
                            thread.wait()
                
                event.accept()
            else:
                event.ignore()
                
        except Exception as e:
            print(f"窗口关闭事件处理时出错: {str(e)}")
            traceback.print_exc()
            event.accept()  # 确保能够关闭

def main():
    """程序入口"""
    try:
        app = QApplication(sys.argv)
        
        # 创建并显示启动画面
        splash_pix = QPixmap("logo.png")
        if splash_pix.isNull():
            splash_pix = QPixmap(400, 300)
            splash_pix.fill(Qt.white)
        
        splash = QSplashScreen(splash_pix)
        splash.show()
        app.processEvents()
        
        # 创建主窗口
        window = RecommendAnalysis()
        
        # 显示主窗口并关闭启动画面
        window.show()
        splash.finish(window)
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"启动程序时出错: {str(e)}")
        traceback.print_exc()
        
        # 显示错误对话框
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Critical)
        error_msg.setWindowTitle("启动错误")
        error_msg.setText("程序启动失败")
        error_msg.setInformativeText(f"错误详情:\n{str(e)}")
        error_msg.setDetailedText(traceback.format_exc())
        error_msg.exec_()
        
        sys.exit(1)

if __name__ == "__main__":
    main() 