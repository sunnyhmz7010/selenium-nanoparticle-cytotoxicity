"""
TabTransformer 小数据集优化版 - 针对几千条数据防止过拟合
压缩模型容量、强正则化、简化特征输入
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
import warnings

warnings.filterwarnings('ignore')

# ==================== 1. 设置设备 ====================
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"正在使用设备: {device}")

# ==================== 2. 加载数据 ====================
print("\n正在加载数据...")
df = pd.read_excel('d0en01240h1.xlsx', sheet_name='Viability')
print(f"数据加载完成，共 {len(df)} 条记录")

# ==================== 3. 定义特征 ====================
# 类别特征（核心：只保留高价值的类别特征）
categ_features = [
    'Material', 'Shape', 'Coat/Functional Group',
    'Synthesis_Method', 'Surface_Charge', 'Cell_Type',
    'Human_Animal', 'Cell_Tissue', 'Test', 'Test_Indicator'
]

# 连续特征（可选：如果效果不好，可以暂时不用）
cont_features = [
    'Diameter (nm)', 'Size_in_Water (nm)',
    'Time (hr)', 'Concentration (ug/ml)'
]

# 目标变量
target = 'Cell_Viability (%)'

# ==================== 4. 数据清洗 ====================
print("\n正在预处理数据...")

# 过滤异常值：细胞存活率应该在 0-200% 之间（有些实验可能超过100）
df = df[(df[target] >= 0) & (df[target] <= 200)]
print(f"过滤异常值后，剩余 {len(df)} 条记录")

# 提取特征
X_categ_raw = df[categ_features].copy()
X_cont_raw = df[cont_features].copy() if cont_features else pd.DataFrame()
y = df[target].values

# 处理缺失值
X_categ_raw = X_categ_raw.fillna('Missing')
if len(cont_features) > 0:
    X_cont_raw = X_cont_raw.fillna(X_cont_raw.median())

# ==================== 5. 数据增强（可选）====================
print("\n正在进行数据增强...")


def add_noise(X, noise_level=0.01):
    """给数值特征添加少量随机噪声，增加数据多样性"""
    noise = np.random.normal(0, noise_level, X.shape)
    return X + noise


# 编码类别特征
encoder = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
X_categ_encoded = encoder.fit_transform(X_categ_raw).astype(int)

# 标准化连续特征
if len(cont_features) > 0:
    scaler = StandardScaler()
    X_cont_scaled = scaler.fit_transform(X_cont_raw)
    # 可选：添加噪声进行数据增强
    X_cont_augmented = add_noise(X_cont_scaled, noise_level=0.01)
else:
    X_cont_scaled = np.zeros((len(df), 1))  # 占位符
    X_cont_augmented = X_cont_scaled

print(f"类别特征数量: {X_categ_encoded.shape[1]}")
print(f"连续特征数量: {X_cont_scaled.shape[1] if len(cont_features) > 0 else 0}")

# ==================== 6. 划分数据集 ====================
X_categ_train, X_categ_val, X_cont_train, X_cont_val, y_train, y_val = train_test_split(
    X_categ_encoded, X_cont_scaled, y, test_size=0.2, random_state=42
)

# 转换为PyTorch张量
train_dataset = TensorDataset(
    torch.tensor(X_categ_train, dtype=torch.long),
    torch.tensor(X_cont_train, dtype=torch.float32),
    torch.tensor(y_train, dtype=torch.float32).reshape(-1, 1)
)

val_dataset = TensorDataset(
    torch.tensor(X_categ_val, dtype=torch.long),
    torch.tensor(X_cont_val, dtype=torch.float32),
    torch.tensor(y_val, dtype=torch.float32).reshape(-1, 1)
)

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)  # 小batch size
val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

print(f"训练集大小: {len(train_dataset)}")
print(f"验证集大小: {len(val_dataset)}")

# ==================== 7. 创建简化版模型 ====================
print("\n正在创建简化版模型...")

categories = [len(encoder.categories_[i]) for i in range(X_categ_encoded.shape[1])]
num_cont = X_cont_scaled.shape[1] if len(cont_features) > 0 else 0

print("\n使用方案B：实体嵌入 + MLP（0层Transformer）")


class SimplifiedTabTransformer(nn.Module):
    """
    简化版TabTransformer - 针对小数据集优化
    - 实体嵌入（Entity Embedding）
    - 直接拼接 + MLP（跳过Transformer层）
    - 强正则化（Dropout + Weight Decay）
    """

    def __init__(self, category_sizes, num_continuous, embedding_dim=8,
                 hidden_dims=[64, 32], dropout=0.4):
        super().__init__()

        # 1. 实体嵌入层（小维度：4-16）
        self.embeddings = nn.ModuleList([
            nn.Embedding(size, embedding_dim) for size in category_sizes
        ])

        # 2. 连续特征投影（如果有）
        if num_continuous > 0:
            self.cont_proj = nn.Linear(num_continuous, embedding_dim)
        else:
            self.cont_proj = None

        # 3. 计算输入维度
        input_dim = len(category_sizes) * embedding_dim
        if num_continuous > 0:
            input_dim += embedding_dim

        # 4. MLP预测头（1-2层，带强Dropout）
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),  # 批归一化稳定训练
                nn.ReLU(),
                nn.Dropout(dropout)  # 强Dropout (0.3-0.5)
            ])
            prev_dim = hidden_dim

        # 输出层
        layers.append(nn.Linear(prev_dim, 1))

        self.mlp = nn.Sequential(*layers)

        # 初始化权重
        self._init_weights()

    def _init_weights(self):
        """Xavier初始化，帮助收敛"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.xavier_uniform_(module.weight)

    def forward(self, x_categ, x_cont):
        # 实体嵌入
        embedded = [self.embeddings[i](x_categ[:, i]) for i in range(len(self.embeddings))]
        x = torch.cat(embedded, dim=1)  # (batch, num_categ * embed_dim)

        # 连续特征（如果有）
        if self.cont_proj is not None and x_cont is not None:
            cont_emb = self.cont_proj(x_cont)
            x = torch.cat([x, cont_emb], dim=1)

        # MLP预测
        return self.mlp(x)


