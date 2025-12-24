# tools/analyze_headers.py
import sqlite3
import sys
import os
from pathlib import Path

# 将项目根目录加入路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config

def get_file_type(header_bytes):
    """根据文件头判断类型"""
    hex_str = header_bytes.hex().upper()
    
    if hex_str.startswith("504B0304"):
        return "ZIP (标准)"
    elif hex_str.startswith("52617221"):
        return "RAR (需要安装 rarfile + UnRAR.exe)"
    elif hex_str.startswith("377ABCAF271C"):
        return "7z  (需要安装 py7zr)"
    elif hex_str.startswith("89504E47"):
        return "PNG (这不是压缩包)"
    elif hex_str.startswith("FFD8FF"):
        return "JPG (这不是压缩包)"
    else:
        return f"未知格式 ({hex_str})"

def analyze_unsupported():
    db_path = config.DB_PATH
    table_name = config.TARGET_TABLE
    
    print(f"🚀 开始分析数据库: {db_path.name} ({table_name})")
    
    if not db_path.exists():
        print("❌ 数据库不存在")
        return

    conn = sqlite3.connect(str(db_path))
    # 显式设置 row_factory 为 Row，这样可以使用字段名访问，更安全
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. 查询所有不支持的文件
    sql = f"SELECT file_path FROM {table_name} WHERE status = 'UNSUPPORTED'"
    
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        if not rows:
            print("✅ 太好了！数据库中没有 UNSUPPORTED 状态的文件。")
            return

        print(f"🔍 发现 {len(rows)} 个 UNSUPPORTED 文件，开始检测文件头...\n")
        print(f"{'文件类型':<35} | {'文件名'}")
        print("-" * 80)

        rar_count = 0
        seven_z_count = 0  # 变量名避免以数字开头
        zip_count = 0
        unknown_count = 0

        # 2. 逐个检查
        for row in rows:
            # 因为上面设置了 row_factory，这里直接用 keys 访问
            file_path_str = row['file_path']
            file_path = Path(file_path_str)
            
            if not file_path.exists():
                print(f"{'❌ 文件丢失':<35} | {file_path.name}")
                continue
                
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(6)
                    file_type = get_file_type(header)
                    
                    # 打印结果，文件名过长可以截断显示
                    print(f"{file_type:<35} | {file_path.name}")
                    
                    if "RAR" in file_type: rar_count += 1
                    elif "7z" in file_type: seven_z_count += 1
                    elif "ZIP" in file_type: zip_count += 1
                    else: unknown_count += 1
                    
            except Exception as e:
                print(f"{'❌ 读取失败':<35} | {file_path.name}")

        print("\n" + "="*50)
        print("📊 统计结果:")
        print(f"   RAR 文件: {rar_count} 个 (请配置 tools/UnRAR.exe)")
        print(f"   7z  文件: {seven_z_count} 个 (请运行 pip install py7zr)")
        print(f"   ZIP 文件: {zip_count} 个 (可能是不支持的压缩算法)")
        print(f"   未知/损坏: {unknown_count} 个")
        print("="*50)

    except Exception as e:
        print(f"❌ 数据库查询错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_unsupported()