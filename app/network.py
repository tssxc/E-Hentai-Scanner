# app/network.py
from pathlib import Path
import re
import html
import logging
from typing import Optional, Dict, Union
from functools import lru_cache

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import IpBlockedError
from .archive_processor import ArchiveProcessor

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)

class EHentaiHashSearcher:
    def __init__(self, cookies: Optional[Dict] = None):
        # 1. 初始化网络会话
        self.session = requests.Session()
        self._setup_session(cookies)
        
        # 根据 Cookie 判断是表站还是里站
        self.domain = "https://exhentai.org" if cookies and cookies.get('igneous') != 'mystery' else "https://e-hentai.org"
        self.api_url = "https://api.e-hentai.org/api.php"
        
        # 2. 初始化本地归档处理器
        self.processor = ArchiveProcessor()
        
        # 3. [优化] 简单的内存缓存，避免重复请求相同的画廊元数据
        self._metadata_cache = {}

    def _setup_session(self, cookies):
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        })
        # 增加重试策略
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        if cookies:
            self.session.cookies.update(cookies)
        
        # 强制设置 nw=1 (跳过成人警告)
        self.session.cookies.set('nw', '1', domain='.e-hentai.org')
        self.session.cookies.set('nw', '1', domain='.exhentai.org')

    def process_archive(self, archive_path: Union[str, object], target: str = 'cover') -> Union[str, None]:
        """
        处理归档文件：计算 Hash 或 提取标题 -> 搜索
        """
        archive_path = Path(archive_path)

        # === 纯标题搜索模式 ===
        if target == 'title':
            from .utils import parse_gallery_title
            
            # 解析文件名获取核心标题
            parsed_info = parse_gallery_title(archive_path.stem)
            keyword = parsed_info.get('title')
            
            # 兜底：如果解析结果太短，使用文件名
            if not keyword or len(keyword) < 2:
                keyword = archive_path.stem
            
            logger.debug(f"🔍 [Scanner] 标题模式处理: {keyword}")
            return self.search_by_keyword(keyword)

        # === Hash 搜索模式 ===
        f_hash, status = self.processor.get_file_hash(archive_path, target_mode=target)
        
        if status != "OK":
            return status

        return self.search_by_hash(f_hash, is_cover=(target == 'cover'))

    def search_by_hash(self, file_hash: str, is_cover: bool = True) -> Union[str, None]:
        if not file_hash: return None
        
        params = f"f_shash={file_hash}&fs_similar=1" + ("&fs_covers=1" if is_cover else "")
        search_url = f"{self.domain}/?{params}"
        
        logger.debug(f"🔍 [Network] Hash搜索: {file_hash[:8]}... | Mode: {'Cover' if is_cover else 'Page'}")

        try:
            response = self.session.get(search_url, timeout=30)
            
            if "Your IP address has been" in response.text:
                raise IpBlockedError("IP 被 E-Hentai 封禁")

            result_url = self._parse_search_result(response.text)
            if result_url:
                logger.debug(f"✅ [Network] 找到匹配: {result_url}")
                return result_url
            else:
                logger.debug(f"⚪ [Network] 未找到匹配 (No Match)")
                return "NO_MATCH"
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ [Network] 请求失败: {e}")
            return None

    def search_by_keyword(self, keyword: str) -> Union[str, None]:
        if not keyword: return None
        
        logger.debug(f"🔍 [Network] 文本搜索: {keyword}")
        params = {"f_search": keyword, "f_apply": "Apply Filter"}

        try:
            response = self.session.get(self.domain + "/", params=params, timeout=30)
            if "Your IP address has been" in response.text:
                raise IpBlockedError("IP 被 E-Hentai 封禁")

            result_url = self._parse_search_result(response.text)
            if result_url:
                logger.info(f"✅ [Network] 文本匹配成功: {result_url}")
                return result_url
            else:
                logger.debug(f"⚪ [Network] 文本未找到匹配")
                return "NO_MATCH"
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ [Network] 搜索请求失败: {e}")
            return None

    def get_gallery_metadata(self, gallery_url: str) -> Optional[Dict]:
        """根据 URL 获取元数据 (带缓存)"""
        match = re.search(r'/g/(\d+)/([\w]+)', gallery_url)
        if not match: return None
        
        gid, token = int(match.group(1)), match.group(2)
        cache_key = f"{gid}_{token}"

        # [优化] 检查缓存
        if cache_key in self._metadata_cache:
            logger.debug(f"⚡ [Cache] 命中元数据缓存: {gid}")
            return self._metadata_cache[cache_key]

        logger.debug(f"☁️ [API] 获取元数据: GID={gid}")

        payload = {
            "method": "gdata",
            "gidlist": [[gid, token]],
            "namespace": 1
        }

        try:
            res = self.session.post(self.api_url, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            
            if not data.get('gmetadata'): 
                logger.warning(f"⚠️ [API] 未返回 gmetadata 数据")
                return None
            
            gmeta = data['gmetadata'][0]
            
            title_jpn = html.unescape(gmeta.get('title_jpn') or "")
            title_en = html.unescape(gmeta.get('title') or "")
            final_title = title_jpn if title_jpn else title_en
            
            tags = gmeta.get('tags', [])
            if category := gmeta.get('category'):
                tags.append(f"reclass:{category.lower()}")
            
            result = {
                "title": final_title,
                "title_jpn": title_jpn,
                "title_en": title_en,
                "tags": tags,
                "uploader": gmeta.get('uploader'),
                "category": category
            }
            
            # [优化] 写入缓存
            self._metadata_cache[cache_key] = result
            return result

        except Exception as e:
            logger.warning(f"⚠️ [API] 获取元数据异常: {e}")
            return None

    def _parse_search_result(self, html_content: str) -> Optional[str]:
        """解析搜索结果页面"""
        if "/g/" not in html_content:
            return None

        # 优先使用 BeautifulSoup 解析，更准确
        if BeautifulSoup:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                # 查找 class="gl3c glname" 的 div (PC端) 或者直接查找链接
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    # 匹配 /g/12345/abcdef/ 格式
                    if re.search(r'/g/\d+/[a-z0-9]+', href):
                        if self.domain in href:
                            return href
                        elif href.startswith("/"):
                            return self.domain + href
            except Exception:
                pass

        # 正则兜底
        match = re.search(r'https?://e[x-]?hentai\.org/g/\d+/[a-z0-9]+/', html_content)
        if match: return match.group(0)
        
        return None