# -*- coding: utf-8 -*-
"""
纳米硒毒性预测 - 自动特征选择（穷举31种非空组合）
对应论文“组合特征分析”部分，以及专利权利要求6。
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error
from itertools import combinations
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
SEED = 42
np.random.seed(SEED)

# ============================================
# 1. 读取数据（自动查找文件）
# ============================================
possible_paths = [
    Path(r"E:\Python\pythonProject1\纳米硒毒性预测验证集数据 _修正.xlsx"),
    Path(r"E:\Python\pythonProject1\纳米硒毒性预测验证集数据_修正.xlsx"),
    Path(r".\纳米硒毒性预测验证集数据 _修正.xlsx"),
    Path(r".\纳米硒毒性预测验证集数据_修正.xlsx"),
]

DATA_FILE = None
for p in possible_paths:
    if p.exists():
        DATA_FILE = p
        break

if DATA_FILE is None:
    user_input = input("未找到默认文件，请手动输入路径: ").strip()
    DATA_FILE = Path(user_input)
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"文件不存在: {DATA_FILE}")

print(f"使用文件: {DATA_FILE}")
df_raw = pd.read_excel(DATA_FILE, sheet_name="工作表1")
print(f"原始数据形状: {df_raw.shape}")

# ============================================
# 2. 列名映射
# ============================================
col_mapping = {
    'Cell_Viability': ['Cell_Viability', 'Cell_Viability (%)', '存活率', 'Viability'],
    'Time_hr': ['Time (hr)', 'Time', '小时', 'h'],
    'Concentration_ugml': ['Concentration (ug/ml)', 'Concentration (μg/ml)', '浓度'],
    'Diameter_nm': ['Diameter (nm)', 'Diameter', '粒径', '核心粒径'],
    'Size_in_Water_nm': ['Size_in_Water (nm)', 'Size in Water', '水合粒径'],
    'Zeta_mV': ['Zeta_in_Water (mV)', 'Zeta', '电位'],
    'IC50_uM': ['IC50 (µM)', 'IC50 (uM)', 'IC50'],
    'Elemental_Se_wt_raw': ['Elemental Composition (wt%)', 'Elemental Composition', '元素组成'],
    'Crystallinity': ['Crystallinity / Fringe Spacing (Å)', 'Crystallinity', '晶型'],
    'Stability_weeks': ['Long-term Stability (weeks)', 'Stability', '稳定性'],
    'Binding_Energy_Se3d': ['Binding Energy Se3d (eV)', 'Binding Energy', '结合能'],
    'Surface_Charge': ['Surface_Charge', 'Surface Charge', '电荷'],
    'Cell_Type': ['Cell_Type', '细胞类型'],
    'Coat_Group': ['Coat/Functional Group', 'Coat', '修饰'],
    'Test_Method': ['Test', '检测方法'],
    'Material': ['Material', '材料'],
    'Unit_Note': ['Unit_Note', '备注']
}

reverse_map = {}
for target, variants in col_mapping.items():
    for var in variants:
        reverse_map[var] = target

rename_dict = {col: reverse_map[col] for col in df_raw.columns if col in reverse_map}
df = df_raw.rename(columns=rename_dict)
print(f"重命名后列名: {list(df.columns)}")

# ============================================
# 3. 浓度转换与基础清洗
# ============================================
if 'Concentration_ugml' in df.columns and 'Concentration_uM' not in df.columns:
    df['Concentration_ugml'] = pd.to_numeric(df['Concentration_ugml'], errors='coerce')
    df['Concentration_uM'] = df['Concentration_ugml'] / 78.96
elif 'Concentration_uM' not in df.columns:
    for col in df.columns:
        if 'concentration' in col.lower() or '浓度' in col:
            df['Concentration_uM'] = pd.to_numeric(df[col], errors='coerce')
            break

required_cols = ['Cell_Viability', 'Time_hr', 'Concentration_uM']
for col in required_cols:
    if col not in df.columns:
        raise ValueError(f"缺少必要列: {col}")

if 'Material' in df.columns:
    df = df[df['Material'].str.contains('Se', na=False)].copy()

# 提取 Se 含量
import re
def extract_se_wt(s):
    if pd.isna(s):
        return np.nan
    match = re.search(r'Se\s+([0-9.]+)%', str(s))
    if match:
        return float(match.group(1))
    return np.nan

if 'Elemental_Se_wt_raw' in df.columns:
    df['Elemental_Se_wt'] = df['Elemental_Se_wt_raw'].apply(extract_se_wt)

# 数值转换
numeric_cols = ['Cell_Viability', 'Time_hr', 'Concentration_uM', 'Diameter_nm',
                'Size_in_Water_nm', 'Zeta_mV', 'IC50_uM', 'Elemental_Se_wt',
                'Stability_weeks', 'Binding_Energy_Se3d']
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

df = df.dropna(subset=['Cell_Viability', 'Time_hr', 'Concentration_uM'])

if 'Test_Method' in df.columns:
    exclude_tests = ['Characterization', 'Western', 'Cellular Uptake', 'DNA', 'LDH']
    df = df[~df['Test_Method'].str.contains('|'.join(exclude_tests), na=False)]

if 'Diameter_nm' in df.columns and 'Size_in_Water_nm' in df.columns:
    df['Size_in_Water_nm'] = df['Size_in_Water_nm'].fillna(df['Diameter_nm'] * 1.5)
if 'Zeta_mV' in df.columns:
    df['Zeta_mV'] = df['Zeta_mV'].fillna(-15)
if 'IC50_uM' in df.columns:
    df['IC50_uM'] = df['IC50_uM'].fillna(df['IC50_uM'].median())
if 'Elemental_Se_wt' in df.columns:
    df['Elemental_Se_wt'] = df['Elemental_Se_wt'].fillna(df['Elemental_Se_wt'].median())
if 'Stability_weeks' in df.columns:
    df['Stability_weeks'] = df['Stability_weeks'].fillna(13)
if 'Binding_Energy_Se3d' in df.columns:
    df['Binding_Energy_Se3d'] = df['Binding_Energy_Se3d'].fillna(55)
if 'Crystallinity' in df.columns:
    df['Crystallinity'] = df['Crystallinity'].fillna('Amorphous')

categorical_cols = ['Surface_Charge', 'Cell_Type', 'Coat_Group', 'Test_Method', 'Crystallinity']
for col in categorical_cols:
    if col in df.columns:
        df[col] = df[col].fillna('Unknown').astype(str)

# 标签编码
le_charge = LabelEncoder()
le_cell = LabelEncoder()
le_coat = LabelEncoder()
le_test = LabelEncoder()
le_crystal = LabelEncoder()

df['Charge_Code'] = le_charge.fit_transform(df['Surface_Charge']) if 'Surface_Charge' in df.columns else 0
df['Cell_Code'] = le_cell.fit_transform(df['Cell_Type']) if 'Cell_Type' in df.columns else 0
df['Coat_Code'] = le_coat.fit_transform(df['Coat_Group']) if 'Coat_Group' in df.columns else 0
df['Test_Code'] = le_test.fit_transform(df['Test_Method']) if 'Test_Method' in df.columns else 0
df['Crystal_Code'] = le_crystal.fit_transform(df['Crystallinity']) if 'Crystallinity' in df.columns else 0

# 特征工程
df['Log_Concentration'] = np.log1p(df['Concentration_uM'])
if 'Diameter_nm' in df.columns and 'Size_in_Water_nm' in df.columns:
    df['Size_Ratio'] = df['Size_in_Water_nm'] / df['Diameter_nm'].replace(0, np.nan)
    df['Size_Ratio'] = df['Size_Ratio'].fillna(1.5)
else:
    df['Size_Ratio'] = 1.5
df['Time_Log'] = np.log1p(df['Time_hr'])

df_val = df.dropna(subset=['Cell_Viability', 'Time_hr', 'Concentration_uM'])
print(f"验证集有效样本数: {len(df_val)}")

# ============================================
# 4. 穷举31种特征组合
# ============================================
print("\n" + "=" * 70)
print("自动特征选择 (穷举所有候选特征组合)")
print("=" * 70)

candidate_features = ['IC50_uM', 'Elemental_Se_wt', 'Stability_weeks', 'Binding_Energy_Se3d', 'Crystal_Code']
base_numeric = ['Log_Concentration', 'Time_Log', 'Diameter_nm', 'Zeta_mV', 'Size_Ratio']
base_cat = ['Charge_Code', 'Cell_Code', 'Coat_Code', 'Test_Code']

def cv_mae_for_subset(df, selected):
    numeric_cols = base_numeric.copy()
    cat_cols = base_cat.copy()
    for f in selected:
        if f in ['IC50_uM', 'Elemental_Se_wt', 'Stability_weeks', 'Binding_Energy_Se3d']:
            numeric_cols.append(f)
        elif f == 'Crystal_Code':
            cat_cols.append(f)
    numeric_cols = [c for c in numeric_cols if c in df.columns]
    cat_cols = [c for c in cat_cols if c in df.columns]
    if not numeric_cols or not cat_cols:
        return np.nan, np.nan

    X_num = df[numeric_cols].values
    var = np.var(X_num, axis=0)
    keep = var > 1e-10
    if np.sum(keep) < X_num.shape[1]:
        X_num = X_num[:, keep]
    X_cat = df[cat_cols].values
    scaler = StandardScaler()
    X_num_scaled = scaler.fit_transform(X_num)
    X = np.hstack([X_num_scaled, X_cat])
    y = df['Cell_Viability'].values

    kf = KFold(n_splits=3, shuffle=True, random_state=SEED)
    mae_list = []
    for train_idx, val_idx in kf.split(X):
        rf = RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_split=5, random_state=SEED)
        rf.fit(X[train_idx], y[train_idx])
        pred = rf.predict(X[val_idx])
        mae_list.append(mean_absolute_error(y[val_idx], pred))
    return np.mean(mae_list), np.std(mae_list)

best_mae = float('inf')
best_combo = None
all_results = []

print("\n穷举所有特征组合 (共31种)...")
for r in range(1, len(candidate_features) + 1):
    for combo in combinations(candidate_features, r):
        mae_mean, mae_std = cv_mae_for_subset(df_val, list(combo))
        if np.isnan(mae_mean):
            continue
        all_results.append((combo, mae_mean, mae_std))
        if mae_mean < best_mae:
            best_mae = mae_mean
            best_combo = combo

all_results.sort(key=lambda x: x[1])
print("\n最佳特征组合 (按3折CV MAE升序):")
print(f"第1名: {list(best_combo)} -> MAE = {best_mae:.2f}%")
for i in range(1, min(5, len(all_results))):
    combo, mae, _ = all_results[i]
    print(f"第{i+1}名: {list(combo)} -> MAE = {mae:.2f}%")

auto_best_features = list(best_combo) if best_combo is not None else []
print(f"\n自动选择的最优特征组合: {auto_best_features}")

# ============================================
# 5. 用最优组合训练最终模型并输出结果
# ============================================
if auto_best_features:
    numeric_cols = base_numeric.copy()
    cat_cols = base_cat.copy()
    for f in auto_best_features:
        if f in ['IC50_uM', 'Elemental_Se_wt', 'Stability_weeks', 'Binding_Energy_Se3d']:
            numeric_cols.append(f)
        elif f == 'Crystal_Code':
            cat_cols.append(f)
    numeric_cols = [c for c in numeric_cols if c in df_val.columns]
    cat_cols = [c for c in cat_cols if c in df_val.columns]

    X_num = df_val[numeric_cols].values
    var = np.var(X_num, axis=0)
    keep = var > 1e-10
    if np.sum(keep) < X_num.shape[1]:
        X_num = X_num[:, keep]
    X_cat = df_val[cat_cols].values
    scaler = StandardScaler()
    X_num_scaled = scaler.fit_transform(X_num)
    X = np.hstack([X_num_scaled, X_cat])
    y = df_val['Cell_Viability'].values

    kf = KFold(n_splits=3, shuffle=True, random_state=SEED)
    maes = []
    for train_idx, val_idx in kf.split(X):
        rf = RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_split=5, random_state=SEED)
        rf.fit(X[train_idx], y[train_idx])
        pred = rf.predict(X[val_idx])
        maes.append(mean_absolute_error(y[val_idx], pred))
    avg_mae = np.mean(maes)
    rf_full = RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_split=5, random_state=SEED)
    rf_full.fit(X, y)
    from sklearn.metrics import r2_score
    r2 = r2_score(y, rf_full.predict(X))
    print(f"\n最优特征组合 3折CV MAE: {avg_mae:.2f}%")
    print(f"全量R²: {r2:.4f}")
else:
    print("\n未找到有效特征组合")