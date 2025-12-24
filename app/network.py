# modules/network.py
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

try:
    import rarfile
except ImportError:
    rarfile = None
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
        
        logger.debug(f"HashSearcher 初始化完成. 目标站点: {self.site_name}")

    def _setup_session(self, cookies):
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        })
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        if cookies:
            self.session.cookies.update(cookies)
        
        # 强制开启设置
        self.session.cookies.set('nw', '1', domain='.e-hentai.org')
        self.session.cookies.set('nw', '1', domain='.exhentai.org')

    def verify_connection(self) -> bool:
        logger.debug(f"🔌 [Connect] 正在验证连接: {self.domain}")
        try:
            start_time = time.time()
            r = self.session.get(self.domain, timeout=30)
            elapsed = time.time() - start_time
            
            if r.status_code == 200 and len(r.text) > 500:
                logger.info(f"✅ 网络连接正常 ({self.site_name}), 耗时: {elapsed:.2f}s")
                return True
            logger.warning(f"⚠️ 连接响应异常 (Code: {r.status_code}, Length: {len(r.text)})")
            return False
        except Exception as e:
            logger.error(f"❌ 网络连接验证失败: {e}", exc_info=True)
            return False

    def calculate_sha1(self, file_path: Union[str, Path]) -> Optional[str]:
        """计算文件 SHA1"""
        logger.debug(f"正在计算 Hash: {file_path}")
        sha1 = hashlib.sha1()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(65536):
                    sha1.update(chunk)
            digest = sha1.hexdigest()
            logger.debug(f"Hash 计算完成: {digest}")
            return digest
        except OSError as e:
            logger.error(f"❌ 计算哈希失败: {e}")
            return None

    def search_by_hash(self, file_hash: str, is_cover: bool = True) -> Union[str, None]:
        if not file_hash: 
            logger.warning("跳过搜索: 空 Hash")
            return None
        
        params = f"f_shash={file_hash}&fs_similar=1" + ("&fs_covers=1" if is_cover else "")
        search_url = f"{self.domain}/?{params}"
        
        logger.debug(f"🔍 [Search] URL: {search_url}")

        try:
            start_time = time.time()
            response = self.session.get(search_url, timeout=60)
            elapsed = time.time() - start_time
            logger.debug(f"搜索响应: Status={response.status_code}, 耗时={elapsed:.2f}s")
            
            # ================= [新增] 响应内容预览 =================
            # 打印前 1000 个字符，足够看到 HTML 头部、Title 和关键的错误信息
            # 使用 !r 避免换行符破坏日志格式
            logger.debug(f"📜 [响应预览] {response.text[:1000]!r}")
            # =======================================================

            if "Your IP address has been" in response.text:
                logger.critical("🛑 检测到 IP 封禁页面")
                raise IpBlockedError("IP 被 E-Hentai 封禁")

            # 解析结果
            result_url = self._parse_search_result(response.text)
            if result_url:
                logger.info(f"✅ 找到匹配: {result_url}")
                return result_url
            else:
                logger.debug("未找到匹配结果 (NO_MATCH)")
                return "NO_MATCH"

        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ 搜索请求超时或失败: {e}")
            return None

    def _parse_search_result(self, html_content: str) -> Optional[str]:
        """从搜索结果 HTML 中提取画廊 URL"""
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
        从压缩包中提取目标图片
        Returns: (extracted_file_path, error_code)
        """
        try:
            if zipfile.is_zipfile(archive_path):
                handler = zipfile.ZipFile(archive_path, 'r')
            elif rarfile and rarfile.is_rarfile(archive_path):
                handler = rarfile.RarFile(archive_path, 'r')
            else:
                logger.warning(f"不支持的压缩格式: {archive_path.suffix}")
                return None, "UNSUPPORTED"
            
            with handler:
                file_list = handler.namelist()
                imgs = sorted([f for f in file_list if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
                
                if not imgs: 
                    logger.warning(f"压缩包内无图片: {archive_path.name}")
                    return None, "NO_IMAGES"

                # 策略选择
                if target_mode == 'cover':
                    target_img = imgs[0]
                    logger.debug(f"提取封面 (第1张): {target_img}")
                else: 
                    target_index = 9 if len(imgs) >= 10 else -1
                    target_img = imgs[target_index]
                    logger.debug(f"提取内页 (Index {target_index}): {target_img}")
                
                extract_path = temp_dir / Path(target_img).name
                # 安全性：防止路径遍历
                if '..' in str(extract_path):
                     return None, "FILE_ERROR"

                with open(extract_path, 'wb') as f_out:
                    f_out.write(handler.read(target_img))
                
                return extract_path, "OK"

        except (zipfile.BadZipFile, Exception) as e:
            if rarfile and isinstance(e, rarfile.Error):
                logger.error(f"❌ RAR Error ({archive_path.name}): {e}")
            else:
                logger.error(f"❌ Archive Error ({archive_path.name}): {e}")
            return None, "FILE_ERROR"

    def process_archive(self, archive_path: Union[str, Path], target: str = 'cover') -> Union[str, None]:
        archive_path = Path(archive_path)
        if not archive_path.exists():
            logger.error(f"文件不存在: {archive_path}")
            return None

        logger.debug(f"📂 处理压缩包: {archive_path.name} (模式: {target})")

        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_path, status = self._extract_image_from_archive(archive_path, target, Path(temp_dir))
            
            if extracted_path:
                f_hash = self.calculate_sha1(extracted_path)
                return self.search_by_hash(f_hash, is_cover=(target == 'cover'))
            else:
                return status

    def get_gallery_metadata(self, gallery_url: str) -> Optional[Dict]:
        match = re.search(r'/g/(\d+)/([\w]+)', gallery_url)
        if not match:
            return None
        
        gid, token = int(match.group(1)), match.group(2)
        payload = {"method": "gdata", "gidlist": [[gid, token]], "namespace": 1}

        try:
            res = self.session.post(self.api_url, json=payload, timeout=30)
            data = res.json()
            
            if not data.get('gmetadata'):
                return None
                
            gmeta = data['gmetadata'][0]
            title = html.unescape(gmeta.get('title_jpn') or gmeta.get('title'))
            tags = gmeta.get('tags', [])
            
            if category := gmeta.get('category'):
                tags.append(f"reclass:{category.lower()}")
            
            return {"title": title, "tags": tags}

        except Exception as e:
            logger.warning(f"⚠️ 获取元数据失败: {e}")
            return None