# tools/export_database.py
"""
数据库导出工具 (增强版)
将数据库表导出为 JSON (用于迁移) 和 CSV (用于查看)
"""
import os
import sys
import json
import csv
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.database import DatabaseManager
from app import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def custom_serializer(obj):
    """JSON 序列化辅助函数"""
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    return str(obj)

def export_table(cursor, table_name, output_dir):
    """导出单个表"""
    logger.info(f"📤 正在导出: {table_name}")
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if not rows:
            logger.warning(f"   ⚠️ 表 {table_name} 为空，跳过。")
            return

        # 获取列名
        columns = [description[0] for description in cursor.description]
        data_list = [dict(row) for row in rows]

        # 1. JSON (用于导入恢复)
        json_path = output_dir / f"export_{table_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2, default=custom_serializer)
        
        # 2. CSV (用于Excel查看)
        csv_path = output_dir / f"export_{table_name}.csv"
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data_list)
            
        logger.info(f"   ✅ 已保存: {json_path.name}")

    except Exception as e:
        logger.error(f"   ❌ 导出 {table_name} 失败: {e}")

def main():
    logger.info("🚀 开始数据库备份...")
    
    # 确保输出目录存在
    output_dir = config.DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 使用 DatabaseManager 连接
    try:
        # 注意：这里使用 config 中的路径，自动适配环境
        with DatabaseManager(config.DB_PATH) as db:
            # 获取所有非系统表
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = db.cursor.fetchall()
            
            if not tables:
                logger.warning("⚠️ 未找到任何表。")
                return

            count = 0
            for row in tables:
                table_name = row['name'] # Row对象支持 key 访问
                export_table(db.cursor, table_name, output_dir)
                count += 1
                
            logger.info(f"🎉 备份完成！共处理 {count} 个表。文件位于: {output_dir}")
            
    except Exception as e:
        logger.error(f"❌ 严重错误: {e}")

if __name__ == "__main__":
    main()