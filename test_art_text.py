#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
艺术字渲染测试工具

这个工具用于测试视频艺术字渲染功能，会从视频中提取第一秒的帧，
然后用PyQt5绘图功能添加艺术字，并保存结果。
"""

import os
import sys
import cv2
import tempfile
import argparse
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage, QPainter, QFont, QColor, QPixmap, QPen
from PyQt5.QtCore import Qt, QRect

# 创建全局QApplication实例
app = None


def extract_first_frame(video_path, output_path=None):
    """
    从视频中提取第一秒的帧
    
    Args:
        video_path: 视频文件路径
        output_path: 输出图片路径，如果为None则创建临时文件
        
    Returns:
        str: 提取的帧图片路径
    """
    try:
        # 使用OpenCV打开视频文件
        video = cv2.VideoCapture(video_path)
        
        if not video.isOpened():
            print(f"错误: 无法打开视频文件 {video_path}")
            return None
        
        # 获取视频帧率
        fps = video.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25  # 默认帧率
            print(f"警告: 无法获取视频帧率，使用默认值 {fps}")
        
        # 计算第一秒中间的帧索引
        frame_index = int(fps / 2)
        
        # 设置读取位置
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        
        # 读取帧
        success, frame = video.read()
        
        if not success:
            print(f"错误: 无法读取视频 {video_path} 的第 {frame_index} 帧")
            video.release()
            return None
        
        # 如果没有指定输出路径，创建临时文件
        if not output_path:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            output_path = temp_file.name
            temp_file.close()
        
        # 保存帧为图片
        cv2.imwrite(output_path, frame)
        
        # 释放视频对象
        video.release()
        
        return output_path
    
    except Exception as e:
        print(f"提取视频帧时出错: {str(e)}")
        traceback.print_exc()
        return None


def render_art_text(image_path, text, style="标准", color="白色", position="底部居中", font_size=36, custom_font=None):
    """
    在图片上渲染艺术字
    
    Args:
        image_path: 图片路径
        text: 要渲染的文本
        style: 字体样式
        color: 文字颜色
        position: 文本位置
        font_size: 字体大小
        custom_font: 自定义字体文件路径，可选
        
    Returns:
        str: 渲染后的图片路径
    """
    global app
    
    # 确保QApplication实例存在
    if app is None:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            print("已创建QApplication实例")
    
    try:
        # 颜色映射
        color_map = {
            "白色": QColor(255, 255, 255),
            "黑色": QColor(0, 0, 0),
            "红色": QColor(255, 0, 0),
            "蓝色": QColor(0, 0, 255),
            "绿色": QColor(0, 255, 0),
            "黄色": QColor(255, 255, 0),
            "粉色": QColor(255, 192, 203),
            "紫色": QColor(128, 0, 128),
            "橙色": QColor(255, 165, 0)
        }
        text_color = color_map.get(color, QColor(255, 255, 255))
        
        # 加载自定义字体（如果提供）
        font_family = None
        if custom_font and os.path.exists(custom_font):
            try:
                from PyQt5.QtGui import QFontDatabase
                font_id = QFontDatabase.addApplicationFont(custom_font)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        font_family = families[0]
                        print(f"已加载自定义字体: {os.path.basename(custom_font)} -> {font_family}")
                else:
                    print(f"无法加载自定义字体: {custom_font}")
            except Exception as e:
                print(f"加载自定义字体时出错: {str(e)}")
                traceback.print_exc()
        
        # 字体映射 - 使用Qt支持的字体
        font_map = {
            "标准": "Arial",
            "艺术风格一": "Arial",
            "艺术风格二": "Times New Roman",
            "霓虹灯": "Impact",
            "复古": "Georgia",
            "水墨风": "SimKai",  # 楷体
            "书法": "SimLi",     # 隶书
            "华丽花体": "STXingkai"  # 行楷
        }
        
        # 获取字体名称
        if font_family:
            # 优先使用自定义字体
            font_name = font_family
            print(f"使用自定义字体: {font_name}")
        else:
            # 否则使用预定义字体
            font_name = font_map.get(style, "Arial")
        
        # 使用OpenCV读取图片以获取尺寸
        cv_img = cv2.imread(image_path)
        height, width, channels = cv_img.shape
        
        # 创建临时文件保存渲染结果
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        output_path = temp_file.name
        temp_file.close()
        
        # 加载图片到QImage
        image = QImage(image_path)
        if image.isNull():
            print(f"错误: 无法加载图片 {image_path}")
            return None
        
        # 创建绘制器
        painter = QPainter()
        painter.begin(image)
        
        # 设置抗锯齿
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # 创建字体
        font = QFont(font_name, font_size)
        font.setBold(True)  # 加粗提高可读性
        painter.setFont(font)
        
        # 测量文本尺寸
        fm = painter.fontMetrics()
        try:
            # Qt5.11+使用horizontalAdvance
            text_width = fm.horizontalAdvance(text)
        except AttributeError:
            # 旧版本使用width
            text_width = fm.width(text)
        text_height = fm.height()
        
        # 计算背景矩形区域高度
        bg_height = int(text_height * 1.5)
        
        # 确定文本位置和背景区域
        x, y = 0, 0
        if position == "顶部居中":
            x = (width - text_width) // 2
            y = text_height + 10
            bg_rect = QRect(0, 0, width, bg_height)
        elif position == "底部居中":
            x = (width - text_width) // 2
            y = height - 10
            bg_rect = QRect(0, height - bg_height, width, bg_height)
        elif position == "居中":
            x = (width - text_width) // 2
            y = (height + text_height) // 2
            bg_rect = QRect(0, (height - bg_height) // 2, width, bg_height)
        else:  # 默认底部居中
            x = (width - text_width) // 2
            y = height - 10
            bg_rect = QRect(0, height - bg_height, width, bg_height)
        
        # 绘制半透明背景
        bg_color = QColor(0, 0, 0, 128)  # 半透明黑色
        painter.fillRect(bg_rect, bg_color)
        
        # 设置文本画笔颜色
        painter.setPen(text_color)
        
        # 如果是霓虹灯样式，添加发光效果
        if style == "霓虹灯":
            # 添加文字阴影/光晕效果
            glow_color = QColor(text_color)
            glow_color.setAlpha(80)  # 降低不透明度
            
            # 绘制4个方向的阴影
            offsets = [(1, 1), (-1, 1), (1, -1), (-1, -1)]
            for offset_x, offset_y in offsets:
                painter.setPen(glow_color)
                painter.drawText(x + offset_x, y + offset_y, text)
        
        # 绘制文本
        painter.setPen(text_color)
        painter.drawText(x, y, text)
        
        # 完成绘制
        painter.end()
        
        # 保存结果
        if image.save(output_path, "JPG", 95):
            print(f"成功渲染艺术字图片: {output_path}")
            return output_path
        else:
            print(f"保存渲染结果失败!")
            return None
    
    except Exception as e:
        print(f"渲染艺术字时出错: {str(e)}")
        traceback.print_exc()
        return None


def preview_image(image_path):
    """
    使用OpenCV预览图片
    
    Args:
        image_path: 图片路径
    """
    try:
        # 读取图片
        img = cv2.imread(image_path)
        if img is None:
            print(f"错误: 无法读取图片 {image_path}")
            return
        
        # 获取图片尺寸
        height, width = img.shape[:2]
        
        # 如果图片太大，调整窗口大小
        max_width = 1280
        max_height = 720
        window_width = width
        window_height = height
        
        if width > max_width or height > max_height:
            scale = min(max_width / width, max_height / height)
            window_width = int(width * scale)
            window_height = int(height * scale)
        
        # 创建窗口并显示图片
        window_name = "艺术字预览"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, window_width, window_height)
        cv2.imshow(window_name, img)
        
        print("按任意键关闭预览窗口...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    except Exception as e:
        print(f"预览图片时出错: {str(e)}")
        traceback.print_exc()


def main():
    """主函数"""
    global app
    
    # 首先确保存在QApplication实例
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        print("已创建QApplication实例")
    
    parser = argparse.ArgumentParser(description="艺术字渲染测试工具")
    parser.add_argument("video_path", help="视频文件路径")
    parser.add_argument("--text", "-t", default="测试艺术字", help="要渲染的文本")
    parser.add_argument("--style", "-s", default="标准", 
                        choices=["标准", "艺术风格一", "艺术风格二", "霓虹灯", "复古", "水墨风", "书法", "华丽花体"],
                        help="字体样式")
    parser.add_argument("--color", "-c", default="白色",
                        choices=["白色", "黑色", "红色", "蓝色", "绿色", "黄色", "粉色", "紫色", "橙色"],
                        help="文字颜色")
    parser.add_argument("--position", "-p", default="底部居中",
                        choices=["顶部居中", "底部居中", "居中"],
                        help="文本位置")
    parser.add_argument("--font-size", "-f", type=int, default=36, help="字体大小")
    parser.add_argument("--output", "-o", help="输出图片路径")
    parser.add_argument("--no-preview", action="store_true", help="不预览结果")
    parser.add_argument("--custom-font", help="自定义字体文件路径")
    
    args = parser.parse_args()
    
    # 检查视频文件是否存在
    if not os.path.exists(args.video_path):
        print(f"错误: 视频文件不存在: {args.video_path}")
        return 1
    
    # 获取指定输出路径或创建临时文件
    output_path = args.output
    if not output_path:
        output_dir = os.path.dirname(os.path.abspath(args.video_path))
        output_name = os.path.splitext(os.path.basename(args.video_path))[0] + "_art_text.jpg"
        output_path = os.path.join(output_dir, output_name)
    
    print(f"从视频 {args.video_path} 提取第一秒帧...")
    frame_path = extract_first_frame(args.video_path)
    
    if not frame_path:
        print("提取视频帧失败，无法继续处理")
        return 1
    
    print(f"提取帧成功: {frame_path}")
    
    # 检查自定义字体
    if args.custom_font:
        if not os.path.exists(args.custom_font):
            print(f"警告: 指定的自定义字体文件不存在: {args.custom_font}")
            args.custom_font = None
        else:
            print(f"将使用自定义字体: {args.custom_font}")
    
    print(f"渲染艺术字: '{args.text}' (样式: {args.style}, 颜色: {args.color}, 位置: {args.position})...")
    
    result_path = render_art_text(
        frame_path, 
        args.text,
        style=args.style,
        color=args.color,
        position=args.position,
        font_size=args.font_size,
        custom_font=args.custom_font
    )
    
    if not result_path:
        print("渲染艺术字失败")
        # 删除临时帧文件
        if os.path.exists(frame_path) and "temp" in frame_path:
            os.unlink(frame_path)
        return 1
    
    # 将结果复制到最终输出路径
    if result_path != output_path:
        import shutil
        shutil.copy2(result_path, output_path)
        print(f"结果已保存至: {output_path}")
        
        # 删除临时文件
        if os.path.exists(result_path) and "temp" in result_path:
            os.unlink(result_path)
    
    # 预览结果
    if not args.no_preview:
        print("预览渲染结果...")
        preview_image(output_path)
    
    # 删除临时帧文件
    if os.path.exists(frame_path) and "temp" in frame_path:
        os.unlink(frame_path)
    
    print("处理完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 