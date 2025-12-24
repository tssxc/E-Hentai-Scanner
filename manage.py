# manage.py
"""
E-Hentai Scanner 统一管理入口
"""
import sys
import argparse
from app import config
from app.logger import setup_logging
from app.controller import AppController

def main():
    # 1. 初始化日志 (确保只执行一次)
    setup_logging(config.LOG_PATH_APP)

    parser = argparse.ArgumentParser(description="E-Hentai Scanner CLI Manager")
    subparsers = parser.add_subparsers(dest='command', help='可用命令', required=True)

    # 注册命令
    subparsers.add_parser('scan_new', help='[增量] 扫描新文件')
    subparsers.add_parser('retry', help='[重扫] 重试失败项')
    subparsers.add_parser('dedup', help='[维护] 扫描重复URL')
    
    single = subparsers.add_parser('single', help='[测试] 扫描单个文件')
    single.add_argument('path', help='文件路径')
    single.add_argument('--mode', choices=['cover', 'second'], default='cover')

    args = parser.parse_args()
    
    # 2. 初始化控制器
    app = AppController()
    
    try:
        if args.command == 'scan_new':
            app.scan_new_files()
            
        elif args.command == 'retry':
            app.retry_failures()
            
        elif args.command == 'dedup':
            app.scan_dedup()
            
        elif args.command == 'single':
            app.scan_single(args.path, scan_mode=args.mode)
            
    except KeyboardInterrupt:
        print("\n🛑 用户停止")
    except Exception as e:
        print(f"❌ 发生严重错误: {e}")
    finally:
        app.cleanup()

# ⚠️ 确保只有这一个入口检查，且没有在函数外直接调用 main() 或 app.scan_new()
if __name__ == "__main__":
    main()