import sys

from PyQt5.QtWidgets import QMainWindow, QApplication
from ui.ui import Ui_MainWindow
from logger import logger, QTextBrowserLogger


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        text_browser_handler = QTextBrowserLogger(self.textBrowser)
        logger.addHandler(text_browser_handler)

    def login(self):
        logger.info("登入")

    def claim_task(self):
        logger.info("领取任务")

    def start_upload(self):
        logger.info("开始上传")

    def get_today_recommendations(self):
        logger.info("查询今日推荐")

    def delete_non_recommended_videos(self):
        logger.info("删除平台不推荐的视频")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
