import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QMainWindow, QApplication, QTableWidgetItem, QCheckBox, QHBoxLayout, QWidget, QPushButton, \
    QFileDialog, QMessageBox
from ui.ui import Ui_MainWindow
from logger import logger, QTextBrowserLogger
from zfb import *
import pandas as pd

conn = sqlite3.connect('data.db')


class Thread(QThread):
    df = pd.DataFrame()
    model = 0  # 0领取任务 1是传视频 2是查询今日推荐 3是删除平台不推荐视频
    max_workers = 3
    error_signal = pyqtSignal(object)  # 返回异常，并设置cookies失效

    finish_signal = pyqtSignal(object)
    upload_signal = pyqtSignal(int)  # 但账号上传完成, 上传数量 +1, 参数为所在行序号-1
    recommend_signal = pyqtSignal(tuple)  # 更新界面推荐视频数量(账号序号, 推荐数量)
    delete_note_signal = pyqtSignal(tuple)  # 但删除不推荐视频(账号序号, 数量),+n

    def run(self):
        for i in range(self.df.shape[0]):
            try:
                if self.model == 0:
                    self.collecting_tasks(i)

                elif self.model == 1:
                    self.upload_publish_video(i)
                elif self.model == 2:
                    self.get_public_list(i)
                else:
                    self.delete_note(i)
            except Exception as e:
                self.error_signal.emit(i)
        self.finish_signal.emit(None)

    def delete_note(self, i):
        """
        删除平台不推荐视频
        Args:
            i:

        Returns:

        """
        id_listm = get_public_list(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], "delete")
        delete_note(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], id_listm)
        self.delete_note_signal((i, len(id_listm)))

    def get_public_list(self, i):
        """
        查询今日推荐
        Args:
            i:

        Returns:

        """
        recommended_list = get_public_list(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["appid"], "recommend")
        if recommended_list is None:
            return None
        content = f"账号:{self.df.iloc[i]['user_name']}推荐视频id如下:" + "\n    ".join(recommended_list)
        self.recommend_signal((i, len(recommended_list)))
        logger.info(content)

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
        scheduleTime = self.df.iloc[i]["定时日期"] if self.df.iloc[i]["定时日期"] else None
        upload_publish_video(self.df.iloc[i]["cookies_dict"], self.df.iloc[i]["文件夹路径"], "标题", scheduleTime,
                             self.max_workers, signal=self.upload_signal, index=i)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self.lineEdit.setText("3")
        text_browser_handler = QTextBrowserLogger(self.textBrowser)
        logger.addHandler(text_browser_handler)
        self.thread = Thread()
        self.thread.error_signal.connect(self.update_table_cookie)
        self.thread.finish_signal.connect(self.finish)
        self.thread.upload_signal.connect(self.update_table_upload)
        self.thread.recommend_signal.connect(self.update_table_recommend)
        self.thread.delete_note_signal.connect(self.update_table_delete_note)

        self.df = pd.DataFrame()
        self.init_ui()

    def finish(self):
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

    def update_table_recommend(self, data: (int, int)):
        """
        更新推荐视频数量
        Args:
            data:

        Returns:

        """
        count = data[1]
        self.tableWidget.setItem(data[0], 7, QTableWidgetItem(str(count)))
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
        count = int(self.tableWidget.item(i, 5).text()) + 1
        self.tableWidget.setItem(i, 5, QTableWidgetItem(str(count)))
        self.df.at[i, "上传总数"] = count
        self.df.at[i, "当前上传数"] = self.df.iloc[i]["当前上传数"] + 1
        self.tableWidget.setItem(i, 6, QTableWidgetItem(str(self.df.iloc[i]["当前上传数"])))

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
        self.df = pd.read_sql("select appid,  user_name, cookies from user_data", conn)
        self.df['cookies_dict'] = self.df['cookies'].apply(json.loads)
        self.df['check'] = True
        self.df['今日推荐数'] = '未查询'
        self.df['Cookie状态'] = '正常'
        self.df['上传总数'] = 0
        self.df['当前上传数'] = 0
        self.df['话题设置'] = '每日一看'
        self.df['删除不可推荐'] = ''
        self.df['文件总数'] = ''
        self.df['文件夹路径'] = ''
        self.df['定时日期'] = ''
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
            checkbox.setChecked(True)
            checkbox.setText(str(i + 1))
            checkbox_widget = QWidget()
            layout = QHBoxLayout(checkbox_widget)
            layout.addWidget(checkbox)
            layout.setAlignment(checkbox, Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            appid = str(df.iloc[i, 0])  # 获取 appId
            self.tableWidget.setCellWidget(i, 0, checkbox_widget)
            # self.tableWidget.setItem(i, 0, QTableWidgetItem(str(i + 1)))  # 显示序号

            # 第二列：appId
            self.tableWidget.setItem(i, 1, QTableWidgetItem(str(df.iloc[i, 0])))

            # 第三列：账号名称
            self.tableWidget.setItem(i, 2, QTableWidgetItem(str(df.iloc[i, 1])))

            # 第四列：推荐数
            self.tableWidget.setItem(i, 3, QTableWidgetItem(str("未查询")))
            # 第四列：cookies状态
            self.tableWidget.setItem(i, 4, QTableWidgetItem(str("正常")))

            # 第五列：上传总数
            self.tableWidget.setItem(i, 5, QTableWidgetItem('0'))

            # 第六列：当前上传数
            self.tableWidget.setItem(i, 6, QTableWidgetItem('0'))

            # 第七列：话题
            self.tableWidget.setItem(i, 7, QTableWidgetItem(str("话题")))

            # 第八列：删除不可推荐
            self.tableWidget.setItem(i, 8, QTableWidgetItem('0'))

            # 第九列：文件总数
            self.tableWidget.setItem(i, 9, QTableWidgetItem('0'))
            # 第10列：定时日期
            self.tableWidget.setItem(i, 10, QTableWidgetItem(''))
            # 第十一列：按钮
            button = QPushButton("绑定文件夹")
            button.clicked.connect(lambda checked, data=(appid, i): self.bind_folder(data))
            self.tableWidget.setCellWidget(i, 11, button)

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

        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}

        video_count = sum(1 for file in os.listdir(folder_path)
                          if os.path.isfile(os.path.join(folder_path, file)) and os.path.splitext(file)[
                              1].lower() in video_extensions)
        print(video_count)
        self.df.iloc[data[1]]["文件夹路径"] = folder_path
        self.df.iloc[data[1]]["文件总数"] = video_count
        self.update_video_count(data[1], video_count)

    def update_video_count(self, row, count):
        self.tableWidget.setItem(row, 9, QTableWidgetItem(str(count)))

    def update_button(self):
        self.pushButton.setEnabled(not self.thread.isRunning())
        self.pushButton_2.setEnabled(not self.thread.isRunning())
        self.pushButton_3.setEnabled(not self.thread.isRunning())
        self.pushButton_4.setEnabled(not self.thread.isRunning())
        self.pushButton_5.setEnabled(not self.thread.isRunning())

    def claim_task(self):
        logger.info("领取任务")
        self.thread.model = 0
        self.thread.df = self.get_df()
        self.thread.start()
        self.update_button()

    def start_upload(self):
        """
        开始上传
        Returns:

        """
        logger.info("开始上传")
        self.thread.model = 1
        self.thread.df = self.get_df()
        self.thread.max_workers = int(self.lineEdit.text())
        self.thread.start()
        self.update_button()

    def get_today_recommendations(self):
        """
        查询今日推荐
        Returns:

        """
        logger.info("查询今日推荐")
        self.thread.model = 2
        self.thread.df = self.get_df()
        self.thread.start()
        self.update_button()

    def delete_non_recommended_videos(self):
        """
        删除平台不推荐视频
        Returns:

        """
        logger.info("删除平台不推荐的视频")
        self.thread.model = 3
        self.thread.df = self.get_df()
        self.thread.start()
        self.update_button()

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
                self.df.at[i, "check"] = cell_widget.isChecked()

            # 更新话题设置列
            topic_item = self.tableWidget.item(i, 7)
            self.df.at[i, "话题设置"] = topic_item.text() if topic_item else None

            # 更新定时日期列
            date_item = self.tableWidget.item(i, 10)
            self.df.at[i, "定时日期"] = date_item.text() if date_item and date_item.text() else None

        return self.df


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
