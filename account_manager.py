#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QMessageBox, QInputDialog, QFileDialog, 
                            QTableWidgetItem, QHeaderView, QCheckBox)
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
            self.accounts = self.db.get_all_accounts()
            
            if not self.accounts:
                print("[警告] 未找到任何账号数据")
                return
                
            print(f"2. 成功读取到 {len(self.accounts)} 个账号")
            
            # 清空并更新表格
            print("3. 更新表格...")
            self.ui.accountTable.setRowCount(0)
            
            for i, account in enumerate(self.accounts):
                self.ui.accountTable.insertRow(i)
                
                # 第0列：复选框
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                checkbox_item.setCheckState(Qt.Checked)
                self.ui.accountTable.setItem(i, 0, checkbox_item)
                
                # 第1列：序号
                self.ui.accountTable.setItem(i, 1, QTableWidgetItem(str(i+1)))
                
                # 第2列：账号ID (appid)
                self.ui.accountTable.setItem(i, 2, QTableWidgetItem(str(account[1])))
                
                # 第3列：账号名称 (name)
                self.ui.accountTable.setItem(i, 3, QTableWidgetItem(str(account[2])))
                
                # 第4列：今日视频数量 (today_videos)
                self.ui.accountTable.setItem(i, 4, QTableWidgetItem(str(account[4] or '0')))
                
                # 第5列：今日推荐数量 (today_recommended)
                self.ui.accountTable.setItem(i, 5, QTableWidgetItem(str(account[5] or '0')))
                
                # 第6列：今日播放量 (today_views)
                self.ui.accountTable.setItem(i, 6, QTableWidgetItem(str(account[6] or '0')))
                
                # 第7列：是否过画风 (pass_style)
                pass_style = account[7]
                style_item = QTableWidgetItem()
                if pass_style == 1:
                    style_item.setText("通过")
                    style_item.setForeground(QBrush(QColor(0, 153, 0)))  # 绿色
                else:
                    style_item.setText("未通过")
                    style_item.setForeground(QBrush(QColor(255, 0, 0)))  # 红色
                self.ui.accountTable.setItem(i, 7, style_item)
                
                # 第8列：Cookie状态 (cookies_status)
                self.ui.accountTable.setItem(i, 8, QTableWidgetItem(str(account[11] or '')))
                
                # 第9列：上传总数 (total_uploads)
                self.ui.accountTable.setItem(i, 9, QTableWidgetItem(str(account[8] or '0')))
                
                # 第10列至第12列：其他字段 - 暂时留空
                for col in range(10, 13):
                    self.ui.accountTable.setItem(i, col, QTableWidgetItem(''))
                
                # 第13列：是否是主账号 - 暂时留空
                self.ui.accountTable.setItem(i, 13, QTableWidgetItem(''))
                
                # 第14列：操作 - 暂时留空
                self.ui.accountTable.setItem(i, 14, QTableWidgetItem(''))
                
                # 调整行高
                self.ui.accountTable.setRowHeight(i, 30)
            
            print(f"=== 账号加载完成：共显示 {len(self.accounts)} 个账号 ===\n")
            
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