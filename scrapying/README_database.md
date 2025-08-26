# 統一數據庫管理模組使用說明

## 概述

為了統一管理所有爬蟲程式的SQLite數據庫連接，我創建了`database.py`統一數據庫管理模組。所有爬蟲現在都使用這個統一的模組來處理數據庫操作。

## 文件結構

```
scrapying/
├── database.py          # 統一數據庫管理模組
├── news.db             # SQLite數據庫文件
├── chinatimes/
│   └── main.py         # 中國時報爬蟲（已更新）
├── tvbs/
│   └── main.py         # TVBS爬蟲（已更新）
├── setn/
│   └── main.py         # 三立新聞爬蟲（已更新）
└── ltn/
    └── main.py         # 自由時報爬蟲（已更新）
```

## database.py 主要功能

### NewsDatabase 類

- **自動初始化**：自動創建數據庫表結構
- **連接管理**：使用上下文管理器自動處理連接的開啟和關閉
- **插入操作**：
  - `insert_news_item(news_item)` - 插入單條新聞
  - `insert_news_batch(news_items)` - 批量插入新聞
- **查詢操作**：
  - `news_exists(news_id)` - 檢查新聞是否已存在
  - `get_news_by_source(news_name)` - 根據來源獲取新聞
  - `get_latest_news(limit)` - 獲取最新新聞
  - `get_news_count_by_source()` - 統計各來源新聞數量
- **維護操作**：
  - `delete_news_by_id(news_id)` - 刪除指定新聞
  - `cleanup_old_news(days)` - 清理舊新聞

### 全域實例

```python
from database import news_db  # 直接使用預設實例
```

### 向後兼容函數

為了不影響現有代碼，提供了兼容性函數：
- `get_connection()` - 獲取數據庫連接
- `create_news_table()` - 創建表（實際上已自動創建）
- `insert_news_to_db(cursor, news_items)` - 批量插入（兼容舊接口）

## 使用範例

### 基本使用
```python
from database import news_db

# 插入單條新聞
news_item = {
    "id": "news001",
    "news_name": "中國時報",
    "author": "記者姓名",
    "title": "新聞標題",
    "url": "http://example.com",
    "publish_time": "2025-08-26 15:30:00"
}
success = news_db.insert_news_item(news_item)

# 檢查新聞是否存在
exists = news_db.news_exists("news001")

# 獲取統計信息
stats = news_db.get_news_count_by_source()
```

### 批量操作
```python
# 批量插入
news_items = [news_item1, news_item2, news_item3]
insert_count = news_db.insert_news_batch(news_items)
```

## 爬蟲程式更新

所有爬蟲程式已更新為使用統一數據庫模組：

1. **中國時報** (chinatimes/main.py)
   - 使用 `news_db.insert_news_batch()` 進行批量插入
   - 移除了手動的數據庫連接和表創建代碼

2. **TVBS** (tvbs/main.py)
   - 更新了 `news_exists()` 和 `insert_news()` 函數
   - 使用統一的數據庫接口

3. **三立新聞** (setn/main.py)
   - 直接使用 `news_db.news_exists()` 和 `news_db.insert_news_item()`

4. **自由時報** (ltn/main.py)
   - 更新了數據庫檢查和插入邏輯

## 優勢

1. **統一管理**：所有數據庫操作都通過同一個模組處理
2. **自動連接管理**：使用上下文管理器，避免連接洩漏
3. **錯誤處理**：統一的錯誤處理機制
4. **擴展性**：易於添加新功能和維護
5. **向後兼容**：現有代碼無需大幅修改

## 測試

可以運行 `python scrapying/database.py` 來測試數據庫模組的基本功能。

或者分別執行各個爬蟲來測試：
- `pipenv run python scrapying/chinatimes/main.py`
- `pipenv run python scrapying/tvbs/main.py`
- `pipenv run python scrapying/setn/main.py`
- `pipenv run python scrapying/ltn/main.py`

## 數據庫表結構

```sql
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    news_name TEXT,
    author TEXT,
    title TEXT,
    url TEXT,
    publish_time TEXT,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

所有爬蟲都使用這個統一的表結構存儲新聞資料。
