# modules/network.py
import os
import re
import html
import logging
import hashlib
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Dict, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 可选依赖处理
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
        
        if not BeautifulSoup:
            logger.warning("⚠️ 建议安装 'beautifulsoup4' 以获得更好的解析稳定性")

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
            r = self.session.get(self.domain, timeout=10)
            if r.status_code == 200 and len(r.text) > 500:
                logger.info(f"✅ 网络连接正常 ({self.site_name})")
                return True
            logger.warning(f"⚠️ 连接响应异常 (Code: {r.status_code})")
            return False
        except Exception as e:
            logger.error(f"❌ 网络连接验证失败: {e}")
            return False

    def calculate_sha1(self, file_path: Union[str, Path]) -> Optional[str]:
        sha1 = hashlib.sha1()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(65536):  # 增大 buffer 大小
                    sha1.update(chunk)
            return sha1.hexdigest()
        except OSError as e:
            logger.error(f"❌ 计算哈希失败: {e}")
            return None

    def get_gallery_metadata(self, gallery_url: str) -> Optional[Dict]:
        match = re.search(r'/g/(\d+)/([\w]+)', gallery_url)
        if not match:
            return None
        
        gid, token = int(match.group(1)), match.group(2)
        payload = {"method": "gdata", "gidlist": [[gid, token]], "namespace": 1}

        try:
            res = self.session.post(self.api_url, json=payload, timeout=10)
            data = res.json()
            
            if not data.get('gmetadata'):
                raise ParseError("API 返回数据为空")
                
            gmeta = data['gmetadata'][0]
            title = html.unescape(gmeta.get('title_jpn') or gmeta.get('title'))
            tags = gmeta.get('tags', [])
            
            if category := gmeta.get('category'):
                tags.append(f"reclass:{category.lower()}")
            
            return {"title": title, "tags": tags}

        except Exception as e:
            raise NetworkError(f"API 请求异常: {e}")

    def search_by_hash(self, file_hash: str, is_cover: bool = True) -> Union[str, None]:
        if not file_hash: return None
        
        params = f"f_shash={file_hash}&fs_similar=1" + ("&fs_covers=1" if is_cover else "")
        search_url = f"{self.domain}/?{params}"
        
        logger.debug(f"🔍 [Search] Hash: {file_hash[:8]}... | Cover: {is_cover}")

        try:
            response = self.session.get(search_url, timeout=15)
            
            if "Your IP address has been" in response.text:
                raise IpBlockedError("IP 被 E-Hentai 封禁")

            if "/g/" in response.text:
                if BeautifulSoup:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag['href']
                        if "/g/" in href and (self.domain in href or href.startswith("/g/")):
                            return self.domain + href if href.startswith("/") else href
                else:
                    match = re.search(r'https?://e[x-]?hentai\.org/g/\d+/[a-z0-9]+/', response.text)
                    if match: return match.group(0)

            return "NO_MATCH"

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"搜索请求失败: {e}")

    def process_archive(self, archive_path: Union[str, Path], target: str = 'cover') -> Union[str, None]:
        archive_path = Path(archive_path)
        if not archive_path.exists():
            return None

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 打开压缩包
                if zipfile.is_zipfile(archive_path):
                    handler = zipfile.ZipFile(archive_path, 'r')
                elif rarfile and rarfile.is_rarfile(archive_path):
                    handler = rarfile.RarFile(archive_path, 'r')
                else:
                    return "UNSUPPORTED"
                
                with handler:
                    file_list = handler.namelist()
                    # 筛选图片
                    imgs = sorted([f for f in file_list if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
                    
                    if not imgs: return "NO_IMAGES"

                    # 策略选择
                    if target == 'cover':
                        target_img = imgs[0]
                        is_cover_search = True
                    else: # second (第10张或最后一张)
                        target_index = 9 if len(imgs) >= 10 else -1
                        target_img = imgs[target_index]
                        is_cover_search = False
                    
                    # 提取并计算哈希
                    extract_path = temp_path / Path(target_img).name
                    with open(extract_path, 'wb') as f_out:
                        f_out.write(handler.read(target_img))
                    
                    f_hash = self.calculate_sha1(extract_path)
                    return self.search_by_hash(f_hash, is_cover=is_cover_search)

        except (zipfile.BadZipFile, Exception) as e:
            # 如果是 rarfile.Error 需要确保 rarfile 已导入
            if rarfile and isinstance(e, rarfile.Error):
                logger.error(f"❌ RAR Error: {e}")
            else:
                logger.error(f"❌ Archive Error: {e}")
            raise ParseError(f"处理出错: {e}")