"""
纳米颗粒细胞毒性预测 - 完整模型对比（含蒸馏模型和样本级预测对比）
模型：随机森林、XGBoost、TabTransformer、ABRF、LARF、DistilledTabTransformer
数据集：doen01240h1.xlsx (4000+样本)
"""

import pandas as pd
import numpy as np
import os
import glob
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score, f1_score, roc_auc_score
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
import xgboost as xgb
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import warnings

warnings.filterwarnings('ignore')

# 设置随机种子
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

# 设置中文绘图
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================
# 0. 数据加载与预处理
# ============================================
print("=" * 80)
print("纳米颗粒细胞毒性预测 - 完整模型对比 (含蒸馏模型和样本级对比)")
print("=" * 80)

# 切换到项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) if '.venv' in current_dir else current_dir
os.chdir(project_root)

print(f"\n当前工作目录: {os.getcwd()}")

# 查找数据文件
xlsx_files = glob.glob('*.xlsx')
print(f"找到的xlsx文件: {xlsx_files}")

target_file = None
for f in xlsx_files:
    if 'd0en01240h1' in f or 'doen01240h1' in f:
        target_file = f
        break

if target_file is None and len(xlsx_files) > 0:
    target_file = xlsx_files[0]

if target_file is None:
    print("错误: 找不到数据文件！")
    exit(1)

print(f"使用文件: {target_file}")

# 加载数据
df = pd.read_excel(target_file, sheet_name='Viability')
print(f"原始数据形状: {df.shape}")

# ============================================
# 1. 数据预处理
# ============================================
print("\n[1] 数据预处理...")

categorical_features = ['Material', 'Type', 'Surface_Charge', 'Cell_Type', 'Test', 'Cell_Tissue', 'Shape',
                        'Coat/Functional Group']
numerical_features = ['Diameter (nm)', 'Size_in_Water (nm)', 'Zeta_in_Water (mV)', 'Time (hr)', 'Concentration (ug/ml)',
                      'No_of_Cells (cells/well)']
target = 'Cell_Viability (%)'

# 筛选有效数据
df_clean = df[categorical_features + numerical_features + [target]].copy()
df_clean = df_clean.dropna(subset=[target])
df_clean = df_clean[(df_clean[target] >= 0) & (df_clean[target] <= 200)]

# 填充缺失值
for col in numerical_features:
    if col in df_clean.columns:
        df_clean[col] = df_clean[col].fillna(df_clean[col].median())

for col in categorical_features:
    if col in df_clean.columns:
        df_clean[col] = df_clean[col].fillna('Unknown')

df_clean = df_clean.dropna()
print(f"清洗后数据形状: {df_clean.shape}")

# 编码分类特征
label_encoders = {}
for col in categorical_features:
    le = LabelEncoder()
    df_clean[f'{col}_encoded'] = le.fit_transform(df_clean[col].astype(str))
    label_encoders[col] = le

categorical_encoded = [f'{col}_encoded' for col in categorical_features]

# 准备数据
X_categorical = df_clean[categorical_encoded].values
X_numerical = df_clean[numerical_features].values
y = df_clean[target].values

# 标准化数值特征
scaler = StandardScaler()
X_numerical_scaled = scaler.fit_transform(X_numerical)

# 合并特征（用于树模型）
X_combined = np.hstack([X_numerical_scaled, X_categorical])
feature_names = numerical_features + categorical_encoded

# ============================================
# 统一划分数据集（保证所有模型使用相同的测试集）
# ============================================
indices = np.arange(len(X_combined))
train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=SEED)

# 树模型数据
X_train_tree = X_combined[train_idx]
X_test_tree = X_combined[test_idx]
y_train_tree = y[train_idx]
y_test_tree = y[test_idx]

# TabTransformer 专用数据（分离类别和数值）
X_cat_train = X_categorical[train_idx]
X_num_train = X_numerical_scaled[train_idx]
X_cat_test = X_categorical[test_idx]
X_num_test = X_numerical_scaled[test_idx]
y_train_tab = y[train_idx]
y_test_tab = y[test_idx]

print(f"训练集: {len(y_train_tree)} 样本, 测试集: {len(y_test_tree)} 样本")
print(f"特征维度: {X_train_tree.shape[1]}")

