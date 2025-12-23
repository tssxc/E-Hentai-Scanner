# manage.py
"""
E-Hentai Scanner 统一管理入口
类似 Django/Flask 的 manage.py，用于通过命令行调用应用功能
"""
import sys
import argparse
from app.controller import AppController

def main():
    parser = argparse.ArgumentParser(
        description="E-Hentai Scanner Backend Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python manage.py scan_new      # 扫描新文件
  python manage.py retry          # 重试失败项
  python manage.py dedup          # 去重扫描
  python manage.py single <path>  # 扫描单个文件
        """
    )
    
    parser.add_argument(
        'action',
        choices=['scan_new', 'retry', 'dedup', 'single'],
        help="要执行的动作"
    )
    
    parser.add_argument(
        'file_path',
        nargs='?',
        help="单文件扫描时的文件路径（仅当 action=single 时使用）"
    )
    
    args = parser.parse_args()
    
    # 初始化控制器
    app = AppController()
    
    try:
        if args.action == 'scan_new':
            app.scan_new_files()
        elif args.action == 'retry':
            app.retry_failures()
        elif args.action == 'dedup':
            app.scan_dedup()
        elif args.action == 'single':
            if not args.file_path:
                print("❌ 错误: 单文件扫描需要提供文件路径")
                print("   用法: python manage.py single <文件路径>")
                sys.exit(1)
            app.scan_single(args.file_path)
    except KeyboardInterrupt:
        print("\n🛑 用户停止")
    except Exception as e:
        print(f"❌ 发生严重错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        app.cleanup()

if __name__ == "__main__":
    main()

