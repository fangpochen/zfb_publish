#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
import time
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (QMessageBox, QInputDialog, QFileDialog, 
                            QTableWidgetItem, QHeaderView, QProgressDialog,
                            QDateEdit, QCheckBox)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QBrush
import threading
import glob
import sqlite3

from database import db_manager
from api_client import ApiClient

class VideoQueryThread(QThread):
    """视频查询线程，负责异步获取视频数据"""
    
    # 定义信号
    progress_updated = pyqtSignal(int, int)  # 进度更新信号
    query_finished = pyqtSignal(list)  # 查询完成信号
    error_occurred = pyqtSignal(str)  # 错误信号
    
    def __init__(self, api_client, appid, date_range=None):
        """初始化查询线程
        
        Args:
            api_client: API客户端
            appid: 账号ID
            date_range: 日期范围(start_date, end_date)
        """
        super().__init__()
        self.api_client = api_client
        self.appid = appid
        self.date_range = date_range
        self.videos = []
    
    def run(self):
        """线程执行函数"""
        try:
            # 调用API获取视频数据
            params = {"appid": self.appid}
            
            # 添加日期过滤参数
            if self.date_range:
                start_date, end_date = self.date_range
                if start_date:
                    params["start_date"] = start_date.strftime("%Y-%m-%d")
                if end_date:
                    params["end_date"] = end_date.strftime("%Y-%m-%d")
            
            # 查询视频数据
            response = self.api_client.query_videos(params)
            
            if response and "videos" in response:
                self.videos = response["videos"]
                self.query_finished.emit(self.videos)
            else:
                self.error_occurred.emit("API返回数据格式不正确")
                
        except Exception as e:
            self.error_occurred.emit(str(e))
            traceback.print_exc()

