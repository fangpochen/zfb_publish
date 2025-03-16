import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QLineEdit, QPushButton, QLabel, QMessageBox)
from PyQt5.QtCore import Qt
import requests
import platform
import uuid
import socket
import cpuinfo
import logging
import netifaces
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
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_LINK in addrs and not iface.startswith(('lo', 'virbr', 'docker')):
            mac = addrs[netifaces.AF_LINK][0]['addr']
            if mac != "00:00:00:00:00:00":
                return mac
    return None
def verify_key(api_key):
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