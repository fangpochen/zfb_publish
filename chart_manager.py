#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QComboBox, QLabel, QWidget, QSizePolicy)
from PyQt5.QtCore import Qt

# 设置matplotlib中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 显示中文标签
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决保存图像负号'-'显示为方块的问题

class MatplotlibCanvas(FigureCanvas):
    """Matplotlib画布类，用于嵌入PyQt5界面"""
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        """初始化画布
        
        Args:
            parent: 父窗口对象
            width: 宽度，单位英寸
            height: 高度，单位英寸
            dpi: 分辨率
        """
        # 创建一个Figure
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        
        # 初始化父类
        super(MatplotlibCanvas, self).__init__(self.fig)
        self.setParent(parent)
        
        # 调整大小
        FigureCanvas.setSizePolicy(self,
                                  QSizePolicy.Expanding,
                                  QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

class ChartDialog(QDialog):
    """图表对话框，用于显示数据可视化图表"""
    
    def __init__(self, parent=None, title="数据分析图表"):
        """初始化图表对话框
        
        Args:
            parent: 父窗口对象
            title: 对话框标题
        """
        super(ChartDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        
        # 创建布局
        self.layout = QVBoxLayout()
        
        # 创建画布
        self.canvas = MatplotlibCanvas(self, width=8, height=6)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # 创建图表类型选择控件
        self.chart_control = QWidget()
        self.chart_layout = QHBoxLayout(self.chart_control)
        self.chart_layout.addWidget(QLabel("图表类型:"))
        
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["柱状图", "折线图", "饼图", "散点图", "热力图"])
        self.chart_type_combo.currentIndexChanged.connect(self.change_chart_type)
        self.chart_layout.addWidget(self.chart_type_combo)
        
        # 添加控件到布局
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)
        self.layout.addWidget(self.chart_control)
        
        # 设置布局
        self.setLayout(self.layout)
        
        # 当前图表类型
        self.current_chart_type = "柱状图"
        # 当前数据
        self.data = None
    
    def change_chart_type(self, index):
        """切换图表类型
        
        Args:
            index: 图表类型索引
        """
        chart_types = ["柱状图", "折线图", "饼图", "散点图", "热力图"]
        self.current_chart_type = chart_types[index]
        
        # 如果已有数据，则重新绘制图表
        if self.data is not None:
            self.plot_data(self.data)
    
    def plot_data(self, data):
        """绘制数据图表
        
        Args:
            data: 数据，可以是DataFrame或dict
        """
        self.data = data
        
        # 清空当前图表
        self.canvas.axes.clear()
        
        # 根据图表类型绘制
        if self.current_chart_type == "柱状图":
            self._plot_bar_chart(data)
        elif self.current_chart_type == "折线图":
            self._plot_line_chart(data)
        elif self.current_chart_type == "饼图":
            self._plot_pie_chart(data)
        elif self.current_chart_type == "散点图":
            self._plot_scatter_chart(data)
        elif self.current_chart_type == "热力图":
            self._plot_heatmap(data)
        
        # 调整布局并更新画布
        self.canvas.fig.tight_layout()
        self.canvas.draw()
    
    def _plot_bar_chart(self, data):
        """绘制柱状图
        
        Args:
            data: 数据字典或DataFrame
        """
        try:
            if isinstance(data, dict):
                x = list(data.keys())
                y = list(data.values())
                self.canvas.axes.bar(x, y)
                self.canvas.axes.set_title("柱状图")
                self.canvas.axes.set_xlabel("类别")
                self.canvas.axes.set_ylabel("数值")
                if len(x) > 10:
                    self.canvas.axes.tick_params(axis='x', rotation=45)
            elif isinstance(data, pd.DataFrame):
                data.plot(kind='bar', ax=self.canvas.axes)
                self.canvas.axes.set_title("柱状图")
                if len(data) > 10:
                    self.canvas.axes.tick_params(axis='x', rotation=45)
        except Exception as e:
            print(f"绘制柱状图时出错: {str(e)}")
            traceback.print_exc()
    
    def _plot_line_chart(self, data):
        """绘制折线图
        
        Args:
            data: 数据字典或DataFrame
        """
        try:
            if isinstance(data, dict):
                x = list(data.keys())
                y = list(data.values())
                self.canvas.axes.plot(x, y, marker='o')
                self.canvas.axes.set_title("折线图")
                self.canvas.axes.set_xlabel("类别")
                self.canvas.axes.set_ylabel("数值")
                if len(x) > 10:
                    self.canvas.axes.tick_params(axis='x', rotation=45)
            elif isinstance(data, pd.DataFrame):
                data.plot(kind='line', marker='o', ax=self.canvas.axes)
                self.canvas.axes.set_title("折线图")
                if len(data) > 10:
                    self.canvas.axes.tick_params(axis='x', rotation=45)
        except Exception as e:
            print(f"绘制折线图时出错: {str(e)}")
            traceback.print_exc()
    
    def _plot_pie_chart(self, data):
        """绘制饼图
        
        Args:
            data: 数据字典或DataFrame
        """
        try:
            if isinstance(data, dict):
                labels = list(data.keys())
                sizes = list(data.values())
                self.canvas.axes.pie(sizes, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
                self.canvas.axes.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                self.canvas.axes.set_title("饼图")
            elif isinstance(data, pd.DataFrame):
                if len(data.columns) > 1:
                    # 如果有多列，使用第一列作为标签，第二列作为值
                    labels = data.iloc[:, 0].tolist()
                    sizes = data.iloc[:, 1].tolist()
                else:
                    # 只有一列，使用索引作为标签
                    labels = data.index.tolist()
                    sizes = data.iloc[:, 0].tolist()
                
                self.canvas.axes.pie(sizes, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
                self.canvas.axes.axis('equal')
                self.canvas.axes.set_title("饼图")
        except Exception as e:
            print(f"绘制饼图时出错: {str(e)}")
            traceback.print_exc()
    
    def _plot_scatter_chart(self, data):
        """绘制散点图
        
        Args:
            data: 数据DataFrame，需要至少两列数据
        """
        try:
            if isinstance(data, pd.DataFrame) and len(data.columns) >= 2:
                x = data.iloc[:, 0].values
                y = data.iloc[:, 1].values
                
                # 如果有第三列，可以用作点的大小
                if len(data.columns) > 2:
                    sizes = data.iloc[:, 2].values
                    sizes = np.array(sizes) * 10  # 缩放大小
                    self.canvas.axes.scatter(x, y, s=sizes, alpha=0.5)
                else:
                    self.canvas.axes.scatter(x, y, alpha=0.5)
                
                self.canvas.axes.set_title("散点图")
                self.canvas.axes.set_xlabel(data.columns[0])
                self.canvas.axes.set_ylabel(data.columns[1])
                
            elif isinstance(data, dict):
                # 对于字典，我们需要键和值都是数字类型
                try:
                    x = [float(k) for k in data.keys()]
                    y = list(data.values())
                    self.canvas.axes.scatter(x, y)
                    self.canvas.axes.set_title("散点图")
                    self.canvas.axes.set_xlabel("X")
                    self.canvas.axes.set_ylabel("Y")
                except:
                    print("无法将字典键转换为数字类型，散点图需要数值型坐标")
        except Exception as e:
            print(f"绘制散点图时出错: {str(e)}")
            traceback.print_exc()
    
    def _plot_heatmap(self, data):
        """绘制热力图
        
        Args:
            data: 数据DataFrame，需要是二维数值型数据
        """
        try:
            if isinstance(data, pd.DataFrame):
                # 转换为数值型
                numeric_data = data.select_dtypes(include=[np.number])
                if not numeric_data.empty:
                    im = self.canvas.axes.imshow(numeric_data, cmap='viridis')
                    self.canvas.fig.colorbar(im, ax=self.canvas.axes)
                    
                    # 设置坐标轴标签
                    self.canvas.axes.set_xticks(np.arange(len(numeric_data.columns)))
                    self.canvas.axes.set_yticks(np.arange(len(numeric_data.index)))
                    self.canvas.axes.set_xticklabels(numeric_data.columns)
                    self.canvas.axes.set_yticklabels(numeric_data.index)
                    
                    # 旋转x轴标签
                    plt.setp(self.canvas.axes.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
                    
                    # 设置标题
                    self.canvas.axes.set_title("热力图")
                else:
                    print("没有数值型数据可用于热力图")
            elif isinstance(data, dict):
                print("热力图需要二维数值型数据，字典不适用")
        except Exception as e:
            print(f"绘制热力图时出错: {str(e)}")
            traceback.print_exc()

class ChartManager:
    """图表管理类，用于创建和管理各种数据可视化图表"""
    
    def __init__(self, parent=None, log_callback=None):
        """初始化图表管理器
        
        Args:
            parent: 父窗口对象
            log_callback: 日志记录回调函数
        """
        self.parent = parent
        self.log = log_callback if log_callback else print
    
    def show_play_count_chart(self, videos):
        """显示播放量统计图表
        
        Args:
            videos: 视频数据列表
        """
        try:
            if not videos:
                return
                
            # 创建DataFrame
            df = pd.DataFrame(videos)
            
            # 按发布时间排序
            if "publish_time" in df.columns:
                df["publish_time"] = pd.to_datetime(df["publish_time"])
                df = df.sort_values("publish_time")
            
            # 提取播放量数据
            chart_data = {}
            for i, row in df.iterrows():
                title = row.get("title", f"视频{i}")
                # 限制标题长度
                title = title[:10] + "..." if len(title) > 10 else title
                chart_data[title] = row.get("play_count", 0)
            
            # 创建并显示图表对话框
            dialog = ChartDialog(self.parent, title="视频播放量统计")
            dialog.plot_data(chart_data)
            dialog.exec_()
            
        except Exception as e:
            self.log(f"显示播放量图表时出错: {str(e)}")
            traceback.print_exc()
    
    def show_interaction_chart(self, videos):
        """显示互动指标统计图表
        
        Args:
            videos: 视频数据列表
        """
        try:
            if not videos:
                return
                
            # 创建DataFrame
            df = pd.DataFrame(videos)
            
            # 计算互动指标
            interaction_data = {}
            for i, row in df.iterrows():
                title = row.get("title", f"视频{i}")
                # 限制标题长度
                title = title[:10] + "..." if len(title) > 10 else title
                
                # 计算互动率
                play_count = row.get("play_count", 0)
                like_count = row.get("like_count", 0)
                comment_count = row.get("comment_count", 0)
                share_count = row.get("share_count", 0)
                collect_count = row.get("collect_count", 0)
                
                if play_count > 0:
                    interaction_rate = ((like_count + comment_count + share_count + collect_count) / play_count) * 100
                else:
                    interaction_rate = 0
                
                interaction_data[title] = round(interaction_rate, 2)
            
            # 创建并显示图表对话框
            dialog = ChartDialog(self.parent, title="视频互动率统计")
            dialog.plot_data(interaction_data)
            dialog.exec_()
            
        except Exception as e:
            self.log(f"显示互动率图表时出错: {str(e)}")
            traceback.print_exc()
    
    def show_recommendation_chart(self, videos):
        """显示推荐情况统计图表
        
        Args:
            videos: 视频数据列表
        """
        try:
            if not videos:
                return
                
            # 统计推荐和非推荐的视频数量
            recommended_count = 0
            not_recommended_count = 0
            
            for video in videos:
                if video.get("recommended", 0):
                    recommended_count += 1
                else:
                    not_recommended_count += 1
            
            # 创建数据
            chart_data = {
                "已推荐": recommended_count,
                "未推荐": not_recommended_count
            }
            
            # 创建并显示图表对话框
            dialog = ChartDialog(self.parent, title="视频推荐情况统计")
            dialog.chart_type_combo.setCurrentText("饼图")  # 默认使用饼图
            dialog.plot_data(chart_data)
            dialog.exec_()
            
        except Exception as e:
            self.log(f"显示推荐情况图表时出错: {str(e)}")
            traceback.print_exc()
    
    def show_trend_chart(self, videos):
        """显示数据趋势图表
        
        Args:
            videos: 视频数据列表
        """
        try:
            if not videos:
                return
                
            # 创建DataFrame
            df = pd.DataFrame(videos)
            
            # 确保有发布时间
            if "publish_time" not in df.columns:
                self.log("数据缺少发布时间字段，无法生成趋势图")
                return
                
            # 转换发布时间为日期类型
            df["publish_time"] = pd.to_datetime(df["publish_time"])
            
            # 按日期分组，计算每日平均播放量
            df["date"] = df["publish_time"].dt.date
            daily_stats = df.groupby("date").agg({
                "play_count": "mean",
                "like_count": "mean",
                "comment_count": "mean"
            }).reset_index()
            
            # 创建趋势数据
            trend_data = pd.DataFrame()
            trend_data["日期"] = daily_stats["date"]
            trend_data["平均播放量"] = daily_stats["play_count"].round(0)
            trend_data["平均点赞数"] = daily_stats["like_count"].round(0)
            trend_data["平均评论数"] = daily_stats["comment_count"].round(0)
            
            # 设置日期为索引
            trend_data = trend_data.set_index("日期")
            
            # 创建并显示图表对话框
            dialog = ChartDialog(self.parent, title="视频数据趋势分析")
            dialog.chart_type_combo.setCurrentText("折线图")  # 默认使用折线图
            dialog.plot_data(trend_data)
            dialog.exec_()
            
        except Exception as e:
            self.log(f"显示趋势图表时出错: {str(e)}")
            traceback.print_exc()
    
    def show_correlation_chart(self, videos):
        """显示相关性分析图表
        
        Args:
            videos: 视频数据列表
        """
        try:
            if not videos:
                return
                
            # 创建DataFrame
            df = pd.DataFrame(videos)
            
            # 提取数值型字段
            numeric_columns = ["play_count", "like_count", "comment_count", 
                              "share_count", "collect_count", "interaction_rate"]
            
            numeric_df = pd.DataFrame()
            for col in numeric_columns:
                if col in df.columns:
                    numeric_df[col] = df[col]
            
            if numeric_df.empty:
                self.log("数据缺少数值型字段，无法生成相关性图表")
                return
                
            # 计算相关系数
            corr_df = numeric_df.corr()
            
            # 创建并显示图表对话框
            dialog = ChartDialog(self.parent, title="视频数据相关性分析")
            dialog.chart_type_combo.setCurrentText("热力图")  # 默认使用热力图
            dialog.plot_data(corr_df)
            dialog.exec_()
            
        except Exception as e:
            self.log(f"显示相关性图表时出错: {str(e)}")
            traceback.print_exc() 