# app/gui.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
from .controller import AppController

class ScannerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("E-Hentai Scanner 工具箱 (Debug Mode)")
        self.root.geometry("800x650") # 高度增加一点以容纳停止按钮
        
        # 初始化控制器
        self.controller = AppController()
        
        # 消息队列 (用于线程通信)
        self.msg_queue = queue.Queue()
        
        self._init_ui()
        self._check_queue() # 启动队列监听

    def _init_ui(self):
        # 1. 顶部控制区
        frame_top = ttk.LabelFrame(self.root, text="功能控制", padding=10)
        frame_top.pack(fill="x", padx=10, pady=5)
        
        # 按钮样式
        style = ttk.Style()
        style.configure("Big.TButton", font=("微软雅黑", 10), padding=5)
        style.configure("Stop.TButton", font=("微软雅黑", 10, "bold"), foreground="red", padding=5)

        # 第一行按钮
        row1 = ttk.Frame(frame_top)
        row1.pack(fill="x", pady=2)

        self.btn_scan = ttk.Button(row1, text="🚀 开始元数据刮削", style="Big.TButton", 
                                  command=self.start_scan_thread)
        self.btn_scan.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_retry_hash = ttk.Button(row1, text="🔄 重试失败项 (Hash)", style="Big.TButton", 
                                        command=self.start_retry_hash_thread)
        self.btn_retry_hash.pack(side="left", expand=True, fill="x", padx=2)

        # 第二行按钮
        row2 = ttk.Frame(frame_top)
        row2.pack(fill="x", pady=2)

        self.btn_title_scan = ttk.Button(row2, text="📝 标题重扫失败项", style="Big.TButton", 
                                        command=self.start_scan_failed_title_thread)
        self.btn_title_scan.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_dedup = ttk.Button(row2, text="🔍 检测重复文件", style="Big.TButton", 
                                   command=self.start_dedup_thread)
        self.btn_dedup.pack(side="left", expand=True, fill="x", padx=2)
        
        # [新增] 第三行：停止按钮
        row3 = ttk.Frame(frame_top)
        row3.pack(fill="x", pady=5) #稍微多一点间距
        
        self.btn_stop = ttk.Button(row3, text="🛑 停止当前任务", style="Stop.TButton",
                                  state="disabled", # 初始状态禁用
                                  command=self.stop_current_task)
        self.btn_stop.pack(fill="x", padx=2)

        # 2. 进度条区
        frame_progress = ttk.Frame(self.root, padding=5)
        frame_progress.pack(fill="x", padx=10)
        
        self.lbl_status = ttk.Label(frame_progress, text="就绪")
        self.lbl_status.pack(anchor="w")
        
        self.progress = ttk.Progressbar(frame_progress, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=5)

        # 3. 日志区
        frame_log = ttk.LabelFrame(self.root, text="运行日志", padding=5)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.txt_log = scrolledtext.ScrolledText(frame_log, height=10, state='disabled')
        self.txt_log.pack(fill="both", expand=True)

    def log(self, message):
        """向日志框追加文本"""
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')

    def update_progress(self, current, total, msg):
        """更新进度条"""
        self.progress["maximum"] = total
        self.progress["value"] = current
        self.lbl_status.config(text=f"[{current}/{total}] {msg}")

    # --- 线程与回调处理 ---

    def gui_callback(self, type_, data):
        """后台线程调用的回调，将数据放入队列"""
        self.msg_queue.put((type_, data))

    def _check_queue(self):
        """UI 主线程轮询队列"""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                
                if msg_type == 'log':
                    self.log(str(data))
                
                elif msg_type == 'progress':
                    self.update_progress(*data)
                
                elif msg_type == 'done':
                    self.log(f"✅ {data}")
                    self.lbl_status.config(text=str(data))
                    self._set_ui_idle(True) # 恢复按钮
                    messagebox.showinfo("完成", str(data))
                
                elif msg_type == 'stopped': # [新增] 处理停止状态
                    self.log(f"⚠️ {data}")
                    self.lbl_status.config(text=str(data))
                    self._set_ui_idle(True) # 恢复按钮
                    # 停止通常不需要弹窗，或者可以弹一个简单的提示
                    
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._check_queue)

    def _set_ui_idle(self, is_idle):
        """
        设置UI状态
        is_idle=True: 空闲状态 (启用开始按钮，禁用停止按钮)
        is_idle=False: 忙碌状态 (禁用开始按钮，启用停止按钮)
        """
        state_func = "normal" if is_idle else "disabled"
        state_stop = "disabled" if is_idle else "normal"
        
        self.btn_scan.config(state=state_func)
        self.btn_dedup.config(state=state_func)
        self.btn_retry_hash.config(state=state_func)
        self.btn_title_scan.config(state=state_func)
        
        # 停止按钮状态与功能按钮相反
        self.btn_stop.config(state=state_stop)

    # --- 任务控制 ---

    def stop_current_task(self):
        """UI 停止按钮点击事件"""
        self.log(">>> 发送停止指令...")
        # 为了防止用户狂点，点击后暂时禁用停止按钮，等待线程实际结束后恢复
        self.btn_stop.config(state="disabled") 
        self.controller.stop_scanning()

    # --- 任务启动 (线程封装) ---

    def start_scan_thread(self):
        self._set_ui_idle(False)
        self.progress["value"] = 0
        self.log("--- 启动元数据刮削任务 (cover模式) ---")
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        try:
            self.controller.scan_new_files(gui_callback=self.gui_callback)
        except Exception as e:
            self.gui_callback('log', f"❌ 严重错误: {e}")
            self.gui_callback('done', "任务异常终止")

    def start_retry_hash_thread(self):
        self._set_ui_idle(False)
        self.progress["value"] = 0
        self.log("--- 启动失败项重试 (second模式) ---")
        threading.Thread(target=self._run_retry_hash, daemon=True).start()

    def _run_retry_hash(self):
        try:
            self.controller.retry_failures(gui_callback=self.gui_callback)
        except Exception as e:
            self.gui_callback('log', f"❌ 重试任务错误: {e}")
            self.gui_callback('done', "任务异常终止")

    def start_scan_failed_title_thread(self):
        self._set_ui_idle(False)
        self.progress["value"] = 0
        self.log("--- 启动失败项标题重扫 (title模式) ---")
        threading.Thread(target=self._run_scan_failed_title, daemon=True).start()

    def _run_scan_failed_title(self):
        try:
            self.controller.scan_failed_with_title(gui_callback=self.gui_callback)
        except Exception as e:
            self.gui_callback('log', f"❌ 标题重扫错误: {e}")
            self.gui_callback('done', "任务异常终止")

    def start_dedup_thread(self):
        self._set_ui_idle(False)
        self.log("--- 启动重复检测任务 ---")
        threading.Thread(target=self._run_dedup, daemon=True).start()

    def _run_dedup(self):
        try:
            self.controller.run_deduplication(gui_callback=self.gui_callback)
        except Exception as e:
            self.gui_callback('log', f"❌ 严重错误: {e}")
            self.gui_callback('done', "任务异常终止")

def run_gui():
    root = tk.Tk()
    app = ScannerGUI(root)
    root.mainloop()