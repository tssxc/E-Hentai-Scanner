# app/network.py
import os
import re
import html
import logging
import hashlib
import zipfile
import tempfile
import time
from pathlib import Path
from typing import Optional, Dict, Union, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

# ================= 压缩库加载 =================
# 1. RAR 支持
try:
    import rarfile
    if config.UNRAR_PATH.exists():
        rarfile.UNRAR_TOOL = str(config.UNRAR_PATH)
except ImportError:
    rarfile = None

# 2. 7z 支持 (新增)
try:
    import py7zr
except ImportError:
    py7zr = None

# 3. HTML 解析
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from .exceptions import IpBlockedError, NetworkError, ParseError

logger = logging.getLogger(__name__)

class EHentaiHashSearcher:
    def __init__(self, cookies: Optional[Dict] = None):
        self.session = requests.Session()
        self._setup_session(cookies)
        
        self.domain = "https://exhentai.org" if cookies and cookies.get('igneous') != 'mystery' else "https://e-hentai.org"
        self.api_url = "https://api.e-hentai.org/api.php"
        self.site_name = "ExHentai" if "exhentai" in self.domain else "E-Hentai"
        
        # 依赖检查日志
        missing_libs = []
        if not rarfile: missing_libs.append("rarfile")
        if not py7zr: missing_libs.append("py7zr")
        if missing_libs:
            logger.debug(f"ℹ️ 可选解压库未安装: {', '.join(missing_libs)} (部分格式可能不支持)")

    def _setup_session(self, cookies):
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        })
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        if cookies:
            self.session.cookies.update(cookies)
        
        self.session.cookies.set('nw', '1', domain='.e-hentai.org')
        self.session.cookies.set('nw', '1', domain='.exhentai.org')

    def verify_connection(self) -> bool:
        logger.debug(f"🔌 [Connect] 正在验证连接: {self.domain}")
        try:
            start_time = time.time()
            r = self.session.get(self.domain, timeout=5) # 缩短超时
            elapsed = time.time() - start_time
            
            if r.status_code == 200 and len(r.text) > 500:
                logger.info(f"✅ 网络连接正常 ({self.site_name}), 耗时: {elapsed:.2f}s")
                return True
            logger.warning(f"⚠️ 连接响应异常 (Code: {r.status_code}, Length: {len(r.text)})")
            return False
        except Exception as e:
            logger.error(f"❌ 网络连接验证失败: {e}")
            return False

    def calculate_sha1(self, file_path: Union[str, Path]) -> Optional[str]:
        """计算文件 SHA1"""
        sha1 = hashlib.sha1()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(65536):
                    sha1.update(chunk)
            return sha1.hexdigest()
        except OSError as e:
            logger.error(f"❌ 计算哈希失败: {e}")
            return None

    def search_by_hash(self, file_hash: str, is_cover: bool = True) -> Union[str, None]:
        if not file_hash: 
            return None
        
        params = f"f_shash={file_hash}&fs_similar=1" + ("&fs_covers=1" if is_cover else "")
        search_url = f"{self.domain}/?{params}"
        
        logger.debug(f"🔍 [Search] Hash: {file_hash[:8]}...")

        try:
            response = self.session.get(search_url, timeout=60)
            
            if "Your IP address has been" in response.text:
                raise IpBlockedError("IP 被 E-Hentai 封禁")

            # 解析结果
            result_url = self._parse_search_result(response.text)
            if result_url:
                logger.info(f"✅ 找到匹配: {result_url}")
                return result_url
            else:
                return "NO_MATCH"

        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ 搜索请求超时或失败: {e}")
            return None

    def _parse_search_result(self, html_content: str) -> Optional[str]:
        if "/g/" in html_content:
            if BeautifulSoup:
                soup = BeautifulSoup(html_content, 'html.parser')
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    if "/g/" in href and (self.domain in href or href.startswith("/g/")):
                        return self.domain + href if href.startswith("/") else href
            else:
                match = re.search(r'https?://e[x-]?hentai\.org/g/\d+/[a-z0-9]+/', html_content)
                if match: return match.group(0)
        return None

    def _extract_image_from_archive(self, archive_path: Path, target_mode: str, temp_dir: Path) -> Tuple[Optional[Path], str]:
        """
        [核心] 从压缩包中提取图片
        支持 Zip, Rar, 7z
        """
        try:
            handler = None
            is_7z = False

            # 1. 尝试 Zip
            if zipfile.is_zipfile(archive_path):
                handler = zipfile.ZipFile(archive_path, 'r')
            
            # 2. 尝试 RAR
            elif rarfile and rarfile.is_rarfile(archive_path):
                handler = rarfile.RarFile(archive_path, 'r')
            
            # 3. 尝试 7z (需要 py7zr)
            elif py7zr and py7zr.is_7zfile(archive_path):
                handler = py7zr.SevenZipFile(archive_path, mode='r')
                is_7z = True
            
            else:
                logger.warning(f"❌ 不支持的格式或文件损坏: {archive_path.name}")
                return None, "UNSUPPORTED"
            
            with handler:
                # 获取文件列表
                if is_7z:
                    file_list = handler.getnames()
                else:
                    file_list = handler.namelist()
                
                # 筛选图片
                imgs = sorted([f for f in file_list if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
                
                if not imgs: 
                    logger.warning(f"⚠️ 压缩包内无图片: {archive_path.name}")
                    return None, "NO_IMAGES"

                # 选择目标图片
                if target_mode == 'cover':
                    target_img = imgs[0]
                else: 
                    target_index = 9 if len(imgs) >= 10 else -1
                    target_img = imgs[target_index]
                
                extract_path = temp_dir / Path(target_img).name
                
                # 提取文件
                if is_7z:
                    # py7zr 提取逻辑稍有不同
                    handler.extract(path=temp_dir, targets=[target_img])
                    # py7zr 会按目录结构提取，我们需要找到文件并移动出来，或者直接返回完整路径
                    full_extracted_path = temp_dir / target_img
                    if full_extracted_path.exists():
                        return full_extracted_path, "OK"
                    else:
                        return None, "FILE_ERROR"
                else:
                    # Zip / Rar 提取
                    with open(extract_path, 'wb') as f_out:
                        f_out.write(handler.read(target_img))
                    return extract_path, "OK"

        except NotImplementedError:
            # 专门捕获 Zip 压缩算法不支持的情况 (如 Deflate64)
            logger.error(f"❌ 压缩算法不支持 (可能是 Deflate64): {archive_path.name}")
            return None, "FILE_ERROR"
            
        except (zipfile.BadZipFile, Exception) as e:
            if rarfile and isinstance(e, rarfile.Error):
                logger.error(f"❌ RAR Error ({archive_path.name}): {e}")
            elif py7zr and isinstance(e, py7zr.exceptions.Bad7zFile):
                 logger.error(f"❌ 7z Error ({archive_path.name}): {e}")
            else:
                logger.error(f"❌ Archive Error ({archive_path.name}): {e}")
            return None, "FILE_ERROR"

    def process_archive(self, archive_path: Union[str, Path], target: str = 'cover') -> Union[str, None]:
        archive_path = Path(archive_path)
        if not archive_path.exists():
            logger.error(f"文件不存在: {archive_path}")
            return None

        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_path, status = self._extract_image_from_archive(archive_path, target, Path(temp_dir))
            
            if extracted_path and extracted_path.exists():
                f_hash = self.calculate_sha1(extracted_path)
                return self.search_by_hash(f_hash, is_cover=(target == 'cover'))
            else:
                return status

    def get_gallery_metadata(self, gallery_url: str) -> Optional[Dict]:
        match = re.search(r'/g/(\d+)/([\w]+)', gallery_url)
        if not match: return None
        
        gid, token = int(match.group(1)), match.group(2)
        payload = {"method": "gdata", "gidlist": [[gid, token]], "namespace": 1}

        try:
            res = self.session.post(self.api_url, json=payload, timeout=30)
            data = res.json()
            if not data.get('gmetadata'): return None
            gmeta = data['gmetadata'][0]
            
            title_jpn = html.unescape(gmeta.get('title_jpn') or "")
            title_en = html.unescape(gmeta.get('title') or "")
            
            tags = gmeta.get('tags', [])
            if category := gmeta.get('category'):
                tags.append(f"reclass:{category.lower()}")
            
            return {
                "title_jpn": title_jpn,
                "title_en": title_en,
                "title": title_jpn if title_jpn else title_en,
                "tags": tags
            }
        except Exception as e:
            logger.warning(f"⚠️ 获取元数据失败: {e}")
            return None