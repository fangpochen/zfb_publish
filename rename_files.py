import os

def rename_files(directory):
    # 需要移除的关键字列表
    keywords = ['dou', '抖音', '抖', 'Dou+', 'Dou', 'DOU']
    
    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, filename)):
            new_name = filename
            
            # 依次移除所有关键字
            for keyword in keywords:
                new_name = new_name.replace(keyword, '')
            
            # 如果文件名发生了变化，则重命名
            if new_name != filename:
                old_path = os.path.join(directory, filename)
                new_path = os.path.join(directory, new_name)
                try:
                    os.rename(old_path, new_path)
                    print(f'已重命名: {filename} -> {new_name}')
                except Exception as e:
                    print(f'重命名失败 {filename}: {str(e)}')

if __name__ == '__main__':
    # 在这里输入你的视频目录路径
    directory = r'F:\CRVideoMate Output\创作失败'
    rename_files(directory) 