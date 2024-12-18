import sqlite3
import pandas as pd


def update_uploads_and_files(appid):
    """
    更新指定 appid 的记录：
    - total_uploads 和 current_uploads 加 1
    - total_files 减 1

    参数：
    - appid: 要更新的用户的唯一标识符
    """
    conn = None
    try:
        # 连接到数据库
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()

        # 检查是否存在该 appid
        cursor.execute("SELECT total_uploads, current_uploads, total_files FROM user_data WHERE appid = ?", (appid,))
        record = cursor.fetchone()

        if record is None:
            print(f"记录不存在: appid = {appid}")
            return

        total_uploads, current_uploads, total_files = record

        # 确保 total_files 不会减少到负数
        if total_files <= 0:
            print(f"total_files 已经为 0 或更小: appid = {appid}")
            return

        # 更新数据
        cursor.execute(
            '''
            UPDATE user_data
            SET 
                current_uploads = current_uploads + 1,
                total_files = total_files - 1
            WHERE appid = ?
            ''',
            (appid,)
        )

        # 提交更改
        conn.commit()
        print(f"成功更新: appid = {appid}")

    except sqlite3.Error as e:
        print(f"SQLite 错误: {e}")

    finally:
        # 关闭数据库连接
        if conn:
            conn.close()


def update_existing_fields(df: pd.DataFrame, db_path='data.db', table_name='user_data'):
    """
    更新 SQLite 数据库表，仅更新数据库中存在的字段。

    Args:
        df (pandas.DataFrame): 包含要更新数据的 DataFrame，需包含 'appid' 列作为标识。
        db_path (str): 数据库文件路径，默认为 'data.db'。
        table_name (str): 要更新的表名，默认为 'user_data'。
    """
    if 'appid' not in df.columns:
        raise ValueError("DataFrame 必须包含 'appid' 列用于标识记录！")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 获取数据库表的字段列表
        cursor.execute(f"PRAGMA table_info({table_name})")
        db_columns = [col[1] for col in cursor.fetchall()]

        # 找出 DataFrame 中既存在于数据库又需要更新的字段
        valid_columns = [col for col in df.columns if col in db_columns and col != 'appid']

        if not valid_columns:
            print("DataFrame 中没有需要更新的有效字段！")
            return

        for _, row in df.iterrows():
            appid = row['appid']
            update_fields = {col: row[col] for col in valid_columns}

            # 动态生成 SET 子句
            set_clause = ", ".join(f"{field} = ?" for field in update_fields.keys())
            sql = f"UPDATE {table_name} SET {set_clause} WHERE appid = ?"

            # 执行更新
            cursor.execute(sql, list(update_fields.values()) + [appid])

        conn.commit()  # 提交事务
    except Exception as e:
        conn.rollback()  # 发生错误时回滚
    finally:
        conn.close()  # 关闭数据库连接


def delete_records_by_appids(df: pd.DataFrame, db_path='data.db', table_name='user_data'):
    """
    根据传入的 DataFrame 中的 appid 删除 SQLite 数据库中的记录。

    Args:
        df (pandas.DataFrame): 包含要删除数据的 DataFrame，需包含 'appid' 列。
        db_path (str): 数据库文件路径，默认为 'data.db'。
        table_name (str): 表名，默认为 'user_data'。
    """
    if 'appid' not in df.columns:
        raise ValueError("DataFrame 必须包含 'appid' 列用于标识要删除的记录！")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 获取要删除的所有 appid
        appids = df['appid'].dropna().unique()

        if len(appids) == 0:
            print("DataFrame 中没有需要删除的 appid！")
            return

        # 执行删除操作
        placeholders = ", ".join("?" for _ in appids)
        sql = f"DELETE FROM {table_name} WHERE appid IN ({placeholders})"
        cursor.execute(sql, tuple(appids))

        conn.commit()  # 提交事务
        print(f"成功删除 {len(appids)} 条记录。")
    except Exception as e:
        conn.rollback()  # 发生错误时回滚
        print(f"删除过程中发生错误：{e}")
    finally:
        conn.close()  # 关闭数据库连接
