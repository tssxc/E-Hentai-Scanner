# modules/translator.py
import json
from pathlib import Path
from typing import List, Union

class TagTranslator:
    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self.data = self._load_database()

    def _load_database(self) -> List:
        if not self.db_path.exists():
            return []
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                return content.get('data', [])
        except Exception:
            return []

    def translate_tags(self, tags):
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