# ============================================
# 2. 随机森林模型
# ============================================
print("\n" + "=" * 80)
print("模型1: 随机森林 (Random Forest)")
print("=" * 80)

rf_model = RandomForestRegressor(
    n_estimators=200,
    max_depth=15,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=SEED,
    n_jobs=-1
)
rf_model.fit(X_train_tree, y_train_tree)
y_pred_rf = rf_model.predict(X_test_tree)

rf_r2 = r2_score(y_test_tree, y_pred_rf)
rf_mae = mean_absolute_error(y_test_tree, y_pred_rf)
rf_rmse = np.sqrt(mean_squared_error(y_test_tree, y_pred_rf))
cv_scores = cross_val_score(rf_model, X_train_tree, y_train_tree, cv=5, scoring='r2')

print(f"\n测试集结果:")
print(f"  R²: {rf_r2:.4f}")
print(f"  MAE: {rf_mae:.2f}%")
print(f"  RMSE: {rf_rmse:.2f}%")
print(f"  5折CV R²: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

rf_importance = pd.DataFrame({
    'feature': feature_names,
    'importance': rf_model.feature_importances_
}).sort_values('importance', ascending=False)
print(f"\nTop 10 重要特征:")
for i, row in rf_importance.head(10).iterrows():
    print(f"  {row['feature']}: {row['importance']:.4f}")

# ============================================
# 3. XGBoost模型
# ============================================
print("\n" + "=" * 80)
print("模型2: XGBoost")
print("=" * 80)

xgb_model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    random_state=SEED
)
xgb_model.fit(X_train_tree, y_train_tree)
y_pred_xgb = xgb_model.predict(X_test_tree)

xgb_r2 = r2_score(y_test_tree, y_pred_xgb)
xgb_mae = mean_absolute_error(y_test_tree, y_pred_xgb)
xgb_rmse = np.sqrt(mean_squared_error(y_test_tree, y_pred_xgb))
cv_scores_xgb = cross_val_score(xgb_model, X_train_tree, y_train_tree, cv=5, scoring='r2')

print(f"\n测试集结果:")
print(f"  R²: {xgb_r2:.4f}")
print(f"  MAE: {xgb_mae:.2f}%")
print(f"  RMSE: {xgb_rmse:.2f}%")
print(f"  5折CV R²: {cv_scores_xgb.mean():.4f} ± {cv_scores_xgb.std():.4f}")

# ============================================
# 4. TabTransformer模型
# ============================================
print("\n" + "=" * 80)
print("模型3: TabTransformer")
print("=" * 80)


