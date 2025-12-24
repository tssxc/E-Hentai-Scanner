# tools/manual_confirm.py
import os
import sys
import webbrowser
import logging
import sqlite3

# ================= 环境设置 =================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config
from app.common import initialize_components
from app.scanner_core import scan_single_file 

# 配置简单的日志输出
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def manual_confirm_all():
    print("🚀 [工具] 启动人工核对程序...")
    print("   (此工具用于人工判定非 SUCCESS/NO_MATCH 的结果，支持强制覆盖)")
    
    try:
        # 初始化组件
        # [修复] initialize_components 返回 6 个对象，这里正确解包
        db, searcher, translator, _, handler, _ = initialize_components()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return

    try:
        table_name = db.table_name
        # 确保 row_factory 设置正确，以便使用列名访问
        db.conn.row_factory = sqlite3.Row
        cursor = db.conn.cursor()
        
        # 排除已成功(SUCCESS)和明确无结果(NO_MATCH)的记录
        cursor.execute(f"SELECT * FROM {table_name} WHERE status NOT IN ('SUCCESS', 'NO_MATCH')")
        records = cursor.fetchall()
        
        if not records:
            print("✅ 数据库中没有需要处理的记录。")
            return

        total = len(records)
        
        # 遍历每一条需要处理的记录
        for idx, row in enumerate(records, 1):
            file_path = row['file_path']
            file_name = row['file_name']
            
            # [关键] 每次循环都从数据库重新拉取最新状态
            # 因为上一次操作可能会影响接下来的判断，或者防止缓存数据
            current_record = db.get_record_by_path(file_path)
            if not current_record:
                continue

            gallery_url = current_record['gallery_url']
            title = current_record['title']
            tags = current_record['tags']
            status = current_record['status']
            
            file_exists = os.path.exists(file_path)

            print("\n" + "="*70)
            print(f"[{idx}/{total}] 待处理文件: {file_name}")
            print(f"   📂 路径: {file_path}")
            print(f"   📊 初始状态: {status}")
            print("="*70)
            
            processed = False
            while not processed:
                # 实时显示当前信息
                disp_title = title if title else "(无)"
                disp_url = gallery_url if gallery_url else "(无)"
                print(f"🔗 标题: {disp_title}")
                print(f"🌐 URL : {disp_url}")
                print("-" * 70)
                print("👉 [y]确认SUCCESS  [c]重扫封面  [s]重扫第2页  [o]打开网页  [n]跳过  [f]标记FAIL  [q]退出")
                
                choice = input("   指令 > ").lower().strip()
                
                # === 确认当前结果 ===
                if choice in ['y', 'yes']:
                    if not gallery_url or "http" not in str(gallery_url):
                        print("❌ 错误: 当前没有有效 URL，无法标记为成功。")
                        continue
                    db.save_record(file_path, "SUCCESS", gallery_url, title, tags)
                    print("✅ 已更新为: SUCCESS")
                    processed = True

                # === 重新扫描 (封面 c / 第二页 s) ===
                elif choice in ['c', 'cover', 's', 'second']:
                    if not file_exists:
                        print("❌ 文件不存在，无法扫描。")
                        continue
                    
                    mode = 'second' if choice in ['s', 'second'] else 'cover'
                    print(f"🔄 正在执行扫描 (模式: {mode})...")
                    
                    try:
                        # 1. 执行扫描
                        # 注意：scan_single_file 内部会调用 ResultHandler，已经更新了数据库
                        result = scan_single_file(file_path, searcher, handler, scan_mode=mode)
                        
                        # 2. [优化] 重新从数据库获取最新结果
                        # 这样可以确保获取到完整的 title 和 tags (scan_single_file 返回值可能不全)
                        updated_record = db.get_record_by_path(file_path)
                        
                        if updated_record and updated_record['gallery_url']:
                            new_url = updated_record['gallery_url']
                            new_title = updated_record['title']
                            new_tags = updated_record['tags']
                            
                            print(f"✨ [扫描完成] 新结果:")
                            print(f"   标题: {new_title}")
                            print(f"   URL : {new_url}")
                            
                            # 更新当前上下文变量
                            gallery_url = new_url
                            title = new_title
                            tags = new_tags
                            
                            if result['success']:
                                print("   (系统判定: 匹配成功)")
                            else:
                                print("   (系统判定: 匹配度不足/MISMATCH，但已找到 URL)")

                            # 快捷确认
                            confirm = input("👉 是否直接采纳? (y/n): ").lower().strip()
                            if confirm == 'y':
                                db.save_record(file_path, "SUCCESS", new_url, new_title, new_tags)
                                print("✅ 已更新为: SUCCESS")
                                processed = True 
                            else:
                                print("   结果已保存，您可以继续操作(如打开网页确认)。")
                        else:
                            print(f"❌ [无结果] {result.get('message')}")
                            
                    except Exception as e:
                        print(f"❌ 扫描过程出错: {e}")

                # === 其他操作 ===
                elif choice in ['n', 'no', 'skip']:
                    print("⏭️ 跳过")
                    processed = True
                    
                elif choice in ['o', 'open']:
                    if gallery_url and "http" in str(gallery_url):
                        webbrowser.open(gallery_url)
                        print("   已在浏览器打开")
                    else:
                        print("❌ 无有效 URL")
                        
                elif choice in ['f', 'fail']:
                    db.save_record(file_path, "FAIL", gallery_url, title, tags)
                    print("🚫 已标记为 FAIL")
                    processed = True
                    
                elif choice in ['q', 'quit']:
                    print("👋 退出程序")
                    return
                
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals() and db:
            db.close()

if __name__ == "__main__":
    manual_confirm_all()