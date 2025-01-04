import logging
import os
from logging.handlers import RotatingFileHandler

# 创建logger对象
logger = logging.getLogger('app')
logger.setLevel(logging.INFO)  # 设置为INFO级别

# 创建文件处理器
if not os.path.exists('log.log'):
    open('log.log', 'w').close()

file_handler = RotatingFileHandler(
    'log.log',
    maxBytes=5*1024*1024,  # 5MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)  # 文件处理器也设置为INFO级别

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(file_handler)


