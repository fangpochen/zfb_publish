#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QSplashScreen, QTableWidget, QHeaderView, QCheckBox
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QPixmap
from datetime import datetime

from recommend_analysis_ui import RecommendAnalysisUI
from account_manager import AccountManager
from folder_manager import FolderManager
from video_analyzer import VideoAnalyzer
from chart_manager import ChartManager
from database import db_manager

# 尝试导入key_verification模块，如果不存在则提供一个替代实现
try:
    from key_verification import show_verification_dialog
    HAS_KEY_VERIFICATION = True
except ImportError:
    print("警告: key_verification模块不可用，将跳过验证步骤")
    # 创建替代函数
    def show_verification_dialog():
        print("使用替代验证函数，总是返回True")
        return True
    HAS_KEY_VERIFICATION = False

# 添加标志检查函数
def is_first_run():
    """检查是否是打包后的首次运行"""
    # 检查首次运行标志文件
    flag_file = os.path.join("flags", "FIRST_RUN")
    if os.path.exists(flag_file):
        try:
            with open(flag_file, "r") as f:
                content = f.read().strip()
                if content == "1":
                    # 更新标志文件，标记为非首次运行
                    try:
                        with open(flag_file, "w") as f:
                            f.write("0")
                        print("标记为非首次运行")
                    except Exception as e:
                        print(f"更新首次运行标志失败: {e}")
                    return True
        except Exception as e:
            print(f"读取首次运行标志失败: {e}")
    
    # 如果标志文件不存在或内容不为1，则不是首次运行
    return False

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
        
        # 初始化上传控制器
        from upload_controller import UploadController
        self.upload_controller = UploadController(
            parent=self,
            ui=self.ui,
            account_manager=self.account_manager,
            log_callback=self.log_message
        )
        
        # 连接信号
        self.setup_signals()
        
        # 检查是否首次运行
        if is_first_run():
            self.log_message("检测到首次运行，清空所有账号数据...")
            self.clear_account_data()
        else:
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
        
        # 初始化保持登录计时器
        self.keep_login_timer = QTimer(self)
        self.keep_login_timer.timeout.connect(self.keep_login_alive)
        # 检查保持登录框的初始状态
        self.update_keep_login_timer()
    
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
                    # 允许用户调整列宽
                    if hasattr(table, 'horizontalHeader'):
                        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            
            # 设置拆分器初始比例，更多展示账号表格
            if hasattr(self.ui, 'mainSplitter'):
                total_height = self.height()
                self.ui.mainSplitter.setSizes([int(total_height * 0.5), int(total_height * 0.5)])
            
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
            
            # 清除账号按钮 - 直接连接方法，不使用lambda
            if hasattr(self.ui, 'pushButton_8'):
                self.ui.pushButton_8.clicked.connect(self.remove_selected_accounts)
            
            # 清空所有数据按钮
            if hasattr(self.ui, 'clearAllDataButton'):
                self.ui.clearAllDataButton.clicked.connect(
                    lambda: self.account_manager.clear_account_data(clear_all=True) if hasattr(self.account_manager, 'clear_account_data') else None
                )
            
            # 同步所有账号cookies按钮
            if hasattr(self.ui, 'syncAllAccountsCookiesButton'):
                self.ui.syncAllAccountsCookiesButton.clicked.connect(self.sync_all_accounts_cookies)
            
            # 保持登录复选框
            if hasattr(self.ui, 'keepLoginCheck'):
                self.ui.keepLoginCheck.stateChanged.connect(self.update_keep_login_timer)
            
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

    def sync_all_accounts_cookies(self):
        """同步所有账号的cookies"""
        try:
            # 确保账号管理器已初始化
            if not hasattr(self, 'account_manager'):
                print("账号管理器未初始化")
                return
            
            # 获取最新登录的账号ID
            source_appid = None
            if hasattr(self, 'login_appid') and self.login_appid:
                source_appid = self.login_appid
            
            # 调用账号管理器的方法同步cookies
            success_count, total_count = self.account_manager.sync_all_accounts_cookies(source_appid)
            
            # 显示结果消息
            if success_count > 0:
                QMessageBox.information(self, "同步完成", f"成功同步 {success_count}/{total_count} 个账号的cookies。")
            else:
                QMessageBox.warning(self, "同步失败", "没有账号的cookies被同步，请确保已有有效登录的账号。")
            
        except Exception as e:
            print(f"同步账号cookies时出错: {str(e)}")
            traceback.print_exc()

    def update_keep_login_timer(self):
        """根据keepLoginCheck复选框状态更新保持登录定时器"""
        try:
            if hasattr(self.ui, 'keepLoginCheck'):
                if self.ui.keepLoginCheck.isChecked():
                    # 设置定时器，每10分钟触发一次，时间单位为毫秒
                    self.keep_login_timer.start(10 * 60 * 1000)  
                    self.log_message("已启用保持登录功能，将每10分钟自动刷新登录状态")
                else:
                    # 停止定时器
                    self.keep_login_timer.stop()
                    self.log_message("已停用保持登录功能")
        except Exception as e:
            print(f"更新保持登录定时器时出错: {str(e)}")
            traceback.print_exc()
    
    def keep_login_alive(self):
        """定时调用query_videos来保持登录状态"""
        try:
            # 获取选中的账号
            selected_accounts = self.account_manager.get_selected_accounts()
            if not selected_accounts:
                # 如果没有选中账号，尝试获取第一个有效账号
                all_accounts = self.account_manager.get_all_accounts()
                if all_accounts:
                    selected_accounts = [all_accounts[0]]
                
            if selected_accounts:
                self.log_message("正在执行保持登录操作...")
                for account in selected_accounts:
                    appid = account.get('appid')
                    cookies = account.get('cookies_dict')
                    if cookies and appid:
                        try:
                            # 调用query_videos接口保持登录状态，只请求第一页，最小数据量
                            today = datetime.now().strftime('%Y-%m-%d')
                            self.video_analyzer.api_client.query_videos(cookies, appid, today, 1, 5)
                            self.log_message(f"账号 {appid} 登录状态已刷新")
                        except Exception as e:
                            self.log_message(f"刷新账号 {appid} 登录状态时出错: {str(e)}")
            else:
                self.log_message("没有可用账号，无法执行保持登录操作")
                
        except Exception as e:
            self.log_message(f"保持登录操作时出错: {str(e)}")
            traceback.print_exc()

    def remove_selected_accounts(self):
        """删除选中的账号 - 清除账号按钮的处理函数"""
        try:
            self.log_message("开始执行删除账号操作...")
            # 检查UI状态
            self.log_message("验证UI状态...")
            if not hasattr(self, 'ui'):
                self.log_message("错误：UI对象不存在")
                return
            
            if not hasattr(self.ui, 'accountTable'):
                self.log_message("错误：UI中缺少accountTable组件")
                return
            
            # 调试输出表格信息
            rows = self.ui.accountTable.rowCount()
            cols = self.ui.accountTable.columnCount()
            self.log_message(f"账号表格当前有 {rows} 行，{cols} 列")
            
            # 检查复选框状态
            for row in range(rows):
                checkbox_container = self.ui.accountTable.cellWidget(row, 0)
                if checkbox_container:
                    for child in checkbox_container.findChildren(QCheckBox):
                        status = "选中" if child.isChecked() else "未选中"
                        self.log_message(f"第 {row+1} 行复选框状态: {status}")
            
            # 调用账号管理器的方法
            if hasattr(self.account_manager, 'remove_account'):
                self.account_manager.remove_account()
            else:
                self.log_message("错误：account_manager缺少remove_account方法")
        except Exception as e:
            self.log_message(f"删除账号时出错: {str(e)}")
            traceback.print_exc()

    def clear_account_data(self):
        """清空所有账号数据，用于首次运行时"""
        try:
            self.log_message("正在清空账号数据...")
            
            # 检查account_manager是否有clear_account_data方法
            if hasattr(self.account_manager, 'clear_account_data'):
                result = self.account_manager.clear_account_data(clear_all=True)
                if result:
                    self.log_message("成功清空所有账号数据")
                else:
                    self.log_message("清空账号数据失败")
            else:
                # 尝试直接操作数据库
                if hasattr(db_manager, 'remove_all_accounts'):
                    db_manager.remove_all_accounts()
                    self.log_message("成功清空所有账号数据")
                else:
                    self.log_message("警告：无法找到清空账号数据的方法")
            
            # 清空UI表格
            if hasattr(self.ui, 'accountTable'):
                self.ui.accountTable.setRowCount(0)
                self.log_message("已清空账号表格")
            
            # 删除cookies文件
            cookies_dir = os.path.join(os.getcwd(), "cookies")
            if os.path.exists(cookies_dir) and os.path.isdir(cookies_dir):
                try:
                    for file in os.listdir(cookies_dir):
                        if file.endswith(".txt") or file.endswith(".json"):
                            os.remove(os.path.join(cookies_dir, file))
                    self.log_message(f"已清除cookies目录中的文件")
                except Exception as e:
                    self.log_message(f"清除cookies文件时出错: {str(e)}")
            
        except Exception as e:
            self.log_message(f"清空账号数据时出错: {str(e)}")
            traceback.print_exc()

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
        
        # 检查是否是首次运行或是否有key_verification模块
        first_run = is_first_run()
        skip_verification = first_run or not HAS_KEY_VERIFICATION
        
        if not skip_verification:
            # 验证API密钥
            splash.showMessage("正在验证身份...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
            app.processEvents()
            
            # 显示密钥验证对话框
            if not show_verification_dialog():
                # 验证失败，显示错误信息并退出
                splash.close()
                QMessageBox.critical(None, "验证失败", "API密钥验证失败或被取消，程序将退出！")
                sys.exit(1)
        else:
            # 跳过验证
            splash.showMessage("首次运行，跳过验证...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
            app.processEvents()
            print("跳过密钥验证步骤")
        
        # 验证成功或跳过验证，继续加载主界面
        splash.showMessage("正在加载程序...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
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