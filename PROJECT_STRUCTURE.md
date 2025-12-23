# 项目结构说明

本项目采用代码与数据分离的目录结构，便于版本控制和数据管理。

## 📁 目录结构

```
E-Hentai-Scanner/
├── modules/              # 核心功能模块
│   ├── common.py        # 公共初始化函数
│   ├── database.py      # 数据库管理
│   ├── network.py       # 网络请求
│   ├── scanner_core.py  # 扫描核心逻辑
│   ├── task_manager.py  # 任务管理
│   ├── result_handler.py # 结果处理
│   ├── translator.py    # 标签翻译
│   └── ...
│
├── scripts/              # 扫描脚本
│   ├── scan_new.py      # 扫描新文件
│   ├── scan_retry.py    # 重试失败文件
│   ├── scan_dedup.py    # 去重扫描
│   ├── scan_single.py   # 单文件扫描
│   └── similarity_rescan.py # 相似度重扫
│
├── tools/                # 工具脚本和可执行文件
│   ├── manual_confirm.py # 手动确认工具
│   ├── export_database.py # 数据库导出工具
│   ├── rollback_db.py    # 数据库回滚工具
│   ├── reset_changed_from_log.py # 日志重置工具
│   └── UnRAR.exe        # RAR 解压工具
│
├── data/                 # 数据目录（不提交到版本控制）
│   ├── eh_scan_results.db      # 主数据库
│   ├── eh_scan_results.db.bak  # 数据库备份
│   ├── db.text.json            # 标签翻译数据库
│   ├── export_scan_results.json # 导出的 JSON 数据
│   ├── export_scan_results.csv  # 导出的 CSV 数据
│   └── *.txt                   # 其他数据文件
│
├── logs/                 # 日志目录（不提交到版本控制）
│   ├── search_result.log       # 主扫描日志
│   ├── rescan.log              # 重扫日志
│   └── *.log                   # 其他日志文件
│
├── config.py            # 配置文件
├── secrets.py           # 敏感配置（不提交）
├── secrets.py.example   # 配置示例
├── main.py              # 主程序入口
├── requirements.txt     # Python 依赖
└── README.md            # 项目说明
```

## 📋 目录说明

### 代码目录

- **`modules/`**: 核心功能模块，包含所有可复用的业务逻辑
- **`scripts/`**: 各种扫描脚本，用于不同的扫描场景
- **`tools/`**: 工具脚本和可执行文件，包括：
  - Python 工具脚本（手动确认、数据导出等）
  - 第三方可执行文件（如 UnRAR.exe）

### 数据目录

- **`data/`**: 所有运行时数据文件
  - 数据库文件（`.db`, `.db.bak`）
  - 标签翻译数据库（`db.text.json`）
  - 导出的数据文件（JSON、CSV）
  - 其他临时数据文件

- **`logs/`**: 所有日志文件
  - 扫描日志
  - 错误日志
  - 调试日志

### 配置文件

- **`config.py`**: 项目配置（提交到版本控制）
- **`secrets.py`**: 敏感配置（不提交，包含 Cookie 等）
- **`secrets.py.example`**: 配置模板

## 🔒 版本控制

以下目录和文件**不提交**到版本控制（已在 `.gitignore` 中配置）：

- `data/` - 所有数据文件
- `logs/` - 所有日志文件
- `secrets.py` - 敏感配置
- `__pycache__/` - Python 缓存
- `*.db`, `*.db.bak` - 数据库文件
- `*.log` - 日志文件

## 🚀 使用说明

### 初始化项目

1. 克隆项目后，复制 `secrets.py.example` 为 `secrets.py` 并填入配置
2. 确保 `data/` 和 `logs/` 目录存在（程序会自动创建）
3. 安装依赖：`pip install -r requirements.txt`

### 路径配置

所有路径配置在 `config.py` 中：

- `PROJECT_ROOT`: 项目根目录（自动检测）
- `DATA_DIR`: 数据目录（`data/`）
- `LOG_DIR`: 日志目录（`logs/`）
- `UNRAR_PATH`: UnRAR 工具路径（`tools/UnRAR.exe`）

### 数据管理

- 数据库文件位于 `data/` 目录
- 导出工具会将数据导出到 `data/` 目录
- 备份文件自动保存在 `data/` 目录（`.bak` 后缀）

## 📝 注意事项

1. **数据分离**: 代码和数据完全分离，便于备份和迁移
2. **路径配置**: 修改路径时只需更新 `config.py`
3. **工具位置**: 所有工具文件统一放在 `tools/` 目录
4. **日志管理**: 定期清理 `logs/` 目录中的旧日志文件

