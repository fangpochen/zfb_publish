import ast
import os.path
import sys
import time
import warnings
import threading
from concurrent.futures import ThreadPoolExecutor
import zipfile
from datetime import datetime, time
from key_verification import verify_key
import multiprocessing
import logging
import json
import requests
import concurrent.futures
import os
import gc
import psutil
from queue import Queue, Empty
from collections import Counter, deque
from cachetools import TTLCache
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSessionLocal
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
import pandas as pd
from db import update_existing_fields, delete_records_by_appids

warnings.filterwarnings("ignore")
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QBrush, QColor, QPainter, QFont, QIcon
from PyQt5.QtWidgets import QMainWindow, QApplication, QTableWidgetItem, QCheckBox, QHBoxLayout, QWidget, QPushButton, \
    QFileDialog, QMessageBox, QAbstractItemView, QVBoxLayout, QLabel, QLineEdit, QComboBox
from ui.ui import Ui_MainWindow
from zfb import *

# 创建自定义的日志格式化器
class ThreadIdFormatter(logging.Formatter):
    def format(self, record):
        record.threadid = f"Thread-{threading.current_thread().ident}"
        return super().format(record)

# 配置日志
logger = logging.getLogger()

# 如果logger已经有处理器，先清除所有处理器
if logger.handlers:
    logger.handlers.clear()

# 配置格式化器
formatter = ThreadIdFormatter('%(asctime)s - %(levelname)s - %(message)s')

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


