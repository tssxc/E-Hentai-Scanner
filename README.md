# E-Hentai Scanner

一个用于扫描本地漫画压缩包并自动获取 E-Hentai 元数据的 Python 工具。

## ✨ 特性

- 🔍 **智能扫描**: 通过图片 Hash 搜索匹配 E-Hentai 画廊
- 📊 **数据库管理**: SQLite 数据库存储扫描结果
- 🏷️ **标签翻译**: 自动翻译标签为中文
- 🔄 **断点续传**: 支持中断后继续扫描
- 🛡️ **防封禁**: 内置访问频率控制
- 🏗️ **MVC 架构**: 清晰的分层结构，易于扩展

## 📁 项目结构

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
│   └── exceptions.py      # 异常定义
│
├── data/                 # 数据存储（数据库、导出文件等）
├── logs/                 # 日志文件
├── tools/                # 维护工具
│   ├── manual_confirm.py # 手动确认工具
│   ├── export_database.py # 数据库导出工具
│   ├── rollback_db.py    # 数据库回滚工具
│   └── reset_changed_from_log.py # 日志重置工具
│
├── manage.py             # 统一入口（CLI）
├── requirements.txt      # Python 依赖
└── secrets.py.example    # Cookie 配置示例
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 Cookie

1. 复制 `secrets.py.example` 为 `secrets.py`
2. 填入你的 E-Hentai Cookie（参考 [README_SECURITY.md](README_SECURITY.md)）

```python
# secrets.py
MY_COOKIES = {
    'ipb_member_id': 'your_member_id',
    'ipb_pass_hash': 'your_pass_hash',
    'igneous': 'your_igneous',
}
```

### 3. 配置路径

1. 复制 `app/config.example.py` 为 `app/config.py`
2. 修改扫描目录路径：

```python
# app/config.py
DIR_PROD = Path(r"D:\漫画")  # 修改为你的实际路径
DIR_DEBUG = Path(r"D:\漫画")  # 修改为你的测试路径
```

### 4. 运行扫描

```bash
# 扫描新文件
python manage.py scan_new

# 重试失败项
python manage.py retry

# 去重扫描
python manage.py dedup

# 扫描单个文件
python manage.py single "D:\漫画\example.zip"
```

## 📝 功能说明

### 命令行接口

| 命令 | 说明 |
|------|------|
| `scan_new` | 扫描目录中尚未入库的新文件 |
| `retry` | 重试数据库中失败的记录 |
| `dedup` | 处理重复 URL 的文件 |
| `single <path>` | 扫描指定的单个文件 |

### 扫描模式

- **cover**: 搜索封面图（第一张图），速度快但可能误匹配
- **second**: 搜索第10页（如果不够则搜索最后一页），准确度高但速度慢

### 工具脚本

- **manual_confirm.py**: 手动确认 MISMATCH 记录
- **export_database.py**: 导出数据库为 JSON/CSV 格式
- **rollback_db.py**: 从备份恢复数据库
- **reset_changed_from_log.py**: 从日志重置变更记录

## ⚙️ 配置说明

### 调试模式

在 `app/config.py` 中设置 `IS_DEBUG_MODE = True` 可以：

- 使用测试表（`scan_results_test`）
- 限制扫描文件数量（`SCAN_LIMIT = 5`）
- 启用详细日志（`LOG_LEVEL = logging.DEBUG`）

### 访问频率控制

```python
SLEEP_MIN = 4.0  # 最小休眠时间（秒）
SLEEP_MAX = 6.0  # 最大休眠时间（秒）
```

## 🔒 安全说明

⚠️ **重要**: 请勿将包含真实 Cookie 的文件提交到公共仓库！

- `secrets.py` 已在 `.gitignore` 中
- 使用 `secrets.py.example` 作为模板
- 详细说明请参考 [README_SECURITY.md](README_SECURITY.md)

## 📊 数据库结构

数据库表结构：

- `id`: 主键
- `file_path`: 文件完整路径（唯一）
- `file_name`: 文件名
- `gallery_url`: E-Hentai 画廊 URL
- `title`: 标题
- `tags`: 标签（逗号分隔）
- `status`: 状态（SUCCESS, NO_MATCH, ERROR, MISMATCH 等）
- `scan_time`: 扫描时间

## 🛠️ 开发说明

### 架构设计

项目采用 MVC 分层架构：

- **Controller** (`app/controller.py`): 应用层，定义任务接口
- **Service** (`app/services.py`): 业务逻辑层，封装核心功能
- **Model** (`app/database.py`): 数据模型层，数据库操作

### 添加新功能

1. 在 `app/services.py` 中添加新的服务方法
2. 在 `app/controller.py` 中添加对应的控制器方法
3. 在 `manage.py` 中添加命令行参数

### Python 代码调用

```python
from app.controller import AppController

app = AppController()
try:
    app.scan_new_files()
finally:
    app.cleanup()
```

## 📄 许可证

本项目仅供个人学习使用。

## 🔗 相关文档

- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - 架构重构迁移指南
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - 项目结构说明
- [README_SECURITY.md](README_SECURITY.md) - 安全配置说明