class VideoAnalyzer:
    """视频分析模块，处理视频数据分析相关功能"""
    
    def __init__(self, ui, parent=None, log_callback=None):
        """初始化视频分析模块
        
        Args:
            ui: UI对象，包含界面组件
            parent: 父窗口对象，用于显示对话框
            log_callback: 日志记录回调函数
        """
        self.ui = ui
        self.parent = parent
        self.log = log_callback if log_callback else print
        self.db = db_manager
        self.api_client = ApiClient(log_callback=self.log)
        self.query_threads = []  # 保存查询线程
        self.current_videos = []  # 当前显示的视频列表
        
    def query_selected_accounts(self):
        """查询选中账号的视频数据"""
        try:
            # 检查是否有选中的账号
            selected_accounts = []
            
            # 使用账号管理器获取选中的账号
            if hasattr(self.parent, 'account_manager') and hasattr(self.parent.account_manager, 'get_selected_accounts'):
                selected_accounts = self.parent.account_manager.get_selected_accounts()
            else:
                # 确保UI中有accountTable组件
                if not hasattr(self.ui, 'accountTable'):
                    self.log("UI中缺少accountTable组件")
                    return
                    
                # 获取选中的账号
                for row in range(self.ui.accountTable.rowCount()):
                    # 获取单元格小部件（一个容器，其中包含QCheckBox）
                    checkbox_container = self.ui.accountTable.cellWidget(row, 0)
                    is_checked = False
                    
                    if checkbox_container:
                        # 在容器中查找QCheckBox
                        for child in checkbox_container.findChildren(QCheckBox):
                            if child.isChecked():
                                is_checked = True
                                break
                    
                    if is_checked:
                        appid = self.ui.accountTable.item(row, 2).text()
                        name = self.ui.accountTable.item(row, 3).text()
                        selected_accounts.append({
                            'appid': appid,
                            'name': name
                        })
            
            if not selected_accounts:
                QMessageBox.warning(self.parent, "提示", "请先选择至少一个账号")
                return
                
            # 获取查询日期
            query_date = datetime.now().strftime('%Y-%m-%d')
            if hasattr(self.ui, 'dateEdit') and self.ui.dateEdit:
                qdate = self.ui.dateEdit.date()
                query_date = qdate.toString('yyyy-MM-dd')
                
            # 确认查询
            reply = QMessageBox.question(
                self.parent, "确认查询", 
                f"确定要分析选中的 {len(selected_accounts)} 个账号的视频数据吗？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes
            )
            
            if reply != QMessageBox.Yes:
                return
                
            # 清空数据表格
            if hasattr(self.ui, 'dataTableWidget'):
                self.ui.dataTableWidget.setRowCount(0)
                
            # 开始查询
            self.log(f"开始分析 {len(selected_accounts)} 个账号的视频数据，日期: {query_date}")
            
            # 展示进度对话框
            progress = QProgressDialog("正在分析视频数据...", "取消", 0, len(selected_accounts), self.parent)
            progress.setWindowTitle("分析进度")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            
            # 遍历查询每个账号
            all_videos = []
            for i, account in enumerate(selected_accounts):
                if progress.wasCanceled():
                    break
                    
                appid = account['appid']
                name = account['name']
                
                progress.setLabelText(f"正在分析账号: {name}")
                progress.setValue(i)
                
                # 处理特定账号的视频查询
                videos = self._query_account_videos(appid, name, query_date)
                if videos:
                    all_videos.extend(videos)
                    
                # 更新数据表格
                self.update_data_table(all_videos)
                
            # 完成查询
            progress.setValue(len(selected_accounts))
            
            # 如果有视频数据，则更新数据表格
            if all_videos:
                self.log(f"成功分析 {len(all_videos)} 个视频")
                
                # 自动调整列宽
                if hasattr(self.ui, 'dataTableWidget'):
                    for i in range(self.ui.dataTableWidget.columnCount()):
                        self.ui.dataTableWidget.resizeColumnToContents(i)
            else:
                self.log("没有找到符合条件的视频数据")
                
        except Exception as e:
            self.log(f"查询视频时出错: {str(e)}")
            traceback.print_exc()
    
    def process_videos(self, videos):
        """处理API返回的视频数据
        
        Args:
            videos: API返回的视频列表
        """
        try:
            processed_videos = []
            
            for video in videos:
                # 标准化字段名
                processed_video = {
                    "video_id": video.get("video_id", ""),
                    "title": video.get("title", ""),
                    "publish_time": video.get("publish_time", ""),
                    "play_count": video.get("play_count", 0),
                    "like_count": video.get("like_count", 0),
                    "comment_count": video.get("comment_count", 0),
                    "share_count": video.get("share_count", 0),
                    "collect_count": video.get("favorite_count", 0),
                    "appid": video.get("appid", ""),
                    "recommended": video.get("is_recommended", 0),
                    "recommend_time": video.get("recommend_time", ""),
                    "recommend_type": video.get("recommend_type", ""),
                    "duration": video.get("duration", 0)
                }
                
                # 数据类型转换
                for key in ["play_count", "like_count", "comment_count", "share_count", "collect_count"]:
                    try:
                        processed_video[key] = int(processed_video[key])
                    except (ValueError, TypeError):
                        processed_video[key] = 0
                
                # 计算互动率
                try:
                    play_count = processed_video["play_count"]
                    if play_count > 0:
                        interaction_rate = (
                            (processed_video["like_count"] + 
                            processed_video["comment_count"] + 
                            processed_video["share_count"] + 
                            processed_video["collect_count"]) / play_count
                        ) * 100
                    else:
                        interaction_rate = 0
                    processed_video["interaction_rate"] = round(interaction_rate, 2)
                except:
                    processed_video["interaction_rate"] = 0
                
                processed_videos.append(processed_video)
            
            # 添加到当前视频列表
            self.current_videos.extend(processed_videos)
            
            # 保存到数据库
            self.save_videos_to_db(processed_videos)
            
        except Exception as e:
            self.log(f"处理视频数据时出错: {str(e)}")
            traceback.print_exc()
    
    def save_videos_to_db(self, videos):
        """保存视频数据到数据库
        
        Args:
            videos: 处理后的视频列表
        """
        try:
            if not videos:
                self.log("没有视频数据需要保存")
                return
                
            # 按账号和日期分组视频
            videos_by_account = {}
            for video in videos:
                appid = video.get("appid")
                query_date = video.get("analyze_date")
                
                if not appid or not query_date:
                    self.log(f"视频缺少必要信息 appid: {appid}, query_date: {query_date}")
                    continue
                    
                key = (appid, query_date)
                if key not in videos_by_account:
                    videos_by_account[key] = []
                    
                videos_by_account[key].append(video)
            
            # 按账号和日期批量保存视频
            total_success = 0
            for (appid, query_date), account_videos in videos_by_account.items():
                # 转换为API格式
                api_format_videos = []
                for video in account_videos:
                    api_video = {
                        'contentId': video.get('video_id', ''),
                        'title': video.get('title', ''),
                        'publishTime': video.get('publish_time', ''),
                        'playCount': video.get('play_count', 0),
                        'praiseCount': video.get('like_count', 0),
                        'commentCount': video.get('comment_count', 0),
                        'isRecommend': True if video.get('recommended', 0) == 1 else False,
                        'account_name': video.get('account_name', '')
                    }
                    api_format_videos.append(api_video)
                
                if self.db.save_videos_to_db(appid, query_date, api_format_videos):
                    total_success += len(api_format_videos)
                    self.log(f"成功保存 {len(api_format_videos)} 个视频到数据库，账号: {appid}, 日期: {query_date}")
            
            self.log(f"总共成功保存 {total_success}/{len(videos)} 个视频到数据库")
            
        except Exception as e:
            self.log(f"保存视频到数据库时出错: {str(e)}")
            traceback.print_exc()
    
    def update_data_table(self, videos):
        """更新数据表格
        
        Args:
            videos: 要显示的视频列表
        """
        try:
            if not hasattr(self.ui, 'dataTableWidget'):
                self.log("UI中缺少dataTableWidget组件")
                return
                
            # 清空表格
            self.ui.dataTableWidget.setRowCount(0)
            
            # 设置表格列头
            if self.ui.dataTableWidget.columnCount() < 9:
                self.ui.dataTableWidget.setColumnCount(9)
                self.ui.dataTableWidget.setHorizontalHeaderLabels([
                    "作品ID", "标题", "账号昵称", "发布时间", "播放量", 
                    "点赞数", "评论数", "推荐状态", "异常状态"
                ])
            
            # 添加视频数据到表格
            for i, video in enumerate(videos):
                self.ui.dataTableWidget.insertRow(i)
                
                # 作品ID
                item_id = QTableWidgetItem(video.get("content_id", ""))
                self.ui.dataTableWidget.setItem(i, 0, item_id)
                
                # 标题
                item_title = QTableWidgetItem(video.get("title", ""))
                self.ui.dataTableWidget.setItem(i, 1, item_title)
                
                # 账号昵称
                item_account = QTableWidgetItem(video.get("account_name", ""))
                self.ui.dataTableWidget.setItem(i, 2, item_account)
                
                # 发布时间
                send_time = video.get("send_time", "")
                if send_time:
                    try:
                        # 尝试解析时间戳
                        if isinstance(send_time, (int, float)):
                            send_time = datetime.fromtimestamp(send_time/1000).strftime("%Y-%m-%d %H:%M:%S")
                        elif isinstance(send_time, str) and send_time.isdigit():
                            send_time = datetime.fromtimestamp(int(send_time)/1000).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                item_time = QTableWidgetItem(str(send_time))
                self.ui.dataTableWidget.setItem(i, 3, item_time)
                
                # 播放量
                item_play = QTableWidgetItem(str(video.get("pv", 0)))
                self.ui.dataTableWidget.setItem(i, 4, item_play)
                
                # 点赞数
                item_like = QTableWidgetItem(str(video.get("praise_count", 0)))
                self.ui.dataTableWidget.setItem(i, 5, item_like)
                
                # 评论数
                item_comment = QTableWidgetItem(str(video.get("reply_count", 0)))
                self.ui.dataTableWidget.setItem(i, 6, item_comment)
                
                # 推荐状态
                recommend = video.get("recommend", False)
                recommend_text = "已推荐" if recommend else "未推荐"
                item_recommend = QTableWidgetItem(recommend_text)
                if recommend:
                    item_recommend.setBackground(QBrush(QColor(144, 238, 144)))  # 浅绿色
                else:
                    item_recommend.setBackground(QBrush(QColor(255, 200, 200)))  # 浅红色
                self.ui.dataTableWidget.setItem(i, 7, item_recommend)
                
                # 异常状态
                is_abnormal = video.get("is_abnormal", False)
                item_abnormal = QTableWidgetItem("是" if is_abnormal else "否")
                if is_abnormal:
                    item_abnormal.setBackground(QBrush(QColor(255, 200, 200)))  # 浅红色
                self.ui.dataTableWidget.setItem(i, 8, item_abnormal)
                
                # 设置每一行的高度
                self.ui.dataTableWidget.setRowHeight(i, 30)
            
            # 调整列宽
            self.ui.dataTableWidget.setColumnWidth(0, 100)  # 作品ID
            self.ui.dataTableWidget.setColumnWidth(1, 200)  # 标题
            self.ui.dataTableWidget.setColumnWidth(2, 100)  # 账号昵称
            self.ui.dataTableWidget.setColumnWidth(3, 150)  # 发布时间
            self.ui.dataTableWidget.setColumnWidth(4, 80)   # 播放量
            self.ui.dataTableWidget.setColumnWidth(5, 80)   # 点赞数
            self.ui.dataTableWidget.setColumnWidth(6, 80)   # 评论数
            self.ui.dataTableWidget.setColumnWidth(7, 80)   # 推荐状态
            self.ui.dataTableWidget.setColumnWidth(8, 80)   # 异常状态
            
            # 更新视频数量标签
            if hasattr(self.ui, 'videoCountLabel'):
                self.ui.videoCountLabel.setText(f"共 {len(videos)} 个视频")
                
        except Exception as e:
            self.log(f"更新数据表格时出错: {str(e)}")
            traceback.print_exc()
    
    def check_duplicate_video(self, video_id):
        """检查视频是否重复
        
        Args:
            video_id: 视频ID
            
        Returns:
            bool: 是否重复
        """
        try:
            # 检查数据库中是否有相同ID的视频
            video_count = self.db.get_video_count_by_id(video_id)
            return video_count > 1
        except Exception as e:
            self.log(f"检查视频重复性时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def export_data_to_excel(self):
        """导出数据到Excel文件"""
        try:
            if not self.current_videos:
                QMessageBox.warning(self.parent, "提示", "没有可导出的数据")
                return
                
            # 打开文件保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self.parent, "保存Excel文件", 
                f"视频数据_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx", 
                "Excel文件 (*.xlsx);;所有文件 (*.*)"
            )
            
            if not file_path:
                return  # 用户取消保存
                
            # 创建DataFrame
            df = pd.DataFrame(self.current_videos)
            
            # 重命名列
            columns_map = {
                "video_id": "视频ID",
                "title": "标题",
                "publish_time": "发布时间",
                "play_count": "播放量",
                "like_count": "点赞数",
                "comment_count": "评论数",
                "share_count": "分享数",
                "collect_count": "收藏数",
                "interaction_rate": "互动率(%)",
                "appid": "账号ID",
                "recommended": "是否推荐",
                "recommend_time": "推荐时间",
                "recommend_type": "推荐类型",
                "duration": "视频时长(秒)"
            }
            
            df = df.rename(columns=columns_map)
            
            # 保存到Excel
            df.to_excel(file_path, index=False)
            
            self.log(f"成功导出 {len(self.current_videos)} 条数据到文件: {file_path}")
            QMessageBox.information(self.parent, "导出成功", f"成功导出 {len(self.current_videos)} 条数据")
            
        except Exception as e:
            self.log(f"导出数据到Excel时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self.parent, "导出失败", f"导出数据失败: {str(e)}")
    
    def analyze_data(self):
        """分析数据，生成统计图表"""
        try:
            if not self.current_videos:
                QMessageBox.warning(self.parent, "提示", "没有可分析的数据")
                return
                
            # TODO: 实现数据分析功能
            # 可以调用图表模块生成各种统计图表
            
            self.log("开始分析数据...")
            
        except Exception as e:
            self.log(f"分析数据时出错: {str(e)}")
            traceback.print_exc()
    
    def _query_account_videos(self, appid, name, query_date):
        """
        查询账号的视频数据
        
        Args:
            appid: 账号ID
            name: 账号名称
            query_date: 查询日期
            
        Returns:
            list: 处理后的视频列表
        """
        try:
            # 1. 获取账号的cookies
            cookies = self.db.get_account_cookies(appid)
            if not cookies:
                self.log(f"账号 {name} 的cookies无效")
                return []
            
            # 2. 切换到目标账号
            if not self.api_client.get_sub_cookies(cookies, appid):
                self.log(f"切换到账号 {appid} 失败")
                return None
            
            # 3. 检查账号画风
            style_result = self.api_client.check_account_style(cookies, appid)
            pass_style = style_result.get('is_matching', False) if style_result else False
            
            # 4. 分页获取所有视频数据
            page = 1
            page_size = 20
            all_videos = []
            total_videos = 0
            total_recommend = 0
            
            while True:
                # 查询一页视频数据
                result = self.api_client.query_videos(cookies, appid, query_date, page, page_size)
                if not result:
                    break
                
                videos, total = result
                if not videos:
                    break
                
                # 处理视频数据
                processed_videos = self._process_account_videos(videos, appid, name, query_date)
                all_videos.extend(processed_videos)
                
                # 统计推荐和异常视频
                for video in processed_videos:
                    if not video.get('is_abnormal', True):
                        total_recommend += 1
                total_videos = len(all_videos)
                
                # 检查是否还有更多页
                if len(all_videos) >= total:
                    break
                
                page += 1
            
            # 5. 更新数据库中的账号状态
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            
            # 更新accounts表
            cursor.execute('''
                UPDATE accounts 
                SET today_videos = ?,
                    today_recommended = ?,
                    pass_style = ?,
                    last_updated = datetime('now')
                WHERE appid = ?
            ''', (
                total_videos,
                total_recommend,
                1 if pass_style else 0,
                appid
            ))
            
            conn.commit()
            conn.close()
            
            # 6. 更新UI显示
            self._update_account_ui(appid, {
                'today_videos': total_videos,
                'today_recommend': total_recommend,
                'pass_style': pass_style,
                'is_analyzed': True
            })
            
            # 更新下方视频列表
            if hasattr(self.ui, 'dataTableWidget'):
                self.update_data_table(all_videos)
            
            return all_videos
            
        except Exception as e:
            self.log(f"查询账号 {name} 的视频数据时出错: {str(e)}")
            traceback.print_exc()
            return []
    
    def _check_account_style(self, appid, cookies):
        """
        检查账号是否通过画风
        
        参数:
            appid: 账号ID
            cookies: 账号的cookies
            
        返回:
            bool: 是否通过画风
        """
        try:
            # 调用API检查画风
            style_result = self.api_client.check_account_style(cookies, appid)
            
            if not style_result:
                self.log(f"账号 {appid} 画风检查API请求失败")
                return False
            
            # 解析API响应，判断是否通过画风
            pass_style = style_result.get('is_matching', False)
            
            style_title = style_result.get('title', '未知')
            self.log(f"账号 {appid} 画风评估：{style_title}，{'通过' if pass_style else '未通过'}")
            
            return pass_style
            
        except Exception as e:
            self.log(f"检查账号画风时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def _update_account_style_status(self, appid, pass_style):
        """
        更新账号画风状态到数据库
        
        参数:
            appid: 账号ID
            pass_style: 是否通过画风
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE accounts SET pass_style = ? WHERE appid = ?", 
                (1 if pass_style else 0, appid)
            )
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.log(f"更新账号 {appid} 画风状态到数据库时出错: {str(e)}")
            traceback.print_exc()
    
    def _update_account_ui(self, appid, data):
        """
        更新UI中账号表格的状态
        
        参数:
            appid: 账号ID
            data: 需要更新的数据，字典格式
        """
        try:
            # 查找账号在表格中的行
            for row in range(self.ui.accountTable.rowCount()):
                appid_item = self.ui.accountTable.item(row, 2)
                if appid_item and appid_item.text() == appid:
                    # 更新画风状态
                    if "pass_style" in data:
                        pass_style = data["pass_style"]
                        style_item = QTableWidgetItem("通过" if pass_style else "未通过")
                        style_item.setForeground(QBrush(QColor("#67C23A" if pass_style else "#F56C6C")))
                        self.ui.accountTable.setItem(row, 7, style_item)
                    
                    # 更新当日视频数量
                    if "today_videos" in data:
                        self.ui.accountTable.setItem(row, 4, QTableWidgetItem(str(data["today_videos"])))
                    
                    # 更新当日推荐数量
                    if "today_recommend" in data:
                        self.ui.accountTable.setItem(row, 5, QTableWidgetItem(str(data["today_recommend"])))
                    
                    # 更新当日播放量
                    if "today_plays" in data:
                        self.ui.accountTable.setItem(row, 6, QTableWidgetItem(str(data["today_plays"])))
                    
                    break
                    
        except Exception as e:
            self.log(f"更新账号 {appid} UI状态时出错: {str(e)}")
            traceback.print_exc()
    
    def _process_account_videos(self, videos, appid, name, query_date):
        """
        处理视频数据
        
        Args:
            videos: 原始视频数据列表
            appid: 账号ID
            name: 账号名称
            query_date: 查询日期
            
        Returns:
            list: 处理后的视频列表
        """
        try:
            processed_videos = []
            for video in videos:
                # 只处理必要的字段
                content_id = video.get('contentId', '') or video.get('id', '')
                if not content_id:
                    continue
                    
                processed_video = {
                    'content_id': content_id,
                    'title': video.get('title', '无标题'),
                    'send_time': video.get('sendTime', '') or video.get('publishTime', ''),
                    'pv': int(video.get('pv', '0') or video.get('playCount', '0')),
                    'praise_count': int(video.get('praiseCount', 0)),
                    'reply_count': int(video.get('replyCount', 0) or video.get('commentCount', 0)),
                    'account_name': name,
                    'appid': appid,
                    'analyze_date': query_date
                }
                
                # 判断是否可以推荐
                can_recommend = video.get('canContentRecommended', False)
                audit_reasons = video.get('auditReasonDTOList', [])
                
                # 如果有审核原因或不可推荐,标记为异常视频
                processed_video['is_abnormal'] = not can_recommend or len(audit_reasons) > 0
                processed_video['recommend'] = can_recommend and len(audit_reasons) == 0
                
                # 如果有审核原因,记录第一个原因
                if audit_reasons:
                    processed_video['audit_reason'] = audit_reasons[0].get('reason', '')
                
                processed_videos.append(processed_video)
            
            # 保存到数据库
            if processed_videos:
                self.db.save_videos(processed_videos)  # 使用content_id作为唯一标识更新
            
            return processed_videos
            
        except Exception as e:
            self.log(f"处理视频数据时出错: {str(e)}")
            traceback.print_exc()
            return []
    
    def _save_account_analysis(self, appid, account_name, stats, query_date):
        """保存账号分析结果到数据库"""
        try:
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO account_analysis 
                (appid, date, total_videos, recommend_videos, total_views, 
                total_likes, total_comments, total_shares, avg_views, 
                avg_likes, avg_comments, recommend_rate, engagement_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                appid,
                query_date,  # 使用date而不是analyze_date
                stats.get('total_count', 0),
                stats.get('recommend_count', 0),
                stats.get('total_views', 0),
                stats.get('total_likes', 0),
                stats.get('total_comments', 0),
                stats.get('total_shares', 0),
                stats.get('avg_views', 0),
                stats.get('avg_likes', 0),
                stats.get('avg_comments', 0),
                stats.get('recommend_rate', 0),
                stats.get('engagement_rate', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存账号 {account_name} 分析结果时出错: {str(e)}")
            if 'conn' in locals():
                conn.close()
            return False

class VideoUploader:
    """视频上传管理器，处理账号视频上传相关功能"""
    
    def __init__(self, ui, parent=None, log_callback=None):
        """初始化视频上传管理器
        
        Args:
            ui: UI对象，包含界面组件
            parent: 父窗口对象，用于显示对话框
            log_callback: 日志记录回调函数
        """
        self.ui = ui
        self.parent = parent
        self.log = log_callback if log_callback else print
        self.db = db_manager
        self.upload_thread = None
        self.upload_running = False
        
    def start_upload(self):
        """开始上传视频任务"""
        try:
            # 检查是否有选中的账号
            selected_rows = []
            
            # 确保UI中有accountTable组件
            if not hasattr(self.ui, 'accountTable'):
                self.log("UI中缺少accountTable组件")
                return
                
            for row in range(self.ui.accountTable.rowCount()):
                checkbox = self.ui.accountTable.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    selected_rows.append(row)
            
            if not selected_rows:
                QMessageBox.warning(self.parent, "提示", "请先选择至少一个账号")
                return
                
            # 获取上传间隔
            upload_interval = 10  # 默认10秒
            if hasattr(self.ui, 'uploadIntervalSpinBox'):
                upload_interval = self.ui.uploadIntervalSpinBox.value()
                
            # 检查是否已经在上传
            if self.upload_running:
                reply = QMessageBox.question(
                    self.parent, "上传中", 
                    "上传任务正在进行中，是否要停止？",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.stop_upload()
                    self.log("已停止上传任务")
                
                return
                
            # 确认开始上传
            reply = QMessageBox.question(
                self.parent, "确认上传", 
                f"确定要开始上传吗？将按照每个账号文件夹的设置进行上传，\n上传间隔设置为 {upload_interval} 秒。",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
                
            # 准备上传参数
            self.selected_accounts = []
            for row in selected_rows:
                appid = self.ui.accountTable.item(row, 2).text()
                self.selected_accounts.append(appid)
                
            # 开始上传线程
            self.upload_running = True
            
            # 更新按钮状态
            if hasattr(self.ui, 'startButton'):
                self.ui.startButton.setText("停止上传")
                
            # 创建并启动上传线程
            self.upload_thread = threading.Thread(
                target=self._upload_videos,
                args=(self.selected_accounts, upload_interval)
            )
            self.upload_thread.daemon = True
            self.upload_thread.start()
            
            self.log(f"开始视频上传任务，共选择 {len(self.selected_accounts)} 个账号")
            
        except Exception as e:
            self.log(f"开始上传时出错: {str(e)}")
            traceback.print_exc()
            
    def stop_upload(self):
        """停止视频上传任务"""
        try:
            self.upload_running = False
            
            # 更新按钮状态
            if hasattr(self.ui, 'startButton'):
                self.ui.startButton.setText("开始上传")
                
            self.log("上传任务已停止")
            
        except Exception as e:
            self.log(f"停止上传时出错: {str(e)}")
            traceback.print_exc()
            
    def _upload_videos(self, account_ids, interval):
        """后台上传视频的线程函数
        
        Args:
            account_ids (list): 要上传的账号ID列表
            interval (int): 上传间隔秒数
        """
        try:
            self.log(f"上传线程已启动，上传间隔: {interval}秒")
            
            while self.upload_running and account_ids:
                for appid in account_ids:
                    if not self.upload_running:
                        break
                        
                    # 获取该账号的所有文件夹
                    folders = self.db.get_folder_settings(appid)
                    
                    # 检查每个文件夹是否需要上传
                    for folder in folders:
                        if not self.upload_running:
                            break
                            
                        folder_id = folder[0]
                        folder_path = folder[1]
                        total_files = folder[2]
                        max_uploads = folder[3]
                        uploaded_count = folder[4]
                        status = folder[5]
                        
                        # 检查是否已经达到上传上限
                        if uploaded_count >= max_uploads:
                            self.log(f"账号 {appid} 文件夹 {folder_path} 已达到上传上限 ({uploaded_count}/{max_uploads})")
                            continue
                            
                        # 获取待上传的视频文件
                        videos = self._get_pending_videos(folder_path, uploaded_count)
                        if not videos:
                            self.log(f"账号 {appid} 文件夹 {folder_path} 没有待上传的视频")
                            continue
                            
                        # 获取上传进度并上传一个视频
                        video_path = videos[0]
                        success = self._upload_single_video(appid, folder_id, video_path)
                        
                        if success:
                            # 更新上传计数
                            self.db.update_upload_count(folder_id, uploaded_count + 1)
                            self.log(f"账号 {appid} 成功上传视频: {os.path.basename(video_path)}")
                        else:
                            self.log(f"账号 {appid} 上传视频失败: {os.path.basename(video_path)}")
                            
                        # 更新文件夹状态
                        self._update_folder_status(folder_id)
                        
                        # 等待指定的时间间隔
                        for i in range(interval):
                            if not self.upload_running:
                                break
                            time.sleep(1)
                        
                # 一轮上传完成后等待更长时间
                if self.upload_running:
                    self.log("所有账号完成一轮上传，等待下一轮...")
                    time.sleep(interval * 2)
                    
            self.log("上传线程已结束")
            
        except Exception as e:
            self.log(f"上传视频时出错: {str(e)}")
            traceback.print_exc()
        finally:
            # 确保任务结束时重置UI状态
            self.upload_running = False
            # 在主线程中更新UI
            if QApplication.instance():
                QApplication.instance().processEvents()
                if hasattr(self.ui, 'startButton'):
                    self.ui.startButton.setText("开始上传")
                    
    def _get_pending_videos(self, folder_path, uploaded_count):
        """获取待上传的视频文件列表
        
        Args:
            folder_path (str): 文件夹路径
            uploaded_count (int): 已上传的视频数量
            
        Returns:
            list: 待上传的视频文件路径列表
        """
        try:
            if not os.path.exists(folder_path):
                self.log(f"文件夹不存在: {folder_path}")
                return []
                
            # 获取文件夹中的所有视频文件
            video_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
            video_files = []
            
            for ext in video_extensions:
                for file_path in glob.glob(os.path.join(folder_path, f'*{ext}')):
                    video_files.append(file_path)
                    
            # 排序，确保每次上传顺序一致
            video_files.sort()
            
            # 获取未上传的视频
            pending_videos = video_files[uploaded_count:] if uploaded_count < len(video_files) else []
            
            return pending_videos
            
        except Exception as e:
            self.log(f"获取待上传视频失败: {str(e)}")
            traceback.print_exc()
            return []
            
    def _upload_single_video(self, appid, folder_id, video_path):
        """上传单个视频
        
        Args:
            appid (str): 账号ID
            folder_id (int): 文件夹ID
            video_path (str): 视频文件路径
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 这里实现实际的上传逻辑
            # 由于实际上传需要调用支付宝相关API，这里仅做模拟
            self.log(f"正在上传视频: {os.path.basename(video_path)}")
            
            # 模拟上传过程
            time.sleep(2)
            
            # 记录上传记录
            video_name = os.path.basename(video_path)
            video_size = os.path.getsize(video_path)
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 确保数据库有add_upload_record方法
            if hasattr(self.db, 'add_upload_record'):
                self.db.add_upload_record(
                    appid, folder_id, video_path, video_name, 
                    video_size, current_time, "成功"
                )
            
            return True
            
        except Exception as e:
            self.log(f"上传视频 {video_path} 失败: {str(e)}")
            traceback.print_exc()
            
            # 记录失败记录
            try:
                video_name = os.path.basename(video_path)
                video_size = os.path.getsize(video_path)
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if hasattr(self.db, 'add_upload_record'):
                    self.db.add_upload_record(
                        appid, folder_id, video_path, video_name, 
                        video_size, current_time, f"失败: {str(e)}"
                    )
            except:
                pass
                
            return False
            
    def _update_folder_status(self, folder_id):
        """更新文件夹状态
        
        Args:
            folder_id (int): 文件夹ID
        """
        try:
            # 获取文件夹信息
            if hasattr(self.db, 'get_folder_by_id'):
                folder = self.db.get_folder_by_id(folder_id)
                
                if folder:
                    total_files = folder[2]
                    max_uploads = folder[3]
                    uploaded_count = folder[4]
                    
                    # 计算状态
                    status = "待上传"
                    
                    if uploaded_count >= max_uploads:
                        status = "已完成"
                    elif uploaded_count > 0:
                        status = "上传中"
                        
                    # 更新状态
                    if hasattr(self.db, 'update_folder_status'):
                        self.db.update_folder_status(folder_id, status)
                        
        except Exception as e:
            self.log(f"更新文件夹状态失败: {str(e)}")
            traceback.print_exc() 