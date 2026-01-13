# manage.py
import argparse
import sys
import logging
from app import config
from app.logger import setup_logging
from app.controller import AppController

def main():
    setup_logging(config.LOG_PATH_APP)
    logger = logging.getLogger("manage")

    parser = argparse.ArgumentParser(description="E-Hentai Scanner Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("scan", help="[CLI] 扫描新文件")
    subparsers.add_parser("retry", help="[CLI] 重试失败项")
    subparsers.add_parser("dedup", help="[CLI] 命令行去重")
    
    # 新增 gui 命令
    subparsers.add_parser("gui", help="[GUI] 启动图形界面 (推荐)")

    args = parser.parse_args()

    # 如果没有参数，默认启动 GUI
    if not args.command:
        print("未指定命令，默认启动 GUI...")
        args.command = "gui"

    if args.command == "gui":
        # 启动 GUI
        from app.gui import run_gui
        run_gui()
        return

    # CLI 模式逻辑
    controller = AppController()
    try:
        if args.command == "scan":
            controller.scan_new_files()
        elif args.command == "retry":
            controller.retry_failures()
        elif args.command == "dedup":
            controller.run_deduplication()
    except KeyboardInterrupt:
        print("\n🛑 用户终止")
    except Exception as e:
        logger.exception(f"运行时错误: {e}")
    finally:
        controller.shutdown()

if __name__ == "__main__":
    main()
    #TODO 查重