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
    "9303a6bb9269018206b8ddeb066aede53df90a5e2f9bf2cab216034a42313322",  # KEY-2024-ZETA-011
    "8d62696068ccc677eb023703585fbe9098e1eb7158771fd8c10f9c0eecbe2f2d",  # KEY-2024-ETA-012
    "1685de385db33a295b95299ac2f7e129f083a25b7f9e6889b1230331581ed8f6",  # KEY-2024-THETA-013
    "379d8ea5064134c117edc5ceb69900e82516e725bea0398d2758ad7e13b5204f",  # KEY-2024-IOTA-014
    "e04ff26e3a5de0871453b49bd5d538eea955432fefd8e1df85266249d2e8f9bc",  # KEY-2024-KAPPA-015
    "b9b06879dfa9be0cdc4179a4c961e23ad12b381cd405b104464b393b7636f016",  # KEY-2024-LAMBDA-016
    "440cae878be5f91345f58eba0a808605aa29a028c17625c21f18c22269dc23fd",  # KEY-2024-MU-017
    "d51f40aa5ef3a82854728a79ffe20c484bf8c8f95f38831efd274a41b7e6c80f",  # KEY-2024-NU-018
    "e0b80a832f9ebba5b3c20c9c2bd44c055db92e9076cd17e408f9fb5e1fef3a01",  # KEY-2024-XI-019
    "2af4375161ceafe2cba6c93c56f0a7ed9bf22b2f7db15ca82f2f48b151f95d5f",  # KEY-2024-OMICRON-020
    "636968f2e441a962709adf25864fad989a45b72fbe010e1aaa3c10a7a51e6d59",  # KEY-2024-PI-021
    "e3652fee22f948f9571bfe3972113b1cad7548c9e43a6a5c21675233fbd5c933",  # KEY-2024-RHO-022
    "325536db2a6f76854d71268bc77791962a62137fc435739d32430f227f00e55f",  # KEY-2024-SIGMA-023
    "5db18be96dc9c94a093a6d8a0cb42165ae6f7bfbc69457ebd52213d4406b2737",  # KEY-2024-TAU-024
    "6e95b2ed03271fb700700d66fa2636de42206885e129ef6f5c820b7782adce36",  # KEY-2024-UPSILON-025
    "9db3a1e535bc84a72e914b233d6d5693f05869ed3ab9372a320d68b0e78e7a13",  # KEY-2024-PHI-026
    "48ffae468540142766d2a72ce777c4854005c8bc600ffde7b79e4d0daca59532",  # KEY-2024-CHI-027
    "f6b96406eb634c66ed774cc366a6b3c28d235c126b0a248e84c8ba16f0f97dac",  # KEY-2024-PSI-028
    "37d3a42541a0a632b885af74cc1b1671cd4551dc256ff622eb47eede253d5fdc",  # KEY-2024-OMEGA-029
    "862c9351c88424fa6e815a0bf474fa19550f86e68e734e0bcd62c6c834caa358",  # KEY-2024-SIGMA2-030
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