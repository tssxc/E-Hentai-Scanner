# 项目结构说明

本项目采用代码与数据分离的目录结构，便于管理。

## 📁 目录结构

```
E-Hentai-Scanner/
├── app/                  # 核心应用包
│   ├── __init__.py       # 暴露核心接口
│   ├── config.py         # 配置文件（需从 config.example.py 复制）
│   ├── config.example.py # 配置示例
│   ├── database.py       # 数据库模型
│   ├── network.py        # 网络请求服务
│   ├── services.py       # 业务逻辑层
│   ├── controller.py     # 控制器层
│   ├── scanner_core.py   # 扫描核心
│   ├── result_handler.py # 结果处理
│   ├── task_manager.py   # 任务管理
│   ├── translator.py     # 标签翻译
│   ├── utils.py          # 工具函数
│   ├── logger.py         # 日志配置
│   ├── common.py         # 公共初始化
│   └── exceptions.py     # 异常定义
│
├── data/                 # 数据目录
│   ├── eh_scan_results.db      # 主数据库
│   ├── eh_scan_results.db.bak  # 数据库备份
│   ├── db.text.json            # 标签翻译数据库
│   ├── export_scan_results.json # 导出的 JSON 数据
│   ├── export_scan_results.csv  # 导出的 CSV 数据
│   └── *.txt                   # 其他数据文件
│
├── logs/                 # 日志目录
│   ├── search_result.log       # 主扫描日志
│   ├── rescan.log              # 重扫日志
│   └── *.log                   # 其他日志文件
│
├── tools/                # 工具脚本和可执行文件
│   ├── manual_confirm.py # 手动确认工具
│   ├── export_database.py # 数据库导出工具
│   ├── rollback_db.py    # 数据库回滚工具
│   ├── reset_changed_from_log.py # 日志重置工具
│   └── UnRAR.exe        # RAR 解压工具
│
├── manage.py             # 统一入口（CLI）
├── requirements.txt      # Python 依赖
├── secrets.py            # 敏感配置
├── secrets.py.example    # 配置示例
└── README.md             # 项目说明
```

## 📋 目录说明

### 代码目录

- **`app/`**: 核心应用包，包含所有业务逻辑和功能模块
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

- **`app/config.py`**: 项目配置（需从 `app/config.example.py` 复制）
- **`secrets.py`**: 敏感配置（包含 Cookie 等）
- **`secrets.py.example`**: 配置模板

## 🔒 数据与配置管理

以下目录和文件包含重要数据或敏感信息，请注意妥善保管：

- `data/` - 包含所有数据库和扫描结果
- `logs/` - 包含运行日志
- `secrets.py` - 包含敏感 Cookie 信息，**请勿分享给他人**

## 🚀 使用说明

### 初始化项目

1. 复制 `secrets.py.example` 为 `secrets.py` 并填入配置
2. 复制 `app/config.example.py` 为 `app/config.py` 并修改路径
3. 确保 `data/` 和 `logs/` 目录存在（程序会自动创建）
4. 安装依赖：`pip install -r requirements.txt`

### 路径配置

所有路径配置在 `app/config.py` 中：

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
2. **路径配置**: 修改路径时只需更新 `app/config.py`
3. **工具位置**: 所有工具文件统一放在 `tools/` 目录
4. **日志管理**: 定期清理 `logs/` 目录中的旧日志文件
5. **安全保护**: `secrets.py` 包含敏感信息，请妥善保管，不要分享给他人
