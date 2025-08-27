#!/usr/bin/env python3
"""
新聞爬蟲統一管理器 - 使用ORM版本
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any
import concurrent.futures
import threading

# 導入ORM版本的爬蟲
try:
    from scrapying.setn_new import SETNScraper
except ImportError:
    SETNScraper = None
    print("警告: SETN爬蟲導入失敗")

try:
    from scrapying.ltn_scraper_orm import LTNScraper  
except ImportError:
    LTNScraper = None
    print("警告: LTN爬蟲導入失敗")

try:
    from scrapying.tvbs_scraper_orm import TVBSScraper
except ImportError:
    TVBSScraper = None
    print("警告: TVBS爬蟲導入失敗")

try:
    from scrapying.chinatimes_scraper_orm import ChinaTimesScraper
except ImportError:
    ChinaTimesScraper = None
    print("警告: ChinaTimes爬蟲導入失敗")

from news_orm_db import NewsORMDatabase

news_orm_db = NewsORMDatabase()


class UnifiedScraperManager:
    """統一的新聞爬蟲管理器 - ORM版本"""
    
    def __init__(self):
        self.scrapers = {}
        self._initialize_scrapers()
    
    def _initialize_scrapers(self):
        """初始化所有可用的爬蟲"""
        if SETNScraper:
            self.scrapers['SETN'] = SETNScraper()
        
        if LTNScraper:
            self.scrapers['LTN'] = LTNScraper()
        
        if TVBSScraper:
            self.scrapers['TVBS'] = TVBSScraper()
        
        if ChinaTimesScraper:
            self.scrapers['ChinaTimes'] = ChinaTimesScraper()
        
        print(f"已初始化 {len(self.scrapers)} 個爬蟲: {list(self.scrapers.keys())}")
    
    def _scrape_single_source(self, name: str, scraper, max_pages: int = 1) -> tuple:
        """單一爬蟲執行函數"""
        try:
            print(f"🔄 開始執行 {name} 爬蟲...")
            result = scraper.scrape_news(max_pages=max_pages)
            print(f"✅ {name} 完成 - 總計:{result['total']}, 新增:{result['new']}, 跳過:{result['skipped']}, 失敗:{result['failed']}")
            return name, result
        except Exception as e:
            print(f"❌ {name} 爬蟲執行失敗: {e}")
            return name, {'error': str(e)}
    
    def run_all_scrapers(self, max_pages: int = 1) -> Dict[str, Any]:
        """並行執行所有爬蟲"""
        print(f"🚀 並行執行所有爬蟲 (每個爬蟲最多 {max_pages} 頁)")
        print("=" * 50)
        
        results = {}
        total_stats = {'total': 0, 'new': 0, 'skipped': 0, 'failed': 0}
        
        # 使用線程池並行執行所有爬蟲
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.scrapers)) as executor:
            # 提交所有爬蟲任務
            futures = {
                executor.submit(self._scrape_single_source, name, scraper, max_pages): name
                for name, scraper in self.scrapers.items()
            }
            
            # 等待所有任務完成
            for future in concurrent.futures.as_completed(futures):
                name, result = future.result()
                results[name] = result
                
                # 累計統計（只有成功的結果才計入）
                if 'error' not in result:
                    for key in total_stats:
                        if key in result and isinstance(result[key], int):
                            total_stats[key] += result[key]
        
        results['總計'] = total_stats
        print(f"\n📊 並行執行完成！總計: {total_stats}")
        return results
    
    def run_single_scraper(self, scraper_name: str, max_pages: int = 1) -> Dict[str, Any]:
        """執行單個爬蟲"""
        if scraper_name not in self.scrapers:
            available = list(self.scrapers.keys())
            raise ValueError(f"爬蟲 '{scraper_name}' 不存在。可用的爬蟲: {available}")
        
        print(f"執行 {scraper_name} 爬蟲 (最多 {max_pages} 頁)")
        scraper = self.scrapers[scraper_name]
        return scraper.scrape_news(max_pages=max_pages)
    
    def get_database_stats(self) -> Dict[str, Any]:
        """獲取資料庫統計信息"""
        print("資料庫統計信息:")
        print("-" * 30)
        
        total_count = news_orm_db.get_news_count()
        print(f"總新聞數: {total_count}")
        
        source_counts = news_orm_db.get_news_count_by_source()
        print("\n各來源統計:")
        for source, count in source_counts:
            print(f"  {source}: {count} 條新聞")
        
        return {
            'total_count': total_count,
            'source_counts': dict(source_counts)
        }
    
    def show_recent_news(self, limit: int = 10):
        """顯示最近的新聞"""
        print(f"\n最近 {limit} 條新聞:")
        print("-" * 50)
        
        recent_news = news_orm_db.get_recent_news(limit)
        for i, news in enumerate(recent_news, 1):
            print(f"{i:2d}. [{news['news_source']}] {news['title'][:60]}...")
            print(f"     作者: {news['author']} | 時間: {news['publish_time']}")


def main():
    """主函數"""
    print("新聞爬蟲統一管理系統 (ORM版本)")
    print("=" * 50)
    
    manager = UnifiedScraperManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'all':
            # 執行所有爬蟲
            max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            results = manager.run_all_scrapers(max_pages)
            
        elif command in ['setn', 'ltn', 'tvbs', 'chinatimes']:
            # 執行指定爬蟲
            max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            scraper_name = command.upper()
            if scraper_name == 'CHINATIMES':
                scraper_name = 'ChinaTimes'
            result = manager.run_single_scraper(scraper_name, max_pages)
            print(f"執行結果: {result}")
            
        elif command == 'stats':
            # 顯示統計
            manager.get_database_stats()
            manager.show_recent_news()
            return
            
        else:
            print("無效的命令")
            print("使用方式:")
            print("  python unified_manager_orm.py all [頁數]     # 執行所有爬蟲")
            print("  python unified_manager_orm.py setn [頁數]    # 執行SETN爬蟲")
            print("  python unified_manager_orm.py ltn [頁數]     # 執行LTN爬蟲")
            print("  python unified_manager_orm.py tvbs [頁數]    # 執行TVBS爬蟲")
            print("  python unified_manager_orm.py chinatimes [頁數]  # 執行中國時報爬蟲")
            print("  python unified_manager_orm.py stats         # 顯示統計信息")
            return
    else:
        # 默認執行所有爬蟲（1頁）
        results = manager.run_all_scrapers(1)
    
    # 顯示最終統計
    print("\n" + "=" * 50)
    print("最終統計:")
    manager.get_database_stats()
    manager.show_recent_news(5)


if __name__ == "__main__":
    main()
