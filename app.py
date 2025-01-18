import ast
import os.path
import sys
import time
import warnings
import threading
from concurrent.futures import ThreadPoolExecutor
import zipfile
from datetime import datetime
from key_verification import verify_key
import multiprocessing
import logging

warnings.filterwarnings("ignore")
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QBrush, QColor, QPainter, QFont, QIcon
from PyQt5.QtWidgets import QMainWindow, QApplication, QTableWidgetItem, QCheckBox, QHBoxLayout, QWidget, QPushButton, \
    QFileDialog, QMessageBox, QAbstractItemView, QVBoxLayout, QLabel, QLineEdit
from ui.ui import Ui_MainWindow
from zfb import *
import pandas as pd
from db import update_existing_fields, delete_records_by_appids

# 创建自定义的日志格式化器
class ThreadIdFormatter(logging.Formatter):
    def format(self, record):
        record.threadid = f"Thread-{threading.current_thread().ident}"
        return super().format(record)

# 配置日志
logger = logging.getLogger()
formatter = ThreadIdFormatter('%(asctime)s - %(threadid)s - %(levelname)s - %(message)s')

# 配置文件处理器
file_handler = logging.FileHandler('log.log', encoding='utf-8')
file_handler.setFormatter(formatter)

# 配置控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

conn = sqlite3.connect('data.db')


