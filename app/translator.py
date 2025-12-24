# app/translator.py
import json
import logging
from pathlib import Path
from typing import List, Union

logger = logging.getLogger(__name__)

class TagTranslator:
    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self._data = None  # 内部缓存，初始为空

    @property
    def data(self) -> List:
        """懒加载属性：首次访问时才读取文件"""
        if self._data is None:
            self._data = self._load_database()
        return self._data

    def _load_database(self) -> List:
        if not self.db_path.exists():
            return []
        try:
            logger.debug(f"📖 [LazyLoad] 正在加载翻译库: {self.db_path.name}")
            with open(self.db_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                data = content.get('data', [])
                logger.debug(f"✅ 翻译库加载完毕，条目数: {len(data)}")
                return data
        except Exception as e:
            logger.error(f"❌ 加载翻译库失败: {e}")
            return []

    def translate_tags(self, tags):
        # 访问 self.data 会触发懒加载
        if not self.data or not tags:
            return tags
            
        translated_tags = []
        for tag_str in tags:
            parts = tag_str.split(':', 1)
            namespace, key = parts if len(parts) == 2 else ('misc', tag_str)
            new_namespace, new_key = namespace, key
            
            for ns_data in self.data:
                if ns_data.get('namespace') == namespace:
                    new_namespace = ns_data.get('frontMatters', {}).get('name', namespace)
                    tag_map = ns_data.get('data', {})
                    if key in tag_map:
                        new_key = tag_map[key].get('name', key)
                    break
            translated_tags.append(f"{new_namespace}:{new_key}")
        return translated_tags