import csv
import sys
import sqlite3
import logging
from pathlib import Path

# 将项目根目录加入路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("Importer")

def import_custom_csv(csv_file_path: str):
    """
    导入特定格式的 CSV 到数据库
    格式: id,file_path,file_name,gallery_url,title,tags,status,scan_time
    """
    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        logger.error(f"❌ 文件未找到: {csv_path}")
        return

    logger.info(f"📂 读取文件: {csv_path.name}")
    logger.info(f"💾 目标数据库: {config.DB_PATH}")

    # 连接数据库
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    success_count = 0
    error_count = 0

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # 检查 CSV 表头是否符合预期 (可选)
            expected_fields = {'file_path', 'status'} # 至少要有这些
            if not expected_fields.issubset(set(reader.fieldnames or [])):
                logger.warning(f"⚠️ CSV 表头可能缺失关键字段，当前表头: {reader.fieldnames}")

            # 开启事务
            cursor.execute("BEGIN TRANSACTION")
            
            for row in reader:
                try:
                    # 准备数据
                    # 如果 CSV 中 id 为空，设为 None 让数据库自增；如果不为空，则使用 CSV 中的 id
                    raw_id = row.get('id')
                    row_id = int(raw_id) if raw_id and raw_id.strip() else None
                    
                    file_path = row.get('file_path')
                    if not file_path:
                        continue

                    # 提取其他字段，如果 CSV 缺列则给默认值
                    file_name = row.get('file_name', Path(file_path).name)
                    gallery_url = row.get('gallery_url', '')
                    title = row.get('title', '')
                    tags = row.get('tags', '')
                    status = row.get('status', 'UNKNOWN')
                    scan_time = row.get('scan_time') # 如果为空，后面 SQL 会设为 NULL，或者你可以给默认值
                    
                    # 注意：数据库还有一个 'note' 字段，CSV 里没有，这里给默认空字符串
                    note = row.get('note', '') 

                    # 使用 INSERT OR REPLACE 
                    # 这样如果 ID 或 file_path (UNIQUE) 冲突，会覆盖旧数据
                    sql = """
                    INSERT OR REPLACE INTO scan_results 
                    (id, file_path, file_name, gallery_url, title, tags, status, scan_time, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    
                    cursor.execute(sql, (
                        row_id, 
                        file_path, 
                        file_name, 
                        gallery_url, 
                        title, 
                        tags, 
                        status, 
                        scan_time,
                        note
                    ))
                    
                    success_count += 1
                    if success_count % 100 == 0:
                        print(f"⏳ 已处理 {success_count} 条...", end='\r')

                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ 行导入失败: {row.get('file_path', 'Unknown')} | {e}")

            # 提交事务
            conn.commit()
            logger.info(f"\n✅ 导入完成! 成功: {success_count}, 失败: {error_count}")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ 发生严重错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import_file = project_root / "data\\backup\\export_scan_results.csv" # 默认文件名
    
    # 支持命令行参数: python tools/import_table_data.py my_data.csv
    if len(sys.argv) > 1:
        import_file = sys.argv[1]
        
    print(f"🚀 开始导入: {import_file}")
    import_custom_csv(import_file)