#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QMessageBox, QInputDialog, QFileDialog, 
                            QTableWidgetItem, QHeaderView, QCheckBox, QPushButton, QWidget, QVBoxLayout, QLabel)
from PyQt5.QtCore import Qt, QDate
import json
from PyQt5.QtGui import QBrush, QColor

from database import db_manager

class AccountManager:
    """账号管理模块，处理账号相关功能"""
    
    def __init__(self, ui, parent=None, log_callback=None):
        """初始化账号管理模块
        
        Args:
            ui: UI对象，包含界面组件
            parent: 父窗口对象，用于显示对话框
            log_callback: 日志记录回调函数
        """
        self.ui = ui
        self.parent = parent
        self.log = log_callback if log_callback else print
        self.db = db_manager
        self.accounts = []  # 所有账号列表
        self.filtered_accounts = []  # 过滤后的账号列表
        
        # 初始化API客户端
        from api_client import ApiClient
        self.api_client = ApiClient(log_callback=self.log)
        
    def load_accounts(self):
        """加载所有账号"""
        print("\n=== 开始加载账号数据 ===")
        try:
            # 从数据库加载账号
            print("1. 从数据库读取账号数据...")
            self.accounts = self.db.load_accounts()
            
            if not self.accounts:
                print("[警告] 未找到任何账号数据")
                self.ui.accountTable.setRowCount(0)
                return
                
            print(f"2. 成功读取到 {len(self.accounts)} 个账号")
            
            # 清空并更新表格
            print("3. 更新表格...")
            self.ui.accountTable.setRowCount(0)
            
            for i, account in enumerate(self.accounts):
                self.ui.accountTable.insertRow(i)
                
                # 第0列：复选框
                checkbox = QCheckBox()
                checkbox.setChecked(True)  # 默认选中
                checkbox_container = QWidget()
                checkbox_layout = QVBoxLayout(checkbox_container)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.ui.accountTable.setCellWidget(i, 0, checkbox_container)
                
                # 第1列：序号
                self.ui.accountTable.setItem(i, 1, QTableWidgetItem(str(i+1)))
                
                # 第2列：账号ID (appid)
                self.ui.accountTable.setItem(i, 2, QTableWidgetItem(str(account['appid'])))
                
                # 第3列：账号名称 (name)
                self.ui.accountTable.setItem(i, 3, QTableWidgetItem(str(account['name'])))
                
                # 第4列：今日视频数量 (today_videos)
                self.ui.accountTable.setItem(i, 4, QTableWidgetItem(str(account['today_videos'] or '0')))
                
                # 第5列：今日推荐数量 (today_recommended)
                self.ui.accountTable.setItem(i, 5, QTableWidgetItem(str(account['today_recommended'] or '0')))
                
                # 第6列：今日播放量 (today_views)
                self.ui.accountTable.setItem(i, 6, QTableWidgetItem(str(account['today_views'] or '0')))
                
                # 第7列：是否过画风 (pass_style)
                pass_style = account['pass_style']
                style_item = QTableWidgetItem()
                if pass_style:
                    style_item.setText("通过")
                    style_item.setForeground(QBrush(QColor(0, 153, 0)))  # 绿色
                else:
                    style_item.setText("未通过")
                    style_item.setForeground(QBrush(QColor(255, 0, 0)))  # 红色
                self.ui.accountTable.setItem(i, 7, style_item)
                
                # 第8列：Cookie状态 (cookies_status)
                self.ui.accountTable.setItem(i, 8, QTableWidgetItem(str(account['cookies_status'] or '')))
                
                # 第9列：上传总数 (total_uploads)
                self.ui.accountTable.setItem(i, 9, QTableWidgetItem(str(account['total_uploads'] or '0')))
                
                # 第10列至第12列：其他字段 - 暂时留空
                for col in range(10, 13):
                    self.ui.accountTable.setItem(i, col, QTableWidgetItem(''))
                
                # 第13列和第14列：文件夹路径和视频数量
                appid = account['appid']
                
                # 尝试从folder_settings表获取完整信息
                folder_info = None
                if hasattr(self.db, 'get_folder_setting'):
                    folder_info = self.db.get_folder_setting(appid)
                
                # 如果从folder_settings获取到了信息
                if folder_info and folder_info.get('folder_path'):
                    folder_path = folder_info.get('folder_path')
                    video_count = folder_info.get('total_files', 0)
                    
                    # 设置文件夹路径到第13列 - 显示完整绝对路径
                    folder_item = QTableWidgetItem(folder_path)
                    folder_item.setToolTip(folder_path)
                    self.ui.accountTable.setItem(i, 13, folder_item)
                    
                    # 设置视频数量到第14列
                    count_item = QTableWidgetItem(f"{video_count}个")
                    
                    # 根据视频数量设置不同颜色
                    if video_count > 10:
                        count_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                    elif video_count > 0:
                        count_item.setForeground(QBrush(QColor("#E6A23C")))  # 橙色
                    else:
                        count_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                        
                    self.ui.accountTable.setItem(i, 14, count_item)
                else:
                    # 使用accounts表中的数据
                    folder_path = account['folder_path'] or ''
                    if folder_path:
                        # 显示完整路径
                        folder_item = QTableWidgetItem(folder_path)
                        folder_item.setToolTip(folder_path)
                        self.ui.accountTable.setItem(i, 13, folder_item)
                        
                        # 计算视频数量
                        video_count = self._count_video_files(folder_path)
                        count_item = QTableWidgetItem(f"{video_count}个")
                        
                        # 根据视频数量设置不同颜色
                        if video_count > 10:
                            count_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                        elif video_count > 0:
                            count_item.setForeground(QBrush(QColor("#E6A23C")))  # 橙色
                        else:
                            count_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                            
                        self.ui.accountTable.setItem(i, 14, count_item)
                        
                        # 同步更新到folder_settings表
                        if hasattr(self.db, 'save_account_folder'):
                            self.db.save_account_folder(appid, folder_path)
                    else:
                        self.ui.accountTable.setItem(i, 13, QTableWidgetItem('未设置'))
                        self.ui.accountTable.setItem(i, 14, QTableWidgetItem('0'))
                
                # 第15列：添加设置文件夹按钮
                self.add_folder_button_to_row(i)
                
            # 调整列宽
            print("4. 调整列宽...")
            self.ui.accountTable.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            
            # 更新每个账号的画风信息
            print("5. 更新完成")
            
        except Exception as e:
            print(f"[错误] 加载账号失败: {str(e)}")
            traceback.print_exc()
    
    def update_account_table(self, accounts):
        """更新账号表格
        
        Args:
            accounts: 要显示的账号列表
        """
        try:
            # 确保UI中有accountTable组件
            if not hasattr(self.ui, 'accountTable'):
                self.log("UI中缺少accountTable组件")
                return
                
            # 清空账号表格
            self.ui.accountTable.setRowCount(0)
            
            # 记录过滤后的账号
            self.filtered_accounts = accounts
            
            # 添加账号数据到表格
            for i, account in enumerate(accounts):
                self.ui.accountTable.insertRow(i)
                
                # 第0列：复选框
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                checkbox_item.setCheckState(Qt.Checked)  # 默认选中所有账号
                self.ui.accountTable.setItem(i, 0, checkbox_item)
                
                # 第1列：序号
                item_num = QTableWidgetItem(str(i+1))
                self.ui.accountTable.setItem(i, 1, item_num)
                
                # 转换数据格式，处理元组或字典
                appid = ""
                name = ""
                
                if isinstance(account, tuple) and len(account) >= 2:
                    # 如果是元组格式 (appid, name, ...)
                    appid = str(account[0])
                    name = str(account[1])
                elif isinstance(account, dict):
                    # 如果是字典格式 {'appid': ..., 'name': ...}
                    appid = str(account.get('appid', ''))
                    name = str(account.get('name', ''))
                
                # 第2列：账号ID
                item_id = QTableWidgetItem(appid)
                self.ui.accountTable.setItem(i, 2, item_id)
                
                # 第3列：账号名称
                item_name = QTableWidgetItem(name)
                self.ui.accountTable.setItem(i, 3, item_name)
                
                # 其他列根据需要填充
                for col in range(4, self.ui.accountTable.columnCount()):
                    self.ui.accountTable.setItem(i, col, QTableWidgetItem(''))
                
                # 设置每一行的高度
                self.ui.accountTable.setRowHeight(i, 30)
            
            # 更新完成后触发选择变化事件
            self.ui.accountTable.itemSelectionChanged.emit()
            
        except Exception as e:
            self.log(f"更新账号表格失败: {str(e)}")
            traceback.print_exc()
    
    def add_account(self):
        """添加新账号"""
        try:
            # 获取账号信息
            appid, ok1 = QInputDialog.getText(self.parent, "添加账号", "请输入账号ID:")
            if not ok1 or not appid:
                return
                
            name, ok2 = QInputDialog.getText(self.parent, "添加账号", "请输入账号名称:")
            if not ok2 or not name:
                return
                
            cookies, ok3 = QInputDialog.getText(self.parent, "添加账号", "请输入账号Cookies:")
            if not ok3:
                return
                
            # 添加账号到数据库
            if hasattr(self.db, 'add_account'):
                success = self.db.add_account(appid, name, cookies)
                if success:
                    self.log(f"成功添加账号: {name} ({appid})")
                    # 重新加载账号列表
                    self.load_accounts()
                else:
                    QMessageBox.warning(self.parent, "错误", f"添加账号失败")
            else:
                self.log("数据库管理器缺少add_account方法")
                
        except Exception as e:
            self.log(f"添加账号时出错: {str(e)}")
            traceback.print_exc()
    
    def remove_account(self):
        """删除选中的账号"""
        try:
            # 检查是否有选中的账号
            selected_rows = []
            for row in range(self.ui.accountTable.rowCount()):
                checkbox = self.ui.accountTable.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    selected_rows.append(row)
            
            if not selected_rows:
                QMessageBox.warning(self.parent, "提示", "请先选择至少一个账号")
                return
                
            # 确认删除
            reply = QMessageBox.question(
                self.parent, "确认删除", 
                f"确定要删除选中的 {len(selected_rows)} 个账号吗？\n删除后，这些账号的所有数据将被清除。",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 执行删除
                success_count = 0
                
                for row in selected_rows:
                    appid = self.ui.accountTable.item(row, 2).text()
                    if hasattr(self.db, 'remove_account'):
                        if self.db.remove_account(appid):
                            success_count += 1
                
                if success_count > 0:
                    self.log(f"成功删除 {success_count}/{len(selected_rows)} 个账号")
                    # 重新加载账号列表
                    self.load_accounts()
                else:
                    QMessageBox.warning(self.parent, "错误", f"删除账号失败")
                    
        except Exception as e:
            self.log(f"删除账号时出错: {str(e)}")
            traceback.print_exc()
    
    def search_accounts(self, keyword):
        """搜索账号
        
        Args:
            keyword: 搜索关键词
        """
        try:
            if not keyword:
                # 显示所有账号
                self.update_account_table(self.accounts)
                return
                
            # 根据关键词过滤账号
            filtered = [
                account for account in self.accounts 
                if keyword.lower() in account.get('name', '').lower() or 
                   keyword.lower() in account.get('appid', '').lower()
            ]
            
            # 更新账号表格
            self.update_account_table(filtered)
            
            # 记录日志
            self.log(f"搜索账号 '{keyword}', 找到 {len(filtered)} 个结果")
            
        except Exception as e:
            self.log(f"搜索账号时出错: {str(e)}")
            traceback.print_exc()
    
    def select_all_accounts(self):
        """选中所有账号"""
        try:
            for row in range(self.ui.accountTable.rowCount()):
                checkbox_item = self.ui.accountTable.item(row, 0)
                if checkbox_item:
                    checkbox_item.setCheckState(Qt.Checked)
            self.log("已选中所有账号")
        except Exception as e:
            self.log(f"选中所有账号时出错: {str(e)}")
            traceback.print_exc()
    
    def deselect_all_accounts(self):
        """取消选中所有账号"""
        try:
            for row in range(self.ui.accountTable.rowCount()):
                checkbox_item = self.ui.accountTable.item(row, 0)
                if checkbox_item:
                    checkbox_item.setCheckState(Qt.Unchecked)
            self.log("已取消选中所有账号")
        except Exception as e:
            self.log(f"取消选中所有账号时出错: {str(e)}")
            traceback.print_exc()
    
    def clear_account_data(self, clear_all=False):
        """清空账号数据
        
        Args:
            clear_all: 是否清空所有账号的数据
        """
        try:
            if clear_all:
                # 确认清空所有账号数据
                reply = QMessageBox.question(
                    self.parent, "确认清空", 
                    "确定要清空所有账号的数据吗？此操作不可撤销。",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # 直接清空accounts表
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute("DELETE FROM accounts")
                        conn.commit()
                        self.log("成功清空所有账号数据")
                        # 重新加载账号列表
                        self.load_accounts()
                    except Exception as e:
                        self.log(f"清空数据库失败: {str(e)}")
                        conn.rollback()
                        QMessageBox.warning(self.parent, "错误", "清空账号数据失败")
                    finally:
                        conn.close()
            else:
                # 清空选中账号的数据
                selected_rows = []
                for row in range(self.ui.accountTable.rowCount()):
                    checkbox_item = self.ui.accountTable.item(row, 0)
                    if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                        selected_rows.append(row)
                
                if not selected_rows:
                    QMessageBox.warning(self.parent, "提示", "请先选择至少一个账号")
                    return
                    
                # 确认清空
                reply = QMessageBox.question(
                    self.parent, "确认清空", 
                    f"确定要清空选中的 {len(selected_rows)} 个账号的数据吗？此操作不可撤销。",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # 执行清空
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    try:
                        for row in selected_rows:
                            appid = self.ui.accountTable.item(row, 2).text()
                            cursor.execute("DELETE FROM accounts WHERE appid = ?", (appid,))
                        conn.commit()
                        self.log(f"成功清空 {len(selected_rows)} 个账号的数据")
                        # 重新加载账号列表
                        self.load_accounts()
                    except Exception as e:
                        self.log(f"清空数据库失败: {str(e)}")
                        conn.rollback()
                        QMessageBox.warning(self.parent, "错误", "清空账号数据失败")
                    finally:
                        conn.close()
                        
        except Exception as e:
            self.log(f"清空账号数据时出错: {str(e)}")
            traceback.print_exc()
    
    def login_new_account(self):
        """登录新账号，获取cookie和账号信息"""
        try:
            self.log("开始登录新账号...")
            
            # 调用API客户端的登录方法
            result = self.api_client.login_account()
            
            if result:
                cookies_dict, appid, user_name, all_request = result
                self.log(f"登录成功: {user_name} ({appid})")
                
                # 重新加载账号列表
                self.load_accounts()
                
                # 显示成功提示
                QMessageBox.information(self.parent, "登录成功", f"成功登录账号: {user_name}")
            else:
                self.log("登录失败")
                QMessageBox.warning(self.parent, "登录失败", "登录失败，请重试")
                
        except Exception as e:
            self.log(f"登录新账号时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self.parent, "登录出错", f"登录过程中出现错误: {str(e)}")
    
    def fetch_sub_accounts(self):
        """获取子账号列表"""
        try:
            # 获取所有账号的cookies
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT appid, cookies, name FROM accounts")
            accounts = cursor.fetchall()
            conn.close()
            
            if not accounts:
                self.log("未找到任何账号")
                return
            
            success_count = 0
            for account in accounts:
                try:
                    appid = account[0]
                    cookies_str = account[1]
                    name = account[2]
                    
                    # 解析cookies
                    cookies = json.loads(cookies_str) if isinstance(cookies_str, str) else cookies_str
                    
                    # 调用API获取子账号
                    self.log(f"开始获取账号 {name} ({appid}) 的子账号...")
                    sub_accounts = self.api_client.get_life_option_list(cookies, appid)
                    
                    if sub_accounts:
                        # 保存子账号信息到数据库
                        for sub_account in sub_accounts:
                            sub_appid = sub_account.get('appId')
                            sub_name = sub_account.get('appName')
                            
                            if sub_appid and sub_name:
                                if self.db.save_account(sub_appid, sub_name, cookies):
                                    success_count += 1
                                    self.log(f"成功保存子账号: {sub_name} ({sub_appid})")
                                else:
                                    self.log(f"保存子账号失败: {sub_name} ({sub_appid})")
                    
                except Exception as e:
                    self.log(f"处理账号 {appid} 的子账号时出错: {str(e)}")
                    continue
            
            # 重新加载账号列表
            self.load_accounts()
            
            if success_count > 0:
                QMessageBox.information(self.parent, "获取子账号成功", f"成功获取并保存 {success_count} 个子账号")
            else:
                QMessageBox.information(self.parent, "提示", "未找到任何子账号")
            
        except Exception as e:
            self.log(f"获取子账号时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self.parent, "获取子账号出错", f"获取子账号过程中出现错误: {str(e)}")
    
    def add_folder_button_to_row(self, row):
        """为表格行添加文件夹按钮
        
        Args:
            row: 表格行索引
        """
        try:
            if not hasattr(self.ui, 'accountTable'):
                return
                
            # 创建按钮
            button = QPushButton("设置文件夹")
            button.setProperty("type", "info")
            button.setProperty("size", "small")
            
            # 设置点击事件
            button.clicked.connect(lambda: self.select_folder_for_account(row))
            
            # 添加到表格
            self.ui.accountTable.setCellWidget(row, 15, button)
            
        except Exception as e:
            self.log(f"添加文件夹按钮失败: {str(e)}")
            traceback.print_exc()
    
    def select_folder_for_account(self, row):
        """为指定账号选择文件夹
        
        Args:
            row: 表格行索引
        """
        try:
            if not hasattr(self.ui, 'accountTable'):
                return
                
            # 获取账号ID
            appid_item = self.ui.accountTable.item(row, 2)
            if not appid_item:
                self.log("无法获取账号ID")
                return
                
            appid = appid_item.text()
            
            # 打开文件夹选择对话框
            folder_path = QFileDialog.getExistingDirectory(
                self.parent,
                "选择视频文件夹",
                "",
                QFileDialog.ShowDirsOnly
            )
            
            if not folder_path:
                self.log("未选择文件夹")
                return
                
            # 设置账号文件夹
            if self.set_account_folder(appid, folder_path):
                # 获取已保存的文件夹信息（包括视频数量）
                folder_info = None
                if hasattr(self.db, 'get_folder_setting'):
                    folder_info = self.db.get_folder_setting(appid, folder_path)
                
                if folder_info and folder_info.get('folder_path') and 'total_files' in folder_info:
                    # 使用数据库中的信息
                    folder_path = folder_info.get('folder_path')
                    video_count = folder_info.get('total_files', 0)
                    
                    # 更新文件夹路径列 - 显示完整绝对路径
                    folder_item = QTableWidgetItem(folder_path)
                    folder_item.setToolTip(folder_path)
                    self.ui.accountTable.setItem(row, 13, folder_item)
                    
                    # 更新视频数量列
                    count_item = QTableWidgetItem(f"{video_count}个")
                    
                    # 根据视频数量设置不同颜色
                    if video_count > 10:
                        count_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                    elif video_count > 0:
                        count_item.setForeground(QBrush(QColor("#E6A23C")))  # 橙色
                    else:
                        count_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                        
                    self.ui.accountTable.setItem(row, 14, count_item)
                else:
                    # 手动计算并显示
                    # 更新文件夹路径列 - 显示完整绝对路径
                    folder_item = QTableWidgetItem(folder_path)
                    folder_item.setToolTip(folder_path)
                    self.ui.accountTable.setItem(row, 13, folder_item)
                    
                    # 更新视频数量列
                    video_count = self._count_video_files(folder_path)
                    count_item = QTableWidgetItem(f"{video_count}个")
                    
                    # 根据视频数量设置不同颜色
                    if video_count > 10:
                        count_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                    elif video_count > 0:
                        count_item.setForeground(QBrush(QColor("#E6A23C")))  # 橙色
                    else:
                        count_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                        
                    self.ui.accountTable.setItem(row, 14, count_item)
                
                self.log(f"已为账号 {appid} 设置文件夹: {folder_path}，视频数量: {video_count}个")
            else:
                self.log(f"设置账号 {appid} 的文件夹失败")
                
        except Exception as e:
            self.log(f"选择文件夹时出错: {str(e)}")
            traceback.print_exc()
    
    def set_account_folder(self, appid, folder_path):
        """设置账号的上传文件夹
        
        Args:
            appid: 账号ID
            folder_path: 文件夹路径
            
        Returns:
            bool: 是否设置成功
        """
        try:
            # 首先检查文件夹是否存在
            if not os.path.exists(folder_path):
                self.log(f"文件夹不存在: {folder_path}")
                return False
                
            # 保存到数据库
            if hasattr(self.db, 'save_account_folder'):
                success = self.db.save_account_folder(appid, folder_path)
                if success:
                    self.log(f"成功设置账号 {appid} 的文件夹: {folder_path}")
                    return True
                else:
                    self.log(f"保存账号文件夹失败: {appid} -> {folder_path}")
                    return False
            else:
                self.log("数据库管理器缺少save_account_folder方法")
                return False
                
        except Exception as e:
            self.log(f"设置账号文件夹时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def get_account_folder(self, appid):
        """获取账号的上传文件夹路径
        
        Args:
            appid: 账号ID
            
        Returns:
            dict: 文件夹信息，包含路径和视频数量
        """
        try:
            # 从数据库获取
            if hasattr(self.db, 'get_account_folder'):
                folder_info = self.db.get_account_folder(appid)
                
                # 验证文件夹是否存在
                if folder_info and folder_info.get('folder_path') and os.path.exists(folder_info.get('folder_path')):
                    return folder_info
                    
                return None
            else:
                self.log("数据库管理器缺少get_account_folder方法")
                return None
                
        except Exception as e:
            self.log(f"获取账号文件夹时出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def show_folder_info(self, row, folder_path):
        """在表格中显示文件夹信息
        
        Args:
            row: 表格行索引
            folder_path: 文件夹路径
        """
        try:
            if not hasattr(self.ui, 'accountTable'):
                return
                
            # 获取行的appid
            appid_item = self.ui.accountTable.item(row, 2)
            if not appid_item:
                self.log("无法获取账号ID")
                return
                
            appid = appid_item.text()
            
            # 尝试从folder_settings表获取完整信息
            folder_info = None
            if hasattr(self.db, 'get_folder_setting'):
                folder_info = self.db.get_folder_setting(appid, folder_path)
            
            # 如果没有获取到信息，则手动计算视频数量
            if folder_info and 'total_files' in folder_info:
                video_count = folder_info.get('total_files', 0)
            else:
                # 获取文件夹中的视频文件数量
                video_count = self._count_video_files(folder_path)
            
            # 设置文件夹路径到第13列 - 显示完整绝对路径
            folder_item = QTableWidgetItem(folder_path)
            folder_item.setToolTip(folder_path)  # 完整路径显示在悬停提示中
            self.ui.accountTable.setItem(row, 13, folder_item)
            
            # 设置视频数量到第14列
            count_item = QTableWidgetItem(f"{video_count}个")
            
            # 根据视频数量设置不同颜色
            if video_count > 10:
                count_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
            elif video_count > 0:
                count_item.setForeground(QBrush(QColor("#E6A23C")))  # 橙色
            else:
                count_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                
            self.ui.accountTable.setItem(row, 14, count_item)
            
        except Exception as e:
            self.log(f"显示文件夹信息失败: {str(e)}")
            traceback.print_exc()
            # 设置一个简单的错误信息
            self.ui.accountTable.setItem(row, 13, QTableWidgetItem("显示失败"))
            self.ui.accountTable.setItem(row, 14, QTableWidgetItem("0"))
    
    def _count_video_files(self, folder_path):
        """计算文件夹中的视频文件数量
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            int: 视频文件数量
        """
        try:
            if not folder_path or not os.path.exists(folder_path):
                return 0
                
            video_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
            count = 0
            
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file)[1].lower()
                    if ext in video_extensions:
                        count += 1
            
            return count
        except Exception as e:
            self.log(f"计算视频文件数量失败: {str(e)}")
            traceback.print_exc()
            return 0
    
    def _add_folder_support_to_db(self):
        """向数据库管理器添加文件夹支持功能"""
        try:
            # 添加save_account_folder方法
            def save_account_folder(self, appid, folder_path):
                """保存账号的上传文件夹路径
                
                Args:
                    appid: 账号ID
                    folder_path: 文件夹路径
                    
                Returns:
                    bool: 是否保存成功
                """
                try:
                    conn = self.get_connection()
                    cursor = conn.cursor()
                    
                    # 检查account_folders表是否存在
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_folders'")
                    if not cursor.fetchone():
                        # 创建表
                        cursor.execute('''
                            CREATE TABLE account_folders (
                                appid TEXT PRIMARY KEY,
                                folder_path TEXT,
                                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                    
                    # 插入或更新记录
                    cursor.execute('''
                        INSERT OR REPLACE INTO account_folders (appid, folder_path)
                        VALUES (?, ?)
                    ''', (appid, folder_path))
                    
                    conn.commit()
                    conn.close()
                    return True
                    
                except Exception as e:
                    print(f"保存账号文件夹失败: {str(e)}")
                    traceback.print_exc()
                    return False
            
            # 添加get_account_folder方法
            def get_account_folder(self, appid):
                """获取账号的上传文件夹路径
                
                Args:
                    appid: 账号ID
                    
                Returns:
                    str: 文件夹路径，如果未设置则返回None
                """
                try:
                    conn = self.get_connection()
                    cursor = conn.cursor()
                    
                    # 检查account_folders表是否存在
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_folders'")
                    if not cursor.fetchone():
                        # 表不存在，返回None
                        conn.close()
                        return None
                    
                    # 查询文件夹路径
                    cursor.execute('SELECT folder_path FROM account_folders WHERE appid = ?', (appid,))
                    result = cursor.fetchone()
                    
                    conn.close()
                    return result[0] if result else None
                    
                except Exception as e:
                    print(f"获取账号文件夹失败: {str(e)}")
                    traceback.print_exc()
                    return None
            
            # 添加get_all_account_folders方法
            def get_all_account_folders(self):
                """获取所有账号的文件夹设置
                
                Returns:
                    dict: 账号ID与文件夹路径的映射字典
                """
                try:
                    conn = self.get_connection()
                    cursor = conn.cursor()
                    
                    # 检查account_folders表是否存在
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_folders'")
                    if not cursor.fetchone():
                        # 表不存在，返回空字典
                        conn.close()
                        return {}
                    
                    # 查询所有账号的文件夹路径
                    cursor.execute('SELECT appid, folder_path FROM account_folders')
                    results = cursor.fetchall()
                    
                    conn.close()
                    return {row[0]: row[1] for row in results}
                    
                except Exception as e:
                    print(f"获取所有账号文件夹失败: {str(e)}")
                    traceback.print_exc()
                    return {}
            
            # 将方法绑定到db_manager对象
            import types
            self.db.save_account_folder = types.MethodType(save_account_folder, self.db)
            self.db.get_account_folder = types.MethodType(get_account_folder, self.db)
            self.db.get_all_account_folders = types.MethodType(get_all_account_folders, self.db)
            
            # 确保表存在
            self.db.save_account_folder("test", "test")
            
            self.log("成功添加文件夹支持功能到数据库管理器")
            
        except Exception as e:
            self.log(f"添加文件夹支持功能失败: {str(e)}")
            traceback.print_exc()
            
    def get_selected_accounts_with_folders(self):
        """获取选中的账号及其文件夹信息
        
        Returns:
            dict: 账号与其文件夹、cookies的映射字典 {appid: {'folder': folder_path, 'cookies': cookies}}
        """
        try:
            if not hasattr(self.ui, 'accountTable'):
                return {}
                
            account_folders = {}
            for row in range(self.ui.accountTable.rowCount()):
                # 检查是否选中
                checkbox_item = self.ui.accountTable.cellWidget(row, 0)
                if not checkbox_item or not hasattr(checkbox_item, 'isChecked') or not checkbox_item.isChecked():
                    continue
                    
                # 获取appid
                appid_item = self.ui.accountTable.item(row, 2)
                if not appid_item:
                    continue
                    
                appid = appid_item.text()
                
                # 获取文件夹路径
                folder_path = self.get_account_folder(appid)
                if not folder_path:
                    continue
                    
                # 获取cookies
                cookies = self.get_account_cookies(appid)
                if not cookies:
                    continue
                    
                account_folders[appid] = {
                    'folder': folder_path,
                    'cookies': cookies
                }
                
            return account_folders
            
        except Exception as e:
            self.log(f"获取选中账号文件夹失败: {str(e)}")
            traceback.print_exc()
            return {}
    
    def get_account_cookies(self, appid):
        """获取指定账号的cookies
        
        Args:
            appid: 账号ID
            
        Returns:
            dict: cookies数据，如果未找到则返回None
        """
        try:
            if hasattr(self.db, 'get_account_cookies'):
                return self.db.get_account_cookies(appid)
            else:
                # 直接从数据库获取
                conn = self.db.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('SELECT cookies FROM accounts WHERE appid = ?', (appid,))
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0]:
                    try:
                        return json.loads(result[0])
                    except:
                        return result[0]  # 如果不是JSON格式，直接返回字符串
                return None
                
        except Exception as e:
            self.log(f"获取账号cookies失败: {str(e)}")
            traceback.print_exc()
            return None 