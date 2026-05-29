import os
# 默认表名（当没有传参时使用）
TABLE_RAW = 'defects_data_raw'
TABLE_CLEAN = 'defects_data_clean'

# 清洗参数
MIN_REPAIR_COST = 0
MAX_REPAIR_COST = 10000

# 日期校验范围
MIN_YEAR = 1900
MAX_YEAR = 2026

# 严重度有序分类
SEVERITY_ORDER = ["Minor", "Moderate", "Critical"]

# 合法分类值
VALID_DEFECT_TYPES = ["Cosmetic", "Functional", "Structural"]
VALID_SEVERITIES = ["Minor", "Moderate", "Critical"]
VALID_LOCATIONS = ["Internal", "Surface", "Component"]
VALID_INSPECTION_METHODS = ["Visual Inspection", "Automated Testing", "Manual Testing"]

# 鱼骨图数值
FISHHEAD = 'Product\nDefect'
FISHBONE_DIM = ['defect_type', 'defect_location', 'severity', 'inspection_method']

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 所有输出路径统一管理
PATHS = {
    'pareto': os.path.join(OUTPUT_DIR, 'pareto.png'),
    'heatmap': os.path.join(OUTPUT_DIR, 'heatmap.png'),
    'control_chart': os.path.join(OUTPUT_DIR, 'control_chart.png'),
    'detection_comparison': os.path.join(OUTPUT_DIR, 'detection_comparison.png'),
    'fishbone_data': os.path.join(OUTPUT_DIR, 'fishbone_data.csv'),
}