class ResourceManager:
    """资源管理器,负责管理系统资源和清理"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.temp_files = set()
            self.cache = TTLCache(maxsize=100, ttl=3600)  # 1小时过期
            self.memory_usage = deque(maxlen=10)  # 记录最近10次内存使用
            self._cleanup_timer = None
            self.initialized = True
    
    def start_monitoring(self):
        """开始资源监控"""
        def monitor():
            while True:
                try:
                    # 记录内存使用
                    memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                    self.memory_usage.append(memory)
                    
                    # 如果内存使用过高,触发清理
                    if memory > 1000:  # 超过1GB
                        self.cleanup()
                        
                    time.sleep(60)  # 每分钟检查一次
                except Exception as e:
                    logger.error(f"资源监控异常: {e}")
                    
        threading.Thread(target=monitor, daemon=True).start()
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理临时文件
            for file in list(self.temp_files):
                try:
                    if os.path.exists(file):
                        os.remove(file)
                        self.temp_files.remove(file)
                except Exception as e:
                    logger.error(f"清理临时文件失败 {file}: {e}")
            
            # 清理过期缓存
            self.cache.expire()
            
            # 强制垃圾回收
            gc.collect()
            
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
    
    def add_temp_file(self, file_path):
        """添加临时文件到管理器"""
        self.temp_files.add(file_path)
    
    def __del__(self):
        self.cleanup()

class Thread(QThread):
    df = pd.DataFrame()
    model = 0  # 0领取任务 1是传视频 2是查询今日推荐 3是删除平台不推荐视频 4获取子账号
    max_workers = min(os.cpu_count() * 2, 20)  # 根据CPU核心数动态设置,最大20
    error_signal = pyqtSignal(object)  # 返回异常，并设置cookies失效
    finish_signal = pyqtSignal(object)
    upload_signal = pyqtSignal(int)  # 但账号上传完成, 传数量 +1, 参数为所在行序号-1
    recommend_signal = pyqtSignal(tuple)  # 更新界面推荐视频数量(账号序号, 推荐数量)
    delete_note_signal = pyqtSignal(tuple)  # 但删除不推荐视频(账号序号, 数量),+n
    running = False
    timing = None
    web_timing = None
    delete_original = True  # 默认为True

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._init_thread_pool()
        self.active_tasks = []
        self.task_lock = threading.Lock()
        self.resource_manager = ResourceManager()
        self.error_count = Counter()
        self.retry_delays = [1, 2, 4, 8, 16]  # 指数退避重试
        
    def _init_thread_pool(self):
        """初始化线程池"""
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="Worker"
        )
        self.task_queue = Queue(maxsize=100)  # 限制任务队列大小
        self.thread_control = ThreadControl()
    
    def handle_error(self, operation, error):
        """处理错误和重试"""
        self.error_count[operation] += 1
        retry_count = self.error_count[operation]
        
        if retry_count <= len(self.retry_delays):
            delay = self.retry_delays[retry_count - 1]
            logger.warning(f"{operation} 失败,{delay}秒后重试: {error}")
            time.sleep(delay)
            return True  # 可以重试
        else:
            logger.error(f"{operation} 失败次数过多,停止重试: {error}")
            self.error_signal.emit(error)
            return False  # 不再重试
    
    def _run_task(self, task_func, *args):
        """优化的任务执行函数"""
        operation = task_func.__name__
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                future = self.thread_pool.submit(task_func, *args)
                self.thread_control.add_future(future)
                result = future.result()
                self.thread_control.remove_future(future)
                self.error_count[operation] = 0  # 重置错误计数
                return result
            except Exception as e:
                retry_count += 1
                if not self.handle_error(operation, e):
                    break
        
        return None
    
    def run(self):
        self.running = True
        self._stop_event.clear()
        start_time = time.time()
        
        # 初始化统计信息
        total_stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "details": [],  # 存储每个视频的详细信息
            "time_spent": {
                "hours": 0,
                "minutes": 0,
                "seconds": 0,
                "total_seconds": 0
            }
        }
        
        try:
            logger.info(f"开始执行模式 {self.model} 的任务")
            task_count = 0
            
            for i in range(self.df.shape[0]):
                if self._stop_event.is_set():
                    logger.info("检测到停止信号，正在终止任务...")
                    break
                
                # 防止过多任务同时进行，限制活跃任务数量
                with self.task_lock:
                    active_task_count = len([f for f in self.active_tasks if not f.done()])
                
                # 如果活跃任务过多，等待一段时间
                if active_task_count > self.max_workers * 0.8:  # 当活跃任务数超过80%时暂停添加
                    logger.info(f"活跃任务数 {active_task_count} 接近最大线程数，等待任务完成...")
                    time.sleep(3)  # 等待3秒后继续
                
                try:
                    task_count += 1
                    logger.info(f"开始第 {task_count} 个任务（账号索引: {i}）")
                    
                    if self.model == 0:
                        self._run_task(self.collecting_tasks, i)
                    elif self.model == 1:
                        self._wait_for_timing()
                        if not self._stop_event.is_set():
                            result = self._run_task(self.upload_publish_video, i)
                            if isinstance(result, dict):
                                # 累加统计信息
                                total_stats["total"] += result.get("total", 0)
                                total_stats["success"] += result.get("success", 0)
                                total_stats["failed"] += result.get("failed", 0)
                                
                                # 添加详细信息
                                if "details" in result:
                                    total_stats["details"].extend(result.get("details", []))
                                
                                # 只有在真正成功上传时才发送更新信号
                                if result.get("success", 0) > 0:
                                    self.upload_signal.emit(i)
                                    
                    elif self.model == 2:
                        result = self._run_task(self.get_public_list, i)
                        if isinstance(result, tuple):
                            self.recommend_signal.emit(result)
                    elif self.model == 3:
                        result = self._run_task(self.delete_note, i)
                        if isinstance(result, tuple):
                            self.delete_note_signal.emit(result)
                    elif self.model == 4:
                        self._run_task(self.get_lifeOptionList, i)
                    
                    logger.info(f"账号 {i} 的任务已完成")
                    
                except TimeoutError as e:
                    logger.error(f"账号 {i} 的任务超时: {str(e)}")
                    self.error_signal.emit(i)
                except Exception as e:
                    logger.error(f"账号 {i} 的任务执行错误: {str(e)}")
                    self.error_signal.emit(i)
            
            # 在所有任务完成后计算总耗时
            if self.model == 1:
                end_time = time.time()
                total_time = end_time - start_time
                total_stats["time_spent"] = {
                    "hours": int(total_time // 3600),
                    "minutes": int((total_time % 3600) // 60),
                    "seconds": int(total_time % 60),
                    "total_seconds": total_time
                }
                # 等待所有活跃任务完成
                logger.info("等待所有上传任务完成...")
                self._wait_for_all_tasks(timeout=300)  # 等待最多5分钟
                # 发送完整的统计信息
                self.finish_signal.emit(total_stats)
            else:
                # 对于非上传任务，发送一个简单的完成信号
                self.finish_signal.emit(True)
                
            logger.info(f"模式 {self.model} 的所有任务已完成")
                    
        except Exception as e:
            logger.error(f"执行任务时发生严重错误: {str(e)}", exc_info=True)
            self.finish_signal.emit({"error": str(e)})
        finally:
            self._cleanup()
            self.running = False
            logger.info("任务线程已退出")
            
    def _wait_for_all_tasks(self, timeout=60):
        """等待所有活跃任务完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.task_lock:
                active_task_count = len([f for f in self.active_tasks if not f.done()])
                if active_task_count == 0:
                    return True
            logger.info(f"等待 {active_task_count} 个活跃任务完成...")
            time.sleep(3)  # 每3秒检查一次
        
        # 如果超时，取消所有任务
        logger.warning(f"等待任务完成超时({timeout}秒)，强制取消剩余任务")
        with self.task_lock:
            for future in self.active_tasks:
                if not future.done():
                    future.cancel()
        return False

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
        
        # 取消所有正在运行的任务
        with self.task_lock:
            active_tasks_count = len(self.active_tasks)
            logger.info(f"需要清理 {active_tasks_count} 个活动任务")
            
            for future in self.active_tasks:
                if not future.done():
                    future.cancel()
            self.active_tasks.clear()
        
        # 关闭并重新创建线程池
        try:
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=False)
                logger.info("线程池已关闭")
        except Exception as e:
            logger.error(f"关闭线程池时出错: {str(e)}")
        finally:
            # 创建新的线程池
            self._init_thread_pool()
            logger.info("任务清理完成")

    def stop(self):
        """优雅停止所有任务"""
        try:
            self.thread_control.stop()
            self.thread_pool.shutdown(wait=True, cancel_futures=True)
            self.resource_manager.cleanup()
        except Exception as e:
            logger.error(f"停止线程池失败: {e}")
        finally:
            super().stop()

    def get_lifeOptionList(self, i):
        """
        调用接口获取子账号
        Args:
            i: 行索引
        Returns:
            bool: 是否成功获取子账号
        """
        try:
            appid = self.df.iloc[i]["appid"]
            cookies = self.df.iloc[i]["cookies_dict"]
            get_lifeOptionList(cookies, appid)
            return True  # 返回成功标志
        except Exception as e:
            logger.error(f"获取子账号失败: {str(e)}")
            return False

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
            i: 行索引

        Returns:
            上传结果统计
        """
        try:
            # 根据选择的定时方式设置 scheduleTime
            if self.timing:  # 如果是软件定时
                # 获取今天的日期
                today = datetime.now().date()
                # 将时间字符串转换为时间对象
                time_parts = self.timing.split(':')
                schedule_time = datetime.combine(
                    today, 
                    time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]))
                )
                scheduleTime = schedule_time.strftime('%Y-%m-%d %H:%M:%S')
            elif self.web_timing:  # 如果是Web定时
                scheduleTime = self.web_timing
            else:
                scheduleTime = None  # 不定时
            
            logger.info(f"定时发布时间设置为: {scheduleTime}")
            logger.info(f"文件夹路径:{self.df.iloc[i]['folder_path']}")
            logger.info(f'话题:{self.df.iloc[i]["topic_settings"]}')
            logger.info(f'线程数:{self.max_workers}')
            logger.info("cookies:" + str(self.df.iloc[i]["cookies_dict"]))
            logger.info("appid:" + str(self.df.iloc[i]["appid"]))
            
            stats = upload_publish_video(
                self.df.iloc[i]["cookies_dict"], 
                self.df.iloc[i]["folder_path"],
                self.df.iloc[i]["topic_settings"],
                scheduleTime=scheduleTime,
                max_workers=int(self.max_workers),  # 确保转换为整数
                appid=self.df.iloc[i]["appid"], 
                index=i,
                max_uploads=self.df.iloc[i]["total_uploads"], 
                delete_original=self.delete_original,
                topic_info=self.df.iloc[i].get("topic_info")  # 添加话题信息
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"upload_publish_video报错:{e}")
            return {"success": False, "index": i}


class VirtualTableWidget(QTableWidget):
    """虚拟表格控件,实现高效的大数据显示"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._page_size = 50
        self._cache = TTLCache(maxsize=100, ttl=300)  # 5分钟缓存
        self._loading = False
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI属性"""
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().valueChanged.connect(self._handle_scroll)
        self.viewport().installEventFilter(self)
        
    def setData(self, df):
        """设置数据源"""
        self._data = df
        self.setRowCount(len(df))
        self._load_visible_rows()
        
    def _get_visible_range(self):
        """获取可见行范围"""
        viewport_rect = self.viewport().rect()
        first_row = self.rowAt(viewport_rect.top())
        last_row = self.rowAt(viewport_rect.bottom())
        
        if first_row < 0:
            first_row = 0
        if last_row < 0:
            last_row = first_row + self._page_size
            
        return max(0, first_row - 5), min(self.rowCount(), last_row + 5)
    
    def _handle_scroll(self):
        """处理滚动事件"""
        if not self._loading:
            self._loading = True
            try:
                self._load_visible_rows()
            finally:
                self._loading = False
    
    def _load_visible_rows(self):
        """加载可见行数据"""
        if self._data is None:
            return
            
        start_row, end_row = self._get_visible_range()
        
        # 批量更新UI
        self.setUpdatesEnabled(False)
        try:
            for row in range(start_row, end_row):
                self._load_row(row)
        finally:
            self.setUpdatesEnabled(True)
    
    def _load_row(self, row):
        """加载单行数据"""
        if row >= len(self._data):
            return
            
        cache_key = f"row_{row}"
        if cache_key in self._cache:
            return
            
        try:
            row_data = self._data.iloc[row]
            self._fill_row(row, row_data)
            self._cache[cache_key] = True
        except Exception as e:
            logger.error(f"加载行 {row} 失败: {e}")
    
    def _fill_row(self, row, row_data):
        """填充行数据"""
        try:
            # 第一列：复选框
            checkbox = QCheckBox()
            checkbox.setChecked(row_data.get("check_", False))
            checkbox.setText(str(row + 1))
            self.setCellWidget(row, 0, checkbox)
            
            # 设置基本单元格数据
            basic_data = {
                1: str(row_data.get("appid", "")),
                2: str(row_data.get("user_name", "")),
                3: str(row_data.get("daily_recommendations", 0)),
                4: str(row_data.get("cookies_status", "")),
                5: str(row_data.get("total_uploads", 0)),
                6: str(row_data.get("topic_settings", "")),
                7: str(row_data.get("delete_unrecommended", "")),
                8: str(row_data.get("total_files", 0)),
                9: "是" if row_data.get("is_main_account", False) else "否",
                10: str(row_data.get("folder_path", "")),
                12: str(row_data.get("daily_success", 0)),
                13: str(row_data.get("daily_failed", 0)),
                14: str(row_data.get("last_publish_time", ""))
            }
            
            # 批量设置单元格
            for col, value in basic_data.items():
                item = QTableWidgetItem(value)
                self.setItem(row, col, item)
            
            # 设置按钮
            button = QPushButton("绑定文件夹")
            if row_data.get("total_files", 0) > 0:
                button.setStyleSheet("background-color: rgb(90, 212, 105)")
            else:
                button.setStyleSheet("background-color: rgb(227, 61, 48)")
            self.setCellWidget(row, 11, button)
            
        except Exception as e:
            logger.error(f"填充行 {row} 数据失败: {e}")
    
    def clear(self):
        """清理表格和缓存"""
        super().clear()
        self._cache.clear()
        self._data = None

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        try:
            logger.info("开始初始化主窗口...")
            super().__init__()
            
            # 添加resize_timer用于延迟处理resize事件
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.handle_resize_timeout)
            
            # 数据库连接管理
            self.db_lock = threading.RLock()  # 可重入锁
            self.conn = None
            self._init_db_connection()
            
            # 日志管理初始化
            self.log_file_path = "log.log"
            self.log_max_size = 5 * 1024 * 1024  # 5MB
            self.check_and_rotate_log()
            
            self.current_offset = 0
            if os.path.exists(self.log_file_path):
                self.current_offset = len(open(self.log_file_path, "r", encoding="utf-8").readlines())

            self.setupUi(self)
            
            # 设置窗口图标
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            
            self.lineEdit.setText("50")
            self.thread = Thread()
            self.thread.error_signal.connect(self.update_table_cookie)
            self.thread.finish_signal.connect(self.finish)
            self.thread.upload_signal.connect(self.update_table_upload)
            self.thread.recommend_signal.connect(self.update_table_recommend)
            self.thread.delete_note_signal.connect(self.update_table_delete_note)
            
            # 绑定按钮事件
            self._setup_button_connections()
            
            # 设置定时器
            self.timers = {}
            self._setup_timers()

            self.df = pd.DataFrame()
            self.init_ui()

            # 添加这些设置来启用行选择
            self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.tableWidget.setSelectionMode(QAbstractItemView.SingleSelection)

            # 在 horizontalLayout_2 中添加 Chrome 配置按钮
            self.chrome_config_button = QPushButton("配置Chrome路径")
            self.chrome_config_button.clicked.connect(self.configure_chrome_path)
            self.horizontalLayout_2.addWidget(self.chrome_config_button)

            # 创建话题搜索布局
            self._setup_topic_search()

            # 启动时检查每日重置
            self.check_daily_reset()
            
        except Exception as e:
            logger.error(f"主窗口初始化失败: {str(e)}")
            print(f"初始化失败: {str(e)}")
            
    def _setup_button_connections(self):
        """设置按钮点击事件连接"""
        self.pushButton_7.clicked.connect(self.set_tags)  # 绑定设置话题
        self.pushButton_9.clicked.connect(self.set_upload_counts)  # 绑定设置上传数量
        self.pushButton_6.clicked.connect(self.stop_tasks)
        self.pushButton_6.setEnabled(False)  # 初始状态禁用停止按钮
        self.pushButton_8.clicked.connect(self.clear_account)
        self.pushButton_10.clicked.connect(self.get_lifeOptionList)
        self.pushButton_11.clicked.connect(lambda: self.all_check(True))
        self.pushButton_12.clicked.connect(lambda: self.all_check(False))
        
    def _setup_timers(self):
        """集中设置和管理所有定时器"""
        try:
            # 定义定时器配置
            timer_configs = {
                'log_update': {
                    'interval': 2000,  # 增加到2秒
                    'callback': self.update_log,
                    'active': True
                },
                'db_update': {
                    'interval': 5000,  # 增加到5秒
                    'callback': self.init_ui,
                    'active': False
                },
                'login_check': {
                    'interval': 300000,  # 5分钟
                    'callback': self.timer_login_start,
                    'active': self.checkBox.isChecked()
                },
                'log_rotation': {
                    'interval': 300000,  # 5分钟
                    'callback': self.check_and_rotate_log,
                    'active': True
                },
                'key_verify': {
                    'interval': 1800000,  # 30分钟
                    'callback': self.verify_key_periodically,
                    'active': True
                },
                'daily_reset': {
                    'interval': 300000,  # 5分钟
                    'callback': self.check_daily_reset,
                    'active': True
                },
                'file_check': {
                    'interval': 300000,  # 5分钟
                    'callback': self.update_file_counts,
                    'active': True
                }
            }
            
            # 创建并启动定时器
            self.timers = {}
            for name, config in timer_configs.items():
                timer = QTimer(self)
                timer.timeout.connect(self._create_debounced_callback(config['callback']))
                if config['active']:
                    timer.start(config['interval'])
                self.timers[name] = {
                    'timer': timer,
                    'interval': config['interval'],
                    'active': config['active']
                }
                
            # 特殊处理：设置登录定时器与复选框关联
            self.checkBox.stateChanged.connect(self._update_login_timer)
            
            logger.info("定时器初始化完成")
            
        except Exception as e:
            logger.error(f"设置定时器时出错: {str(e)}")
            
    def _create_debounced_callback(self, callback):
        """创建防抖动的回调函数"""
        last_call = {'time': 0}
        min_interval = 100  # 最小间隔时间(毫秒)
        
        def debounced_callback():
            current_time = time.time() * 1000  # 转换为毫秒
            if current_time - last_call['time'] >= min_interval:
                try:
                    callback()
                    last_call['time'] = current_time
                except Exception as e:
                    logger.error(f"执行回调函数时出错: {str(e)}")
                    
        return debounced_callback
        
    def update_log(self):
        """优化的日志更新方法"""
        try:
            if not os.path.exists(self.log_file_path):
                if self.timers['log_update']['active']:
                    self.timers['log_update']['timer'].stop()
                    self.timers['log_update']['active'] = False
                self.textBrowser.append(f"日志文件 {self.log_file_path} 不存在！")
                return

            # 使用with语句确保文件正确关闭
            with open(self.log_file_path, "r", encoding="utf-8-sig") as log_file:
                log_file.seek(self.current_offset)
                new_lines = log_file.readlines()
                self.current_offset = log_file.tell()

                if new_lines:  # 只在有新内容时更新
                    # 批量更新文本
                    self.textBrowser.setUpdatesEnabled(False)
                    for line in new_lines:
                        self.textBrowser.append(line.strip())
                    self.textBrowser.setUpdatesEnabled(True)
                    
                    # 滚动到底部
                    scrollbar = self.textBrowser.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
                    
        except Exception as e:
            logger.error(f"更新日志失败: {str(e)}")

    def _update_login_timer(self):
        """根据复选框状态更新登录定时器"""
        if self.checkBox.isChecked():
            if not self.timers['login_check']['active']:
                self.timers['login_check']['timer'].start(self.timers['login_check']['interval'])
                self.timers['login_check']['active'] = True
                logger.info("登录定时器已启动")
        else:
            if self.timers['login_check']['active']:
                self.timers['login_check']['timer'].stop()
                self.timers['login_check']['active'] = False
                logger.info("登录定时器已停止")
                
    def _setup_topic_search(self):
        """设置话题搜索相关控件"""
        self.topic_layout = QHBoxLayout()
        
        # 创建话题下拉框
        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumWidth(200)
        self.topic_combo.setMaxVisibleItems(10)  # 设置最大显示项数
        self.topic_combo.setEditable(True)  # 设置为可编辑
        self.topic_combo.lineEdit().setPlaceholderText("点击搜索话题")  # 设置占位文本
        # 添加标志位，避免循环搜索
        self.is_updating_topics = False
        # 保存话题信息的字典
        self.topic_info = {}
        self.topic_combo.lineEdit().textChanged.connect(self.search_topics)  # 输入文字时搜索
        self.topic_combo.activated.connect(self.on_topic_selected)  # 选择话题时触发
        
        # 设置下拉框样式
        self.topic_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 1px 18px 1px 3px;
                min-width: 6em;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ccc;
                background: white;
                selection-background-color: #e6e6e6;
            }
        """)
        
        # 将控件添加到布局
        self.topic_layout.addWidget(QLabel("话题搜索:"))  # 添加标签
        self.topic_layout.addWidget(self.topic_combo)
        self.topic_layout.addStretch()  # 添加弹性空间
        
        # 将话题搜索布局添加到现有布局中
        self.horizontalLayout_3.addLayout(self.topic_layout)
        
        # 添加话题信息存储
        self.current_topic_info = None

    def _init_db_connection(self):
        """初始化数据库连接，确保线程安全"""
        try:
            with self.db_lock:
                # 关闭现有连接(如果有的话)
                if self.conn:
                    try:
                        self.conn.close()
                        logger.info("已关闭旧的数据库连接")
                    except Exception as e:
                        logger.error(f"关闭数据库连接时出错: {str(e)}")
                
                # 创建新连接
                self.conn = sqlite3.connect('data.db', check_same_thread=False)
                # 启用外键约束
                self.conn.execute("PRAGMA foreign_keys = ON")
                # 优化性能
                self.conn.execute("PRAGMA synchronous = NORMAL")
                self.conn.execute("PRAGMA journal_mode = WAL")
                self.conn.execute("PRAGMA temp_store = MEMORY")
                
                logger.info("已创建新的数据库连接")
                
                # 设置连接超时
                self.conn.execute("PRAGMA busy_timeout = 30000")  # 30秒
        except Exception as e:
            logger.error(f"初始化数据库连接失败: {str(e)}")
            raise
    
    def get_db_connection(self):
        """获取数据库连接，如果连接已断开则重新连接"""
        try:
            with self.db_lock:
                # 检查连接是否有效
                try:
                    self.conn.execute("SELECT 1")
                    return self.conn
                except (sqlite3.Error, AttributeError):
                    logger.warning("数据库连接已断开，尝试重新连接")
                    self._init_db_connection()
                    return self.conn
        except Exception as e:
            logger.error(f"获取数据库连接失败: {str(e)}")
            self._init_db_connection()
            return self.conn

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

    def paintEvent(self, event):
        """正确的绘制事件处理"""
        super().paintEvent(event)
        # 绘制水印
        painter = QPainter(self.tableWidget.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Arial", 50))
        painter.setPen(QColor(30, 31, 34, 128))
        text = "仅供学习使用"
        text_rect = painter.fontMetrics().boundingRect(text)
        
        x = int((self.tableWidget.viewport().width() - text_rect.width()) / 2)
        y = int((self.tableWidget.viewport().height() - text_rect.height()) / 2)
        
        painter.drawText(x, y + text_rect.height(), text)
        painter.end()

    def resizeEvent(self, event):
        """窗口大小调整事件处理"""
        # 暂停所有更新
        self.tableWidget.setUpdatesEnabled(False)
        
        # 调用基类的resizeEvent
        super().resizeEvent(event)
        
        # 启动resize定时器,延迟处理resize后的更新
        self.resize_timer.start(300)  # 300ms后执行更新
        
    def handle_resize_timeout(self):
        """处理resize后的更新"""
        # 重新启用更新
        self.tableWidget.setUpdatesEnabled(True)
        # 刷新表格布局
        self.tableWidget.viewport().update()

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
                self.timers['login_check']['timer'].start(self.timers['login_check']['interval'])
                self.timers['login_check']['active'] = True
                logger.info("登录定时器已启动")
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
                    self.tableWidget.setItem(i, 8, QTableWidgetItem(str(video_count)))
                    
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

    def filter_table(self):
        """根据搜索框内容过滤表格"""
        search_text = self.search_input.text().lower()
        
        for row in range(self.tableWidget.rowCount()):
            show_row = False
            # 在appId列(索引1)和账号名称列(索引2)中搜索
            for col in [1, 2]:
                item = self.tableWidget.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            self.tableWidget.setRowHidden(row, not show_row)

    def verify_key_periodically(self):
        """
        定期验证密钥
        """
        try:
            # 从配置文件读取密钥
            if os.path.exists('.keyconfig'):
                with open('.keyconfig', 'r') as f:
                    config = json.load(f)
                    api_key = config.get('key')
                    if api_key:
                        # 验证密钥
                        if not verify_key(api_key):
                            logger.error("密钥验证失败")
                            QMessageBox.critical(self, "错误", "密钥验证失败，程序将退出")
                            # 停止所有任务
                            if self.thread.isRunning():
                                self.stop_tasks()
                            # 退出程序
                            sys.exit(1)
                        else:
                            logger.info("密钥验证成功")
                    else:
                        logger.error("未找到密钥")
                        QMessageBox.critical(self, "错误", "未找到密钥，程序将退出")
                        sys.exit(1)
            else:
                logger.error("未找到密钥配置文件")
                QMessageBox.critical(self, "错误", "未找到密钥配置文件，程序将退出")
                sys.exit(1)
        except Exception as e:
            logger.error(f"验证密钥时发生错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"验证密钥时发生错误: {str(e)}，程序将退出")
            sys.exit(1)

    def disable_all_buttons(self):
        """
        禁用所有功能按钮
        """
        try:
            # 禁用所有功能按钮
            for button in [self.pushButton, self.pushButton_2, 
                         self.pushButton_3, self.pushButton_4, 
                         self.pushButton_5, self.pushButton_6,
                         self.pushButton_7, self.pushButton_8,
                         self.pushButton_9, self.pushButton_10,
                         self.pushButton_11, self.pushButton_12]:
                button.setEnabled(False)
        except Exception as e:
            logger.error(f"禁用按钮时发生错误: {str(e)}")

    def search_topics(self):
        """
        根据输入的关键词搜索话题
        """
        try:
            # 如果正在更新话题列表，直接返回
            if self.is_updating_topics:
                return

            keywords = self.topic_combo.currentText().strip()
            # 如果关键词带有#号，不触发搜索
            if keywords.startswith('#') and keywords.endswith('#'):
                return
                
            if not keywords:
                self.topic_combo.clear()
                self.topic_info.clear()  # 清空话题信息
                return
                
            # 获取当前选中行的cookies和appId
            selected_rows = []
            for i in range(self.tableWidget.rowCount()):
                checkbox = self.tableWidget.cellWidget(i, 0)
                if isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                    selected_rows.append(i)
                    
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择账号")
                return
                
            row = selected_rows[0]
            cookies = self.df.iloc[row]["cookies_dict"]
            appid = self.df.iloc[row]["appid"]
            
            # 请求话题推荐接口
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Connection': 'keep-alive',
                'Content-Type': 'application/json;charset=UTF-8',
                'Origin': 'https://c.alipay.com',
                'Referer': 'https://c.alipay.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            params = {
                '_input_charset': 'utf-8',
                '_output_charset': 'utf-8',
            }
            
            json_data = {
                'keywords': keywords,
                'publicId': appid,
                'sourceId': 'S',
            }
            
            logger.info(f"搜索话题请求参数: {json_data}")
            
            response = requests.post(
                'https://fuwu.alipay.com/platform/queryTopicRecommend.json',
                params=params,
                cookies=cookies,
                headers=headers,
                json=json_data,
            )
            
            logger.info(f"搜索话题响应: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("stat") == "ok":
                    # 设置标志位，避免触发搜索
                    self.is_updating_topics = True
                    
                    # 清空下拉框和话题信息
                    self.topic_combo.clear()
                    self.topic_info.clear()
                    
                    # 添加搜索结果到下拉框
                    topics = data.get("result", [])
                    if topics:
                        for topic in topics:
                            topic_name = topic.get("name", "")
                            topic_id = topic.get("topicId", "")
                            if topic_name:
                                display_text = f"#{topic_name}#"
                                self.topic_combo.addItem(display_text)
                                # 保存话题完整信息
                                self.topic_info[display_text] = {
                                    'name': topic_name,
                                    'topicId': topic_id
                                }
                        # 显示下拉列表
                        self.topic_combo.showPopup()
                        logger.info(f"找到{len(topics)}个话题")
                    else:
                        logger.info("未找到相关话题")
                    
                    # 重置标志位
                    self.is_updating_topics = False
                else:
                    error_msg = data.get("errorMessage", "未知错误")
                    logger.error(f"搜索话题失败: {error_msg}")
            else:
                logger.error(f"搜索话题请求失败: HTTP {response.status_code}")
                            
        except Exception as e:
            logger.error(f"搜索话题失败: {str(e)}")
            # 重置标志位
            self.is_updating_topics = False

    def on_topic_selected(self, index):
        """当选择话题时触发"""
        try:
            selected_topic = self.topic_combo.currentText()
            if selected_topic:
                # 从话题数据中获取完整信息
                topic_data = self.topic_info[selected_topic]
                self.current_topic_info = {
                    'topicInfoVOList': [{
                        'name': selected_topic.strip('#'),  # 去掉#号
                        'topicId': topic_data.get('topicId', '')
                    }]
                }
                # 设置话题文本
                self.lineEdit_2.setText(selected_topic)
                logger.info(f"已选择话题: {selected_topic}, ID: {topic_data.get('topicId', '')}")
            else:
                self.current_topic_info = None
                logger.info("已清除话题选择")
        except Exception as e:
            logger.error(f"选择话题时发生错误: {str(e)}")
            self.current_topic_info = None

    def get_check_row(self):
        """
        获取到选中的所有行
        Returns:
            list: 选中状态列表
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
            self.timers['db_update']['timer'].start(self.timers['db_update']['interval'])
            
            # 更新按钮状态
            self.update_button()
            
        except Exception as e:
            logger.error(f"领取任务失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"领取任务失败: {str(e)}")

    def start_upload(self):
        """开始上传视频"""
        try:
            logger.info("开始上传视频")
            self.thread.model = 1
            df = self.get_df()
            data = self.get_check_row()
            df = df.loc[data]
            
            # 获取定时发布时间
            if self.radioButton_2.isChecked():  # 如果选择了定时发布
                self.thread.web_timing = self.dateTimeEdit.text()
            else:
                self.thread.web_timing = None
            
            # 设置是否删除原视频
            self.thread.delete_original = self.delete_video_checkbox.isChecked()
            
            # 设置线程数
            self.thread.max_workers = int(self.lineEdit.text())
            logger.info(f"设置线程数为: {self.thread.max_workers}")
            
            # 更新话题信息
            if self.current_topic_info:
                df['topic_info'] = [self.current_topic_info] * len(df)
            
            update_existing_fields(df)
            self.thread.df = df
            self.thread.start()
            self.timers['db_update']['timer'].start(self.timers['db_update']['interval'])
            self.update_button()
            
        except Exception as e:
            logger.error(f"上传过程发生错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"上传失败: {str(e)}")
            return

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
        self.timers['db_update']['timer'].start(self.timers['db_update']['interval'])
        self.update_button()

    def delete_non_recommended_videos(self):
        """
        删除平台不推荐视频
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
            self.timers['db_update']['timer'].start(self.timers['db_update']['interval'])
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


    def check_daily_reset(self):
        """检查是否需要重置每日统计"""
        try:
            current_date = datetime.now().date()
            
            # 从数据库读取所有账号
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            
            # 获取所有账号的appid和最后发布时间
            cursor.execute('''
                SELECT appid, last_publish_time 
                FROM user_data
            ''')
            accounts = cursor.fetchall()
            
            for appid, last_publish_time in accounts:
                should_reset = False
                
                # 如果没有最后发布时间，或者最后发布时间不是今天，需要重置
                if not last_publish_time:
                    should_reset = True
                else:
                    try:
                        last_date = datetime.strptime(last_publish_time.split()[0], '%Y-%m-%d').date()
                        should_reset = last_date != current_date
                    except Exception as e:
                        logger.error(f"解析最后发布时间失败 - appid: {appid}, error: {str(e)}")
                        should_reset = True
                
                if should_reset:
                    logger.info(f"重置账号 {appid} 的每日统计数据")
                    cursor.execute('''
                        UPDATE user_data 
                        SET daily_success = 0,
                            daily_failed = 0
                        WHERE appid = ?
                    ''', (appid,))
            
            conn.commit()
            conn.close()
            
            # 重新加载数据并更新界面
            self.init_ui()
            
            logger.info("每日统计重置检查完成")
            
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
                    self.tableWidget.setItem(i, 8, QTableWidgetItem(str(video_count)))
                    
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

    def filter_table(self):
        """根据搜索框内容过滤表格"""
        search_text = self.search_input.text().lower()
        
        for row in range(self.tableWidget.rowCount()):
            show_row = False
            # 在appId列(索引1)和账号名称列(索引2)中搜索
            for col in [1, 2]:
                item = self.tableWidget.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            self.tableWidget.setRowHidden(row, not show_row)

    def set_upload_counts(self):
        """设置上传总数"""
        try:
            # 获取选中的行
            data = self.get_check_row()
            count_str = self.lineEdit_3.text()
            
            try:
                count = int(count_str)
                if count < 0:
                    self.textBrowser.append("上传总数不能为负数")
                    return
            except ValueError:
                self.textBrowser.append("请输入有效的整数")
                return
                
            # 更新数据库
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # 遍历选中的行
            updated = False
            for i in range(len(data)):
                if data[i]:
                    updated = True
                    appid = self.df.iloc[i]["appid"]
                    # 更新数据库
                    cursor.execute('''
                        UPDATE user_data 
                        SET total_uploads = ?
                        WHERE appid = ?
                    ''', (count, appid))
                    
                    # 更新DataFrame
                    self.df.at[i, "total_uploads"] = count
                    # 更新界面显示
                    self.tableWidget.setItem(i, 5, QTableWidgetItem(str(count)))
            
            conn.commit()
            
            if updated:
                logger.info(f"已更新选中账号的上传总数为: {count}")
                QMessageBox.information(self, "成功", f"已将选中账号的上传总数设置为: {count}")
            else:
                QMessageBox.warning(self, "提示", "请先选择要设置的账号")
            
        except Exception as e:
            logger.error(f"设置上传总数失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"设置上传总数失败: {str(e)}")

    def set_tags(self):
        """
        设置话题
        """
        try:
            data = self.get_check_row()
            tag = self.lineEdit_2.text()
            if not tag:
                QMessageBox.warning(self, "警告", "请输入或选择话题")
                return
                
            self.df.loc[data, "topic_settings"] = tag
            df = self.df.loc[data]
            update_existing_fields(df)
            
            for i in range(len(data)):
                if data[i]:
                    self.tableWidget.setItem(i, 6, QTableWidgetItem(tag))
                    
        except Exception as e:
            logger.error(f"设置话题失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"设置话题失败: {str(e)}")

    def finish(self, stats):
        """
        处理任务完成的回调函数
        :param stats: 包含任务完成的统计信息的字典
        """
        try:
            # 停止定时器
            if 'db_update' in self.timers:
                self.timers['db_update']['timer'].stop()
                self.timers['db_update']['active'] = False
            
            if self.thread.model == 0:
                QMessageBox.information(self, "完成", "任务完成")
            elif self.thread.model == 1:
                if isinstance(stats, dict):
                    # 获取统计信息
                    total = stats.get('total', 0)
                    success = stats.get('success', 0)
                    failed = stats.get('failed', 0)
                    details = stats.get('details', [])
                    time_spent = stats.get('time_spent', {})
                    
                    hours = time_spent.get('hours', 0)
                    minutes = time_spent.get('minutes', 0)
                    seconds = time_spent.get('seconds', 0)
                    
                    # 构建时间字符串
                    time_str = ""
                    if hours > 0:
                        time_str += f"{hours}小时"
                    if minutes > 0:
                        time_str += f"{minutes}分钟"
                    if seconds > 0 or not time_str:
                        time_str += f"{seconds}秒"
                    
                    # 构建详细信息字符串
                    detail_str = ""
                    if details:
                        detail_str = "\n\n详细信息:\n"
                        for detail in details:
                            status = "成功" if detail.get("success") else "失败"
                            video_name = detail.get("video_name", "未知视频")
                            message = detail.get("message", "")
                            publish_time = detail.get("publish_time", "")
                            detail_str += f"{video_name}: {status} - {message}"
                            if publish_time:
                                detail_str += f" ({publish_time})"
                            detail_str += "\n"
                    
                    # 显示最终统计结果
                    msg = (f"上传完成！\n\n"
                          f"总计视频：{total}个\n"
                          f"成功：{success}个\n"
                          f"失败：{failed}个\n\n"
                          f"总耗时：{time_str}"
                          f"{detail_str}")
                    
                    QMessageBox.information(self, "完成", msg)
                else:
                    QMessageBox.information(self, "完成", "视频上传完成")
            elif self.thread.model == 2:
                QMessageBox.information(self, "完成", "推荐更新完成")
            elif self.thread.model == 3:
                QMessageBox.information(self, "完成", "删除非推荐视频完成")
            elif self.thread.model == 4:
                QMessageBox.information(self, "完成", "获取子账号完成")
                # 读取子账号完成后刷新界面
                self.init_ui()
                
            # 更新UI状态
            self.update_button()
            
        except Exception as e:
            logger.error(f"处理完成事件时发生错误: {str(e)}")
            QMessageBox.warning(self, "警告", "处理完成事件时发生错误")

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
            data: (行索引, 删除数量)
        """
        try:
            # 删除不可推荐在第7列（空白列的位置）
            current_count = int(self.tableWidget.item(data[0], 7).text()) if self.tableWidget.item(data[0], 7) and self.tableWidget.item(data[0], 7).text() else 0
            new_count = current_count + data[1]
            self.tableWidget.setItem(data[0], 7, QTableWidgetItem(str(new_count)))
            self.df.at[data[0], "删除不可推荐"] = new_count
        except Exception as e:
            logger.error(f"更新删除不推荐视频数量失败: {str(e)}")

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
        """从数据库读取并显示数据"""
        try:
            # 获取数据库连接
            conn = self.get_db_connection()
            
            # 读取数据
            try:
                self.df = pd.read_sql("select * from user_data", conn)
                self.df['cookies_dict'] = self.df['cookies'].apply(json.loads)
                self.show_table(self.df)
                logger.info("数据库读取成功，UI已更新")
            except Exception as e:
                logger.error(f"读取数据库失败: {str(e)}")
                QMessageBox.warning(self, "警告", f"读取数据失败: {str(e)}")
                
        except Exception as e:
            logger.error(f"初始化UI失败: {str(e)}")
            print(f"初始化UI失败: {str(e)}")

    def login(self):
        try:
            logger.info("登入")
            cookies_dict, appid, user_name, all_request = login()
            self.init_ui()

        except Exception as e:
            logger.error(str(e))

    def show_table(self, df: pd.DataFrame):
        """优化的表格显示方法"""
        try:
            # 暂停表格更新
            self.tableWidget.setUpdatesEnabled(False)
            self.tableWidget.setSortingEnabled(False)
            
            # 设置行数
            self.tableWidget.setRowCount(0)
            self.tableWidget.setRowCount(df.shape[0])
            
            # 检查列数
            current_columns = self.tableWidget.columnCount()
            required_columns = ["今日成功", "今日失败", "最近发布时间"]
            existing_headers = [self.tableWidget.horizontalHeaderItem(i).text() if self.tableWidget.horizontalHeaderItem(i) else "" 
                              for i in range(current_columns)]
            
            # 设置列数
            if not all(col in existing_headers for col in required_columns):
                self.tableWidget.setColumnCount(15)  # 固定列数
                
                # 设置列标题
                headers = [
                    "序号", "appId", "账号名称", "今日推荐数", "Cookies状态",
                    "上传总数", "话题设置", "删除不可推荐", "文件总数",
                    "是否是主账号", "文件夹路径", "操作", "今日成功", "今日失败", "最近发布时间"
                ]
                for i, header in enumerate(headers):
                    self.tableWidget.setHorizontalHeaderItem(i, QTableWidgetItem(header))
            
            # 批量处理数据
            batch_size = 50  # 每批处理的行数
            for start in range(0, df.shape[0], batch_size):
                end = min(start + batch_size, df.shape[0])
                
                # 处理这一批数据
                for i in range(start, end):
                    self._fill_table_row(i, df.iloc[i])
                
                # 每批处理完后让UI有机会响应
                QApplication.processEvents()
                
            # 恢复表格更新和排序
            self.tableWidget.setSortingEnabled(True)
            self.tableWidget.setUpdatesEnabled(True)
            
            # 应用当前的搜索过滤
            self.filter_table()
            
        except Exception as e:
            logger.error(f"显示表格数据时出错: {str(e)}")
            self.tableWidget.setUpdatesEnabled(True)
            QMessageBox.warning(self, "错误", f"显示数据失败: {str(e)}")
            
    def _fill_table_row(self, row_index, row_data):
        """填充单行数据"""
        try:
            # 第一列：复选框 + 序号
            checkbox = QCheckBox()
            checkbox.setChecked(row_data["check_"])
            checkbox.setText(str(row_index + 1))
            checkbox.stateChanged.connect(self.get_check_row)
            self.tableWidget.setCellWidget(row_index, 0, checkbox)
            
            # 设置基本单元格数据
            basic_data = {
                1: str(row_data["appid"]),
                2: row_data["user_name"],
                3: str(row_data["daily_recommendations"]),
                4: row_data["cookies_status"],
                5: str(row_data["total_uploads"]),
                6: str(row_data["topic_settings"]),
                7: str(row_data["delete_unrecommended"]),
                8: str(row_data["total_files"]),
                9: "是" if row_data["is_main_account"] else "否",
                10: str(row_data["folder_path"]),
                12: str(row_data.get("daily_success", 0)),
                13: str(row_data.get("daily_failed", 0)),
                14: str(row_data.get("last_publish_time", ""))
            }
            
            # 批量设置单元格
            for col, value in basic_data.items():
                self.tableWidget.setItem(row_index, col, QTableWidgetItem(value))
            
            # 设置绑定文件夹按钮
            button = QPushButton("绑定文件夹")
            if row_data["total_files"] > 0:
                button.setStyleSheet("background-color: rgb(90, 212, 105)")
            else:
                button.setStyleSheet("background-color: rgb(227, 61, 48)")
            button.clicked.connect(lambda checked, data=(row_data["appid"], row_index): self.bind_folder(data))
            self.tableWidget.setCellWidget(row_index, 11, button)
            
        except Exception as e:
            logger.error(f"填充表格行 {row_index} 时出错: {str(e)}")

    def bind_folder(self, data: (str, int)):
        """
        绑定文件夹
        Args:
            data: (appid, row)
        """
        try:
            # 打开文件夹选择对话框
            folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")

            if not folder_path:
                QMessageBox.information(self, "提示", "未选择文件夹")
                return

            # 检查文件夹是否存在
            if not os.path.exists(folder_path):
                QMessageBox.warning(self, "错误", "选择的文件夹不存在")
                return

            try:
                video_count = self.get_video_count(folder_path)
            except Exception as e:
                logger.error(f"获取视频数量失败: {str(e)}")
                QMessageBox.warning(self, "错误", f"获取视频数量失败: {str(e)}")
                return

            # 更新按钮样式
            button = self.sender()
            if button:
                if video_count > 0:
                    button.setStyleSheet("background-color: rgb(90, 212, 105)")
                else:
                    button.setStyleSheet("background-color: rgb(227, 61, 48)")

            # 更新表格
            self.tableWidget.setItem(data[1], 10, QTableWidgetItem(str(folder_path)))
            self.tableWidget.setItem(data[1], 8, QTableWidgetItem(str(video_count)))

            try:
                # 获取数据库连接
                conn = self.get_db_connection()

                # 更新DataFrame
                self.df.at[data[1], "folder_path"] = folder_path
                self.df.at[data[1], "total_files"] = video_count
                appid = self.df.iloc[data[1]]["appid"]
                
                # 使用参数化查询更新数据库
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE user_data 
                    SET folder_path = ?, total_files = ?
                    WHERE appid = ?
                """, (folder_path, video_count, appid))
                conn.commit()

            except sqlite3.Error as e:
                logger.error(f"数据库更新失败: {str(e)}")
                QMessageBox.warning(self, "错误", f"数据库更新失败: {str(e)}")
                # 尝试重新连接数据库
                try:
                    self._init_db_connection()
                    self.init_ui()
                except Exception as e:
                    logger.error(f"数据库重连失败: {str(e)}")
                    QMessageBox.critical(self, "严重错误", "数据库连接失败，请重启应用")
                return

        except Exception as e:
            logger.error(f"绑定文件夹失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"绑定文件夹失败: {str(e)}")

    @staticmethod
    def get_video_count(path: str) -> int:
        """
        获取文件夹中的视频文件数量
        Args:
            path: 文件夹路径
        Returns:
            int: 视频文件数量
        """
        try:
            if not os.path.exists(path):
                return 0

            video_extensions = {'.mp4'}
            video_count = 0

            for file in os.listdir(path):
                try:
                    if os.path.isfile(os.path.join(path, file)) and \
                       os.path.splitext(file)[1].lower() in video_extensions:
                        video_count += 1
                except Exception as e:
                    logger.error(f"处理文件 {file} 时出错: {str(e)}")
                    continue

            return video_count

        except Exception as e:
            logger.error(f"获取视频数量时出错: {str(e)}")
            return 0

    def update_table_upload(self, i: int):
        """
        更新上传进度
        
        Args:
            i: 行索引，标识要更新的账号
        """
        try:
            # 获取当前成功数量并加1
            current_success = int(self.tableWidget.item(i, 12).text()) if self.tableWidget.item(i, 12) and self.tableWidget.item(i, 12).text() else 0
            new_success = current_success + 1
            
            # 更新UI显示
            self.tableWidget.setItem(i, 12, QTableWidgetItem(str(new_success)))
            
            # 更新最后发布时间
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.tableWidget.setItem(i, 14, QTableWidgetItem(current_time))
            
            # 更新数据库
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                appid = self.df.iloc[i]["appid"]
                
                # 更新成功数量和最后发布时间
                cursor.execute('''
                    UPDATE user_data 
                    SET daily_success = ?,
                        last_publish_time = ?
                    WHERE appid = ?
                ''', (new_success, current_time, appid))
                conn.commit()
                
                # 更新DataFrame
                self.df.at[i, "daily_success"] = new_success
                self.df.at[i, "last_publish_time"] = current_time
                
                logger.info(f"账号 {appid} 的上传成功数量已更新为 {new_success}")
            except Exception as e:
                logger.error(f"更新数据库失败: {str(e)}")
            
        except Exception as e:
            logger.error(f"更新上传进度失败: {str(e)}")


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