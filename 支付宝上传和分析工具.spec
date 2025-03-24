# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

block_cipher = None

# 定义资源文件
datas = []

# 添加fonts目录
if os.path.exists('fonts'):
    datas.append(('fonts', 'fonts'))

# 添加其他可能的资源目录
for dir_name in ['assets', 'data', 'ui', 'utils']:
    if os.path.exists(dir_name):
        datas.append((dir_name, dir_name))

# 添加单个文件
for file_name in ['logo.ico', 'logo.png', 'config.json.example', 'favorite_topics.json']:
    if os.path.exists(file_name):
        datas.append((file_name, '.'))

# 添加certifi证书文件
try:
    import certifi
    cert_path = certifi.where()
    if os.path.exists(cert_path):
        datas.append((cert_path, 'certifi'))
        print(f"添加证书文件: {cert_path}")
except ImportError:
    print("警告: 未安装certifi模块")

# 收集所有Python文件
py_files = []
for root, dirs, files in os.walk('.'):
    if '__pycache__' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            file_path = os.path.join(root, file)
            py_files.append(file_path)

a = Analysis(
    ['launcher\launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.sip',
        'requests', 'urllib3', 'sqlite3', 'pandas', 'cryptography', 'concurrent.futures',
        'threading', 'json', 'datetime', 'numpy', 'zipfile', 'logging',
        'multiprocessing', 'ast', 'warnings', 'certifi', 'ssl', 'socket',
        'PIL', 'time', 'os', 'sys', 'platform', 'shutil', 'uuid', 're', 'random',
        'key_verification', 'database', 'recommend_analysis_ui', 'account_manager',
        'folder_manager', 'video_analyzer', 'chart_manager', 'upload_controller',
        'api_client', 'main'
    ] + ['account_manager', 'api_client', 'app', 'build', 'build_dir', 'chart_manager', 'database', 'db', 'folder_manager', 'generate_hash', 'key_verification', 'logger', 'main', 'recommend_analysis_ui', 'rename_files', 'test_api', 'test_art_text', 'test_db', 'test_upload', 'upload_controller', 'upload_ui', 'video_analyzer', 'zfb', 'utils.queue_manager', 'utils.thread_pool', 'utils.upload_controller', 'utils.upload_processor', 'utils.upload_statistics', 'utils.video_task', 'utils.__init__', 'ui.ui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hooks/simple_hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='支付宝上传和分析工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=".",  # 设置为当前目录
    console=True,  # 使用控制台模式以便查看报错信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico' if os.path.exists('logo.ico') else None,
)
