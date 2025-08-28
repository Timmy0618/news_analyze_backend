#!/usr/bin/env python3
"""
資料庫管理工具 - 簡化版本
提供配置顯示、連接測試、統計資訊
"""

import sys

def show_config():
    """顯示當前配置"""
    try:
        from config import Config
        
        print("=== 當前資料庫配置 ===")
        print(f"資料庫類型: {Config.DATABASE_TYPE}")
        print(f"資料庫 URL: {Config.get_database_url()}")
        print(f"除錯模式: {Config.DEBUG}")
        
        print("\n=== 爬蟲設定 ===")
        enabled_scrapers = Config.get_enabled_scrapers()
        print(f"啟用爬蟲: {', '.join(enabled_scrapers)}")
        print(f"最大併發數: {Config.MAX_CONCURRENT_SCRAPERS}")
        
    except Exception as e:
        print(f"❌ 配置載入失敗: {e}")

def test_connection():
    """測試資料庫連接和統計"""
    try:
        import database_orm
        from models import News
        from sqlalchemy.orm import sessionmaker
        
        print("=== 資料庫連接測試 ===")
        
        # 測試連接
        with database_orm.engine.connect() as conn:
            print("✅ 資料庫連接成功")
        
        # 統計資料
        Session = sessionmaker(bind=database_orm.engine)
        session = Session()
        
        total = session.query(News).count()
        print(f"📊 總新聞數: {total} 筆")
        
        if total > 0:
            # 各來源統計
            from sqlalchemy import func
            sources = session.query(
                News.news_source, 
                func.count(News.pk)
            ).group_by(News.news_source).all()
            
            print("\n各來源統計:")
            for source, count in sources:
                print(f"  {source}: {count} 筆")
                
            # 最新資料
            latest = session.query(News).order_by(News.create_time.desc()).first()
            if latest:
                print(f"\n📅 最新資料: {latest.create_time}")
                print(f"🏷️  最新來源: {latest.news_source}")
                print(f"📰 最新標題: {latest.title[:50]}...")
        
        session.close()
        
    except Exception as e:
        print(f"❌ 連接測試失敗: {e}")

def main():
    if len(sys.argv) < 2:
        print("使用方式:")
        print("  python3 db_manager.py config    # 顯示配置")
        print("  python3 db_manager.py test      # 測試連接")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'config':
        show_config()
    elif command == 'test':
        show_config()
        print()
        test_connection()
    else:
        print(f"未知命令: {command}")

if __name__ == "__main__":
    main()
