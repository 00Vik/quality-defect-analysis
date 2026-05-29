# service.py
import pandas as pd
from data_clean import process_data
from database import create_connection
from db_safe import validate_table_name, q

# -------------------------
# registry 初始化
# -------------------------
def init_registry():
    conn = create_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS table_registry (
            table_name TEXT PRIMARY KEY,
            type TEXT,
            status TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def register_table(name, ttype="raw", status="active"):
    conn = create_connection()
    conn.execute(
        "INSERT OR REPLACE INTO table_registry VALUES (?, ?, ?, datetime('now'))",
        (name, ttype, status)
    )
    conn.commit()
    conn.close()

# -------------------------
# 创建数据集
# -------------------------
def create_dataset(csv_path, raw_table, clean_table):
    if not validate_table_name(raw_table) or not validate_table_name(clean_table):
        raise ValueError("非法表名")

    raw_df, clean_df, dirty_records, dirty_data = process_data(csv_path)
    
    conn = create_connection()

    # raw
    raw_df.to_sql(raw_table, conn, if_exists="replace", index=False)
    register_table(raw_table, "raw")

    # clean
    clean_df.to_sql(clean_table, conn, if_exists="replace", index=False)
    register_table(clean_table, "clean")

    conn.close()

    return len(raw_df), len(clean_df)



# -------------------------
# 删除数据集
# -------------------------
def delete_dataset(table):
    if not validate_table_name(table):
        raise ValueError("非法表名")

    conn = create_connection()
    conn.execute(f'DROP TABLE IF EXISTS {q(table)}')
    conn.execute("DELETE FROM table_registry WHERE table_name=?", (table,))
    conn.commit()
    conn.close()


# -------------------------
# 获取可用表
# -------------------------
def list_tables():
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM table_registry WHERE status='active'")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return tables


# -------------------------
# 加载表数据
# -------------------------
def load_table(table):
    conn = create_connection()
    df = pd.read_sql_query(f"SELECT * FROM {q(table)}", conn)
    conn.close()
    return df


# -------------------------
# 删除所有表
# -------------------------
def drop_all_tables():
    conn = create_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    for t in tables:
        if t.startswith("sqlite_") or t == "table_registry":
            continue
        cur.execute(f'DROP TABLE IF EXISTS "{t}"')
        cur.execute("DELETE FROM table_registry WHERE table_name=?", (t,))
        print("删除:", t)

    conn.commit()
    conn.close()