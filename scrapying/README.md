# 新聞爬蟲統一架構

這個專案提供了一個可擴充和維護的新聞爬蟲基礎架構，讓所有新聞網站的爬蟲都可以繼承統一的格式。

## 架構特點

### 1. 基礎類別 (`base_scraper.py`)
- **統一介面**: 所有爬蟲繼承相同的基礎功能
- **日期檢查**: 自動檢查新聞是否為當天
- **錯誤處理**: 完整的錯誤處理和日誌記錄
- **並行處理**: 支援多網址並行請求
- **資料庫整合**: 統一的資料庫操作介面

### 2. 管理器 (`scraper_manager.py`)
- **統一管理**: 可以註冊和管理多個爬蟲
- **批量執行**: 支援並行執行所有爬蟲
- **結果統計**: 自動統計執行結果
- **錯誤容錯**: 單一爬蟲失敗不影響其他爬蟲

### 3. 統一資料庫 (`database.py`)
- **連接管理**: 統一的資料庫連接管理
- **重複檢查**: 自動檢查新聞是否已存在
- **批量操作**: 支援批量插入提高效率

## 使用方式

### 創建新的爬蟲

```python
from base_scraper import BaseNewsScraper
from typing import List, Dict, Any

class YourNewsScraper(BaseNewsScraper):
    """您的新聞爬蟲"""
    
    def __init__(self):
        super().__init__(
            news_source="您的新聞源名稱",
            base_url="https://your-news-site.com",
            target_url="https://your-news-site.com/politics"
        )
    
    def get_next_page_url(self, current_page: int) -> str:
        """獲取下一頁網址"""
        return f"{self.target_url}?page={current_page}"
    
    async def parse_news_list(self, html_content: str) -> List[Dict[str, Any]]:
        """解析新聞列表頁面"""
        # 實作您的新聞列表解析邏輯
        # 返回格式: [{"id": "", "title": "", "url": "", "date": ""}]
        pass
    
    async def parse_news_detail(self, html_content: str, news_info: Dict[str, Any]) -> Dict[str, Any]:
        """解析新聞詳細內容"""
        # 實作您的新聞詳情解析邏輯
        # 返回格式: {"id": "", "title": "", "content": "", "author": "", "date": "", "source": ""}
        pass
```

### 使用管理器執行爬蟲

```python
from scraper_manager import ScraperManager
from your_scraper import YourNewsScraper

async def main():
    # 創建管理器
    manager = ScraperManager()
    
    # 註冊爬蟲
    manager.register_scraper("YourNews", YourNewsScraper())
    
    # 執行所有爬蟲
    results = await manager.run_all_scrapers(max_pages=5)
    
    # 顯示結果
    manager.print_summary()

# 執行
import asyncio
asyncio.run(main())
```

### 單獨使用爬蟲

```python
from your_scraper import YourNewsScraper

async def main():
    scraper = YourNewsScraper()
    result = await scraper.run(max_pages=3)
    print(f"執行結果: {result}")

import asyncio
asyncio.run(main())
```

## 現有爬蟲

### 已實作的爬蟲
- **LTN**: 自由時報政治新聞
- **TVBS**: TVBS政治新聞  
- **SETN**: 三立新聞政治新聞
- **中國時報**: 中國時報政治新聞

### 爬蟲特性
- ✅ 只抓取當天新聞
- ✅ 自動去重複
- ✅ 統一資料庫儲存
- ✅ 錯誤處理和重試
- ✅ 日誌記錄

## 資料庫結構

```sql
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    news_name TEXT NOT NULL,
    author TEXT,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    publish_time TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 目錄結構

```
scrapying/
├── base_scraper.py         # 基礎爬蟲類別
├── scraper_manager.py      # 爬蟲管理器
├── database.py            # 統一資料庫模組
├── ltn_scraper_new.py     # LTN爬蟲(新版)
├── chinatimes/main.py     # 中國時報爬蟲
├── tvbs/main.py          # TVBS爬蟲
├── setn/main.py          # SETN爬蟲
├── ltn/main.py           # LTN爬蟲
└── news.db               # SQLite資料庫
```

## 優勢

### 1. 可維護性
- **統一介面**: 所有爬蟲遵循相同的結構和方法
- **模組化設計**: 功能分離，易於維護和擴充
- **錯誤隔離**: 單一爬蟲問題不影響整體系統

### 2. 可擴充性
- **抽象設計**: 新增爬蟲只需實作必要的方法
- **配置靈活**: 可以輕鬆調整參數和行為
- **功能豐富**: 內建常用功能，減少重複代碼

### 3. 效能優化
- **並行處理**: 支援多爬蟲並行執行
- **批量操作**: 資料庫批量插入提高效率
- **智慧去重**: 自動檢查避免重複抓取

### 4. 監控和除錯
- **詳細日誌**: 完整的執行日誌記錄
- **統計報告**: 自動生成執行統計
- **錯誤追蹤**: 詳細的錯誤資訊和堆疊追蹤

## 使用範例

### 執行所有爬蟲
```bash
cd scrapying
python scraper_manager.py
# 選擇 1: 執行所有爬蟲
```

### 檢查資料庫統計
```bash
pipenv run python -c "from database import news_db; print(news_db.get_news_count_by_source())"
```

### 執行單一爬蟲（舊版相容）
```bash
pipenv run python chinatimes/main.py
pipenv run python tvbs/main.py
pipenv run python setn/main.py
pipenv run python ltn/main.py
```

這個架構讓新聞爬蟲的開發、維護和擴充變得更加簡單和統一！