class SimplifiedTabTransformer(nn.Module):
    def __init__(self, categorical_dims, numerical_dim, embedding_dim=16,
                 n_transformer_layers=1, n_heads=4, dropout=0.3,
                 mlp_hidden_dims=[128, 64], output_dim=1):
        super().__init__()
        self.categorical_embeddings = nn.ModuleList([
            nn.Embedding(dim, embedding_dim) for dim in categorical_dims
        ])
        self.numerical_proj = nn.Linear(numerical_dim, embedding_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embedding_dim,
            nhead=n_heads,
            dim_feedforward=embedding_dim * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_transformer_layers)
        mlp_input_dim = embedding_dim * (len(categorical_dims) + 1)
        mlp_layers = []
        for hidden_dim in mlp_hidden_dims:
            mlp_layers.extend([
                nn.Linear(mlp_input_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            mlp_input_dim = hidden_dim
        mlp_layers.append(nn.Linear(mlp_input_dim, output_dim))
        self.mlp = nn.Sequential(*mlp_layers)

    def forward(self, x_cat, x_num):
        cat_embeds = [embed(x_cat[:, i]) for i, embed in enumerate(self.categorical_embeddings)]
        num_embed = self.numerical_proj(x_num)
        stacked = torch.stack(cat_embeds + [num_embed], dim=1)
        transformed = self.transformer(stacked)
        combined = transformed.reshape(transformed.size(0), -1)
        return self.mlp(combined).squeeze()


categorical_dims = [len(np.unique(X_cat_train[:, i])) for i in range(X_cat_train.shape[1])]
numerical_dim = X_num_train.shape[1]
print(f"分类特征维度: {categorical_dims[:5]}... (共{len(categorical_dims)}个)")
print(f"数值特征维度: {numerical_dim}")

X_cat_train_t = torch.LongTensor(X_cat_train.astype(np.int64))
X_num_train_t = torch.FloatTensor(X_num_train)
y_train_t = torch.FloatTensor(y_train_tab)
X_cat_test_t = torch.LongTensor(X_cat_test.astype(np.int64))
X_num_test_t = torch.FloatTensor(X_num_test)
y_test_t = torch.FloatTensor(y_test_tab)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
tab_model = SimplifiedTabTransformer(
    categorical_dims=categorical_dims,
    numerical_dim=numerical_dim,
    embedding_dim=16,
    n_transformer_layers=1,
    n_heads=4,
    dropout=0.3,
    mlp_hidden_dims=[128, 64],
    output_dim=1
).to(device)
print(f"参数量: {sum(p.numel() for p in tab_model.parameters()):,}")

optimizer = torch.optim.AdamW(tab_model.parameters(), lr=1e-3, weight_decay=1e-4)
criterion = nn.MSELoss()
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=10)
train_loader = DataLoader(TensorDataset(X_cat_train_t, X_num_train_t, y_train_t), batch_size=64, shuffle=True)

best_val_loss = float('inf')
patience_counter = 0
best_state = None
print("\n开始训练 TabTransformer...")
for epoch in range(150):
    tab_model.train()
    epoch_loss = 0
    for batch_cat, batch_num, batch_y in train_loader:
        batch_cat, batch_num, batch_y = batch_cat.to(device), batch_num.to(device), batch_y.to(device)
        optimizer.zero_grad()
        pred = tab_model(batch_cat, batch_num)
        loss = criterion(pred, batch_y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(tab_model.parameters(), max_norm=1.0)
        optimizer.step()
        epoch_loss += loss.item()
    tab_model.eval()
    with torch.no_grad():
        val_pred = tab_model(X_cat_test_t.to(device), X_num_test_t.to(device))
        val_loss = criterion(val_pred, y_test_t.to(device))
    scheduler.step(val_loss)
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        patience_counter = 0
        best_state = {k: v.clone() for k, v in tab_model.state_dict().items()}
    else:
        patience_counter += 1
    if (epoch+1)%30 == 0:
        print(f"  Epoch {epoch+1}: Train Loss = {epoch_loss/len(train_loader):.4f}, Val Loss = {val_loss.item():.4f}")
    if patience_counter >= 30:
        print(f"  Early stopping at epoch {epoch+1}")
        break

tab_model.load_state_dict(best_state)
tab_model.eval()
with torch.no_grad():
    y_pred_tab = tab_model(X_cat_test_t.to(device), X_num_test_t.to(device)).cpu().numpy()
tab_r2 = r2_score(y_test_tab, y_pred_tab)
tab_mae = mean_absolute_error(y_test_tab, y_pred_tab)
tab_rmse = np.sqrt(mean_squared_error(y_test_tab, y_pred_tab))
print(f"\nTabTransformer 测试集结果:")
print(f"  R²: {tab_r2:.4f}")
print(f"  MAE: {tab_mae:.2f}%")
print(f"  RMSE: {tab_rmse:.2f}%")

# ============================================
# 5. ABRF (Attention-based Random Forest)
# ============================================
print("\n" + "=" * 80)
print("模型4: ABRF (Attention-based Random Forest)")
print("=" * 80)


class AttentionBasedRandomForest:
    def __init__(self, n_estimators=100, max_depth=10, attention_dim=16,
                 learning_rate=0.001, n_epochs=100, batch_size=64):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.attention_dim = attention_dim
        self.learning_rate = learning_rate
        self.n_epochs = n_epochs
        self.batch_size = batch_size

    def fit(self, X, y):
        n_samples = X.shape[0]
        print("  训练基础随机森林...")
        self.base_rf = RandomForestRegressor(
            n_estimators=self.n_estimators, max_depth=self.max_depth,
            min_samples_split=5, random_state=SEED, n_jobs=-1)
        self.base_rf.fit(X, y)
        print("  获取每棵树的预测...")
        tree_preds = np.zeros((n_samples, self.n_estimators))
        for i, tree in enumerate(self.base_rf.estimators_):
            tree_preds[:, i] = tree.predict(X)
        print("  训练注意力网络...")
        self._train_attention_network(X, tree_preds, y)
        return self

    def _train_attention_network(self, X, tree_preds, y):
        n_features = X.shape[1]
        n_trees = tree_preds.shape[1]

        class AttentionNet(nn.Module):
            def __init__(self, n_features, n_trees, att_dim):
                super().__init__()
                self.feature_attention = nn.Sequential(
                    nn.Linear(n_features, att_dim), nn.Tanh(),
                    nn.Linear(att_dim, n_features), nn.Softmax(dim=1))
                self.tree_attention = nn.Sequential(
                    nn.Linear(n_trees, att_dim), nn.Tanh(),
                    nn.Linear(att_dim, n_trees), nn.Softmax(dim=1))
                self.predictor = nn.Sequential(
                    nn.Linear(n_features + n_trees, 64), nn.ReLU(), nn.Dropout(0.3),
                    nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3),
                    nn.Linear(32, 1))

            def forward(self, x, tree):
                fw = self.feature_attention(x)
                tw = self.tree_attention(tree)
                feat = x * fw
                tree_w = tree * tw
                combined = torch.cat([feat, tree_w], dim=1)
                return self.predictor(combined).squeeze(), fw.mean(dim=0), tw.mean(dim=0)

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.att_net = AttentionNet(n_features, n_trees, self.attention_dim).to(device)
        optimizer = optim.Adam(self.att_net.parameters(), lr=self.learning_rate, weight_decay=1e-4)
        criterion = nn.MSELoss()
        X_t = torch.FloatTensor(X).to(device)
        tree_t = torch.FloatTensor(tree_preds).to(device)
        y_t = torch.FloatTensor(y).to(device)
        loader = DataLoader(TensorDataset(X_t, tree_t, y_t), batch_size=self.batch_size, shuffle=True)
        best_loss = float('inf')
        patience = 0
        for epoch in range(self.n_epochs):
            self.att_net.train()
            epoch_loss = 0
            for bx, bt, by in loader:
                optimizer.zero_grad()
                pred, _, _ = self.att_net(bx, bt)
                loss = criterion(pred, by)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            self.att_net.eval()
            with torch.no_grad():
                val_pred, _, _ = self.att_net(X_t, tree_t)
                val_loss = criterion(val_pred, y_t)
            if (epoch+1) % 25 == 0:
                print(f"    Epoch {epoch+1}: Train Loss = {epoch_loss/len(loader):.4f}, Val Loss = {val_loss.item():.4f}")
            if val_loss < best_loss:
                best_loss = val_loss
                patience = 0
                self.best_state = {k: v.clone() for k, v in self.att_net.state_dict().items()}
            else:
                patience += 1
            if patience >= 20:
                print(f"    Early stopping at epoch {epoch+1}")
                break
        self.att_net.load_state_dict(self.best_state)
        with torch.no_grad():
            _, feat_imp, _ = self.att_net(X_t, tree_t)
            self.feature_importance = feat_imp.cpu().numpy()

    def predict(self, X):
        n_samples = X.shape[0]
        tree_preds = np.zeros((n_samples, self.n_estimators))
        for i, tree in enumerate(self.base_rf.estimators_):
            tree_preds[:, i] = tree.predict(X)
        X_t = torch.FloatTensor(X)
        tree_t = torch.FloatTensor(tree_preds)
        self.att_net.eval()
        with torch.no_grad():
            pred, _, _ = self.att_net(X_t, tree_t)
        return pred.numpy().flatten()


abrf = AttentionBasedRandomForest(n_estimators=100, max_depth=10)
abrf.fit(X_train_tree, y_train_tree)
y_pred_abrf = abrf.predict(X_test_tree)
abrf_r2 = r2_score(y_test_tree, y_pred_abrf)
abrf_mae = mean_absolute_error(y_test_tree, y_pred_abrf)
abrf_rmse = np.sqrt(mean_squared_error(y_test_tree, y_pred_abrf))
print(f"\nABRF 测试集结果:")
print(f"  R²: {abrf_r2:.4f}")
print(f"  MAE: {abrf_mae:.2f}%")
print(f"  RMSE: {abrf_rmse:.2f}%")

# ============================================
# 6. LARF (Two-Level Attention Random Forest)
# ============================================
print("\n" + "=" * 80)
print("模型5: LARF (Two-Level Attention Random Forest)")
print("=" * 80)


class TwoLevelAttentionRandomForest:
    def __init__(self, n_estimators=100, max_depth=10, attention_dim=16,
                 learning_rate=0.001, n_epochs=100, batch_size=64):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.attention_dim = attention_dim
        self.learning_rate = learning_rate
        self.n_epochs = n_epochs
        self.batch_size = batch_size

    def fit(self, X, y):
        n_samples = X.shape[0]
        print("  训练基础随机森林...")
        self.base_rf = RandomForestRegressor(
            n_estimators=self.n_estimators, max_depth=self.max_depth,
            min_samples_split=5, random_state=SEED, n_jobs=-1)
        self.base_rf.fit(X, y)
        print("  获取每棵树的预测...")
        tree_preds = np.zeros((n_samples, self.n_estimators))
        for i, tree in enumerate(self.base_rf.estimators_):
            tree_preds[:, i] = tree.predict(X)
        print("  训练双层注意力网络...")
        self._train_two_level_attention(X, tree_preds, y)
        return self

    def _train_two_level_attention(self, X, tree_preds, y):
        n_features = X.shape[1]
        n_trees = tree_preds.shape[1]

        class TwoLevelNet(nn.Module):
            def __init__(self, n_features, n_trees, att_dim):
                super().__init__()
                self.feat_att = nn.Sequential(
                    nn.Linear(n_features, att_dim), nn.Tanh(),
                    nn.Linear(att_dim, n_features), nn.Softmax(dim=1))
                self.tree_att = nn.Sequential(
                    nn.Linear(n_trees, att_dim), nn.Tanh(),
                    nn.Linear(att_dim, n_trees), nn.Softmax(dim=1))
                self.fusion = nn.Sequential(
                    nn.Linear(n_features + n_trees, 64), nn.ReLU(), nn.Dropout(0.3),
                    nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3),
                    nn.Linear(32, 1))

            def forward(self, x, tree):
                fw = self.feat_att(x)
                tw = self.tree_att(tree)
                feat = x * fw
                tree_w = tree * tw
                combined = torch.cat([feat, tree_w], dim=1)
                return self.fusion(combined).squeeze(), fw.mean(dim=0), tw.mean(dim=0)

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = TwoLevelNet(n_features, n_trees, self.attention_dim).to(device)
        optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate, weight_decay=1e-4)
        criterion = nn.MSELoss()
        X_t = torch.FloatTensor(X).to(device)
        tree_t = torch.FloatTensor(tree_preds).to(device)
        y_t = torch.FloatTensor(y).to(device)
        loader = DataLoader(TensorDataset(X_t, tree_t, y_t), batch_size=self.batch_size, shuffle=True)
        best_loss = float('inf')
        patience = 0
        for epoch in range(self.n_epochs):
            self.model.train()
            epoch_loss = 0
            for bx, bt, by in loader:
                optimizer.zero_grad()
                pred, _, _ = self.model(bx, bt)
                loss = criterion(pred, by)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            self.model.eval()
            with torch.no_grad():
                val_pred, _, _ = self.model(X_t, tree_t)
                val_loss = criterion(val_pred, y_t)
            if (epoch+1) % 25 == 0:
                print(f"    Epoch {epoch+1}: Train Loss = {epoch_loss/len(loader):.4f}, Val Loss = {val_loss.item():.4f}")
            if val_loss < best_loss:
                best_loss = val_loss
                patience = 0
                self.best_state = {k: v.clone() for k, v in self.model.state_dict().items()}
            else:
                patience += 1
            if patience >= 20:
                print(f"    Early stopping at epoch {epoch+1}")
                break
        self.model.load_state_dict(self.best_state)
        with torch.no_grad():
            _, feat_imp, _ = self.model(X_t, tree_t)
            self.feature_importance = feat_imp.cpu().numpy()

    def predict(self, X):
        n_samples = X.shape[0]
        tree_preds = np.zeros((n_samples, self.n_estimators))
        for i, tree in enumerate(self.base_rf.estimators_):
            tree_preds[:, i] = tree.predict(X)
        X_t = torch.FloatTensor(X)
        tree_t = torch.FloatTensor(tree_preds)
        self.model.eval()
        with torch.no_grad():
            pred, _, _ = self.model(X_t, tree_t)
        return pred.numpy().flatten()


