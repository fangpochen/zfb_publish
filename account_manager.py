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
import uuid

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
            
            # 设置表格标题
            column_titles = [
                "选择", "序号", "账号ID", "账号名称", "今日视频", "今日推荐", 
                "今日播放", "检测状态", "登录状态", "上传总数", "当前成功", "当前失败"
            ]
            
            # 确保表格有足够的列
            if self.ui.accountTable.columnCount() < len(column_titles):
                self.ui.accountTable.setColumnCount(len(column_titles))
                
            # 设置列标题
            for i, title in enumerate(column_titles):
                self.ui.accountTable.setHorizontalHeaderItem(i, QTableWidgetItem(title))
            
            for i, account in enumerate(self.accounts):
                self.ui.accountTable.insertRow(i)
                
                # 第0列：复选框
                checkbox = QCheckBox()
                # 根据数据库中的is_checked字段设置复选框状态
                checkbox.setChecked(account.get('is_checked', True))
                checkbox_container = QWidget()
                checkbox_layout = QVBoxLayout(checkbox_container)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.ui.accountTable.setCellWidget(i, 0, checkbox_container)
                
                # 连接复选框状态变化信号，保存到数据库
                checkbox.stateChanged.connect(lambda state, app_id=account['appid']: self.on_checkbox_changed(app_id, state))
                
                # 第1列：序号
                self.ui.accountTable.setItem(i, 1, QTableWidgetItem(str(i+1)))
                
                # 第2列：账号ID (appid)
                self.ui.accountTable.setItem(i, 2, QTableWidgetItem(str(account['appid'])))
                
                # 第3列：账号名称 (name)
                self.ui.accountTable.setItem(i, 3, QTableWidgetItem(str(account['name'])))
                
                # 第4列：今日视频数量 (today_videos)
                self.ui.accountTable.setItem(i, 4, QTableWidgetItem(str(account['today_videos'] or '0')))
                
                # 第5列：今日推荐数 (today_recommended)
                self.ui.accountTable.setItem(i, 5, QTableWidgetItem(str(account['today_recommended'] or '0')))
                
                # 第6列：今日播放量 (today_views)
                self.ui.accountTable.setItem(i, 6, QTableWidgetItem(str(account['today_views'] or '0')))
                
                # 第7列：通过检测
                pass_style_item = QTableWidgetItem("通过" if account['pass_style'] else "未通过")
                
                # 根据通过状态设置颜色
                if account['pass_style']:
                    pass_style_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                else:
                    pass_style_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                    
                self.ui.accountTable.setItem(i, 7, pass_style_item)
                
                # 第8列：Cookie状态 (cookies_status)
                cookie_item = QTableWidgetItem(str(account['cookies_status']))
                
                # 根据Cookie状态设置颜色
                if account['cookies_status'] == '正常':
                    cookie_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                else:
                    cookie_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                    
                self.ui.accountTable.setItem(i, 8, cookie_item)
                
                # 获取appid
                appid = account['appid']
                
                # 第9列：上传总数（从folder_settings表获取max_uploads值）
                max_uploads = 0
                
                # 获取文件夹设置信息
                if hasattr(self.db, 'get_folder_settings'):
                    folder_settings = self.db.get_folder_settings(appid)
                    if folder_settings and len(folder_settings) > 0:
                        # 获取第一个文件夹的最大上传数值
                        max_uploads = folder_settings[0].get('max_uploads', 0)
                
                # 设置上传总数单元格
                max_uploads_item = QTableWidgetItem(str(max_uploads))
                self.ui.accountTable.setItem(i, 9, max_uploads_item)
                
                # 第10列：当前成功数
                success_item = QTableWidgetItem("0")
                success_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                self.ui.accountTable.setItem(i, 10, success_item)
                
                # 第11列：当前失败数
                failed_item = QTableWidgetItem("0")
                failed_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                self.ui.accountTable.setItem(i, 11, failed_item)
                
                # 添加文件夹路径和视频数量信息
                folder_settings = None
                if hasattr(self.db, 'get_folder_settings'):
                    folder_settings = self.db.get_folder_settings(appid)
                
                if folder_settings and folder_settings:
                    # 为每个账号添加文件夹路径和视频数量信息
                    folder_path = folder_settings[0]['folder_path'] if folder_settings else ''
                    total_files = folder_settings[0]['total_files'] if folder_settings else 0
                    
                    # 确保有足够的列
                    while self.ui.accountTable.columnCount() < 15:
                        self.ui.accountTable.insertColumn(self.ui.accountTable.columnCount())
                    
                    # 显示文件夹路径
                    folder_item = QTableWidgetItem(folder_path)
                    folder_item.setToolTip(folder_path)
                    self.ui.accountTable.setItem(i, 13, folder_item)
                    
                    # 显示视频数量
                    count_item = QTableWidgetItem(f"{total_files}个")
                    
                    # 根据视频数量设置不同颜色
                    if total_files > 10:
                        count_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                    elif total_files > 0:
                        count_item.setForeground(QBrush(QColor("#E6A23C")))  # 橙色
                    else:
                        count_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                    
                    self.ui.accountTable.setItem(i, 14, count_item)
                
                # 添加文件夹按钮
                self.add_folder_button_to_row(i)
                
                # 设置每一行的高度
                self.ui.accountTable.setRowHeight(i, 40)
                
            # 调整列宽
            self.ui.accountTable.setColumnWidth(0, 40)   # 复选框列
            self.ui.accountTable.setColumnWidth(1, 50)   # 序号列
            self.ui.accountTable.setColumnWidth(2, 150)  # 账号ID列
            self.ui.accountTable.setColumnWidth(3, 120)
            self.ui.accountTable.setColumnWidth(4, 80)   # 今日视频数量列
            self.ui.accountTable.setColumnWidth(5, 80)   # 今日推荐数列
            self.ui.accountTable.setColumnWidth(6, 80)   # 今日播放量列
            self.ui.accountTable.setColumnWidth(7, 80)   # 通过检测列
            self.ui.accountTable.setColumnWidth(8, 80)   # Cookie状态列
            self.ui.accountTable.setColumnWidth(9, 80)   # 上传总数列
            self.ui.accountTable.setColumnWidth(10, 80)  # 当前成功数列
            self.ui.accountTable.setColumnWidth(11, 80)  # 当前失败数列
            
            # 为文件夹路径和视频数量列设置列宽
            if self.ui.accountTable.columnCount() >= 15:
                self.ui.accountTable.setColumnWidth(13, 200)  # 文件夹路径列
                self.ui.accountTable.setColumnWidth(14, 80)   # 视频数量列
            
            # 隐藏垂直表头
            self.ui.accountTable.verticalHeader().setVisible(False)
            
            # 设置表格禁止编辑
            self.ui.accountTable.setEditTriggers(QHeaderView.NoEditTriggers)
            
            # 表格自适应宽度
            self.ui.accountTable.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            self.ui.accountTable.horizontalHeader().setStretchLastSection(True)
            
            print("4. 账号数据加载完成")
            
        except Exception as e:
            self.log(f"加载账号数据失败: {str(e)}")
            traceback.print_exc()
            
    def on_checkbox_changed(self, appid, state):
        """复选框状态变化处理
        
        Args:
            appid: 账号ID
            state: 复选框状态
        """
        try:
            # 更新数据库中的勾选状态
            if hasattr(self.db, 'update_account_check_status'):
                is_checked = (state == Qt.Checked)
                self.db.update_account_check_status(appid, is_checked)
                # 更新内存中账号数据
                for account in self.accounts:
                    if account['appid'] == appid:
                        account['is_checked'] = is_checked
                        break
        except Exception as e:
            self.log(f"更新账号勾选状态失败: {str(e)}")
            traceback.print_exc()
            
    def select_all_accounts(self):
        """选中所有账号"""
        try:
            updated_appids = []
            for row in range(self.ui.accountTable.rowCount()):
                # 获取单元格小部件（一个容器，其中包含QCheckBox）
                checkbox_container = self.ui.accountTable.cellWidget(row, 0)
                if checkbox_container:
                    # 在容器中查找QCheckBox
                    for child in checkbox_container.findChildren(QCheckBox):
                        if not child.isChecked():  # 只更新未选中的复选框
                            child.setChecked(True)
                            # 获取appid
                            appid_item = self.ui.accountTable.item(row, 2)
                            if appid_item:
                                updated_appids.append(appid_item.text())
                        break
            
            # 批量更新数据库
            if updated_appids and hasattr(self.db, 'get_connection'):
                conn = self.db.get_connection()
                cursor = conn.cursor()
                try:
                    for appid in updated_appids:
                        cursor.execute('''
                            UPDATE accounts
                            SET is_checked = 1
                            WHERE appid = ?
                        ''', (appid,))
                    conn.commit()
                except Exception as e:
                    self.log(f"批量更新勾选状态失败: {str(e)}")
                    conn.rollback()
                finally:
                    conn.close()
                    
            self.log("已选中所有账号")
        except Exception as e:
            self.log(f"选中所有账号时出错: {str(e)}")
            traceback.print_exc()
    
    def deselect_all_accounts(self):
        """取消选中所有账号"""
        try:
            updated_appids = []
            for row in range(self.ui.accountTable.rowCount()):
                # 获取单元格小部件（一个容器，其中包含QCheckBox）
                checkbox_container = self.ui.accountTable.cellWidget(row, 0)
                if checkbox_container:
                    # 在容器中查找QCheckBox
                    for child in checkbox_container.findChildren(QCheckBox):
                        if child.isChecked():  # 只更新已选中的复选框
                            child.setChecked(False)
                            # 获取appid
                            appid_item = self.ui.accountTable.item(row, 2)
                            if appid_item:
                                updated_appids.append(appid_item.text())
                        break
            
            # 批量更新数据库
            if updated_appids and hasattr(self.db, 'get_connection'):
                conn = self.db.get_connection()
                cursor = conn.cursor()
                try:
                    for appid in updated_appids:
                        cursor.execute('''
                            UPDATE accounts
                            SET is_checked = 0
                            WHERE appid = ?
                        ''', (appid,))
                    conn.commit()
                except Exception as e:
                    self.log(f"批量更新勾选状态失败: {str(e)}")
                    conn.rollback()
                finally:
                    conn.close()
                    
            self.log("已取消选中所有账号")
        except Exception as e:
            self.log(f"取消选中所有账号时出错: {str(e)}")
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
            
            # 确保表格有足够的列
            column_titles = [
                "选择", "序号", "账号ID", "账号名称", "今日视频", "今日推荐", 
                "今日播放", "检测状态", "登录状态", "上传总数", "当前成功", "当前失败"
            ]
            
            if self.ui.accountTable.columnCount() < len(column_titles):
                self.ui.accountTable.setColumnCount(len(column_titles))
                
            # 设置列标题
            for i, title in enumerate(column_titles):
                self.ui.accountTable.setHorizontalHeaderItem(i, QTableWidgetItem(title))
            
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
                
                # 第10列：当前成功数
                success_item = QTableWidgetItem("0")
                success_item.setForeground(QBrush(QColor("#67C23A")))  # 绿色
                self.ui.accountTable.setItem(i, 10, success_item)
                
                # 第11列：当前失败数
                failed_item = QTableWidgetItem("0")
                failed_item.setForeground(QBrush(QColor("#F56C6C")))  # 红色
                self.ui.accountTable.setItem(i, 11, failed_item)
                
                # 其他列根据需要填充
                for col in [4, 5, 6, 7, 8, 9]:
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
    
    def login_new_account(self):
        """登录新账号，获取cookie和账号信息"""
        try:
            self.log("开始登录新账号...")
            
            # 调用API客户端的登录方法
            result = self.api_client.login_account()
            
            if result:
                cookies_dict, appid, user_name, all_request = result
                self.log(f"登录成功: {user_name} ({appid})")
                
                # 询问是否要同步cookies到所有账号
                sync_reply = QMessageBox.question(
                    self.parent, "同步cookies", 
                    "是否将该账号的cookies同步给所有账号？\n这将使所有账号使用相同的登录凭证。",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.Yes
                )
                
                if sync_reply == QMessageBox.Yes:
                    self.log("开始同步cookies到所有账号...")
                    success_count, total_count = self.sync_all_accounts_cookies(appid)
                    if success_count > 0:
                        self.log(f"成功同步cookies到 {success_count}/{total_count} 个账号")
                        QMessageBox.information(self.parent, "同步完成", f"成功同步cookies到 {success_count}/{total_count} 个账号")
                    else:
                        self.log("没有账号需要同步cookies")
                
                # 重新加载账号列表
                self.load_accounts()
                
                # 显示成功提示
                QMessageBox.information(self.parent, "登录成功", f"成功登录账号: {user_name}")
                return True
            else:
                self.log("登录失败")
                QMessageBox.warning(self.parent, "登录失败", "登录失败，请重试")
                return False
                
        except Exception as e:
            self.log(f"登录新账号时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self.parent, "登录出错", f"登录过程中出现错误: {str(e)}")
            return False
    
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
                
            # 确保目录存在
            if not os.path.exists(folder_path):
                self.log(f"所选文件夹不存在: {folder_path}")
                return
            
            # 计算视频文件数量
            video_count = self._count_video_files(folder_path)
            
            # 更新数据库中的文件夹设置
            update_success = False
            default_max_uploads = 50  # 默认最大上传数
            
            if hasattr(self.db, 'add_folder'):
                # 正确地调用add_folder方法，传递单独的参数而不是字典
                update_success = self.db.add_folder(appid, folder_path, default_max_uploads, video_count)
            elif hasattr(self.db, 'save_account_folder'):
                # 使用旧的save_account_folder方法
                update_success = self.db.save_account_folder(appid, folder_path)
            
            if update_success:
                # 确保有足够的列
                while self.ui.accountTable.columnCount() < 15:
                    self.ui.accountTable.insertColumn(self.ui.accountTable.columnCount())
                
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
            list: 账号与文件夹信息列表 [{account: 账号信息, folders: 文件夹列表}]
        """
        try:
            if not hasattr(self.ui, 'accountTable'):
                return []
                
            account_folders = []
            for row in range(self.ui.accountTable.rowCount()):
                # 检查是否选中
                checkbox_container = self.ui.accountTable.cellWidget(row, 0)
                is_checked = False
                
                if checkbox_container:
                    for child in checkbox_container.findChildren(QCheckBox):
                        if child.isChecked():
                            is_checked = True
                            break
                
                if not is_checked:
                    continue
                    
                # 获取appid
                appid_item = self.ui.accountTable.item(row, 2)
                if not appid_item:
                    continue
                    
                appid = appid_item.text()
                name_item = self.ui.accountTable.item(row, 3)
                name = name_item.text() if name_item else ""
                
                # 获取账号信息
                account = {
                    'appid': appid,
                    'name': name
                }
                
                # 获取cookies
                cookies_dict = self.get_account_cookies(appid)
                if not cookies_dict:
                    continue
                    
                account['cookies'] = cookies_dict
                
                # 获取文件夹信息
                folders = []
                try:
                    folder_path = self.get_account_folder(appid)
                    if folder_path:
                        # 检查folder_path是否为字典类型，提取实际路径
                        actual_path = ''
                        if isinstance(folder_path, dict):
                            # 从字典中提取实际路径
                            actual_path = folder_path.get('folder_path', '')
                        else:
                            actual_path = folder_path
                        
                        # 添加到账号对象中（方便直接访问）
                        account['folder_path'] = actual_path
                        
                        # 只有在路径非空且存在时才添加到文件夹列表
                        if actual_path and os.path.exists(actual_path):
                            folders.append({
                                'path': actual_path,
                                'limit': 10  # 默认限制
                            })
                        else:
                            self.log(f"文件夹路径无效或不存在: '{actual_path}'")
                except Exception as e:
                    self.log(f"处理账号 {appid} 的文件夹时出错: {str(e)}")
                    traceback.print_exc()
                
                # 添加到结果列表
                account_folders.append({
                    'account': account,
                    'folders': folders
                })
                
            return account_folders
            
        except Exception as e:
            self.log(f"获取选中账号文件夹失败: {str(e)}")
            traceback.print_exc()
            return []
    
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
    
    def get_selected_accounts(self):
        """获取选中的账号列表
        
        Returns:
            list: 包含选中账号信息的列表，每个元素是一个字典
        """
        try:
            if not hasattr(self.ui, 'accountTable'):
                return []
                
            selected_accounts = []
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
                    # 获取账号信息
                    appid_item = self.ui.accountTable.item(row, 2)
                    name_item = self.ui.accountTable.item(row, 3)
                    
                    if appid_item and name_item:
                        selected_accounts.append({
                            'appid': appid_item.text(),
                            'name': name_item.text(),
                            'cookies_dict': self.get_account_cookies(appid_item.text())
                        })
            
            return selected_accounts
            
        except Exception as e:
            self.log(f"获取选中账号失败: {str(e)}")
            traceback.print_exc()
            return []
    
    def sync_all_accounts_cookies(self, source_appid=None):
        """同步所有账号的cookies
        
        Args:
            source_appid: 源账号ID，如果为None则使用最近一次登录的账号
            
        Returns:
            tuple: (成功更新的账号数, 总账号数)
        """
        try:
            self.log("开始同步所有账号的cookies...")
            
            # 如果没有指定源账号，尝试查找最近登录的账号
            if not source_appid:
                try:
                    # 从数据库查询最近登录的账号
                    recent_account = self.db.get_recent_login_account()
                    if recent_account:
                        source_appid = recent_account['appid']
                        self.log(f"使用最近登录的账号 {recent_account['name']}({source_appid}) 的cookies进行同步")
                    else:
                        self.log("未找到最近登录的账号，请指定一个源账号")
                        return 0, 0
                except Exception as e:
                    self.log(f"查询最近登录账号失败: {str(e)}")
                    return 0, 0
            
            # 获取源账号的cookies
            try:
                source_cookies = self.db.get_account_cookies(source_appid)
                if not source_cookies:
                    self.log(f"源账号 {source_appid} 没有有效的cookies")
                    return 0, 0
                
                self.log(f"成功获取源账号 {source_appid} 的cookies")
            except Exception as e:
                self.log(f"获取源账号cookies失败: {str(e)}")
                return 0, 0
            
            # 获取所有账号
            try:
                all_accounts = self.db.load_accounts()
                if not all_accounts:
                    self.log("数据库中没有账号")
                    return 0, 0
                
                total_count = len(all_accounts)
                self.log(f"找到 {total_count} 个账号")
            except Exception as e:
                self.log(f"获取账号列表失败: {str(e)}")
                return 0, 0
            
            # 更新所有账号的cookies
            success_count = 0
            for account in all_accounts:
                current_appid = account['appid']
                current_name = account['name']
                
                # 跳过源账号
                if current_appid == source_appid:
                    continue
                
                try:
                    # 更新账号的cookies
                    if self.db.update_account_cookies(current_appid, source_cookies):
                        success_count += 1
                        self.log(f"成功更新账号 {current_name}({current_appid}) 的cookies")
                    else:
                        self.log(f"更新账号 {current_name}({current_appid}) 的cookies失败")
                except Exception as e:
                    self.log(f"更新账号 {current_name}({current_appid}) 的cookies失败: {str(e)}")
            
            self.log(f"cookies同步完成，成功更新 {success_count}/{total_count-1} 个账号")
            
            # 重新加载账号列表以刷新UI
            self.load_accounts()
            
            return success_count, total_count-1
        except Exception as e:
            self.log(f"同步账号cookies时出错: {str(e)}")
            traceback.print_exc()
            return 0, 0 