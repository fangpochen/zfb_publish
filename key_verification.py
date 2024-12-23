import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QLineEdit, QPushButton, QLabel, QMessageBox)
from PyQt5.QtCore import Qt
import requests
import platform
import uuid
import socket
import cpuinfo

class KeyVerificationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.verified = False
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('API密钥验证')
        self.setFixedSize(400, 200)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel('请输入API密钥进行验证')
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText('在此输入您的API密钥')
        layout.addWidget(self.key_input)
        
        verify_button = QPushButton('验证')
        verify_button.clicked.connect(self.verify_key)
        layout.addWidget(verify_button)
        
        self.status_label = QLabel('')
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        layout.addStretch()

    def verify_key(self):
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, '警告', '请输入API密钥')
            return
            
        self.status_label.setText('正在验证...')
        result = self.verify_api_key(api_key)
        
        if result and result.get('status') == 'success':  # 根据实际API返回格式调整
            QMessageBox.information(self, '成功', '密钥验证成功！')
            self.verified = True
            self.close()
        else:
            self.status_label.setText('验证失败')
            QMessageBox.critical(self, '错误', '密钥验证失败，请检查后重试')

    def verify_api_key(self, api_key):
        hostname = socket.gethostname()
        os_info = f"{platform.system()} {platform.release()}"
        cpu_info = cpuinfo.get_cpu_info()['brand_raw']
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                        for elements in range(0,2*6,2)][::-1])

        url = "http://localhost:8000/api/v1/api-keys/verify"
        headers = {"Content-Type": "application/json"}
        payload = {
            "key": api_key,
            "machine_info": {
                "hostname": hostname,
                "os": os_info,
                "cpu": cpu_info,
                "mac": mac
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            if result.get("valid") is True:
                return {"status": "success"}
            return {"status": "failed"}
        except requests.exceptions.RequestException as e:
            print(f"验证失败: {e}")
            return None

def verify_key_with_gui():
    app = QApplication(sys.argv)
    window = KeyVerificationWindow()
    window.show()
    app.exec_()
    return window.verified 