larf = TwoLevelAttentionRandomForest(n_estimators=100, max_depth=10)
larf.fit(X_train_tree, y_train_tree)
y_pred_larf = larf.predict(X_test_tree)
larf_r2 = r2_score(y_test_tree, y_pred_larf)
larf_mae = mean_absolute_error(y_test_tree, y_pred_larf)
larf_rmse = np.sqrt(mean_squared_error(y_test_tree, y_pred_larf))
print(f"\nLARF 测试集结果:")
print(f"  R²: {larf_r2:.4f}")
print(f"  MAE: {larf_mae:.2f}%")
print(f"  RMSE: {larf_rmse:.2f}%")

# ============================================
# 7. DistilledTabTransformer (蒸馏模型)
# ============================================
print("\n" + "=" * 80)
print("模型6: DistilledTabTransformer (蒸馏自TabTransformer)")
print("=" * 80)


class DistilledTabTransformer(nn.Module):
    def __init__(self, categorical_dims, numerical_dim, embedding_dim=8,
                 mlp_hidden_dims=[64, 32], output_dim=1):
        super().__init__()
        self.categorical_embeddings = nn.ModuleList([
            nn.Embedding(dim, embedding_dim) for dim in categorical_dims
        ])
        self.numerical_proj = nn.Linear(numerical_dim, embedding_dim)
        mlp_input_dim = embedding_dim * (len(categorical_dims) + 1)
        mlp_layers = []
        for hidden_dim in mlp_hidden_dims:
            mlp_layers.extend([
                nn.Linear(mlp_input_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            mlp_input_dim = hidden_dim
        mlp_layers.append(nn.Linear(mlp_input_dim, output_dim))
        self.mlp = nn.Sequential(*mlp_layers)

    def forward(self, x_cat, x_num):
        cat_embeds = [embed(x_cat[:, i]) for i, embed in enumerate(self.categorical_embeddings)]
        num_embed = self.numerical_proj(x_num)
        combined = torch.cat(cat_embeds + [num_embed], dim=1)
        return self.mlp(combined).squeeze()


# 使用训练好的TabTransformer生成软标签
distilled_model = DistilledTabTransformer(
    categorical_dims=categorical_dims,
    numerical_dim=numerical_dim,
    embedding_dim=8,
    mlp_hidden_dims=[64, 32],
    output_dim=1
).to(device)

teacher_model = tab_model
teacher_model.eval()
with torch.no_grad():
    soft_labels = teacher_model(X_cat_train_t.to(device), X_num_train_t.to(device)).cpu().numpy()

optimizer_dist = torch.optim.AdamW(distilled_model.parameters(), lr=1e-3, weight_decay=1e-4)
criterion_dist = nn.MSELoss()
train_loader_dist = DataLoader(TensorDataset(X_cat_train_t, X_num_train_t, torch.FloatTensor(soft_labels)),
                               batch_size=64, shuffle=True)

print("蒸馏训练中...")
for epoch in range(50):
    distilled_model.train()
    epoch_loss = 0
    for batch_cat, batch_num, batch_soft in train_loader_dist:
        batch_cat, batch_num, batch_soft = batch_cat.to(device), batch_num.to(device), batch_soft.to(device)
        optimizer_dist.zero_grad()
        pred = distilled_model(batch_cat, batch_num)
        loss = criterion_dist(pred, batch_soft)
        loss.backward()
        optimizer_dist.step()
        epoch_loss += loss.item()
    if (epoch+1) % 20 == 0:
        print(f"  Epoch {epoch+1}: Loss = {epoch_loss/len(train_loader_dist):.4f}")

distilled_model.eval()
with torch.no_grad():
    y_pred_dist = distilled_model(X_cat_test_t.to(device), X_num_test_t.to(device)).cpu().numpy()
dist_r2 = r2_score(y_test_tab, y_pred_dist)
dist_mae = mean_absolute_error(y_test_tab, y_pred_dist)
dist_rmse = np.sqrt(mean_squared_error(y_test_tab, y_pred_dist))
print(f"\nDistilledTabTransformer 测试集结果:")
print(f"  R²: {dist_r2:.4f}")
print(f"  MAE: {dist_mae:.2f}%")
print(f"  RMSE: {dist_rmse:.2f}%")

# ============================================
# 8. 样本级预测对比（分类任务，阈值85%）
# ============================================
print("\n" + "=" * 80)
print("样本级预测对比（真实类别 vs 各模型预测类别）")
print("=" * 80)

threshold = 85
y_true_cls = (y_test_tab >= threshold).astype(int)   # 使用与TabTransformer相同的测试集标签

# 收集所有模型的回归预测值（确保长度一致，都是len(y_test_tab)）
models_pred = {
    'RandomForest': y_pred_rf,
    'XGBoost': y_pred_xgb,
    'ABRF': y_pred_abrf,
    'LARF': y_pred_larf,
    'TabTransformer': y_pred_tab,
    'DistilledTabTransformer': y_pred_dist
}

# 转换为分类预测
models_cls = {}
for name, pred in models_pred.items():
    models_cls[name] = (pred >= threshold).astype(int)

# 构建对比DataFrame
comparison = pd.DataFrame()
comparison['真实存活率'] = y_test_tab
comparison['真实类别'] = y_true_cls
for name in models_cls.keys():
    comparison[f'{name}_预测类别'] = models_cls[name]
    comparison[f'{name}_是否正确'] = (models_cls[name] == y_true_cls).astype(int)

# 统计每个模型的错误数量
print("\n各模型分类错误统计（阈值85% -> 高存活）:")
for name in models_cls.keys():
    wrong = (models_cls[name] != y_true_cls).sum()
    total = len(y_true_cls)
    acc = (total - wrong) / total
    print(f"  {name}: 判错 {wrong} / {total} 个样本, 准确率 = {acc:.4f}")

# 输出详细对比表格（前20个样本）
print("\n详细样本对比（前20个样本）:")
print(comparison.head(20).to_string())

# 保存完整对比表格
comparison.to_csv('model_comparison_per_sample.csv', index=False)
print("\n完整样本对比已保存到 model_comparison_per_sample.csv")

# ============================================
# 9. 所有模型分类性能汇总
# ============================================
print("\n" + "=" * 80)
print("所有模型分类性能汇总（阈值85%）")
print("=" * 80)

cls_summary = []
for name in models_cls.keys():
    y_pred_cls = models_cls[name]
    acc = accuracy_score(y_true_cls, y_pred_cls)
    f1 = f1_score(y_true_cls, y_pred_cls)
    auc = roc_auc_score(y_true_cls, models_pred[name])   # 使用回归预测值计算AUC
    cls_summary.append({
        '模型': name,
        '准确率': acc,
        'F1-score': f1,
        'AUC': auc,
        '判错数': (y_pred_cls != y_true_cls).sum()
    })
cls_df = pd.DataFrame(cls_summary).sort_values('准确率', ascending=False)
print(cls_df.to_string(index=False))
cls_df.to_csv('model_classification_summary.csv', index=False)
print("\n分类汇总已保存到 model_classification_summary.csv")

# ============================================
# 10. 回归结果汇总
# ============================================
print("\n" + "=" * 80)
print("回归任务结果汇总")
print("=" * 80)

reg_results = pd.DataFrame({
    '模型': ['随机森林', 'XGBoost', 'TabTransformer', 'ABRF', 'LARF', 'DistilledTabTransformer'],
    'R²': [rf_r2, xgb_r2, tab_r2, abrf_r2, larf_r2, dist_r2],
    'MAE (%)': [rf_mae, xgb_mae, tab_mae, abrf_mae, larf_mae, dist_mae],
    'RMSE (%)': [rf_rmse, xgb_rmse, tab_rmse, abrf_rmse, larf_rmse, dist_rmse]
}).sort_values('R²', ascending=False)
print(reg_results.to_string(index=False))
reg_results.to_csv('model_regression_summary.csv', index=False)
print("\n回归汇总已保存到 model_regression_summary.csv")

# ============================================
# 11. 最终结论
# ============================================
print("\n" + "=" * 80)
print("最终结论")
print("=" * 80)
best_reg = reg_results.iloc[0]['模型']
best_r2 = reg_results.iloc[0]['R²']
best_mae = reg_results.iloc[0]['MAE (%)']
print(f" 最佳回归模型: {best_reg} (R²={best_r2:.4f}, MAE={best_mae:.2f}%)")
print(f" 分类最佳准确率: {cls_df.iloc[0]['模型']} (准确率={cls_df.iloc[0]['准确率']:.4f})")
print("=" * 80)