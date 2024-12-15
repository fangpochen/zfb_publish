import ast
import os.path
import sys
import time

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QMainWindow, QApplication, QTableWidgetItem, QCheckBox, QHBoxLayout, QWidget, QPushButton, \
    QFileDialog, QMessageBox
from ui.ui import Ui_MainWindow
from zfb import *
import pandas as pd
from db import update_existing_fields, delete_records_by_appids

conn = sqlite3.connect('data.db')


class Thread(QThread):
    df = pd.DataFrame()
    model = 0  # 0领取任务 1是传视频 2是查询今日推荐 3是删除平台不推荐视频 4获取子账号
    max_workers = 3
    error_signal = pyqtSignal(object)  # 返回异常，并设置cookies失效
    finish_signal = pyqtSignal(object)
    upload_signal = pyqtSignal(int)  # 但账号上传完成, 上传数量 +1, 参数为所在行序号-1
    recommend_signal = pyqtSignal(tuple)  # 更新界面推荐视频数量(账号序号, 推荐数量)
    delete_note_signal = pyqtSignal(tuple)  # 但删除不推荐视频(账号序号, 数量),+n
    running = False
    timing = None
    web_timing = None

    def run(self):
        self.running = True
        for i in range(self.df.shape[0]):
            if not self.get_running():
                break
            try:
                if self.model == 0:
                    self.collecting_tasks(i)

                elif self.model == 1:
                    while True:
                        if self.timing is not None:
                            time_data = self.timing.split(":")
                            current_time = datetime.now().strftime('%H:%M:%S').split(":")
                            print(time_data, current_time)
                            if int(time_data[0]) == int(current_time[0]) and int(time_data[1]) == int(
                                    current_time[1]) and int(
                                time_data[2]) == int(current_time[2]):
                                break
                            time.sleep(1)
                        else:
                            break
                    self.upload_publish_video(i)
                elif self.model == 2:
                    print(f"开始查询今日推荐{i}")
                    self.get_public_list(i)
                elif self.model == 3:
                    self.delete_note(i)
                elif self.model == 4:
                    self.get_lifeOptionList(i)
            except Exception as e:
                self.error_signal.emit(i)

        self.finish_signal.emit(None)
        self.running = False

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

    def get_running(self):
        return self.running

    def stop(self):
        self.running = False
        logger.info("停止")

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
        print(id_listm)
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
        print(f"获取第{i}个账号推荐")
        try:
            get_public_list(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], "recommend",
                            not self.df.iloc[i]["is_main_account"], self.df.iloc[i]["mian_account_appid"])
        except Exception as e:
            print("账号推荐异常:", e)
        print(f"获取第{i}个账号推荐完成")

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
            pass
            upload_publish_video(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["folder_path"],
                                 self.df.iloc[i]["topic_settings"],
                                 scheduleTime, max_workers=self.max_workers, appid=self.df.iloc[i]["appid"], index=i,
                                 max_uploads=self.df.iloc[i]["total_uploads"])

        except Exception as e:
            logger.info(f"upload_publish_video报错:{e}")


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.log_file_path = "log.log"
        self.current_offset = 0
        if os.path.exists(self.log_file_path):
            self.current_offset = len(open(self.log_file_path, "r", encoding="utf-8").readlines())

        self.setupUi(self)
        self.lineEdit.setText("3")
        self.thread = Thread()
        self.thread.error_signal.connect(self.update_table_cookie)
        self.thread.finish_signal.connect(self.finish)
        self.thread.upload_signal.connect(self.update_table_upload)
        self.thread.recommend_signal.connect(self.update_table_recommend)
        self.thread.delete_note_signal.connect(self.update_table_delete_note)
        self.pushButton_7.clicked.connect(self.set_tags)  # 绑定设置话题
        self.pushButton_9.clicked.connect(self.set_upload_counts)  # 绑定设置上传数量
        self.pushButton_6.clicked.connect(self.thread_stop)
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

    def all_check(self, status):
        try:
            for i in range(self.tableWidget.rowCount()):
                cell_widget = self.tableWidget.cellWidget(i, 0)
                cell_widget.setChecked(status)
        except Exception as e:
            print(e)

    def thread_stop(self):
        self.thread.stop()
        self.update_button()

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
                print(df.loc[i])
                request_all = ast.literal_eval(df.loc[i, "request_all"])
                keep_cookies(request_all)
        except Exception as e:
            print(e)

    def get_lifeOptionList(self):
        """
        获取子账号
        Returns:
        """
        try:
            self.thread.model = 4
            df = self.get_df()
            df = df.loc[df["is_main_account"] == 1]
            data = self.get_check_row()
            df = df.loc[data]
            update_existing_fields(df)
            self.thread.df = df
            self.thread.start()
            self.update_button()
        except Exception as e:
            print("get_lifeOptionList:", e)

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
            count = int(self.tableWidget.item(i, 5).text()) + 1
            self.tableWidget.setItem(i, 5, QTableWidgetItem(str(count)))
            self.df.at[i, "total_uploads"] = count
            self.df.at[i, "当前上传数"] = self.df.iloc[i]["当前上传数"] + 1
            self.df.at[i, "total_files"] = self.df.iloc[i]["total_files"] - 1
            self.tableWidget.setItem(i, 6, QTableWidgetItem(str(self.df.iloc[i]["当前上传数"])))
            self.tableWidget.setItem(i, 9, QTableWidgetItem(str(self.df.iloc[i]["total_files"])))
        except Exception as e:
            print(e)

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

        for i in range(df.shape[0]):
            # 第一列：复选框 + 序号
            checkbox = QCheckBox()
            checkbox.setChecked(df.iloc[i]["check_"])
            checkbox.setText(str(i + 1))

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

            # 第六列：当前上传数
            self.tableWidget.setItem(i, 6, QTableWidgetItem(str(self.df.iloc[i]["current_uploads"])))

            # 第七列：话题
            self.tableWidget.setItem(i, 7, QTableWidgetItem(str(self.df.iloc[i]["topic_settings"])))

            # 第八列：删除不可推荐
            self.tableWidget.setItem(i, 8, QTableWidgetItem(str(self.df.iloc[i]["delete_unrecommended"])))

            # 第九列：文件总数
            self.tableWidget.setItem(i, 9, QTableWidgetItem(str(self.df.iloc[i]["total_files"])))
            if self.df.iloc[i]["folder_path"] is not None:
                count = self.get_video_count(self.df.iloc[i]["folder_path"])

                self.df.at[i, "total_files"] = count
                self.tableWidget.setItem(i, 9, QTableWidgetItem(str(count)))

            self.tableWidget.setItem(i, 10, QTableWidgetItem("是" if self.df.iloc[i]["is_main_account"] else "否"))
            # 第11列：绑定文件夹
            self.tableWidget.setItem(i, 11, QTableWidgetItem(str(self.df.iloc[i]["folder_path"])))
            # 第12列：按钮
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
            self.tableWidget.setCellWidget(i, 12, button)

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
        if video_count > 0:
            button = self.sender()
            button.setStyleSheet("""
            background-color:rgb(78, 208, 94)""")
        print(video_count)
        try:
            self.df.at[data[1], "folder_path"] = folder_path
            self.df.at[data[1], "total_files"] = video_count
            appid = self.df.iloc[data[1]]["appid"]
            df = self.df[self.df["appid"] == appid]
            update_existing_fields(df)
            self.init_ui()
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
            print(type(cell_widget))
            if isinstance(cell_widget, QCheckBox):
                data.append(cell_widget.isChecked())
        self.df["check_"] = data
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
            self.tableWidget.setItem(row, 9, QTableWidgetItem(str(count)))
        except Exception as e:
            print(e)

    def update_button(self):
        try:
            # 直接取反 `self.thread.isRunning()` 的值
            enabled = not self.thread.isRunning()

            # 使用循环来批量设置按钮状态
            for button in [self.pushButton, self.pushButton_2, self.pushButton_3, self.pushButton_4, self.pushButton_5]:
                button.setEnabled(enabled)
            self.pushButton_6.setEnabled(self.thread.isRunning())
        except Exception as e:
            print(e)

    def claim_task(self):
        logger.info("领取任务")
        self.thread.model = 0
        df = self.get_df()
        data = self.get_check_row()
        df = df.loc[data]
        update_existing_fields(df)
        self.thread.df = df
        self.thread.start()
        self.timer_db.start(1000)
        self.update_button()

    def start_upload(self):
        """
        开始上传
        Returns:

        """
        logger.info("开始上传")
        self.thread.model = 1
        if self.radioButton.isChecked():
            self.thread.timing = self.timeEdit.text()
            self.thread.web_timing = None
        elif self.radioButton_2.isChecked():
            self.thread.web_timing = self.dateTimeEdit.text()
            self.thread.timing = None
        else:
            self.thread.web_timing = None
            self.thread.timing = None
        df = self.get_df()
        data = self.get_check_row()
        df = df.loc[data]
        update_existing_fields(df)
        self.thread.df = df
        self.thread.max_workers = int(self.lineEdit.text())

        self.thread.start()
        self.timer_db.start(1000)
        try:
            self.update_button()
        except Exception as e:
            print(e)

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
            topic_item = self.tableWidget.item(i, 7)
            self.df.at[i, "topic_settings"] = topic_item.text()

            # total_uploads列
            count_item = self.tableWidget.item(i, 5)
            self.df.at[i, "total_uploads"] = int(count_item.text()) if count_item else None

        return self.df


if __name__ == '__main__':
    current_date = datetime.now().strftime('%Y-%m-%d')
    allowed_dates = ['2024-12-16', '2024-12-14']
    if current_date not in allowed_dates:
        sys.exit(0)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
