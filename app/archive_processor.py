# app/archive_processor.py
import os
import logging
import hashlib
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple, BinaryIO, Union

from . import config

# ================= 压缩库加载 =================
try:
    import rarfile
    if config.UNRAR_PATH.exists():
        rarfile.UNRAR_TOOL = str(config.UNRAR_PATH)
except ImportError:
    rarfile = None

try:
    import py7zr
except ImportError:
    py7zr = None

logger = logging.getLogger(__name__)

class ArchiveProcessor:
    def __init__(self):
        self._check_dependencies()

    def _check_dependencies(self):
        missing = []
        if not rarfile: missing.append("rarfile (处理 RAR)")
        if not py7zr: missing.append("py7zr (处理 7Z)")
        if missing:
            logger.debug(f"ℹ️ [Init] 部分压缩库未安装，对应格式将无法处理: {', '.join(missing)}")

    def calculate_sha1_from_stream(self, file_stream: BinaryIO) -> str:
        """从文件流计算 SHA1"""
        sha1 = hashlib.sha1()
        # 64KB chunks
        while chunk := file_stream.read(65536):
            sha1.update(chunk)
        return sha1.hexdigest()

    def calculate_sha1(self, file_path: Union[str, Path]) -> Optional[str]:
        """从本地文件路径计算 SHA1"""
        try:
            with open(file_path, 'rb') as f:
                return self.calculate_sha1_from_stream(f)
        except OSError as e:
            logger.error(f"❌ [IO] 读取文件失败: {file_path} - {e}")
            return None

    def get_file_hash(self, archive_path: Union[str, Path], target_mode: str = 'cover') -> Tuple[Optional[str], str]:
        """
        统一接口：获取文件的 Hash。
        会自动尝试内存流式读取，如果失败则回退到解压模式。
        
        Returns:
            (hash_str, status_code)
            status_code: 'OK', 'NO_IMAGES', 'FILE_ERROR', 'UNSUPPORTED'
        """
        archive_path = Path(archive_path)
        if not archive_path.exists():
            return None, "FILE_ERROR"

        logger.debug(f"📦 [Scanner] 处理文件: {archive_path.name}")

        # 1. 尝试流式读取
        f_hash, status = self._get_hash_from_archive_stream(archive_path, target_mode)

        # 2. 如果需要回退 (Fallback)
        if status == "USE_FALLBACK":
            logger.info(f"🔄 [Scanner] 启用解压模式 (Fallback): {archive_path.name}")
            with tempfile.TemporaryDirectory() as temp_dir:
                extracted_path, extract_status = self._extract_image_to_disk(archive_path, target_mode, Path(temp_dir))
                if extracted_path:
                    f_hash = self.calculate_sha1(extracted_path)
                    return f_hash, "OK"
                else:
                    return None, extract_status # 返回具体错误，如 FILE_ERROR

        return f_hash, status

    def _get_hash_from_archive_stream(self, archive_path: Path, target_mode: str) -> Tuple[Optional[str], str]:
        """内部方法：尝试从压缩包中直接读取图片流计算 Hash"""
        is_zip = zipfile.is_zipfile(archive_path)
        is_rar = rarfile and rarfile.is_rarfile(archive_path) if rarfile else False

        if not (is_zip or is_rar):
            # 7z 不支持流式读取，直接返回 USE_FALLBACK
            if py7zr and py7zr.is_7zfile(archive_path):
                return None, "USE_FALLBACK"
            return None, "UNSUPPORTED"

        archive_handler = None
        try:
            if is_zip:
                archive_handler = zipfile.ZipFile(archive_path, 'r')
                namelist = archive_handler.namelist()
            else:
                archive_handler = rarfile.RarFile(archive_path, 'r')
                namelist = archive_handler.namelist()

            # 筛选图片
            imgs = sorted([f for f in namelist if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
            if not imgs:
                logger.warning(f"⚠️ [Archive] 压缩包内无图片: {archive_path.name}")
                return None, "NO_IMAGES"

            # 选择目标图片
            target_img = imgs[0]
            if target_mode == 'second':
                 target_img = imgs[9] if len(imgs) >= 10 else imgs[-1]

            logger.debug(f"📄 [Archive] 流式读取: {target_img} (in {archive_path.name})")

            with archive_handler.open(target_img) as f_stream:
                file_hash = self.calculate_sha1_from_stream(f_stream)
                return file_hash, "OK"

        except Exception as e:
            logger.debug(f"⚠️ [Archive] 流式读取失败 ({archive_path.name}), 转为解压模式: {e}")
            return None, "USE_FALLBACK"
        finally:
            if archive_handler:
                archive_handler.close()

    def _extract_image_to_disk(self, archive_path: Path, target_mode: str, temp_dir: Path) -> Tuple[Optional[Path], str]:
        """内部方法：解压模式"""
        handler = None
        is_7z = False
        
        try:
            if py7zr and py7zr.is_7zfile(archive_path):
                handler = py7zr.SevenZipFile(archive_path, mode='r')
                is_7z = True
            elif zipfile.is_zipfile(archive_path):
                handler = zipfile.ZipFile(archive_path, 'r')
            elif rarfile and rarfile.is_rarfile(archive_path) if rarfile else False:
                handler = rarfile.RarFile(archive_path, 'r')
            
            if not handler: return None, "UNSUPPORTED"

            with handler:
                names = handler.getnames() if is_7z else handler.namelist()
                imgs = sorted([f for f in names if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
                
                if not imgs: return None, "NO_IMAGES"

                target_img = imgs[0]
                if target_mode == 'second':
                     target_img = imgs[9] if len(imgs) >= 10 else imgs[-1]
                
                # 7z 处理
                if is_7z:
                    handler.extract(path=temp_dir, targets=[target_img])
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith(Path(target_img).name):
                                return Path(root) / file, "OK"
                    return None, "FILE_ERROR"
                
                # Zip/Rar 处理
                else:
                    handler.extract(target_img, temp_dir)
                    full_path = temp_dir / target_img
                    return full_path, "OK"

        except Exception as e:
            logger.error(f"❌ [Archive] 解压失败 {archive_path.name}: {e}")
            return None, "FILE_ERROR"