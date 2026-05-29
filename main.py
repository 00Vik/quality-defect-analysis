import pandas as pd
import numpy as np
from typing import Optional
from fastapi import FastAPI, HTTPException
from database import create_connection, table_exists
from data_clean import process_data, load_from_database
from config import TABLE_RAW, TABLE_CLEAN

app = FastAPI(title="质量缺陷数据分析API", description="使用FastAPI + SQLite + Pandas")

def dataframe_to_json(df):
    df = df.replace([np.inf, -np.inf], None)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")

# -------------------------检查表是否存在-------------------------
def ensure_table(table_name):

    if not table_exists(table_name):
        raise HTTPException(
            status_code=400, 
            detail=f"数据表 {table_name} 不存在，请先执行 /run_clean 接口进行数据清洗")
    return None

# ------------------------- API接口 -------------------------
@app.get("/")
def read_root():
    return {"message": "欢迎使用质量缺陷数据分析API"}


@app.get("/clean_data")
def get_clean_data():
    """获取清洗后的数据"""
    error = ensure_table(TABLE_CLEAN)
    if error:
        return error 
    clean_df = load_from_database(TABLE_CLEAN)
    return clean_df.to_dict(orient='records')


@app.get("/raw_data")
def get_raw_data():
    """获取原始数据"""
    error = ensure_table(TABLE_RAW)
    if error:
        return error
    raw_df = load_from_database(TABLE_RAW)
    raw_df = dataframe_to_json(raw_df)
    return raw_df.to_dict(orient='records')


@app.get("/dirty_data")
def get_dirty_data():
    """获取脏数据（从CSV读取）"""
    try:
        dirty_df = pd.read_csv('dirty_data.csv')
        dirty_df = dataframe_to_json(dirty_df)
        return dirty_df.to_dict(orient='records')
    except FileNotFoundError:
        return {"message": "暂无脏数据，请先执行清洗"}


@app.get("/dirty_summary")
def get_dirty_summary():
    """获取脏数据汇总统计"""
    try:
        raw_df = load_from_database(TABLE_RAW)
        raw_df = dataframe_to_json(raw_df)
        clean_df = load_from_database(TABLE_CLEAN)
        
        try:
            dirty_df = pd.read_csv('dirty_data.csv')
            dirty_df = dataframe_to_json(dirty_df)
            dirty_count = len(dirty_df)
        except FileNotFoundError:
            dirty_count = 0
        
        summary = {
            "original_count": len(raw_df),
            "cleaned_count": len(clean_df),
            "dirty_count": dirty_count,
            "removed_count": len(raw_df) - len(clean_df)
        }
        return summary
    except Exception as e:
        return {"error": f"数据尚未清洗，请先调用 /run_clean 接口: {str(e)}"}


@app.get("/stats")
def get_statistics():
    """获取清洗后数据的统计信息"""
    try:
        clean_df = load_from_database(TABLE_CLEAN)
        
        stats = {
            "total_records": len(clean_df),
            "defect_types": clean_df['defect_type'].value_counts().to_dict() if 'defect_type' in clean_df.columns else {},
            "severity_distribution": clean_df['severity'].value_counts().to_dict() if 'severity' in clean_df.columns else {},
            "avg_repair_cost": float(clean_df['repair_cost'].mean()) if 'repair_cost' in clean_df.columns else 0,
            "total_repair_cost": float(clean_df['repair_cost'].sum()) if 'repair_cost' in clean_df.columns else 0
        }
        return stats
    except Exception as e:
        return {"error": f"统计失败: {str(e)}"}


@app.get("/defect/{defect_id}")
def get_defect(defect_id: str):
    """根据缺陷ID查询单条记录"""
    try:
        clean_df = load_from_database(TABLE_CLEAN)
        defect = clean_df[clean_df['defect_id'] == defect_id]
        if defect.empty:
            return {"error": f"缺陷ID {defect_id} 不存在"}
        return defect.iloc[0].to_dict()
    except Exception as e:
        return {"error": str(e)}


@app.post("/run_clean")
def run_clean():
    """触发数据清洗流程"""
    try:
        clean_df, dirty_data, dirty_records = process_data()
        return {
            "message": "数据清洗完成",
            "cleaned_count": len(clean_df),
            "dirty_count": len(dirty_data)
        }
    except Exception as e:
        return {"error": f"清洗失败: {str(e)}"}