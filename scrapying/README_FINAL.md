# 新聞爬蟲管理系統

基於 BaseNewsScraper 架構的統一新聞爬蟲管理系統。

## 檔案結構

### 核心系統
- `base_scraper.py` - 基礎爬蟲抽象類別，所有爬蟲都繼承此類別
- `database.py` - 統一資料庫管理模組，支援新舊格式自動轉換
- `unified_manager.py` - 統一爬蟲管理器，提供互動式介面

### 可用爬蟲
- `setn_new.py` - SETN 新聞爬蟲（完全可用 ✅）
- `ltn_scraper_new.py` - LTN 新聞爬蟲（完全可用 ✅）

### 原始爬蟲（保留作為參考）
- `chinatimes/main.py` - 中國時報原始爬蟲（使用 requests）
- `tvbs/main.py` - TVBS 原始爬蟲（使用 requests）
- `setn/main.py` - SETN 原始爬蟲
- `ltn/main.py` - LTN 原始爬蟲

## 使用方法

### 啟動統一管理器
```bash
cd /Users/timmy0618/Code/project/news_analyze
pipenv run python scrapying/unified_manager.py
```

### 選項說明
1. 執行所有爬蟲 - 並行執行所有可用爬蟲
2. 執行單一爬蟲 - 選擇特定爬蟲執行
3. 查看可用爬蟲 - 列出所有註冊的爬蟲
4. 檢查資料庫統計 - 查看儲存的新聞統計
5. 退出

### 直接使用個別爬蟲
```python
import asyncio
from setn_new import SETNScraper

async def run_setn():
    scraper = SETNScraper()
    result = await scraper.run(max_pages=3)
    print(result)

asyncio.run(run_setn())
```

## 系統特色

- ✅ **統一管理介面** - 所有爬蟲使用相同介面
- ✅ **錯誤隔離機制** - 單一爬蟲失敗不影響其他
- ✅ **並行處理能力** - 支援同時執行多個爬蟲
- ✅ **詳細日誌記錄** - 完整的執行過程追蹤
- ✅ **自動重複過濾** - 避免重複儲存相同新聞
- ✅ **可擴展性設計** - 易於添加新的新聞來源

## 資料庫

使用 SQLite 資料庫 (`news.db`)，支援：
- 自動建立表格結構
- 新舊格式相容
- 智能 ID 提取（TVBS、中國時報、LTN、SETN）
- 重複檢查機制

## 新增爬蟲

要添加新的新聞來源：

1. 繼承 `BaseNewsScraper`
2. 實作必要的抽象方法：
   - `parse_news_list()` - 解析新聞列表
   - `parse_news_detail()` - 解析新聞詳情
   - `get_next_page_url()` - 獲取下一頁URL
3. 在 `unified_manager.py` 中註冊新爬蟲

## 注意事項

- 中國時報和 TVBS 的新架構版本因技術問題（CloudFlare 保護、複雜 AJAX）暫未完成
- 原始版本的中國時報和 TVBS 爬蟲仍然可用
- 建議使用 pipenv 環境執行所有爬蟲
