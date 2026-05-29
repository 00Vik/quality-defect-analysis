import pytest
import pandas as pd
import sys
from pathlib import Path
from decimal import Decimal

# 添加项目根目录到 sys.path
sys.path.append(str(Path(__file__).parent.parent))

from data_clean import fix_amount, normalize_date, validate_categories
from config import MIN_REPAIR_COST, MAX_REPAIR_COST

def test_fix_amount_valid():
    result, err = fix_amount(123.45, MIN_REPAIR_COST, MAX_REPAIR_COST)
    assert err is None
    assert result == Decimal('123.45')

def test_fix_amount_negative():
    result, err = fix_amount(-10, MIN_REPAIR_COST, MAX_REPAIR_COST)
    assert err == "金额异常"
    assert result is None

def test_fix_amount_overflow():
    result, err = fix_amount(1_500_000, MIN_REPAIR_COST, MAX_REPAIR_COST)
    assert err == "金额异常"
    assert result is None

def test_fix_amount_non_numeric():
    result, err = fix_amount("abc", MIN_REPAIR_COST, MAX_REPAIR_COST)
    assert err == "金额格式错误"
    assert result is None

def test_normalize_date_valid():
    result, err = normalize_date("2024-06-15")
    assert err is None
    assert result == "2024-06-15"

def test_normalize_date_slash():
    result, err = normalize_date("2024/06/15")
    assert err is None
    assert result == "2024-06-15"

def test_normalize_date_ddmmyyyy():
    result, err = normalize_date("15/06/2024")
    assert err is None
    assert result == "2024-06-15"

def test_normalize_date_invalid():
    result, err = normalize_date("2024-13-01")
    assert err == "日期格式错误"
    assert result is None

def test_validate_categories():
    df = pd.DataFrame({
        'row_id': [1, 2],   # 两行
        'severity': ['Minor', 'Invalid']
    })
    dirty_records = []
    category_rules = {'severity': ['Minor', 'Moderate', 'Critical']}
    df = validate_categories(df, category_rules, dirty_records)
    # 非法值应被置为 None
    assert pd.isna(df.loc[1, 'severity'])
    assert len(dirty_records) == 1
    assert dirty_records[0]['reason'] == "分类值不合法"