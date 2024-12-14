import logging

# 创建一个文件处理器并指定编码为 UTF-8
file_handler = logging.FileHandler('log.log', encoding='utf-8')

# 创建一个日志格式器
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# 获取根日志器并设置级别
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# 将文件处理器添加到根日志器
logger.addHandler(file_handler)


