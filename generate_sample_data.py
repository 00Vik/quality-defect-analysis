import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_sample_data(n=500):
    np.random.seed(42)
    
    defect_types = np.random.choice(
        ["Cosmetic", "Functional", "Structural"], 
        size=n, p=[0.5, 0.3, 0.2]
    )
    
    severities = np.random.choice(
        ["Minor", "Moderate", "Critical"],
        size=n, p=[0.6, 0.3, 0.1]
    )
    
    # 修复成本：严重度越高的平均成本越高
    cost_map = {"Minor": 50, "Moderate": 200, "Critical": 800}
    repair_cost = [
        max(10, np.random.normal(cost_map[s], cost_map[s]*0.3))
        for s in severities
    ]
    
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=np.random.randint(0, 365)) for _ in range(n)]
    
    df = pd.DataFrame({
        "defect_id": [f"D{str(i).zfill(5)}" for i in range(1, n+1)],
        "product_id": np.random.choice(["P001", "P002", "P003"], n),
        "defect_date": dates,
        "defect_type": defect_types,
        "severity": severities,
        "defect_location": np.random.choice(["Internal", "Surface", "Component"], n),
        "inspection_method": np.random.choice(
            ["Visual Inspection", "Automated Testing", "Manual Testing"], n
        ),
        "repair_cost": repair_cost
    })
    
    df.to_csv("sample_data.csv", index=False, encoding="utf-8-sig")
    print(f"已生成 {n} 条模拟数据 -> sample_data.csv")

if __name__ == "__main__":
    generate_sample_data()