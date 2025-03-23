def test_account_check_status():
    """测试账号勾选状态的保存和读取功能"""
    print("\n=== 测试账号勾选状态 ===")
    
    from database import DatabaseManager
    
    # 初始化数据库管理器
    db = DatabaseManager("test_db.sqlite")
    
    # 测试1: 检查是否存在is_checked字段
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(accounts)")
    columns = cursor.fetchall()
    conn.close()
    
    is_checked_exists = False
    for col in columns:
        if col[1] == 'is_checked':
            is_checked_exists = True
            break
    
    print(f"1. is_checked字段存在: {is_checked_exists}")
    assert is_checked_exists, "accounts表中缺少is_checked字段"
    
    # 测试2: 添加测试账号
    test_appid = "test_check_status_appid"
    test_name = "测试勾选状态账号"
    
    # 先检查该测试账号是否已存在，存在则删除
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE appid = ?", (test_appid,))
    if cursor.fetchone():
        cursor.execute("DELETE FROM accounts WHERE appid = ?", (test_appid,))
        conn.commit()
    conn.close()
    
    # 添加账号，默认勾选状态为1（勾选）
    db.add_account(
        appid=test_appid,
        name=test_name,
        cookies="test_cookies",
        folder_path="test_folder_path"
    )
    
    # 测试3: 确认默认勾选状态为1
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_checked FROM accounts WHERE appid = ?", (test_appid,))
    result = cursor.fetchone()
    conn.close()
    
    print(f"2. 新账号默认勾选状态: {result[0]}")
    assert result[0] == 1, "默认勾选状态应为1"
    
    # 测试4: 更新勾选状态为0（未勾选）
    db.update_account_check_status(test_appid, False)
    
    # 验证更新是否成功
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_checked FROM accounts WHERE appid = ?", (test_appid,))
    result = cursor.fetchone()
    conn.close()
    
    print(f"3. 更新后勾选状态: {result[0]}")
    assert result[0] == 0, "勾选状态应已更新为0"
    
    # 测试5: 再次更新勾选状态为1（勾选）
    db.update_account_check_status(test_appid, True)
    
    # 验证更新是否成功
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_checked FROM accounts WHERE appid = ?", (test_appid,))
    result = cursor.fetchone()
    conn.close()
    
    print(f"4. 再次更新后勾选状态: {result[0]}")
    assert result[0] == 1, "勾选状态应已更新为1"
    
    # 清理测试数据
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE appid = ?", (test_appid,))
    conn.commit()
    conn.close()
    
    print("5. 测试完成，测试数据已清理")
    
if __name__ == "__main__":
    # ... existing code ...
    
    # 测试账号勾选状态
    test_account_check_status() 