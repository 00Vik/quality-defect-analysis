import pandas as pd
import numpy as np
import sqlite3
import chardet
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from rapidfuzz import process, fuzz
from functools import lru_cache
from config import MAX_REPAIR_COST, MAX_YEAR, MIN_REPAIR_COST, MIN_YEAR, SEVERITY_ORDER, TABLE_CLEAN, TABLE_RAW, VALID_DEFECT_TYPES, VALID_INSPECTION_METHODS, VALID_LOCATIONS, VALID_SEVERITIES
from database import create_connection


# -----------------------------------------------------------------------------------------
#  清洗函数模块
# -----------------------------------------------------------------------------------------

# -------------------------id标准化-----------------------------------
def normalize_id(id_val): 
    """ID标准化，确保非空，统一小写"""
    if pd.isna(id_val):
        return None,"ID缺失"
    # 统一小写并去除前后空格   
    id_val = str(id_val).strip().lower()
    if id_val == "" or id_val in ["nan", "null", "none"]:
        return None,"ID缺失"
    return id_val,None 

# -------------------------字符串异常处理-----------------------------------    
#预编译常见字符串标准值列表，提升性能
standard_list = ["Minor", "Moderate", "Critical", "Cosmetic", "Functional", "Structural","Internal", "Surface", "Component"]
lower_to_original = {s.lower(): s for s in standard_list}
scorer = fuzz.ratio
@lru_cache(maxsize=1000)  # 缓存结果
def correct_cached(word):
    if not isinstance(word, str):
        return word
    word_lower = word.lower()
    if word_lower in lower_to_original:
        return lower_to_original[word_lower]
    result = process.extractOne(word_lower, lower_to_original.keys(), scorer=scorer)
    return lower_to_original[result[0]] if result and result[1] > 80 else word

def fix_string(str_val):
    """处理缺失值"""
    if pd.isna(str_val) or not isinstance(str_val, str):
        return None,"字符串缺失或格式错误"
    str_val= str_val.replace('\ufeff', '').replace('\xa0', ' ').strip()
    return str_val, None
# -------------------------数值异常处理-----------------------------------
def fix_amount(amount_val,min_value=None,max_value=None):
    """金额异常处理"""
    if pd.isna(amount_val):
        return None,"金额缺失"
    try:
        amount = Decimal(str(amount_val))
        # 异常：≤0 或 >100万
        if amount < min_value or amount > max_value:
            return None,"金额异常"
        return (amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),None)
    except (ValueError, TypeError, InvalidOperation) as e:
        return None,"金额格式错误"

# ------------------------日期统一标准化----------------------------
def normalize_date(date_val):
    """统一输出 YYYY-MM-DD"""
    if pd.isna(date_val):
        return None,"日期缺失"
    date_str=str(date_val).strip()
    try:
        # 支持常见格式
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y%m%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                # 合理性检查：日、月、年份范围
                if dt.year < MIN_YEAR or dt.year > MAX_YEAR:
                    return None,"年份异常"
                return dt.strftime("%Y-%m-%d"),None
            except ValueError as e:
                error_msg = str(e)
                if "month" in error_msg.lower() or "day" in error_msg.lower():
                    return None,"日期格式错误"
                continue
    except Exception as e:        
        pass
    # 自动推断
    try:        
        dt = pd.to_datetime(date_val)
        if dt.year < 1900 or dt.year > datetime.now().year:
                    return None,"年份异常"
        return dt.strftime("%Y-%m-%d"),None
    except Exception as e:
        return None,"日期格式错误"

# -------------------------类型标准化-------------------------
def standardize_types(df,validate_cols=None,validate_types=None):
    """类型标准化，指定列转换为指定类型"""
    if validate_cols is None:
        return df
    for col in validate_cols:
        if col in df.columns:
            df[col] = df[col].astype(validate_types)
    return df

# -----------------标记重复,使用date进行标记-----------------------
def duplicated_mask(df, subset=None):
    """去重，返回去重后的df和被删除的行列表"""
    if subset is None:
        # 完全重复
        duplicated_mask = df.duplicated(keep='first')
        return duplicated_mask
    else:
        # 部分重复
        duplicated_mask = df.duplicated(subset=subset, keep=False)
        return duplicated_mask

