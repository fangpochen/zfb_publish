#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import glob
import traceback
from datetime import datetime
from PyQt5.QtWidgets import (QMessageBox, QInputDialog, QFileDialog, 
                            QTableWidgetItem, QHeaderView, QCheckBox)
from PyQt5.QtCore import Qt

from database import db_manager

class FolderManager:
    """文件夹管理模块，处理文件夹相关功能"""
    
    def __init__(self, ui, parent=None, log_callback=None):
        """初始化文件夹管理模块
        
        Args:
            ui: UI对象，包含界面组件
            parent: 父窗口对象，用于显示对话框
            log_callback: 日志记录回调函数
        """
        self.ui = ui
        self.parent = parent
        self.log = log_callback if log_callback else print
        self.db = db_manager
        
    def view_folders(self):
        """显示当前选中账号的所有文件夹"""
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
                QMessageBox.warning(self.parent, "提示", "请先选择一个账号333")
                return
                
            if len(selected_rows) > 1:
                QMessageBox.warning(self.parent, "提示", "请只选择一个账号查看文件夹")
                return
                
            # 获取选中账号的ID
            row = selected_rows[0]
            appid = self.ui.accountTable.item(row, 2).text()
            if not appid:
                QMessageBox.warning(self.parent, "提示", "获取账号ID失败")
                return
                
            # 确保UI中有folderTableWidget组件
            if not hasattr(self.ui, 'folderTableWidget'):
                self.log("UI中缺少folderTableWidget组件")
                return
                
            # 确保数据库有get_folder_settings方法
            if not hasattr(self.db, 'get_folder_settings'):
                self.log("数据库管理器缺少get_folder_settings方法")
                return
                
            # 获取文件夹列表
            folders = self.db.get_folder_settings(appid)
            
            # 清空文件夹表格
            self.ui.folderTableWidget.setRowCount(0)
            
            # 设置表格列头
            self.ui.folderTableWidget.setColumnCount(6)
            self.ui.folderTableWidget.setHorizontalHeaderLabels([
                "ID", "文件夹路径", "总文件数", "最大上传数", "已上传数", "状态"
            ])
            
            # 添加文件夹数据到表格
            for i, folder in enumerate(folders):
                self.ui.folderTableWidget.insertRow(i)
                
                # 设置每列的数据
                for j, value in enumerate(folder):
                    item = QTableWidgetItem(str(value))
                    # 设置第一列(ID)为不可编辑
                    if j == 0:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.ui.folderTableWidget.setItem(i, j, item)
                    
            # 调整列宽
            self.ui.folderTableWidget.setColumnWidth(0, 50)  # ID列
            self.ui.folderTableWidget.setColumnWidth(1, 250)  # 文件夹路径列
            self.ui.folderTableWidget.setColumnWidth(2, 80)  # 总文件数列
            self.ui.folderTableWidget.setColumnWidth(3, 90)  # 最大上传数列
            self.ui.folderTableWidget.setColumnWidth(4, 80)  # 已上传数列
            self.ui.folderTableWidget.setColumnWidth(5, 80)  # 状态列
            
            # 隐藏ID列
            self.ui.folderTableWidget.setColumnHidden(0, True)
            
            self.log(f"已加载账号 {appid} 的 {len(folders)} 个文件夹")
            
        except Exception as e:
            self.log(f"查看文件夹时出错: {str(e)}")
            traceback.print_exc()
    
    def add_folder(self):
        """向当前选中的账号添加视频文件夹"""
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
                QMessageBox.warning(self.parent, "提示", "请先选择一个账号444")
                return
                
            if len(selected_rows) > 1:
                QMessageBox.warning(self.parent, "提示", "请只选择一个账号添加文件夹")
                return
                
            # 获取选中账号的ID
            row = selected_rows[0]
            appid = self.ui.accountTable.item(row, 2).text()
            if not appid:
                QMessageBox.warning(self.parent, "提示", "获取账号ID失败")
                return
                
            # 打开文件夹选择对话框
            folder_path = QFileDialog.getExistingDirectory(self.parent, "选择视频文件夹")
            if not folder_path:
                return  # 用户取消选择
                
            # 统计文件夹中的视频文件数量
            video_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
            video_files = []
            
            for ext in video_extensions:
                video_files.extend(glob.glob(os.path.join(folder_path, f'*{ext}')))
                
            total_files = len(video_files)
            if total_files == 0:
                QMessageBox.warning(self.parent, "提示", f"所选文件夹中没有视频文件")
                return
                
            # 设置上传限制
            max_uploads, ok = QInputDialog.getInt(
                self.parent, "设置上传限制", 
                f"文件夹中共有 {total_files} 个视频文件，\n请设置最大上传数量（0表示全部）:",
                min=0, max=total_files, value=min(50, total_files)
            )
            
            if not ok:
                return  # 用户取消设置
                
            if max_uploads == 0:
                max_uploads = total_files  # 0表示全部上传
                
            # 确保数据库有add_folder方法
            if not hasattr(self.db, 'add_folder'):
                self.log("数据库管理器缺少add_folder方法")
                return
                
            # 添加文件夹到数据库
            success = self.db.add_folder(appid, folder_path, max_uploads, total_files)
            
            if success:
                self.log(f"成功添加文件夹: {folder_path}")
                # 刷新文件夹列表
                self.view_folders()
            else:
                QMessageBox.warning(self.parent, "错误", f"添加文件夹失败: {folder_path}")
                
        except Exception as e:
            self.log(f"添加文件夹时出错: {str(e)}")
            traceback.print_exc()
    
    def remove_folder(self):
        """删除选中的文件夹"""
        try:
            # 确保UI中有folderTableWidget组件
            if not hasattr(self.ui, 'folderTableWidget'):
                self.log("UI中缺少folderTableWidget组件")
                return
                
            # 检查是否有选中的文件夹
            selected_row = self.ui.folderTableWidget.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self.parent, "提示", "请先选择一个文件夹")
                return
                
            # 获取文件夹ID
            folder_id = self.ui.folderTableWidget.item(selected_row, 0).text()
            folder_path = self.ui.folderTableWidget.item(selected_row, 1).text()
            
            # 确认删除
            reply = QMessageBox.question(
                self.parent, "确认删除", 
                f"确定要删除文件夹 {folder_path} 吗？\n删除后，该文件夹的所有上传记录将被清除。",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 确保数据库有remove_folder方法
                if not hasattr(self.db, 'remove_folder'):
                    self.log("数据库管理器缺少remove_folder方法")
                    return
                    
                # 执行删除
                success = self.db.remove_folder(folder_id)
                
                if success:
                    self.log(f"成功删除文件夹: {folder_path}")
                    # 刷新文件夹列表
                    self.view_folders()
                else:
                    QMessageBox.warning(self.parent, "错误", f"删除文件夹失败: {folder_path}")
                    
        except Exception as e:
            self.log(f"删除文件夹时出错: {str(e)}")
            traceback.print_exc()
    
    def edit_folder_limit(self):
        """编辑文件夹上传限制"""
        try:
            # 确保UI中有folderTableWidget组件
            if not hasattr(self.ui, 'folderTableWidget'):
                self.log("UI中缺少folderTableWidget组件")
                return
                
            # 检查是否有选中的文件夹
            selected_row = self.ui.folderTableWidget.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self.parent, "提示", "请先选择一个文件夹")
                return
                
            # 获取文件夹信息
            folder_id = self.ui.folderTableWidget.item(selected_row, 0).text()
            folder_path = self.ui.folderTableWidget.item(selected_row, 1).text()
            total_files = int(self.ui.folderTableWidget.item(selected_row, 2).text())
            current_limit = int(self.ui.folderTableWidget.item(selected_row, 3).text())
            
            # 设置新的上传限制
            new_limit, ok = QInputDialog.getInt(
                self.parent, "设置上传限制", 
                f"文件夹: {folder_path}\n"
                f"总文件数: {total_files}\n"
                f"当前限制: {current_limit}\n\n"
                f"请设置新的最大上传数量（0表示全部）:",
                min=0, max=total_files, value=current_limit
            )
            
            if not ok:
                return  # 用户取消设置
                
            if new_limit == 0:
                new_limit = total_files  # 0表示全部上传
                
            # 确保数据库有update_folder_limit方法
            if not hasattr(self.db, 'update_folder_limit'):
                self.log("数据库管理器缺少update_folder_limit方法")
                return
                
            # 更新数据库
            success = self.db.update_folder_limit(folder_id, new_limit)
            
            if success:
                self.log(f"成功更新文件夹上传限制: {folder_path}, 新限制: {new_limit}")
                # 刷新文件夹列表
                self.view_folders()
            else:
                QMessageBox.warning(self.parent, "错误", f"更新文件夹上传限制失败: {folder_path}")
                
        except Exception as e:
            self.log(f"编辑文件夹上传限制时出错: {str(e)}")
            traceback.print_exc()
    
    def start_upload(self):
        """开始上传文件夹中的视频"""
        try:
            # 检查是否有选中的文件夹
            selected_row = self.ui.folderTableWidget.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self.parent, "提示", "请先选择一个文件夹")
                return
                
            # 获取文件夹信息
            folder_id = self.ui.folderTableWidget.item(selected_row, 0).text()
            folder_path = self.ui.folderTableWidget.item(selected_row, 1).text()
            
            # 更新文件夹状态为"上传中"
            self.ui.folderTableWidget.item(selected_row, 5).setText("上传中")
            
            # TODO: 实现视频上传功能
            # 这里需要调用视频上传模块的功能
            
            self.log(f"开始上传文件夹中的视频: {folder_path}")
            
        except Exception as e:
            self.log(f"开始上传视频时出错: {str(e)}")
            traceback.print_exc()
            
    def stop_upload(self):
        """停止上传文件夹中的视频"""
        try:
            # 检查是否有选中的文件夹
            selected_row = self.ui.folderTableWidget.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self.parent, "提示", "请先选择一个文件夹")
                return
                
            # 获取文件夹信息
            folder_id = self.ui.folderTableWidget.item(selected_row, 0).text()
            folder_path = self.ui.folderTableWidget.item(selected_row, 1).text()
            
            # 更新文件夹状态为"已停止"
            self.ui.folderTableWidget.item(selected_row, 5).setText("已停止")
            
            # TODO: 实现停止视频上传功能
            # 这里需要调用视频上传模块的功能，停止上传进程
            
            self.log(f"停止上传文件夹中的视频: {folder_path}")
            
        except Exception as e:
            self.log(f"停止上传视频时出错: {str(e)}")
            traceback.print_exc() 