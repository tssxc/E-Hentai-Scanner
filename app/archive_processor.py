# app/archive_processor.py
import os
import logging
import hashlib
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Tuple, BinaryIO, Union

from . import config
from .phash_tool import PHashTool

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
        if not rarfile: missing.append("rarfile")
        if not py7zr: missing.append("py7zr")
        if not PHashTool.is_available(): missing.append("Pillow/ImageHash (pHash查重)")
        
        if missing:
            logger.debug(f"ℹ️ [Init] 部分依赖未安装: {', '.join(missing)}")

    def calculate_sha1_from_stream(self, file_stream: BinaryIO) -> str:
        sha1 = hashlib.sha1()
        while chunk := file_stream.read(65536):
            sha1.update(chunk)
        return sha1.hexdigest()

    def calculate_sha1(self, file_path: Union[str, Path]) -> Optional[str]:
        try:
            with open(file_path, 'rb') as f:
                return self.calculate_sha1_from_stream(f)
        except OSError as e:
            logger.error(f"❌ [IO] 读取文件失败: {file_path} - {e}")
            return None

    def get_file_hash(self, archive_path: Union[str, Path], target_mode: str = 'cover') -> Tuple[Optional[str], str]:
        archive_path = Path(archive_path)
        if not archive_path.exists():
            return None, "FILE_ERROR"

        f_hash, status = self._get_hash_from_archive_stream(archive_path, target_mode)

        if status == "USE_FALLBACK":
            with tempfile.TemporaryDirectory() as temp_dir:
                extracted_path, extract_status = self._extract_image_to_disk(archive_path, target_mode, Path(temp_dir))
                if extracted_path:
                    f_hash = self.calculate_sha1(extracted_path)
                    return f_hash, "OK"
                else:
                    return None, extract_status 

        return f_hash, status

    # [集成] pHash 计算
    def get_image_phash(self, archive_path: Union[str, Path]) -> Optional[str]:
        if not PHashTool.is_available():
            return None

        archive_path = Path(archive_path)
        if not archive_path.exists(): return None

        try:
            image_data = self._get_image_bytes_from_archive(archive_path)
            
            if not image_data:
                 with tempfile.TemporaryDirectory() as temp_dir:
                    extracted_path, status = self._extract_image_to_disk(archive_path, 'cover', Path(temp_dir))
                    if status == 'OK' and extracted_path:
                        with open(extracted_path, 'rb') as f:
                            image_data = f.read()

            return PHashTool.compute(image_data)

        except Exception as e:
            logger.warning(f"⚠️ [pHash] 计算异常 {archive_path.name}: {e}")
            return None

    def _get_image_bytes_from_archive(self, archive_path: Path) -> Optional[bytes]:
        try:
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    imgs = sorted([f for f in zf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
                    if imgs: return zf.read(imgs[0])
            elif rarfile and rarfile.is_rarfile(archive_path):
                with rarfile.RarFile(archive_path, 'r') as rf:
                    imgs = sorted([f for f in rf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
                    if imgs: return rf.read(imgs[0])
        except Exception:
            pass
        return None
    
    def _get_hash_from_archive_stream(self, archive_path: Path, target_mode: str) -> Tuple[Optional[str], str]:
        is_zip = zipfile.is_zipfile(archive_path)
        is_rar = rarfile and rarfile.is_rarfile(archive_path) if rarfile else False

        if not (is_zip or is_rar):
            if py7zr and py7zr.is_7zfile(archive_path): return None, "USE_FALLBACK"
            return None, "UNSUPPORTED"

        archive_handler = None
        try:
            if is_zip:
                archive_handler = zipfile.ZipFile(archive_path, 'r')
                namelist = archive_handler.namelist()
            else:
                archive_handler = rarfile.RarFile(archive_path, 'r')
                namelist = archive_handler.namelist()

            imgs = sorted([f for f in namelist if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
            if not imgs: return None, "NO_IMAGES"

            target_img = imgs[0]
            if target_mode == 'second':
                 target_img = imgs[9] if len(imgs) >= 10 else imgs[-1]

            with archive_handler.open(target_img) as f_stream:
                return self.calculate_sha1_from_stream(f_stream), "OK"
        except Exception:
            return None, "USE_FALLBACK"
        finally:
            if archive_handler: archive_handler.close()

    def _extract_image_to_disk(self, archive_path: Path, target_mode: str, temp_dir: Path) -> Tuple[Optional[Path], str]:
        handler = None
        is_7z = False
        try:
            if py7zr and py7zr.is_7zfile(archive_path):
                handler = py7zr.SevenZipFile(archive_path, mode='r'); is_7z = True
            elif zipfile.is_zipfile(archive_path):
                handler = zipfile.ZipFile(archive_path, 'r')
            elif rarfile and rarfile.is_rarfile(archive_path):
                handler = rarfile.RarFile(archive_path, 'r')
            
            if not handler: return None, "UNSUPPORTED"

            with handler:
                names = handler.getnames() if is_7z else handler.namelist()
                imgs = sorted([f for f in names if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
                if not imgs: return None, "NO_IMAGES"

                target_img = imgs[0]
                if target_mode == 'second':
                     target_img = imgs[9] if len(imgs) >= 10 else imgs[-1]
                
                if is_7z:
                    handler.extract(path=temp_dir, targets=[target_img])
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith(Path(target_img).name): return Path(root) / file, "OK"
                else:
                    handler.extract(target_img, temp_dir)
                    return temp_dir / target_img, "OK"
                return None, "FILE_ERROR"
        except Exception as e:
            return None, "FILE_ERROR"