# -------------------------有序分类函数-------------------------
def ordered_categorical(df, col_name, order_list):
    """将指定列转换为有序分类类型"""
    if col_name in df.columns:
        cat_type = pd.CategoricalDtype(categories=order_list, ordered=True)
        df[col_name] = df[col_name].astype(cat_type)
    return df

# -------------------------标签对齐函数-------------------------
def validate_categories(df, col_rules, dirty_records):
    """
    验证分类列取值是否合法，不合法的置 None 并记录脏数据
    col_rules: {列名: [合法值列表], ...}
    """
    for col, valid_set in col_rules.items():
        if col not in df.columns:
            continue
        #统一字符串
        df[col] = df[col].astype(str).str.strip()

        invalid_mask = (
            df[col].notna()&
            ~df[col].isin(valid_set))
        
        invalid_rows = df[invalid_mask]
        for _, row in invalid_rows.iterrows():
            dirty_records.append({
                "row_id": row["row_id"],
                "row": row.to_dict(),
                "reason": "分类值不合法",
            })
        df.loc[invalid_mask, col] = None

    return df

# -------------------------defect_type和repair_cost的关联检查-------------------------
def check_defect_cost(df, dirty_records, percentile=95):
    """
    检查各缺陷类型的修复成本是否存在异常高值
    超出该类型95%分位数 → 标记为可疑，不删除
    """
    for defect_type in df['defect_type'].dropna().unique():
        type_mask = df['defect_type'] == defect_type
        threshold = df.loc[type_mask, 'repair_cost'].quantile(percentile / 100)
        
        outliers = df[type_mask & (df['repair_cost'] > threshold)]
        for _, row in outliers.iterrows():
            dirty_records.append({
                "row_id": row.get("row_id"),
                "row": row.to_dict(),
                "reason": f"{defect_type} 修复成本异常高: {row['repair_cost']} (阈值={threshold:.2f})"
            })
    return df  

# -------------------------severity和repair_cost的关联检查-------------------------
def check_severity_cost(df, dirty_records):
    """
    严重度与修复成本一致性检查：
    较轻等级的成本不应高于较严重等级的80%分位数成本
    较严重等级的成本不应低于较轻等级的20%分位数成本
    """
    valid = df[df['repair_cost'].notna() & (df['repair_cost'] > 0)]
    if valid.empty:
        return df

    # 各严重度的80%分位数和20%分位数
    lighter_q20 = valid.groupby('severity', observed=True)['repair_cost'].quantile(0.20)
    heavier_q80 = valid.groupby('severity', observed=True)['repair_cost'].quantile(0.80)

    # Minor vs Moderate
    if 'Minor' in heavier_q80.index and 'Moderate' in lighter_q20.index:
        threshold = lighter_q20['Moderate']
        suspicious = valid[
            (valid['severity'] == 'Minor') & 
            (valid['repair_cost'] > threshold)
        ]
        for _, row in suspicious.iterrows():
            dirty_records.append({
                "row_id": row['row_id'],
                "row": row.to_dict(),
                "reason": f"Minor 修复成本 {row['repair_cost']} > Moderate 最低成本 {threshold}"
            })
        threshold = heavier_q80['Minor']    
        suspicious = valid[
            (valid['severity'] == 'Moderate') & 
            (valid['repair_cost'] < threshold)
        ]
        for _, row in suspicious.iterrows():
            dirty_records.append({
                "row_id": row['row_id'],
                "row": row.to_dict(),
                "reason": f"Moderate 修复成本 {row['repair_cost']} < Minor 最高成本 {threshold}"
            })

    # Moderate vs Critical
    if 'Moderate' in heavier_q80.index and 'Critical' in lighter_q20.index:
        threshold = lighter_q20['Critical']
        suspicious = valid[
            (valid['severity'] == 'Moderate') & 
            (valid['repair_cost'] > threshold)
        ]
        for _, row in suspicious.iterrows():
            dirty_records.append({
                "row_id": row['row_id'],
                "row": row.to_dict(),
                "reason": f"Moderate 修复成本 {row['repair_cost']} > Critical 最低成本 {threshold}"
            })
        threshold = heavier_q80['Moderate']    
        suspicious = valid[
            (valid['severity'] == 'Critical') & 
            (valid['repair_cost'] < threshold)
        ]
        for _, row in suspicious.iterrows():
            dirty_records.append({
                "row_id": row['row_id'],
                "row": row.to_dict(),
                "reason": f"Critical 修复成本 {row['repair_cost']} < Moderate 最高成本 {threshold}"
            })

                     
