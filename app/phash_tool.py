# app/phash_tool.py
import logging
import io
from typing import Optional

logger = logging.getLogger(__name__)

# 尝试导入依赖
try:
    from PIL import Image
    import imagehash
    HAS_LIB = True
except ImportError:
    Image = None
    imagehash = None
    HAS_LIB = False

class PHashTool:
    """
    pHash 算法独立封装模块
    """
    @staticmethod
    def is_available() -> bool:
        return HAS_LIB

    @staticmethod
    def compute(image_bytes: bytes) -> Optional[str]:
        """从二进制数据计算 pHash"""
        if not HAS_LIB or not image_bytes:
            return None
        try:
            img = Image.open(io.BytesIO(image_bytes))
            # hash_size=8 是默认值，生成 64位 hash
            return str(imagehash.phash(img, hash_size=8))
        except Exception as e:
            logger.warning(f"⚠️ pHash 计算失败: {e}")
            return None

    @staticmethod
    def calculate_distance(hash_str1: str, hash_str2: str) -> int:
        """计算两个 hash 字符串的汉明距离"""
        if not HAS_LIB or not hash_str1 or not hash_str2:
            return 999
        try:
            h1 = imagehash.hex_to_hash(hash_str1)
            h2 = imagehash.hex_to_hash(hash_str2)
            return h1 - h2
        except Exception:
            return 999
            
    @staticmethod
    def get_similarity_score(distance: int) -> float:
        """将汉明距离转换为 0.0-1.0 的相似度分值 (越接近1越相似)"""
        # 64位hash，距离0为1.0，距离>=32为0.5，距离64为0.0
        return max(0.0, (64 - distance) / 64.0)