class Thread(QThread):
    df = pd.DataFrame()
    model = 0  # 0领取任务 1是传视频 2是查询今日推荐 3是删除平台不推荐视频 4获取子账号
    max_workers = 50
    error_signal = pyqtSignal(object)  # 返回异常，并设置cookies失效
    finish_signal = pyqtSignal(object)
    upload_signal = pyqtSignal(int)  # 但账号上传完成, ���传数量 +1, 参数为所在行序号-1
    recommend_signal = pyqtSignal(tuple)  # 更新界面推荐视频数量(账号序号, 推荐数量)
    delete_note_signal = pyqtSignal(tuple)  # 但删除不推荐视频(账号序号, 数量),+n
    running = False
    timing = None
    web_timing = None
    delete_original = True  # 默认为True

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_tasks = []
        self.task_lock = threading.Lock()

    def run(self):
        self.running = True
        self._stop_event.clear()
        
        try:
            for i in range(self.df.shape[0]):
                if self._stop_event.is_set():
                    logger.info("检测到停止信号，正在终止任务...")
                    break
                
                try:
                    if self.model == 0:
                        self._run_task(self.collecting_tasks, i)
                    elif self.model == 1:
                        self._wait_for_timing()
                        if not self._stop_event.is_set():
                            result = self._run_task(self.upload_publish_video, i)
                            if isinstance(result, dict) and result.get("success"):
                                # 发送上传成功信号，触发界面刷新
                                self.upload_signal.emit(result["index"])
                            # 移除DataFrame的更新，界面会通过信号自动刷新数据
                    elif self.model == 2:
                        self._run_task(self.get_public_list, i)
                    elif self.model == 3:
                        self._run_task(self.delete_note, i)
                    elif self.model == 4:
                        self._run_task(self.get_lifeOptionList, i)
                except Exception as e:
                    logger.error(f"任务执行错误: {str(e)}")
                    self.error_signal.emit(i)
                    
        finally:
            self._cleanup()
            self.finish_signal.emit(None)
            self.running = False

    def _run_task(self, task_func, *args):
        """安全地运行任务并跟踪它"""
        if self._stop_event.is_set():
            return
            
        future = self.thread_pool.submit(task_func, *args)
        with self.task_lock:
            self.active_tasks.append(future)
            
        try:
            future.result()  # 等待任务完成
        except Exception as e:
            logger.error(f"任务执行失败: {str(e)}")
        finally:
            with self.task_lock:
                if future in self.active_tasks:
                    self.active_tasks.remove(future)

    def _wait_for_timing(self):
        """等待定时任务的辅助方法"""
        if self.timing is not None:
            while not self._stop_event.is_set():
                time_data = self.timing.split(":")
                current_time = datetime.now().strftime('%H:%M:%S').split(":")
                if (int(time_data[0]) == int(current_time[0]) and 
                    int(time_data[1]) == int(current_time[1]) and 
                    int(time_data[2]) == int(current_time[2])):
                    break
                time.sleep(1)

    def _cleanup(self):
        """清理所有正在运行的任务"""
        logger.info("开始清理任务...")
        
        # 关闭线程池
        self.thread_pool.shutdown(wait=False)
        
        # 取消所有正在运行的任务
        with self.task_lock:
            for future in self.active_tasks:
                if not future.done():
                    future.cancel()
            self.active_tasks.clear()
        
        # 创建新的线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        logger.info("任务清理完成")

    def stop(self):
        """安全地停止所有任务"""
        logger.info("正在停止所有任务...")
        self._stop_event.set()
        self.running = False
        
        # 停止 zfb 中的任务
        from zfb import thread_control
        thread_control.stop()  # 使用 thread_control 实例来停止任务
        
        self._cleanup()
        logger.info("停止信号已发送")

    def get_running(self):
        return not self._stop_event.is_set()

    def get_lifeOptionList(self, i):
        """
        调用接口获取子账号
        Args:
            i:

        Returns:

        """
        appid = self.df.iloc[i]["appid"]
        cookies = self.df.iloc[i]["cookies_dict"]
        get_lifeOptionList(cookies, appid)

    def delete_note(self, i):
        """
        删除平台不推荐视频
        Args:
            i:

        Returns:

        """
        logger.info(str(self.df.iloc[i]["cookies_dict"]))
        logger.info(str(self.df.iloc[i]["appid"]))
        id_listm = get_public_list(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], "delete",
                                   not self.df.iloc[i]["is_main_account"], self.df.iloc[i]["mian_account_appid"])
        delete_note(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], id_listm,
                    not self.df.iloc[i]["is_main_account"], self.df.iloc[i]["mian_account_appid"])
        self.delete_note_signal.emit((i, len(id_listm)))

    def get_public_list(self, i):
        """
        查询今日推荐
        Args:
            i:

        Returns:

        """
        try:
            get_public_list(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], "recommend",
                            not self.df.iloc[i]["is_main_account"], self.df.iloc[i]["mian_account_appid"])
        except Exception as e:
            print("账号推荐异常:", e)

    def collecting_tasks(self, i):
        """
        领取任务
        Args:
            i:

        Returns:

        """
        taskId_list = get_recomment_tasks(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"])
        collecting_tasks(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], taskId_list)

    def upload_publish_video(self, i):
        """
        调用上传视频
        Args:
            i:

        Returns:

        """
        scheduleTime = self.web_timing
        logger.info(f"文件夹路径:{self.df.iloc[i]['folder_path']}")
        logger.info(f'话题:{self.df.iloc[i]["topic_settings"]}')
        logger.info(f'线程数:{self.max_workers}')
        logger.info("cookies:" + str(self.df.iloc[i]["cookies_dict"]))
        logger.info("appid:" + str(self.df.iloc[i]["appid"]))
        try:
            stats = upload_publish_video(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["folder_path"],
                                         self.df.iloc[i]["topic_settings"],
                                         scheduleTime, max_workers=self.max_workers, appid=self.df.iloc[i]["appid"], index=i,
                                         max_uploads=self.df.iloc[i]["total_uploads"], delete_original=self.delete_original)
            self.handle_upload_complete(stats)

        except Exception as e:
            logger.info(f"upload_publish_video报错:{e}")


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        try:
            logger.info("开始初始化主窗口...")
            super().__init__()
            
            # 日志管理初始化
            self.log_file_path = "log.log"
            self.log_max_size = 5 * 1024 * 1024  # 5MB
            self.check_and_rotate_log()
            
            self.current_offset = 0
            if os.path.exists(self.log_file_path):
                self.current_offset = len(open(self.log_file_path, "r", encoding="utf-8").readlines())

            self.setupUi(self)
            self.lineEdit.setText("50")
            self.thread = Thread()
            self.thread.error_signal.connect(self.update_table_cookie)
            self.thread.finish_signal.connect(self.finish)
            self.thread.upload_signal.connect(self.update_table_upload)
            self.thread.recommend_signal.connect(self.update_table_recommend)
            self.thread.delete_note_signal.connect(self.update_table_delete_note)
            self.pushButton_7.clicked.connect(self.set_tags)  # 绑定设置话题
            self.pushButton_9.clicked.connect(self.set_upload_counts)  # 绑定设置上传数量
            self.pushButton_6.clicked.connect(self.stop_tasks)
            self.pushButton_6.setEnabled(False)  # 初始状态禁用停止按钮
            self.pushButton_8.clicked.connect(self.clear_account)
            self.pushButton_10.clicked.connect(self.get_lifeOptionList)
            self.pushButton_11.clicked.connect(lambda: self.all_check(True))
            self.pushButton_12.clicked.connect(lambda: self.all_check(False))

            # 设置定时器
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_log)
            self.timer.start(1000)  # 每隔 1 秒检查日志文件

            self.timer_db = QTimer(self)
            self.timer_db.timeout.connect(self.init_ui)

            self.df = pd.DataFrame()
            self.init_ui()

            self.timer_login = QTimer(self)
            self.timer_login.timeout.connect(self.request_all)
            self.checkBox.stateChanged.connect(self.timer_login_start)
            if self.checkBox.isChecked():
                self.timer_login.start(300000)

            # 添加删除原视频的复选框
            self.delete_video_checkbox = QCheckBox("上传后删除原视频")
            self.delete_video_checkbox.setChecked(True)  # 默认勾选
            self.horizontalLayout_2.addWidget(self.delete_video_checkbox)

            # 添加这些设置来启用行选择
            self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.tableWidget.setSelectionMode(QAbstractItemView.SingleSelection)

            # 添加日志检查定时器
            self.log_check_timer = QTimer(self)
            self.log_check_timer.timeout.connect(self.check_and_rotate_log)
            self.log_check_timer.start(300000)  # 每5分钟检查一次
            
            # 在 horizontalLayout_2 中添加 Chrome 配置按钮
            self.chrome_config_button = QPushButton("配置Chrome路径")
            self.chrome_config_button.clicked.connect(self.configure_chrome_path)
            self.horizontalLayout_2.addWidget(self.chrome_config_button)

            # 添加每日重置定时器
            self.reset_timer = QTimer(self)
            self.reset_timer.timeout.connect(self.check_daily_reset)
            self.reset_timer.start(300000)  # 每5分钟检查一次

            # 添加文件数量检查定时器
            self.file_check_timer = QTimer(self)
            self.file_check_timer.timeout.connect(self.update_file_counts)
            self.file_check_timer.start(300000)  # 每5分钟检查一次

        except Exception as e:
            logger.error(f"主窗口初始化失败: {str(e)}")
            print(f"初始化失败: {str(e)}")

    def check_and_rotate_log(self):
        """检查并轮换日志文件"""
        try:
            if not os.path.exists(self.log_file_path):
                return
                
            # 检查日志文件大小
            log_size = os.path.getsize(self.log_file_path)
            
            if log_size >= self.log_max_size:
                logger.info("日志文件超过5MB，开始轮换...")
                
                # 创建logs目录（如果不存在）
                logs_dir = "logs"
                if not os.path.exists(logs_dir):
                    os.makedirs(logs_dir)
                
                # 生成新的日志文件名（使用时间戳）
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_name = os.path.join(logs_dir, f"log_{timestamp}.zip")
                
                # 创建ZIP文件
                with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(self.log_file_path, os.path.basename(self.log_file_path))
                
                # 清空当前日志文件
                open(self.log_file_path, 'w', encoding='utf-8').close()
                
                # 更新offset
                self.current_offset = 0
                
                # 清理旧的日志文件（保留最近10个）
                self.cleanup_old_logs()
                
                logger.info(f"日志已轮换，归档为: {archive_name}")
                
        except Exception as e:
            print(f"日志轮换失败: {str(e)}")
            logger.error(f"日志轮换失败: {str(e)}")

    def cleanup_old_logs(self):
        """清理旧的日志文件，只留最近10个"""
        try:
            logs_dir = "logs"
            if not os.path.exists(logs_dir):
                return
                
            # 获取所有日志文件
            log_files = [f for f in os.listdir(logs_dir) if f.startswith("log_") and f.endswith(".zip")]
            
            # 按时间排序
            log_files.sort(reverse=True)
            
            # 删除多余的日志文件
            for old_log in log_files[10:]:
                try:
                    os.remove(os.path.join(logs_dir, old_log))
                    logger.info(f"删除旧日志: {old_log}")
                except Exception as e:
                    logger.error(f"删除旧日志失败 {old_log}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"清理旧日志失败: {str(e)}")

    def update_log(self):
        """更新日志内容到 QTextBrowser"""
        try:
            if not os.path.exists(self.log_file_path):
                return

            with open(self.log_file_path, "r", encoding="utf-8") as log_file:
                log_file.seek(self.current_offset)
                new_lines = log_file.readlines()
                self.current_offset = log_file.tell()

                # 将新内容追加到文本浏览器
                for line in new_lines:
                    self.textBrowser.append(line.strip())
                    
                # 保持滚动到底部
                scrollbar = self.textBrowser.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                
        except Exception as e:
            print(f"更新日志失败: {str(e)}")

    def paintEvent_tabel(self, event):
        super().paintEvent(event)
        painter = QPainter(self.tableWidget.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Arial", 50))
        painter.setPen(QColor(30, 31, 34, 128))
        text = "仅供学习使用"
        text_rect = painter.fontMetrics().boundingRect(text)
        
        # 将浮点数转换为整数
        x = int((self.tableWidget.viewport().width() - text_rect.width()) / 2)
        y = int((self.tableWidget.viewport().height() - text_rect.height()) / 2)
        
        painter.drawText(x, y + text_rect.height(), text)
        painter.end()

    def all_check(self, status):
        try:
            for i in range(self.tableWidget.rowCount()):
                cell_widget = self.tableWidget.cellWidget(i, 0)
                cell_widget.setChecked(status)
        except Exception as e:
            print(e)

    def stop_tasks(self):
        """处理停止按钮点击事件"""
        try:
            if self.thread.isRunning():
                # 禁用停止按钮，防止重复点击
                self.pushButton_6.setEnabled(False)
                self.pushButton_6.setText("正在停止...")
                
                # 显示停止中的提示
                self.statusBar().showMessage("正在停止任务，请稍候...")
                
                # 停止线程
                self.thread.stop()
                
                # 等待线程完全停止
                if not self.thread.wait(5000):  # 等待最多5秒
                    logger.warning("线程未能在预期时间内停止")
                
                # 更新界面状态
                self.pushButton_6.setText("停止")
                self.statusBar().showMessage("任务已停止", 3000)
                self.update_button()
                
                # 刷新界面数据
                self.init_ui()
                
                QMessageBox.information(self, "提示", "任务已停止")
            
        except Exception as e:
            logger.error(f"停止任务时出错: {str(e)}")
            QMessageBox.warning(self, "错误", f"停止任务失败: {str(e)}")

    def timer_login_start(self):
        try:
            if self.checkBox.isChecked():
                self.timer_login.start(300000)
            else:
                self.timer_login.stop()
        except Exception as e:
            print("timer_login_start", e)

    def request_all(self):
        try:
            df = self.get_df()
            df = df[df["is_main_account"] == 1]
            for i in range(df.shape[0]):
                request_all = ast.literal_eval(df.loc[i, "request_all"])
                cookies = df.loc[i, "cookies"]
                appid = df.loc[i, "appid"]
                keep_cookies(request_all, cookies, appid)
        except Exception as e:
            print(e)

    def get_lifeOptionList(self):
        """
        获取子账号
        Returns:
        """
        try:
            # 获取当前选中的行索引
            current_row = self.tableWidget.currentRow()
            if current_row == -1:
                QMessageBox.warning(self, "提示", "请先选择一个账号")
                return
            
            df = self.get_df()
            
            # 检查是否是主账号
            if not df.iloc[current_row]["is_main_account"]:
                QMessageBox.warning(self, "提示", "请选择主账号")
                return
            
            # 获取选中行的cookies和appid
            cookies = df.iloc[current_row]["cookies_dict"]
            appid = df.iloc[current_row]["appid"]
            
            # 调用获取子账号的函数
            self.thread.model = 4
            self.thread.df = pd.DataFrame([df.iloc[current_row]])
            self.thread.start()
            self.update_button()
            
        except Exception as e:
            logger.error(f"get_lifeOptionList error: {str(e)}")
            QMessageBox.warning(self, "错误", f"获取子账号失败: {str(e)}")

    def clear_account(self):
        data = self.get_check_row()
        df = self.df.loc[data]
        delete_records_by_appids(df)
        self.init_ui()
        QMessageBox.information(self, "完成", "账号已清除")

    def update_log(self):
        """更新日志内容到 QTextBrowser"""
        try:
            if not os.path.exists(self.log_file_path):
                self.textBrowser.append(f"日志文件 {self.log_file_path} 不存在！")
                self.timer.stop()
                return

            with open(self.log_file_path, "r", encoding="utf-8-sig") as log_file:
                log_file.seek(self.current_offset)  # 从上次读取的位置继续
                new_lines = log_file.readlines()
                self.current_offset = log_file.tell()  # 更新偏移量

                # 将新内容追加到文本浏览器
                for line in new_lines:
                    self.textBrowser.append(line.strip())
        except Exception as e:
            print(e)

    def set_upload_counts(self):
        try:
            data = self.get_check_row()
            count = self.lineEdit_3.text()
            try:
                count = int(count)
            except ValueError:
                self.textBrowser.append("请输入有效的整数")
                return
            self.df.loc[data, "total_uploads"] = count
            df = self.df.loc[data]
            update_existing_fields(df)

            for i in range(len(data)):
                if data[i]:
                    self.tableWidget.setItem(i, 5, QTableWidgetItem(str(count)))
        except Exception as e:
            print(e)

    def set_tags(self):
        try:
            data = self.get_check_row()
            tag = self.lineEdit_2.text()
            self.df.loc[data, "topic_settings"] = tag
            df = self.df.loc[data]
            update_existing_fields(df)
            for i in range(len(data)):
                if data[i]:
                    self.tableWidget.setItem(i, 7, QTableWidgetItem(tag))
        except Exception as e:
            print(e)

    def finish(self, i):
        """
        执行完成
        Returns:
        """
        if self.thread.model == 0:
            QMessageBox.information(self, "完成", "任务领取完成")
        if self.thread.model == 1:
            QMessageBox.information(self, "完成", "视频上传完成")
        if self.thread.model == 2:
            QMessageBox.information(self, "完成", "今日推荐更新完毕")
        if self.thread.model == 3:
            QMessageBox.information(self, "完成", "删除不推荐视频完成")
        self.update_button()
        self.timer_db.stop()
        self.init_ui()

    def update_table_recommend(self, data: (int, int)):
        """
        更新推荐视频数量
        Args:
            data:

        Returns:

        """
        count = data[1]

        self.tableWidget.setItem(data[0], 3, QTableWidgetItem(str(count)))
        self.df.at[data[0], "今日推荐数"] = count

    def update_table_delete_note(self, data: (int, int)):
        """
        更新删除不推荐视频数量
        Args:
            data:

        Returns:

        """
        count = int(self.tableWidget.item(data[0], 8).text()) + data[1]
        self.tableWidget.setItem(data[0], 8, QTableWidgetItem(str(count)))
        self.df.at[data[0], "删除不可推荐"] = count

    def update_table_upload(self, i):
        """
        视频上传完成，更新界面信息
        Returns:

        """
        try:
            # 更新成功计数
            current_columns = self.tableWidget.columnCount()
            success_count = int(self.tableWidget.item(i, current_columns - 3).text()) + 1
            self.tableWidget.setItem(i, current_columns - 3, QTableWidgetItem(str(success_count)))
            
            # 更新最近发布时间
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.tableWidget.setItem(i, current_columns - 1, QTableWidgetItem(current_time))
            self.df.at[i, "last_publish_time"] = current_time
            
            # 更新total_uploads
            count = int(self.tableWidget.item(i, 5).text()) + 1
            self.tableWidget.setItem(i, 5, QTableWidgetItem(str(count)))
            self.df.at[i, "total_uploads"] = count
            self.df.at[i, "当前上传数"] = self.df.iloc[i]["当前上传数"] + 1
            self.df.at[i, "total_files"] = self.df.iloc[i]["total_files"] - 1
            self.tableWidget.setItem(i, 6, QTableWidgetItem(str(self.df.iloc[i]["当前上传数"])))
            self.tableWidget.setItem(i, 9, QTableWidgetItem(str(self.df.iloc[i]["total_files"])))
        except Exception as e:
            logger.error(f"更新表格失败: {str(e)}")

    def update_table_cookie(self, i: int):
        """
        更新表格当中的 cookies状态
        Args:
            i: 所在行
        Returns:
        """
        item = QTableWidgetItem("失效")
        item.setForeground(QBrush(QColor("red")))
        self.tableWidget.setItem(i, 4, item)

    def init_ui(self):
        self.df = pd.read_sql("select * from user_data", conn)
        self.df['cookies_dict'] = self.df['cookies'].apply(json.loads)
        self.show_table(self.df)

    def login(self):
        try:
            logger.info("登入")
            cookies_dict, appid, user_name, all_request = login()
            self.init_ui()

        except Exception as e:
            logger.error(str(e))

    def show_table(self, df: pd.DataFrame):
        self.tableWidget.setRowCount(0)
        self.tableWidget.setRowCount(df.shape[0])
        
        # 检查是否已经存在这些列
        current_columns = self.tableWidget.columnCount()
        required_columns = ["今日成功", "今日失败", "最近发布时间"]
        existing_headers = [self.tableWidget.horizontalHeaderItem(i).text() if self.tableWidget.horizontalHeaderItem(i) else "" 
                           for i in range(current_columns)]
        
        # 只有在这些列不存在时才添加
        if not all(col in existing_headers for col in required_columns):
            # 设置固定的列数
            self.tableWidget.setColumnCount(13)  # 原有的12列
            # 添加3个新列
            self.tableWidget.setHorizontalHeaderItem(13, QTableWidgetItem("今日成功"))
            self.tableWidget.setHorizontalHeaderItem(14, QTableWidgetItem("今日失败"))
            self.tableWidget.setHorizontalHeaderItem(15, QTableWidgetItem("最近发布时间"))
        
        headers = [
            "序号", "appId", "账号名称", "今日推荐数", "Cookies状态",
            "上传总数", "话题设置", "删除不可推荐", "文件总数",
            "是否是主账号", "文件夹路径", "操作", "今日成功", "今日失败", "最近发布时间"
        ]
        
        for i in range(df.shape[0]):
            # 第一列：复选框 + 序号
            checkbox = QCheckBox()
            checkbox.setChecked(df.iloc[i]["check_"])
            checkbox.setText(str(i + 1))
            checkbox.stateChanged.connect(self.get_check_row)
            appid = str(df.iloc[i, 0])  # 获取 appId
            self.tableWidget.setCellWidget(i, 0, checkbox)
            # self.tableWidget.setItem(i, 0, QTableWidgetItem(str(i + 1)))  # 显示序号

            # 第二列：appId
            self.tableWidget.setItem(i, 1, QTableWidgetItem(str(df.iloc[i]["appid"])))

            # 第三列：账号名称
            self.tableWidget.setItem(i, 2, QTableWidgetItem(df.iloc[i]["user_name"]))

            # 第四列：推荐数
            self.tableWidget.setItem(i, 3, QTableWidgetItem(str(self.df.iloc[i]["daily_recommendations"])))
            # 第四列：cookies状态
            self.tableWidget.setItem(i, 4, QTableWidgetItem(self.df.iloc[i]["cookies_status"]))

            # 第五列：total_uploads
            self.tableWidget.setItem(i, 5, QTableWidgetItem(str(self.df.iloc[i]["total_uploads"])))

            # 第六列：话题
            self.tableWidget.setItem(i, 6, QTableWidgetItem(str(self.df.iloc[i]["topic_settings"])))

            # 第七列：删除不可推荐
            self.tableWidget.setItem(i, 7, QTableWidgetItem(str(self.df.iloc[i]["delete_unrecommended"])))

            # 第八列：文件总数
            self.tableWidget.setItem(i, 8, QTableWidgetItem(str(self.df.iloc[i]["total_files"])))
            if self.df.iloc[i]["folder_path"] is not None:
                count = self.get_video_count(self.df.iloc[i]["folder_path"])

                self.df.at[i, "total_files"] = count
                self.tableWidget.setItem(i, 8, QTableWidgetItem(str(count)))

            self.tableWidget.setItem(i, 9, QTableWidgetItem("是" if self.df.iloc[i]["is_main_account"] else "否"))
            # 第10列：绑定文件夹
            self.tableWidget.setItem(i, 10, QTableWidgetItem(str(self.df.iloc[i]["folder_path"])))
            # 第11列：按钮
            button = QPushButton("绑定文件夹")
            if self.df.iloc[i]["total_files"] > 0:
                button.setStyleSheet("""
                background-color: rgb(90, 212, 105)
                """)
            else:
                button.setStyleSheet("""
                background-color: rgb(227, 61, 48)
                """)
            button.clicked.connect(lambda checked, data=(appid, i): self.bind_folder(data))
            self.tableWidget.setCellWidget(i, 11, button)

            # 添加统计列（使用固定的列索引）
            success_count = self.df.iloc[i].get("daily_success", 0)
            failed_count = self.df.iloc[i].get("daily_failed", 0)
            last_publish_time = self.df.iloc[i].get("last_publish_time", "")
            
            self.tableWidget.setItem(i, 12, QTableWidgetItem(str(success_count)))
            self.tableWidget.setItem(i, 13, QTableWidgetItem(str(failed_count)))
            self.tableWidget.setItem(i, 14, QTableWidgetItem(str(last_publish_time)))

    def bind_folder(self, data: (str, int)):
        """
        绑定文件夹
        Args:
            data: (appid, row)

        Returns:

        """
        # 打开文件夹选择对话框
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")

        if not folder_path:
            QMessageBox.information(self, "提示", "未选择文件夹")
            return

        video_count = self.get_video_count(folder_path)
        button = self.sender()
        if video_count > 0:
            button.setStyleSheet("""
            background-color:rgb(90, 212, 105)""")
        else:
            button.setStyleSheet("""
            background-color: rgb(227, 61, 48)""")
        self.tableWidget.setItem(data[1], 10, QTableWidgetItem(str(folder_path)))
        try:
            self.df.at[data[1], "folder_path"] = folder_path
            self.df.at[data[1], "total_files"] = video_count
            appid = self.df.iloc[data[1]]["appid"]
            df = self.df[self.df["appid"] == appid]
            update_existing_fields(df)
            self.update_video_count(data[1], video_count)
        except Exception as e:
            print(e)

    def get_check_row(self):
        """
        获取到选中的所有行
        Returns:

        """
        row = self.tableWidget.rowCount()
        data = []
        for i in range(row):
            cell_widget = self.tableWidget.cellWidget(i, 0)
            if isinstance(cell_widget, QCheckBox):
                data.append(cell_widget.isChecked())
        self.df["check_"] = data
        update_existing_fields(self.df)
        return data

    @staticmethod
    def get_video_count(path: str) -> int:
        video_count = 0
        if os.path.exists(path):
            video_extensions = {'.mp4'}

            video_count = sum(1 for file in os.listdir(path)
                              if os.path.isfile(os.path.join(path, file)) and os.path.splitext(file)[
                                  1].lower() in video_extensions)

        return video_count

    def update_video_count(self, row, count):
        try:

            self.tableWidget.setItem(row, 8, QTableWidgetItem(str(count)))
        except Exception as e:
            print(e)

    def update_button(self):
        """更新按钮状态"""
        try:
            # 根据线程运行状态设置按钮启用/禁用
            is_running = self.thread.isRunning()
            
            # 设置功能按钮状态
            for button in [self.pushButton, self.pushButton_2, 
                         self.pushButton_3, self.pushButton_4, 
                         self.pushButton_5]:
                button.setEnabled(not is_running)
            
            # 设置停止按钮状态
            self.pushButton_6.setEnabled(is_running)
            
        except Exception as e:
            logger.error(f"更新按钮状态失败: {str(e)}")

    def claim_task(self):
        """领取任务"""
        try:
            logger.info("领取任务")
            self.thread.model = 0
            
            # 准备数据
            df = self.get_df()
            data = self.get_check_row()
            df = df.loc[data]
            update_existing_fields(df)
            self.thread.df = df
            
            # 启动线程
            self.thread.start()
            self.timer_db.start(1000)
            
            # 更新按钮状态
            self.update_button()
            
        except Exception as e:
            logger.error(f"领取任务失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"领取任务失败: {str(e)}")

    def start_upload(self):
        """开始上传任务"""
        try:
            logger.info("开始上传")
            self.thread.model = 1
            
            # 设置定时配置
            if self.radioButton.isChecked():
                self.thread.timing = self.timeEdit.text()
                self.thread.web_timing = None
            elif self.radioButton_2.isChecked():
                self.thread.web_timing = self.dateTimeEdit.text()
                self.thread.timing = None
            else:
                self.thread.web_timing = None
                self.thread.timing = None
            
            # 设置删除视频配置
            self.thread.delete_original = self.delete_video_checkbox.isChecked()
            
            # 准备数据
            df = self.get_df()
            data = self.get_check_row()
            df = df.loc[data]
            update_existing_fields(df)
            self.thread.df = df
            self.thread.max_workers = int(self.lineEdit.text())

            # 启动线程
            self.thread.start()
            self.timer_db.start(1000)
            
            # 更新按钮状态
            self.update_button()
            
        except Exception as e:
            logger.error(f"启动上传任务失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"启动任务失败: {str(e)}")

    def get_today_recommendations(self):
        """
        查询今日推荐
        Returns:

        """
        logger.info("查询今日推荐")
        self.thread.model = 2
        df = self.get_df()
        data = self.get_check_row()
        df = df.loc[data]
        update_existing_fields(df)
        self.thread.df = df
        self.thread.start()
        self.timer_db.start(1000)
        self.update_button()

    def delete_non_recommended_videos(self):
        """
        删除平台��推荐视频
        Returns:

        """
        try:
            logger.info("删除平台不推荐的视频")
            self.thread.model = 3
            df = self.get_df()
            data = self.get_check_row()
            df = df.loc[data]
            update_existing_fields(df)
            self.thread.df = df
            self.thread.start()
            self.timer_db.start(1000)
            self.update_button()
        except Exception as e:
            print(e)

    def get_df(self):
        """
        更新话题以及定时日期
        Returns:
            pandas.DataFrame: 更新后的 DataFrame
        """
        for i in range(self.tableWidget.rowCount()):
            # 检查第 0 列是否包含 QCheckBox
            cell_widget = self.tableWidget.cellWidget(i, 0)
            if isinstance(cell_widget, QCheckBox):  # 判断是否为 QCheckBox
                self.df.at[i, "check_"] = cell_widget.isChecked()

            # 更新topic_settings列
            topic_item = self.tableWidget.item(i, 6)
            self.df.at[i, "topic_settings"] = topic_item.text()

            # total_uploads列
            count_item = self.tableWidget.item(i, 5)
            self.df.at[i, "total_uploads"] = int(count_item.text()) if count_item else None

        return self.df

    def configure_chrome_path(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择Chrome可执行文件",
                "",
                "Chrome Executable (chrome.exe);;All Files (*)"
            )
            
            if file_path:
                config = {}
                if os.path.exists('config.json'):
                    with open('config.json', 'r', encoding='utf-8') as f:
                        config = json.load(f)
                
                config['chrome_path'] = file_path
                
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=4)
                
                QMessageBox.information(self, "成功", "Chrome路径配置已保存！")
                logger.info(f"Chrome路径已配置为: {file_path}")
        except Exception as e:
            logger.error(f"配置Chrome路径失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"配置失败: {str(e)}")

    def handle_upload_complete(self, stats, row_index):
        """处理单个账号的上传完成统计"""
        success_count = stats.get("success", 0)
        failed_count = stats.get("failed", 0)
        
        # 更新DataFrame中的统计数据
        current_success = self.df.at[row_index, "daily_success"] = self.df.at[row_index, "daily_success"] + success_count
        current_failed = self.df.at[row_index, "daily_failed"] = self.df.at[row_index, "daily_failed"] + failed_count
        
        # 更新表格显示
        current_columns = self.tableWidget.columnCount()
        self.tableWidget.setItem(row_index, current_columns - 2, QTableWidgetItem(str(current_success)))
        self.tableWidget.setItem(row_index, current_columns - 1, QTableWidgetItem(str(current_failed)))

    def check_daily_reset(self):
        """检查是否需要重置每日统计"""
        try:
            current_date = datetime.now().date()
            last_reset_file = '.last_reset_date'
            
            # 如果没有上次发布记录，直接返回
            if not os.path.exists(last_reset_file):
                return
            
            # 读取上次发布日期
            with open(last_reset_file, 'r') as f:
                last_date = datetime.strptime(f.read().strip(), '%Y-%m-%d').date()
            
            # 如果上次发布不是今天，重置统计
            if last_date != current_date:
                logger.info("重置每日统计数据")
                
                # 直接更新数据库
                conn = sqlite3.connect('data.db')
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_data 
                    SET daily_success = 0,
                        daily_failed = 0
                ''')
                conn.commit()
                conn.close()
                
                # 重新加载数据并更新界面
                self.init_ui()
                
                logger.info("每日统计重置完成")
            
        except Exception as e:
            logger.error(f"每日重置检查时出错: {str(e)}")

    def update_file_counts(self):
        """更新所有账号的文件总数"""
        try:
            logger.info("开始更新文件总数...")
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            
            for i in range(self.df.shape[0]):
                folder_path = self.df.iloc[i]["folder_path"]
                if folder_path and os.path.exists(folder_path):
                    # 获取文件夹中的视频文件数量
                    video_count = self.get_video_count(folder_path)
                    appid = self.df.iloc[i]["appid"]
                    
                    # 更新数据库
                    cursor.execute('''
                        UPDATE user_data 
                        SET total_files = ?
                        WHERE appid = ?
                    ''', (video_count, appid))
                    
                    # 更新界面
                    self.tableWidget.setItem(i, 8, QTableWidgetItem(str(video_count)))  # 8是文件总数列的索引
                    
                    # 更新DataFrame
                    self.df.at[i, "total_files"] = video_count
                    
                    # 更新按钮颜色
                    button = self.tableWidget.cellWidget(i, 11)  # 11是操作列的索引
                    if button:
                        if video_count > 0:
                            button.setStyleSheet("background-color: rgb(90, 212, 105)")
                        else:
                            button.setStyleSheet("background-color: rgb(227, 61, 48)")
            
            conn.commit()
            conn.close()
            logger.info("文件总数更新完成")
            
        except Exception as e:
            logger.error(f"更新文件总数时出错: {str(e)}")


def show_key_verification():
    """显示密钥验证窗口
    Returns:
        bool: True 表示验证成功，False 表示验证失败
    """
    try:
        # 先检查是否有保存的密钥
        key_file = '.keyconfig'
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r') as f:
                    data = json.load(f)
                    saved_key = data.get('key')
                    if saved_key and verify_key(saved_key):
                        logger.info("使用已保存的密钥验证成功")
                        return True
            except Exception as e:
                logger.error(f"读取保存的密钥失败: {str(e)}")
        
        # 如果没有有效的保存密钥，显示验证窗口
        app = QApplication.instance()
        if app is None:
            logger.debug("创建新的 QApplication 实例")
            app = QApplication(sys.argv)
        
        verified = False
        
        # 创建验证窗口
        verify_window = QMainWindow()
        verify_window.setWindowTitle('API密钥验证')
        verify_window.setFixedSize(400, 200)
        
        # 创建中心部件
        central_widget = QWidget()
        verify_window.setCentralWidget(central_widget)
        
        # 创建主布局前确保central_widget没有已存在的布局
        if central_widget.layout():
            # 如果已存在布局，先清除它
            QWidget().setLayout(central_widget.layout())
            
        # 创建新布局
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # 添加控件
        title_label = QLabel('请输入API密钥进行验证')
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        key_input = QLineEdit()
        key_input.setPlaceholderText('在此输入您的API密钥')
        layout.addWidget(key_input)
        
        remember_checkbox = QCheckBox('记住密钥')
        remember_checkbox.setChecked(True)
        layout.addWidget(remember_checkbox)
        
        status_label = QLabel('')
        status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_label)
        
        def verify():
            nonlocal verified
            api_key = key_input.text().strip()
            if not api_key:
                QMessageBox.warning(verify_window, '警告', '请输入API密钥')
                return
                
            status_label.setText('正在验证...')
            QApplication.processEvents()
            
            if verify_key(api_key):
                QMessageBox.information(verify_window, '成功', '密钥验证成功！')
                if remember_checkbox.isChecked():
                    try:
                        data = {
                            "key": api_key,
                            "timestamp": str(datetime.now())
                        }
                        with open('.keyconfig', 'w') as f:
                            json.dump(data, f)
                        logger.debug("密钥已保存到配置文件")
                    except Exception as e:
                        logger.error(f"保存密钥失败: {str(e)}")
                verified = True
                verify_window.close()
            else:
                status_label.setText('验证失败')
                QMessageBox.critical(verify_window, '错误', '密钥验证失败，请检查后重试')
        
        verify_button = QPushButton('验证')
        verify_button.clicked.connect(verify)
        layout.addWidget(verify_button)
        
        verify_window.show()
        
        # 只在验证窗口运行时执行事件循环
        while not verified and verify_window.isVisible():
            app.processEvents()
            
        return verified
        
    except Exception as e:
        logger.error(f"验证窗口创建失败: {str(e)}")
        return False


def main():
    logger.info("=================== 程序启动 ===================")
    
    # 检查时间限制
    expiry_date = datetime(2025, 3, 31)  # 2025年3月底
    if datetime.now() > expiry_date:
        logger.error("程序已过期")
        QMessageBox.critical(None, "错误", "程序已过期，请联系开发者")
        sys.exit(1)
    
    # 确保在创建任何窗口之前先创建 QApplication
    app = QApplication.instance()
    if app is None:
        logger.debug("创建新的 QApplication 实例")
        app = QApplication(sys.argv)
    
    # 是否启用密钥验证（可以通过配置文件或其他方式控制）
    ENABLE_KEY_VERIFICATION = True 
    # 设置为 False 可以禁用密钥验证
    
    if ENABLE_KEY_VERIFICATION:
        if not show_key_verification():
            logger.error("密钥验证失败，程序退出")
            sys.exit(1)
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    return app.exec_()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    logger.info(f"脚本路径: {os.path.abspath(__file__)}")
    logger.info(f"命令行参数: {sys.argv}")
    sys.exit(main())