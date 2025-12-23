import os
import sys
import webbrowser
import logging
import time

# ================= 环境设置 =================
# 确保可以将项目根目录加入 Python 路径，以便导入 modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # 假设脚本在 tools/ 目录下
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config
from app.common import initialize_components
from app.scanner_core import scan_single_file  # [新增] 导入扫描核心函数

# 配置简单的日志输出
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def manual_confirm_mismatch():
    print("🚀 [工具] 启动手动确认 MISMATCH 文件程序 (v2 带封面重扫)...")
    
    try:
        # [修改] 初始化更多组件，以便进行扫描
        # 返回值: db, searcher, translator, task_manager, handler, target_dir, current_table
        db, searcher, _, _, handler, _, _ = initialize_components()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return

    try:
        # 1. 获取所有状态为 MISMATCH 的记录
        table_name = db.table_name
        
        cursor = db.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} WHERE status = 'MISMATCH'")
        records = cursor.fetchall()
        
        if not records:
            print("✅ 没有找到状态为 'MISMATCH' 的记录。")
            return

        total = len(records)
        print(f"📂 发现 {total} 个待确认文件。\n")

        for idx, row in enumerate(records, 1):
            file_path = row['file_path']
            file_name = row['file_name']
            gallery_url = row['gallery_url']
            title = row['title']
            tags = row['tags']
            
            print("="*60)
            print(f"[{idx}/{total}] 待确认文件")
            print("="*60)
            print(f"📄 文件名: {file_name}")
            print(f"📂 路  径: {file_path}")
            print(f"🔗 匹配库: {title if title else '(无)'}")
            print(f"🌐 U R L : {gallery_url if gallery_url else '(无)'}")
            if tags:
                tags_display = tags[:100] + "..." if len(tags) > 100 else tags
                print(f"🏷️ 标  签: {tags_display}")
            else:
                print(f"🏷️ 标  签: (无)")
            print("-" * 60)
            
            if not gallery_url:
                print("⚠️ [警告] 此记录没有 URL 数据，可能是扫描时被覆盖为空。")
            
            while True:
                # 提供选项
                print("\n👉 操作选项:")
                print("   [y] 确认匹配 (Confirm)  - 将状态改为 SUCCESS")
                print("   [c] 重扫封面 (Cover)    - 尝试重新扫描封面 [新增]")
                print("   [o] 打开网页 (Open)     - 在浏览器查看当前 URL")
                print("   [n] 跳过 (Next)         - 保持 MISMATCH 不变")
                print("   [f] 标记失败 (Fail)     - 将状态改为 FAIL")
                print("   [q] 退出 (Quit)")
                
                choice = input("请输入指令: ").lower().strip()
                
                if choice in ['y', 'yes']:
                    # 确认匹配 -> 修改状态为 SUCCESS
                    db.save_record(file_path, "SUCCESS", gallery_url, title, tags)
                    print("✅ 已更新为: SUCCESS")
                    break

                elif choice in ['c', 'cover']:
                    print("🔄 正在执行封面扫描...")
                    try:
                        # 执行单文件扫描 (Cover 模式)
                        result = scan_single_file(file_path, searcher, handler, scan_mode='cover')
                        
                        if result['success']:
                            print(f"✅ [扫描成功] 数据库已自动更新!")
                            print(f"   新标题: {result.get('title')}")
                            print(f"   新 URL: {result.get('url')}")
                            # 既然已经成功并写入数据库，直接跳出当前文件的循环，处理下一个
                            break 
                        else:
                            print(f"❌ [扫描无结果] {result.get('message')}")
                            print("   您可以继续选择其他操作 (如手动确认旧 URL)。")
                    except Exception as e:
                        print(f"❌ 扫描过程出错: {e}")
                    
                elif choice in ['n', 'no']:
                    print("⏩ 已跳过 (保持 MISMATCH)")
                    break
                    
                elif choice in ['o', 'open']:
                    target_url = gallery_url
                    if not target_url or "http" not in target_url:
                        # 如果当前记录没有 URL，尝试看看刚才是不是扫描失败了但有 URL
                        print("❌ 当前记录无有效 URL")
                    else:
                        print(f"🌐 正在打开: {target_url}")
                        webbrowser.open(target_url)
                        
                elif choice in ['f', 'fail']:
                    # 标记为失败
                    db.save_record(file_path, "FAIL", gallery_url, title, tags)
                    print("🚫 已更新为: FAIL")
                    break
                    
                elif choice in ['q', 'quit']:
                    print("👋 用户退出")
                    return
                
                else:
                    print("❓ 无效输入，请重试")

    except KeyboardInterrupt:
        print("\n🛑 用户强制中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals():
            db.close()
        print("🏁 程序结束")


if __name__ == "__main__":
    manual_confirm_mismatch()