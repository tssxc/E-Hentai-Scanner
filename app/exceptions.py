# modules/exceptions.py

class ScannerBaseError(Exception):
    """项目的基础异常类"""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self):
        if self.code:
            return f"[Code {self.code}] {self.message}"
        return self.message

# ================= 具体的异常类型 (增强版) =================

class IpBlockedError(ScannerBaseError):
    """当检测到 IP 被封禁时抛出"""
    def __init__(self, message="IP 已被 E-Hentai 封禁", code=403):
        # 如果调用时不传参，就使用上面的默认值
        super().__init__(message, code)

class NetworkError(ScannerBaseError):
    """网络连接失败"""
    def __init__(self, message="网络连接异常", code=None):
        super().__init__(message, code)

class ParseError(ScannerBaseError):
    """解析失败"""
    def __init__(self, message="HTML 解析失败", code=None):
        super().__init__(message, code)

class EmptyArchiveError(ScannerBaseError):
    """文件为空"""
    def __init__(self, message="压缩包文件为空或损坏", code=None):
        super().__init__(message, code)