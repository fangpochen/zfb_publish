import PyInstaller.__main__
import os
import pkg_resources

# 确保logo.ico存在
if not os.path.exists('logo.ico'):
    raise FileNotFoundError("logo.ico not found!")

# 获取 jaraco.text 包的资源文件路径
try:
    dist = pkg_resources.get_distribution('jaraco.text')
    lorem_ipsum_path = os.path.join(dist.location, 'jaraco', 'text', 'Lorem ipsum.txt')
    print(f"资源文件路径: {lorem_ipsum_path}")
    if not os.path.exists(lorem_ipsum_path):
        raise FileNotFoundError(f"找不到文件: {lorem_ipsum_path}")
except Exception as e:
    print(f"错误: {str(e)}")
    raise

target_path = os.path.join('jaraco', 'text')

PyInstaller.__main__.run([
    'app.py',                     # 主程序文件
    '--name=视频批量上传',         # 生成的exe名称
    '--windowed',                  # 使用GUI模式
    '--icon=logo.ico',            # 指定图标
    f'--add-data={lorem_ipsum_path};{target_path}',  # 添加 jaraco.text 资源文件
    '--add-data=logo.ico;.',      # 将图标文件打包进exe
    '--hidden-import=pkg_resources.py2_warn',  # 添加隐藏导入
    '--onefile',                  # 打包成单个文件
    '--clean',                    # 清理临时文件
    '--noconfirm',               # 不确认覆盖
]) 
