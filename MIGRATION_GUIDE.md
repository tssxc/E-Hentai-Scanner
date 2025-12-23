# 架构重构迁移指南

## 📋 概述

项目已从脚本式结构重构为后端应用结构，采用标准的 MVC 架构模式。

## 🏗️ 新的目录结构

```
E-Hentai-Scanner/
├── app/                  # [核心] 应用包
│   ├── __init__.py       # 暴露核心接口
│   ├── config.py         # 配置文件
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
├── data/                 # 数据存储
├── logs/                 # 日志文件
├── tools/                # 维护工具
├── manage.py             # [新] 统一入口
└── requirements.txt
```

## 🔄 主要变化

### 1. 配置文件位置
- **旧**: `config.py` (根目录)
- **新**: `app/config.py`

### 2. 模块导入
- **旧**: `from modules.xxx import ...`
- **新**: `from app.xxx import ...`

### 3. 运行方式
- **旧**: `python main.py`
- **新**: `python manage.py <action>`

## 🚀 新的使用方式

### 命令行接口

```bash
# 扫描新文件
python manage.py scan_new

# 重试失败项
python manage.py retry

# 去重扫描
python manage.py dedup

# 扫描单个文件
python manage.py single <文件路径>
```

### Python 代码调用

```python
from app.controller import AppController

# 初始化控制器
app = AppController()

try:
    # 执行任务
    app.scan_new_files()
    # 或
    app.retry_failures()
    # 或
    app.scan_dedup()
finally:
    app.cleanup()
```

### 直接使用服务层

```python
from app.services import ScanService

service = ScanService()
try:
    # 获取待处理文件
    files = service.get_pending_files(Path("D:/漫画"))
    
    # 批量处理
    service.process_batch(files, scan_mode="cover")
finally:
    service.close()
```

## 📝 已更新的文件

以下文件已自动更新以适配新结构：

- ✅ `tools/manual_confirm.py`
- ✅ `tools/export_database.py`
- ✅ `tools/rollback_db.py`
- ✅ `tools/reset_changed_from_log.py`
- ✅ `test_db_read.py`

## ⚠️ 注意事项

1. **配置文件路径**: `app/config.py` 中的 `PROJECT_ROOT` 已更新为 `parent.parent`，因为配置文件现在在 `app/` 目录下。

2. **导入路径**: 所有 `from modules.xxx` 已改为 `from app.xxx` 或相对导入 `from .xxx`。

3. **旧脚本**: `scripts/` 目录下的脚本功能已整合到 `app/controller.py` 中，可通过 `manage.py` 调用。

4. **相似度重扫**: `scripts/similarity_rescan.py` 如需保留，可移动到 `tools/` 目录并更新导入。

## 🔧 迁移检查清单

- [x] 创建 `app/` 目录结构
- [x] 移动 `config.py` 到 `app/config.py`
- [x] 移动 `modules/` 到 `app/`
- [x] 更新所有导入路径
- [x] 创建 `app/services.py`
- [x] 创建 `app/controller.py`
- [x] 创建 `manage.py`
- [x] 更新 `tools/` 脚本
- [x] 删除旧的 `main.py` 和 `scripts/` 目录

## 📚 后续扩展

新的架构非常适合扩展为 Web API：

```python
# 未来可以添加 app/api.py
from flask import Flask
from app.controller import AppController

app = Flask(__name__)
controller = AppController()

@app.route('/scan/new', methods=['POST'])
def scan_new():
    controller.scan_new_files()
    return {'status': 'success'}
```

## 🆘 问题排查

如果遇到导入错误，请检查：

1. Python 路径是否包含项目根目录
2. `app/__init__.py` 是否存在
3. 所有导入是否使用 `from app.xxx` 格式