# -----------------------------------------------------------------------------------------
#  数据库交互函数
# -----------------------------------------------------------------------------------------

# ----------------存储和加载函数---------------------
def save_to_database(df, table_name, if_exists='append'):
    """将DataFrame保存到数据库"""
    conn = create_connection()
    df.to_sql(table_name, conn, if_exists=if_exists, index=False)
    conn.close()
    print(f"数据已保存到数据库表: {table_name}")

def load_from_database(table_name):
    """从数据库加载数据"""
    conn = create_connection()
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    severity_cat = pd.CategoricalDtype(categories=SEVERITY_ORDER, ordered=True)
    defect_type_cat = pd.CategoricalDtype(categories=VALID_DEFECT_TYPES, ordered=True)
    location_cat = pd.CategoricalDtype(categories=VALID_LOCATIONS, ordered=True)
    inspection_method_cat = pd.CategoricalDtype(categories=VALID_INSPECTION_METHODS, ordered=True)
    df['severity'] = df['severity'].astype(severity_cat)
    df['defect_type'] = df['defect_type'].astype(defect_type_cat)
    df['defect_location'] = df['defect_location'].astype(location_cat)
    df['inspection_method'] = df['inspection_method'].astype(inspection_method_cat)
    return df

# -------------------------结构损坏行记录-------------------------
bad_lines_count = 0
def handle_bad_line(bad_line):
    global bad_lines_count
    bad_lines_count += 1
    return None 


# -----------------------------------------------------------------------------------------
#  主处理函数
# -----------------------------------------------------------------------------------------

def process_data(csv_file_path=None, source_table=None, target_table=None):
    """
    处理数据
    csv_file_path: 从CSV导入时用
    source_table: 从数据库读取时指定源表
    target_table: 清洗结果存入的目标表
    """
    # 宽松读取CSV，自动检测编码，跳过坏行
    global bad_lines_count
    bad_lines_count = 0

    if csv_file_path:
        # 检测文件编码
        with open(csv_file_path, 'rb') as f:
            result = chardet.detect(f.read(10000))
            detected_encoding = result['encoding'] or 'gb18030'

        raw_df = pd.read_csv(
            csv_file_path,
            encoding=detected_encoding,
            engine='python',
            sep=',',
            on_bad_lines=handle_bad_line,
            encoding_errors='replace',
            dtype=str
            )
    
        # 删除完全空白列
        raw_df = raw_df.dropna(axis=1, how='all')
        # 删除unnamed列
        raw_df = raw_df.loc[:, ~raw_df.columns.str.contains('^Unnamed')]

        # 结构检查和日志
        print(raw_df.shape)
        print(raw_df.head())
        print(raw_df.columns)
        print(raw_df.isnull().sum())

        raw_df.insert(0, 'row_id', range(1, len(raw_df) + 1))
        # 自动生成表名：csv文件名去掉后缀
        base_name = csv_file_path.split('/')[-1].replace('.csv', '')
        source_table = source_table or f"{base_name}_raw"
        target_table = target_table or f"{base_name}_clean"
        save_to_database(raw_df, source_table, if_exists='replace')
    else:
        source_table = source_table or TABLE_RAW
        target_table = target_table or TABLE_CLEAN
        raw_df = load_from_database(source_table)

    clean_df, dirty_records, dirty_data = clean_dataframe(raw_df)
    print(f"结构损坏行数: {bad_lines_count}")
    save_to_database(clean_df, target_table, if_exists='replace')
    
    if not clean_df.empty:
        clean_df.to_csv(f'{base_name}_clean.csv', index=False, encoding='utf-8-sig')

    if not dirty_data.empty:
        dirty_data.to_csv(f'{base_name}_dirty.csv', index=False, encoding='utf-8-sig')
        
    return raw_df, clean_df, dirty_records, dirty_data


# -----------------------------------------------------------------------------------------
#  主清洗函数
# -----------------------------------------------------------------------------------------

