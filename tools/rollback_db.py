# tools/rollback_db.py
import os
import sys

# 引入上级目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config
from app.database import DatabaseManager

def main():
    print("="*50)
    print("🔙 数据库时光机 (Rollback Tool)")
    print("="*50)
    print(f"📂 目标数据库: {config.DB_PATH}")
    print(f"💾 备份文件源: {config.DB_PATH}.bak")
    print("-" * 50)
    print("⚠️  警告: 此操作将丢弃上次脚本运行后的所有更改！")
    print("⚠️  当前的 .db 文件将被 .bak 文件覆盖。")
    print("-" * 50)

    confirm = input("❓ 确认要回溯到执行前状态吗? (yes/no): ").strip().lower()

    if confirm == 'yes':
        # 初始化一个临时的 DatabaseManager 来执行回溯
        # 注意：这里不需要传入 table_name，因为我们是操作整个文件
        try:
            db = DatabaseManager(config.DB_PATH)
            success = db.rollback_to_backup()
            
            if success:
                print("\n✅ 回溯成功！你可以重新运行扫描程序了。")
            else:
                print("\n❌ 回溯失败，请检查日志。")
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
    else:
        print("🚫 操作已取消。")

if __name__ == "__main__":
    main()