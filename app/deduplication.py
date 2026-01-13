# app/deduplication.py
import logging
import uuid
from collections import defaultdict
from typing import List, Dict

from .utils import parse_gallery_title
from .archive_processor import ArchiveProcessor
from .phash_tool import PHashTool

logger = logging.getLogger(__name__)

class DeduplicationManager:
    """
    高级多维查重管理器
    支持 URL 分组和 pHash 视觉相似度分组
    """
    def __init__(self, db_manager):
        self.db = db_manager
        self.processor = ArchiveProcessor()
        # pHash 汉明距离阈值 (<=5 视为同一张图)
        self.phash_threshold = 5

    def run(self, progress_callback=None) -> int:
        if progress_callback: progress_callback('log', "📊 正在读取数据库记录...")
        records = self.db.get_success_records()
        
        if len(records) < 2:
            return 0

        all_duplicate_records = []
        processed_file_paths = set()

        # ================= Phase 1: URL 分组 =================
        if progress_callback: progress_callback('log', "🔍 [Phase 1] URL 精确查重...")
        
        url_map = defaultdict(list)
        for r in records:
            if r.get('gallery_url'):
                url_map[r['gallery_url']].append(r)
        
        url_group_count = 0
        for url, group in url_map.items():
            if len(group) > 1:
                group_id = f"URL-{uuid.uuid4().hex[:8]}"
                url_group_count += 1
                for item in group:
                    all_duplicate_records.append({
                        **item,
                        'group_id': group_id,
                        'type': 'URL_MATCH',
                        'score': 1.0
                    })
                    processed_file_paths.add(item['file_path'])

        # ================= Phase 2: pHash 视觉分组 =================
        if not PHashTool.is_available():
            logger.warning("⚠️ 缺少依赖，跳过 pHash 查重")
            self.db.store_dedup_results(all_duplicate_records)
            return len(all_duplicate_records)

        if progress_callback: progress_callback('log', "👁️ [Phase 2] pHash 视觉查重 (按作者分组)...")
        
        # 排除已被 URL 分组命中的文件
        candidates = [r for r in records if r['file_path'] not in processed_file_paths]
        
        # 按作者分组
        author_groups = defaultdict(list)
        for r in candidates:
            info = parse_gallery_title(r['file_name'])
            key = "Misc"
            if info.get('artist'): key = f"Artist:{info['artist']}"
            elif info.get('group'): key = f"Group:{info['group']}"
            author_groups[key].append(r)
        
        phash_cache = {}
        phash_group_count = 0
        
        total_groups = len(author_groups)
        curr_group_idx = 0

        for key, items in author_groups.items():
            curr_group_idx += 1
            if len(items) < 2: continue
            
            if progress_callback and curr_group_idx % 10 == 0:
                progress_callback('log', f"Processing {curr_group_idx}/{total_groups}: {key}")

            # 并查集初始化
            parent = list(range(len(items)))
            def find(i):
                if parent[i] != i: parent[i] = find(parent[i])
                return parent[i]
            def union(i, j):
                root_i, root_j = find(i), find(j)
                if root_i != root_j: parent[root_i] = root_j

            # 组内两两比对 (对于单文档重复3次以上的情况：A=B, B=C -> A,B,C 一组)
            has_merge = False
            for i in range(len(items)):
                p1 = self._get_phash(items[i]['file_path'], phash_cache)
                if not p1: continue
                
                for j in range(i + 1, len(items)):
                    p2 = self._get_phash(items[j]['file_path'], phash_cache)
                    if not p2: continue
                    
                    dist = PHashTool.calculate_distance(p1, p2)
                    if dist <= self.phash_threshold:
                        union(i, j)
                        has_merge = True

            if has_merge:
                # 收集分组
                clusters = defaultdict(list)
                for i in range(len(items)):
                    root = find(i)
                    clusters[root].append(items[i])
                
                for root, cluster_items in clusters.items():
                    if len(cluster_items) > 1:
                        group_id = f"PHASH-{uuid.uuid4().hex[:8]}"
                        phash_group_count += 1
                        for item in cluster_items:
                            # 重新计算相对于组内第一个元素的相似度 (仅作参考)
                            base_phash = self._get_phash(cluster_items[0]['file_path'], phash_cache)
                            curr_phash = self._get_phash(item['file_path'], phash_cache)
                            dist = PHashTool.calculate_distance(base_phash, curr_phash)
                            score = PHashTool.get_similarity_score(dist)
                            
                            all_duplicate_records.append({
                                **item,
                                'group_id': group_id,
                                'type': 'PHASH_MATCH',
                                'score': score
                            })

        msg = f"查重结束: {url_group_count} 个 URL 组, {phash_group_count} 个 pHash 组"
        logger.info(msg)
        if progress_callback: progress_callback('log', msg)

        # ================= Phase 3: 保存 =================
        self.db.store_dedup_results(all_duplicate_records)
        return len(all_duplicate_records)

    def _get_phash(self, path, cache):
        if path in cache: return cache[path]
        val = self.processor.get_image_phash(path)
        cache[path] = val
        return val