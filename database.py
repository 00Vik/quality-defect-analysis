import sqlite3
import os
import pandas as pd

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "mydatabase.db")

def create_connection():
    """创建数据库连接"""
    conn = sqlite3.connect('mydatabase.db')
    return conn

def create_table():
    """创建数据表"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            product TEXT,
            amount TEXT,      -- 存储 Decimal 的字符串表示
            quantity INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    print("数据表创建成功")


def table_exists(table_name):
    """检查表是否存在"""
    conn = create_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name=?
    """, (table_name,))

    result = cur.fetchone()

    conn.close()

    return result is not None
