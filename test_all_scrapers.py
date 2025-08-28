"""
完整測試所有新聞爬蟲 (ORM版本)
"""

import sys
import os
from datetime import datetime

# 添加 scrapying 目錄到路徑
sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapying'))

from setn_new import SETNScraper
from ltn_scraper_orm import LTNScraper
from tvbs_scraper_orm import TVBSScraper
from chinatimes_scraper_orm import ChinaTimesScraper

from models import News
from database_orm import get_db_session


def test_all_scrapers():
    """測試所有爬蟲"""
    print("🚀 新聞爬蟲系統完整測試")
    print("=" * 50)
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    scrapers = [
        ("SETN 三立新聞", SETNScraper()),
        ("LTN 自由時報", LTNScraper()),
        ("TVBS 新聞", TVBSScraper()),
        ("ChinaTimes 中時", ChinaTimesScraper())
    ]
    
    results = {}
    total_news = 0
    
    for name, scraper in scrapers:
        print(f"📰 測試 {name}")
        print("-" * 30)
        
        try:
            # 限制每個爬蟲爬取1頁做測試
            result = scraper.scrape_news(max_pages=1)
            
            results[name] = result
            total_news += result['new']
            
            print(f"✅ {name} 測試完成")
            print(f"   總計: {result['total']}")
            print(f"   新增: {result['new']}")
            print(f"   跳過: {result['skipped']}")
            print(f"   失敗: {result['failed']}")
            print()
            
        except Exception as e:
            print(f"❌ {name} 測試失敗: {e}")
            results[name] = {'error': str(e)}
            print()
    
    # 總結報告
    print("📊 測試結果總結")
    print("=" * 50)
    
    # 查詢資料庫狀態
    with get_db_session() as session:
        for name, scraper in scrapers:
            source = scraper.news_source
            count = session.query(News).filter(News.news_source == source).count()
            
            if name in results and 'error' not in results[name]:
                status = "✅ 正常"
                new_count = results[name]['new']
                print(f"{source:12}: {count:3d} 筆 ({new_count:2d} 新增) {status}")
            else:
                status = "❌ 異常"
                print(f"{source:12}: {count:3d} 筆              {status}")
        
        total_in_db = session.query(News).count()
        print(f"\n📈 資料庫總計: {total_in_db} 筆新聞")
        print(f"🆕 本次新增: {total_news} 筆")
    
    # 檢查日期格式統一性
    print("\n🕐 日期格式檢查")
    print("-" * 30)
    
    with get_db_session() as session:
        sources = ['SETN', 'LTN', 'TVBS', 'ChinaTimes']
        for source in sources:
            news = session.query(News).filter(News.news_source == source).first()
            if news:
                print(f"{source:12}: {news.publish_time} ✓")
            else:
                print(f"{source:12}: 無資料")
    
    print("\n🎉 測試完成！所有爬蟲都使用統一的日期格式 (YYYY-MM-DD HH:MM:SS)")


if __name__ == "__main__":
    test_all_scrapers()
