# tools/import_database.py
"""
数据库导入/恢复工具
将 export_database.py 生成的 JSON 数据导入到新数据库中
自动适配字段差异，支持批量高速写入
"""
import sys
import json
import logging
import sqlite3
from pathlib import Path

# 添加项目根目录到路径
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.database import DatabaseManager
from app import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def import_table_from_json(db, table_name, json_file):
    """从 JSON 导入数据到指定表"""
    if not json_file.exists():
        logger.warning(f"⚠️ 文件不存在，跳过: {json_file.name}")
        return

    logger.info(f"📥 正在导入: {table_name} (源: {json_file.name})")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data_list = json.load(f)
            
        if not data_list:
            logger.info("   ℹ️ JSON 数据为空")
            return

        # 1. 获取目标表的列结构 (适配新数据库)
        db.cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = db.cursor.fetchall()
        # 获取所有列名
        valid_columns = {col['name'] for col in columns_info}
        
        # 2. 准备 SQL 语句
        # 动态构建列名列表，确保只插入数据库中存在的列
        sample_record = data_list[0]
        # 找出 JSON 和 数据库 共有的列
        insert_keys = [k for k in sample_record.keys() if k in valid_columns]
        
        if not insert_keys:
            logger.error("   ❌ 无法匹配任何列，导入失败")
            return

        columns_str = ", ".join(insert_keys)
        placeholders = ", ".join(["?"] * len(insert_keys))
        
        # 使用 INSERT OR IGNORE 忽略主键冲突 (保留旧ID)
        # 或者使用 INSERT OR REPLACE (覆盖旧数据)
        sql = f"INSERT OR IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        
        # 3. 转换数据为元组列表 (批量处理)
        batch_data = []
        for item in data_list:
            # 按顺序提取值
            batch_data.append([item.get(k) for k in insert_keys])

        # 4. 执行批量插入
        db.cursor.executemany(sql, batch_data)
        db.conn.commit()
        
        logger.info(f"   ✅ 成功导入 {db.cursor.rowcount} 条记录")

    except Exception as e:
        db.conn.rollback()
        logger.error(f"   ❌ 导入失败: {e}")

def main():
    logger.info("🚀 开始数据库恢复/迁移...")
    data_dir = config.DATA_DIR
    
    # 待导入的表映射关系 (JSON文件名 -> 数据库表名)
    # 你可以根据需要添加更多表
    tasks = [
        ("export_scan_results.json", "scan_results"),
        ("export_duplicates_archive.json", "duplicates_archive"),
        # 兼容测试表
        ("export_scan_results_test.json", "scan_results_test"),
    ]

    try:
        # 连接数据库 (会自动创建新表结构)
        with DatabaseManager(config.DB_PATH) as db:
            # 开启显式事务以提高速度
            db.cursor.execute("BEGIN TRANSACTION")
            
            for json_name, table_name in tasks:
                json_path = data_dir / json_name
                # 检查表是否存在，不存在则跳过 (防止导入到未初始化的表)
                # DatabaseManager._init_schema 应该已经创建了 scan_results
                import_table_from_json(db, table_name, json_path)
            
            db.conn.commit()
            logger.info("🎉 所有导入任务完成！")
            
    except Exception as e:
        logger.error(f"❌ 严重错误: {e}")

if __name__ == "__main__":
    main()