def clean_dataframe(raw_df, dirty_records=None):
    """清洗DataFrame数据"""

    #  创建副本，避免修改原始数据

    raw_df = raw_df.copy()

    #  记录异常行的行号和原因
    dirty_records = dirty_records if dirty_records is not None else []

    #  日志打印原始记录数
    original_count = len(raw_df)
    print("开始清洗数据...")

    #  定义逐行处理函数
    def process_row(row):
        errors = []

        #字符串
        str_columns = ["defect_type", "severity", "defect_location","inspection_method"]    
        for col in str_columns:
            corrected_str = correct_cached(row[col])
            new_str, str_err = fix_string(corrected_str)
            if str_err:
                errors.append(f"{col} - {str_err}")
                row[col] = None
            else:
                row[col] = new_str

        # 金额
        new_amount, amt_err = fix_amount(row["repair_cost"], MIN_REPAIR_COST, MAX_REPAIR_COST)
        if amt_err:
            errors.append(amt_err)
            row["repair_cost"] = None
        else:
            row["repair_cost"] = new_amount

        # 日期
        new_date, date_err = normalize_date(row["defect_date"])
        if date_err:
            errors.append(date_err)
            row["defect_date"] = None
        else:
            row["defect_date"] = new_date

        if errors:
            dirty_records.append({
                "row_id": row["row_id"],
                "row": row.to_dict(),
                "reason": "; ".join(errors)
            })
            return None
        return row
    # 逐行处理（axis=1）
    clean_rows = []
    for _, row in raw_df.iterrows():
        new_row = process_row(row)
        if new_row is not None:
            clean_rows.append(new_row)
    clean_df = pd.DataFrame(clean_rows)
    clean_df = pd.DataFrame(clean_rows) if clean_rows else pd.DataFrame(columns=raw_df.columns)
    
    for col in clean_df.columns:
        bad_rows =clean_df[col].apply(lambda x: isinstance(x,set))
        if bad_rows.any():
            print(f"find set col in {col}")
            print(clean_df.loc[bad_rows, [col]])
    # 去重
    # 获取完全重复和部分重复的行
    comp_dup_mask = duplicated_mask(clean_df)
    part_dup_mask = duplicated_mask(clean_df, subset=["product_id", "defect_id", "defect_type"])
    comp_dup_rows = clean_df[comp_dup_mask]
    part_dup_rows = clean_df[part_dup_mask&~comp_dup_mask]
    if not comp_dup_rows.empty:
    # 直接构造字典列表，减少中间DataFrame的创建和迭代开销
       rows = comp_dup_rows.to_dict('records')
    # 直接构造并扩展，没有中间 DataFrame
       dirty_records.extend(
           {"row_id":row["row_id"], "row": row, "reason": "完全重复记录"}
           for row in rows)
    if not part_dup_rows.empty:
        rows = part_dup_rows.to_dict('records')
        dirty_records.extend(
            {"row_id":row["row_id"], "row": row, "reason": "部分重复记录"}
            for row in rows)
    clean_df = clean_df[~comp_dup_mask & ~part_dup_mask].copy() 

    #  金额类型标准化
    clean_df = standardize_types(clean_df, validate_cols=["repair_cost"], validate_types="float")
    
    # 对齐验证（在有序分类前，把非法值清掉）
    category_rules = {"severity": VALID_SEVERITIES, "defect_type": VALID_DEFECT_TYPES, "defect_location": VALID_LOCATIONS, "inspection_method": VALID_INSPECTION_METHODS}
    clean_df = validate_categories(clean_df, category_rules, dirty_records)

        #  删除异常未修复的行
    clean_df = clean_df.dropna()
    #  有序分类,类型为category
    clean_df = ordered_categorical(clean_df, "severity", SEVERITY_ORDER)
    clean_df = ordered_categorical(clean_df, "defect_type", VALID_DEFECT_TYPES)
    clean_df = ordered_categorical(clean_df, "defect_location", VALID_LOCATIONS)
    clean_df = ordered_categorical(clean_df, "inspection_method", VALID_INSPECTION_METHODS)

    #修复成本和缺陷类型关联的分位数检查
    check_defect_cost(clean_df, dirty_records, percentile=95)
    #严重度和修复成本的一致性检查
    check_severity_cost(clean_df, dirty_records)
    
    # 构造脏数据DataFrame
    dirty_data = pd.DataFrame(dirty_records) if dirty_records else pd.DataFrame()

    #  日志打印清洗结果
    cleaned_count = len(clean_df)
    print(f"清洗完成: 原始记录数={original_count}, 清洗后记录数={cleaned_count}, 删除了 {original_count - cleaned_count} 条记录")

    return clean_df, dirty_records, dirty_data