# 创建模型（极简配置）
model = SimplifiedTabTransformer(
    category_sizes=categories,
    num_continuous=num_cont,
    embedding_dim=8,  # 小嵌入维度（原版32-64）
    hidden_dims=[64, 32],  # 浅层MLP（1-2层）
    dropout=0.4  # 强Dropout
).to(device)

print(f"模型参数总数: {sum(p.numel() for p in model.parameters()):,}")
print(f"嵌入维度: 8")
print(f"MLP结构: 输入 -> 64 -> 32 -> 1")
print(f"Dropout率: 0.4")

# ==================== 8. 训练配置 ====================
print("\n开始训练...")

# 使用AdamW优化器（解耦权重衰减）
optimizer = optim.AdamW(
    model.parameters(),
    lr=5e-4,  # 较低学习率
    weight_decay=1e-2  # 强L2正则化
)

# 学习率衰减（移除verbose参数）
scheduler = optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode='min', factor=0.5, patience=5
)

criterion = nn.MSELoss()

# 早停设置
best_val_loss = float('inf')
patience_counter = 0
patience = 10  # 耐心值10轮
best_model_state = None

num_epochs = 100  # 最大轮数，早停会提前结束

# ==================== 9. 训练循环 ====================
for epoch in range(num_epochs):
    # 训练阶段
    model.train()
    train_loss = 0.0
    train_bar = tqdm(train_loader, desc=f'Epoch {epoch + 1}/{num_epochs} [训练]')

    for batch_categ, batch_cont, batch_labels in train_bar:
        batch_categ = batch_categ.to(device)
        batch_cont = batch_cont.to(device)
        batch_labels = batch_labels.to(device)

        optimizer.zero_grad()
        predictions = model(batch_categ, batch_cont)
        loss = criterion(predictions, batch_labels)
        loss.backward()

        # 梯度裁剪，防止梯度爆炸
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()

        train_loss += loss.item() * batch_categ.size(0)
        train_bar.set_postfix({'loss': f'{loss.item():.4f}'})

    train_loss /= len(train_loader.dataset)

    # 验证阶段
    model.eval()
    val_loss = 0.0
    with torch.no_grad():
        for batch_categ, batch_cont, batch_labels in val_loader:
            batch_categ = batch_categ.to(device)
            batch_cont = batch_cont.to(device)
            batch_labels = batch_labels.to(device)
            predictions = model(batch_categ, batch_cont)
            loss = criterion(predictions, batch_labels)
            val_loss += loss.item() * batch_categ.size(0)

    val_loss /= len(val_loader.dataset)
    scheduler.step(val_loss)

    # 打印当前学习率
    current_lr = optimizer.param_groups[0]['lr']
    print(f'Epoch {epoch + 1}: 训练损失={train_loss:.4f}, 验证损失={val_loss:.4f}, 学习率={current_lr:.6f}')

    # 早停检查
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        patience_counter = 0
        best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        print(f'   保存最佳模型，验证损失={val_loss:.4f}')
    else:
        patience_counter += 1
        print(f'  ⏳ 早停计数: {patience_counter}/{patience}')

    if patience_counter >= patience:
        print(f'\n早停触发！在第 {epoch + 1} 轮停止训练')
        break

# 加载最佳模型
if best_model_state:
    model.load_state_dict(best_model_state)
model = model.to(device)

# ==================== 10. 评估模型 ====================
print("\n正在评估模型...")

model.eval()
all_preds = []
all_labels = []

with torch.no_grad():
    for batch_categ, batch_cont, batch_labels in val_loader:
        batch_categ = batch_categ.to(device)
        batch_cont = batch_cont.to(device)
        predictions = model(batch_categ, batch_cont)
        all_preds.extend(predictions.cpu().numpy())
        all_labels.extend(batch_labels.numpy())

all_preds = np.array(all_preds).flatten()
all_labels = np.array(all_labels).flatten()

# 计算指标
mse = mean_squared_error(all_labels, all_preds)
mae = mean_absolute_error(all_labels, all_preds)
r2 = r2_score(all_labels, all_preds)

print("\n" + "=" * 50)
print(" 模型评估结果")
print("=" * 50)
print(f"均方误差 (MSE): {mse:.4f}")
print(f"平均绝对误差 (MAE): {mae:.4f}")
print(f"R² 分数: {r2:.4f}")
print("=" * 50)

# 预测示例
print("\n 预测示例（前10个验证集样本）：")
for i in range(min(10, len(all_labels))):
    print(f"  真实值: {all_labels[i]:.2f}%  -> 预测值: {all_preds[i]:.2f}%")

# ==================== 11. 保存结果 ====================
results_df = pd.DataFrame({
    '真实值': all_labels,
    '预测值': all_preds,
    '绝对误差': np.abs(all_labels - all_preds)
})
results_df.to_csv('prediction_results.csv', index=False)
print("\n预测结果已保存到 prediction_results.csv")

# 保存模型
torch.save(model.state_dict(), 'simplified_tabtransformer.pth')
print("模型已保存到 simplified_tabtransformer.pth")

print("\n 训练完成！")