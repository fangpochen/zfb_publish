import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QLineEdit, QPushButton, QLabel, QMessageBox, QHBoxLayout,
                            QDialog, QFormLayout, QCheckBox)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon, QPixmap
import requests
import platform
import uuid
import socket
import cpuinfo
import logging
import netifaces
import os
# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('key_verification.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('key_verification')

def get_physical_mac():
    """获取物理MAC地址"""
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_LINK in addrs and not iface.startswith(('lo', 'virbr', 'docker')):
            mac = addrs[netifaces.AF_LINK][0]['addr']
            if mac != "00:00:00:00:00:00":
                return mac
    return None

def verify_key(api_key):
    """验证API密钥

    Args:
        api_key: 用户输入的API密钥
        
    Returns:
        bool: 验证是否成功
    """
    hostname = socket.gethostname()
    os_info = f"{platform.system()} {platform.release()}"
    cpu_info = cpuinfo.get_cpu_info()['brand_raw']
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                    for elements in range(0,2*6,2)][::-1])

    url = "https://api.cloudoption.site/api/v1/api-keys/verify"
    headers = {"Content-Type": "application/json"}
    payload = {
        "key": api_key,
        "machine_info": {
            "hostname": hostname,
            "os": os_info,
            "cpu": cpu_info,
            "mac": mac,
            "item": "upload"
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, verify=True)
        response.raise_for_status()
        result = response.json()
        logger.info(f"密钥验证结果: {result}")
        return result.get("valid", False)
    except requests.exceptions.RequestException as e:
        logger.error(f"密钥验证请求失败: {str(e)}")
        return False

def save_api_key(api_key):
    """保存API密钥到配置文件
    
    Args:
        api_key: 要保存的API密钥
    """
    settings = QSettings("ZFBPublish", "APIKey")
    settings.setValue("api_key", api_key)
    logger.info("API密钥已保存")

def load_api_key():
    """从配置文件加载API密钥
    
    Returns:
        str: 保存的API密钥，如果不存在则返回空字符串
    """
    settings = QSettings("ZFBPublish", "APIKey")
    return settings.value("api_key", "")

def is_remember_key_enabled():
    """检查是否启用了记住密钥功能
    
    Returns:
        bool: 是否记住密钥
    """
    settings = QSettings("ZFBPublish", "APIKey")
    return settings.value("remember_key", True, type=bool)

def save_remember_key_setting(remember):
    """保存记住密钥设置
    
    Args:
        remember: 是否记住密钥
    """
    settings = QSettings("ZFBPublish", "APIKey")
    settings.setValue("remember_key", remember)
    logger.info(f"记住密钥设置已更新: {remember}")

class KeyVerificationDialog(QDialog):
    """API密钥验证对话框"""
    
    def __init__(self, parent=None):
        """初始化密钥验证对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.verified = False
        self.setWindowTitle("API密钥验证")
        self.setFixedSize(400, 220)  # 增加高度以适应新增的复选框
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 标记是否为自动验证
        self.is_auto_verification = False
        
        # 设置布局
        self.setup_ui()
        
        # 加载记住密钥设置
        remember_enabled = is_remember_key_enabled()
        self.remember_checkbox.setChecked(remember_enabled)
        
        # 加载保存的密钥
        if remember_enabled:
            saved_key = load_api_key()
            if saved_key:
                self.key_input.setText(saved_key)
                # 标记为自动验证并执行
                self.is_auto_verification = True
                # 自动尝试验证
                self.verify_api_key()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        
        # 添加Logo（如果存在）
        if os.path.exists("logo.png"):
            logo_label = QLabel()
            pixmap = QPixmap("logo.png")
            logo_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_label)
        
        # 添加说明文字
        info_label = QLabel("请输入API密钥以验证您的身份:")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 添加输入框
        form_layout = QFormLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("请输入您的API密钥...")
        self.key_input.setEchoMode(QLineEdit.Password)  # 密码模式
        form_layout.addRow("API密钥:", self.key_input)
        layout.addLayout(form_layout)
        
        # 添加记住密钥复选框
        self.remember_checkbox = QCheckBox("记住我的密钥")
        self.remember_checkbox.setChecked(True)  # 默认选中
        layout.addWidget(self.remember_checkbox)
        
        # 添加按钮
        button_layout = QHBoxLayout()
        self.verify_button = QPushButton("验证")
        self.verify_button.clicked.connect(self.verify_api_key)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.verify_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def verify_api_key(self):
        """验证用户输入的API密钥"""
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "错误", "请输入API密钥!")
            return
        
        # 显示正在验证的消息
        self.verify_button.setEnabled(False)
        self.verify_button.setText("验证中...")
        QApplication.processEvents()
        
        # 验证密钥
        valid = verify_key(api_key)
        
        self.verify_button.setEnabled(True)
        self.verify_button.setText("验证")
        
        if valid:
            # 保存记住密钥设置
            remember = self.remember_checkbox.isChecked()
            save_remember_key_setting(remember)
            
            # 如果选择记住密钥，则保存密钥
            if remember:
                save_api_key(api_key)
                logger.info("用户选择记住密钥，密钥已保存")
            else:
                # 如果不记住，清除之前保存的密钥
                save_api_key("")
                logger.info("用户选择不记住密钥，已清除之前保存的密钥")
                
            self.verified = True
            
            # 只有在手动验证时才显示成功消息
            if not self.is_auto_verification:
                QMessageBox.information(self, "成功", "API密钥验证成功!")
            else:
                logger.info("自动验证成功，跳过显示成功消息")
            
            self.accept()
        else:
            # 如果是自动验证失败，不显示错误消息，只是重置状态让用户手动输入
            if self.is_auto_verification:
                logger.info("自动验证失败，等待用户手动输入")
                self.is_auto_verification = False  # 重置为手动验证模式
            else:
                QMessageBox.critical(self, "错误", "API密钥验证失败，请检查您的密钥或网络连接!")


def show_verification_dialog():
    """显示验证对话框并返回验证结果
    
    Returns:
        bool: 是否验证成功
    """
    dialog = KeyVerificationDialog()
    result = dialog.exec_()
    return dialog.verified


if __name__ == "__main__":
    # 测试验证对话框
    app = QApplication(sys.argv)
    if show_verification_dialog():
        print("验证成功!")
    else:
        print("验证失败或被取消!")
    sys.exit(0) 