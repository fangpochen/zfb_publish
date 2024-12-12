import logging

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


class QTextBrowserLogger(logging.Handler):
    def __init__(self, text_browser):
        super().__init__()
        self.text_browser = text_browser
        self.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    def emit(self, record):
        msg = self.format(record)
        self.text_browser.append(msg)
        self.text_browser.ensureCursorVisible()
