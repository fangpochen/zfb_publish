import hashlib
import json
import os
from datetime import datetime
import sys
import time
import random
import colorama
from colorama import Fore, Back, Style
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QApplication

# 初始化colorama
colorama.init()

# 加密后的秘钥 (SHA256哈希值)
VALID_KEYS = {
    "134cdb76d93731370a10e953afd3cc48dadd2cfcd46f56fee30355e036aad10e",  # KEY-2024-AASDG-000
    "3764ec5ed7b25bacfdabd577cdd2c61fd14b409e4e97164f53d15456e9f3e4a4",  # KEY-2024-ALPHA-001
    "6ba0b804ac17c806626a84631d3b16bf7be37ace37e62485d5f8367fea4bcb70",  # KEY-2024-BETA-002
    "dee7f27444469e4963f6c511abbcc838f0bf7c184b36827973cffe9308769eaa",  # KEY-2024-GAMMA-003
    "92450ffbb8f6c06830ca674a13c7f7c223b54614821b9d8fb877c66619b1c788",  # KEY-2024-DELTA-004
    "f8104dab2ba294730a74c4f5948e8c394502acc8b449b8add48c6de51b8d88ac",  # KEY-2024-EPSILON-005
    "44361e52dc1d3681a5a5e26de17bbb3a5c9ddaad1a3089e7d9b8e45527233b8b",  # KEY-2024-ALPH24A-006
    "9da165e9dbecd70df4b801a0bb71d6258eccefb32e4ddf4ba58c2fd4173c0d22",  # KEY-2024-B21E2TA-007
    "d8b51ff518fa7f6db7b66cda15cfb71a24b167fa6d77ba25cf5fd2ec5156cd5c",  # KEY-2024-GA1M3MA-008
    "078b3352ea848b144abfcec596c239b34365e5c5e5ef1cf3d2baef74cc318ab7",  # KEY-2024-DEL1TA-009
    "c47dc8f9b6c5cf3e77bcc21304ff00833b5aa7d497ac7a12e7f9c044718b2679",  # KEY-2024-EPS2ILON-010
}

def clear_screen():
    """清除屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """打印程序头部"""
    print(Fore.CYAN + """
    ╔══════════════════════════════════════════╗
    ║             系统授权验证                 ║
    ╚══════════════════════════════════════════╝
    """ + Style.RESET_ALL)

def print_loading(progress):
    """打印加载动画"""
    bar_width = 40
    filled = int(bar_width * progress)
    bar = '█' * filled + '░' * (bar_width - filled)
    print(f'\r{Fore.GREEN}验证进度: |{bar}| {progress*100:.1f}%{Style.RESET_ALL}', end='')

def validate_key(key: str) -> bool:
    """验证输入的秘钥"""
    hashed_key = hashlib.sha256(key.encode()).hexdigest()
    return hashed_key in VALID_KEYS

def save_validated_key(key: str):
    """保存已验证的秘钥"""
    hashed_key = hashlib.sha256(key.encode()).hexdigest()
    data = {
        "key": hashed_key,
        "timestamp": str(datetime.now())
    }
    with open(".keyconfig", "w") as f:
        json.dump(data, f)

def check_saved_key() -> bool:
    """检查保存的秘钥"""
    try:
        if not os.path.exists(".keyconfig"):
            return False
        with open(".keyconfig", "r") as f:
            data = json.load(f)
        return data["key"] in VALID_KEYS
    except:
        return False

def verify_key():
    """验证秘钥的主函数"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        if attempt > 0:
            QMessageBox.warning(None, "警告", f"剩余尝试次数: {max_attempts - attempt}")
        
        key, ok = QInputDialog.getText(None, "系统授权验证", "请输入授权秘钥:")
        if not ok:
            return False
            
        key = key.strip()
        if not key:
            QMessageBox.warning(None, "警告", "秘钥不能为空！")
            attempt += 1
            continue

        if validate_key(key):
            QMessageBox.information(None, "成功", "秘钥验证成功！")
            save_validated_key(key)
            return True
        else:
            QMessageBox.critical(None, "错误", "无效的秘钥！")
            attempt += 1
    return False 