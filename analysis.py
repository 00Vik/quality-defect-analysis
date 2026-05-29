# analysis.py
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
from data_clean import load_from_database
from config import TABLE_CLEAN,SEVERITY_ORDER,FISHBONE_DIM, PATHS
from matplotlib import category

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def load_clean_data(table_name=TABLE_CLEAN):
    """加载清洗后数据，恢复有序分类"""
    df = load_from_database(table_name)
    cat_type = pd.CategoricalDtype(categories=SEVERITY_ORDER, ordered=True)
    if 'severity' in df.columns:
        df['severity'] = df['severity'].astype(cat_type)
    return df

# ========== 1. 帕累托图 ==========
def plot_pareto(df, column='defect_type', title='缺陷类型帕累托图', save_path=PATHS['pareto']):
    counts = df[column].value_counts().sort_values(ascending=False)
    cum_pct = counts.cumsum() / counts.sum() * 100
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    bars=ax1.bar(counts.index, counts.values, color='steelblue', alpha=0.8)
    ax1.set_ylabel('缺陷数量', fontsize=12)
    ax1.set_xlabel(column.replace('_', ' ').title(), fontsize=12)
    ax1.tick_params(axis='x', rotation=0)
    
    total = counts.sum()
    for bar, count in zip(bars, counts.values):
        height = bar.get_height()
        pct = count / total * 100
        ax1.text(bar.get_x() + bar.get_width()/2, height,
                 f'{count}\n({pct:.1f}%)',
                 ha='center', va='bottom', fontsize=8)
        
    ax2 = ax1.twinx()
    ax2.plot(counts.index, cum_pct.values, 'r-o', linewidth=2, markersize=6)
    ax2.set_ylabel('累积百分比 (%)', fontsize=12, color='red')
    ax2.axhline(y=80, color='gray', linestyle='--', alpha=0.7, label='80% 线')
    ax2.legend(loc='lower right')
    
    plt.title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    return counts, cum_pct

# ========== 2. 热力图（严重度 × 缺陷类型 交叉） ==========
def plot_heatmap(df, save_path=PATHS['heatmap']):
    cross = pd.crosstab(df['severity'], df['defect_type'], normalize='all') * 100
    
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cross, annot=True, fmt='.1f', cmap='YlOrRd', 
                cbar_kws={'label': '占比 (%)'}, ax=ax,
                linewidths=0.5, linecolor='white')
    ax.set_title('严重度 × 缺陷类型 热力图 (%)', fontsize=14, fontweight='bold')
    ax.set_ylabel('严重度', fontsize=12)
    ax.set_xlabel('缺陷类型', fontsize=12)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    return cross

# ========== 3. 控制图（按周缺陷数） ==========
def plot_control_chart(df, date_col='defect_date', save_path=PATHS['control_chart']):
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df['week'] = df[date_col].dt.isocalendar().week.astype(int)
    df['year'] = df[date_col].dt.isocalendar().year.astype(int)
    df['year_week'] = df['year'].astype(str) + '-W' + df['week'].astype(str).str.zfill(2)
    
    weekly = df.groupby('year_week').size().reset_index(name='count')
    weekly = weekly.sort_values('year_week')
    
    mean = weekly['count'].mean()
    std = weekly['count'].std()
    ucl = mean + 3 * std
    lcl = max(0, mean - 3 * std)
    
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(range(len(weekly)), weekly['count'].values, 'b-o', markersize=5, linewidth=1.5)
    ax.axhline(y=mean, color='green', linestyle='-', linewidth=1.5, label=f'均值 = {mean:.1f}')
    ax.axhline(y=ucl, color='red', linestyle='--', linewidth=1.5, label=f'UCL = {ucl:.1f}')
    ax.axhline(y=lcl, color='red', linestyle='--', linewidth=1.5, label=f'LCL = {lcl:.1f}')
    
    # 标出超出控制线的点
    outliers = weekly[(weekly['count'] > ucl) | (weekly['count'] < lcl)]
    for idx in outliers.index:
        ax.annotate(weekly.loc[idx, 'year_week'], 
                    (idx, weekly.loc[idx, 'count']),
                    fontsize=8, color='red', ha='center')
    
    ax.set_xticks(range(0, len(weekly), max(1, len(weekly)//10)))
    ax.set_xticklabels(weekly['year_week'].iloc[::max(1, len(weekly)//10)], rotation=45)
    ax.set_title('周缺陷数控制图 (SPC)', fontsize=14, fontweight='bold')
    ax.set_ylabel('缺陷数量', fontsize=12)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    
    print(f"控制图统计: 均值={mean:.1f}, 标准差={std:.1f}, UCL={ucl:.1f}, LCL={lcl:.1f}")
    return weekly, mean, ucl, lcl

# ========== 4. 检测方法对比图 ==========
def plot_detection_comparison(df, save_path=PATHS['control_chart']):
    cross = pd.crosstab(df['inspection_method'], df['severity'], normalize='index') * 100
    
    fig, ax = plt.subplots(figsize=(10, 6))
    cross.plot(kind='bar', stacked=True, ax=ax,
               color=['#2ecc71', '#f39c12', '#e74c3c'],
               edgecolor='white', linewidth=0.5, width=0.7)
    ax.set_title('不同检测方法的严重度检出分布', fontsize=14, fontweight='bold')
    ax.set_ylabel('占比 (%)', fontsize=12)
    ax.set_xlabel('检测方法', fontsize=12)
    ax.legend(title='严重度', bbox_to_anchor=(1.02, 1), loc='upper left')
    ax.tick_params(axis='x', rotation=0)
    
    # 标注数值
    for c in ax.containers:
        ax.bar_label(c, fmt='%.1f%%', fontsize=8, label_type='center', color='white', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    
    # 打印对比摘要
    print("\n检测方法对比摘要:")
    for method in cross.index:
        critical_pct = cross.loc[method, 'Critical'] if 'Critical' in cross.columns else 0
        print(f"  {method}: Critical检出率 = {critical_pct:.1f}%")
    
    return cross

# ========== 5. 鱼骨图数据汇总==========
def export_fishbone_data(df, save_path=PATHS['fishbone_data']):
    """
    导出鱼骨图各维度的频次汇总，供Excel SmartArt使用
    大刺：defect_type, defect_location, severity, inspection_method
    小刺：各维度下的具体值分布
    """
    dimensions = FISHBONE_DIM
    records = []
    for dim in dimensions:
        if dim in df.columns:
            counts = df[dim].value_counts()
            for value, count in counts.items():
                records.append({
                    '维度': dim.replace('_', ' ').title(),
                    '原因': value,
                    '频次': count,
                    '占比(%)': round(count / len(df) * 100, 1)
                    })

    # 生成鱼骨图数据汇总表
    fishbone_df = pd.DataFrame(records)
    fishbone_df.to_csv(save_path, index=False, encoding='utf-8-sig')
    print(f"鱼骨图数据已导出: {save_path}")

    return fishbone_df

