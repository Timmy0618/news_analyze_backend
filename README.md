# 新聞分析系統 (News Analyze)

一個全面的台灣新聞爬蟲與 API 服務系統，支援多家主流新聞媒體的自動化抓取與 REST API 查詢。

## 📋 功能特色

- **多媒體新聞爬蟲**: 支援自由時報(LTN)、三立新聞(SETN)、TVBS、中國時報
- **批量資料處理**: 高效率的批量插入，提升資料庫操作效能
- **RESTful API**: 提供完整的新聞查詢 API 服務
- **自動排程器**: 支援定時自動執行爬蟲任務
- **資料庫支援**: 同時支援 PostgreSQL 和 SQLite
- **ORM 架構**: 使用 SQLAlchemy ORM 確保資料一致性

## 🛠 技術架構

- **後端框架**: FastAPI
- **資料庫**: PostgreSQL / SQLite (可配置)
- **ORM**: SQLAlchemy
- **爬蟲**: requests + BeautifulSoup
- **排程器**: asyncio
- **依賴管理**: pipenv

## 📦 安裝與設定

### 1. 環境需求

- Python 3.8+
- pipenv

### 2. 專案設定

```bash
# 克隆專案
git clone https://github.com/Timmy0618/news_analyze.git
cd news_analyze

# 安裝依賴
pipenv install

# 進入虛擬環境
pipenv shell
```

### 3. 環境變數配置

創建 `.env` 文件並設定以下變數：

```env
# 資料庫配置
DATABASE_TYPE=postgresql  # 或 sqlite
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=news_analyze
POSTGRES_USER=news_user
POSTGRES_PASSWORD=news_password_2024

# SQLite 配置（當 DATABASE_TYPE=sqlite 時）
SQLITE_DB_PATH=./news.db

# 排程器配置
SCHEDULER_INTERVAL=24  # 小時

# API 配置
API_PORT=8000
```

## 🚀 使用說明

### 命令行工具

#### 1. 爬蟲操作

```bash
# 執行所有爬蟲（預設 1 頁）
pipenv run python unified_manager_orm.py all

# 執行所有爬蟲（指定頁數）
pipenv run python unified_manager_orm.py all 3

# 執行特定爬蟲
pipenv run python unified_manager_orm.py ltn 2      # 自由時報 2 頁
pipenv run python unified_manager_orm.py setn 1     # 三立新聞 1 頁
pipenv run python unified_manager_orm.py tvbs 1     # TVBS 1 頁
pipenv run python unified_manager_orm.py chinatimes 1  # 中國時報 1 頁

# 查看資料庫統計
pipenv run python unified_manager_orm.py stats
```

#### 2. API 服務

```bash
# 啟動 API 服務（包含自動排程器）
pipenv run python main.py

# 或直接啟動 FastAPI 應用
pipenv run python -m api.app
```

### REST API 使用

API 服務啟動後，可通過以下端點進行操作：

#### 基本資訊

```bash
# 服務狀態
GET http://localhost:8000/

# 健康檢查
GET http://localhost:8000/health

# API 文檔
GET http://localhost:8000/docs
```

#### 新聞查詢

```bash
# 獲取新聞列表（支援分頁和過濾）
GET http://localhost:8000/news?page=1&per_page=20&source=LTN&search=政治

# 獲取最新新聞
GET http://localhost:8000/news/recent?limit=10&source=TVBS

# 獲取統計資訊
GET http://localhost:8000/stats
```

#### 排程器控制

```bash
# 查看排程器狀態
GET http://localhost:8000/scheduler/status

# 手動執行爬蟲
POST http://localhost:8000/scraper/run
```

### API 參數說明

#### `/news` 端點參數

| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| page | int | 頁碼 | 1 |
| per_page | int | 每頁數量 (1-100) | 20 |
| source | string | 新聞來源過濾 | 全部 |
| search | string | 標題搜尋關鍵字 | 無 |
| start_date | string | 開始日期 (YYYY-MM-DD) | 無 |
| end_date | string | 結束日期 (YYYY-MM-DD) | 無 |

#### 新聞來源代碼

- `LTN`: 自由時報
- `SETN`: 三立新聞
- `TVBS`: TVBS新聞
- `ChinaTimes`: 中國時報

## 🔧 系統架構

### 檔案結構

```
news_analyze/
├── api/                    # API 相關檔案
│   ├── __init__.py
│   ├── app.py             # FastAPI 應用主檔案
│   └── scheduler.py       # 分離的排程器模組
├── scrapying/             # 爬蟲模組
│   ├── setn_new.py        # SETN 爬蟲 (ORM 版本)
│   ├── ltn_scraper_orm.py # LTN 爬蟲 (ORM 版本)
│   ├── tvbs_scraper_orm.py # TVBS 爬蟲 (ORM 版本)
│   └── chinatimes_scraper_orm.py # 中國時報爬蟲 (ORM 版本)
├── base_scraper_orm.py    # 爬蟲基礎類別
├── unified_manager_orm.py # 統一爬蟲管理器
├── news_orm_db.py        # ORM 資料庫管理
├── database_orm.py       # 資料庫連線設定
├── models.py             # SQLAlchemy 模型
├── main.py               # 主程式入口
├── requirements.txt      # Python 依賴列表
├── Pipfile              # pipenv 配置
└── README.md            # 本說明文件
```

### 核心元件

1. **基礎爬蟲類別** (`base_scraper_orm.py`)
   - 提供統一的爬蟲介面
   - 支援批量資料插入
   - 錯誤處理與重試機制

2. **統一管理器** (`unified_manager_orm.py`)
   - 並行執行多個爬蟲
   - 統計資訊彙整
   - 資料庫狀態監控

3. **API 服務** (`api/app.py`)
   - RESTful API 端點
   - 自動文檔生成
   - 資料驗證與序列化

4. **排程器** (`api/scheduler.py`)
   - 定時執行爬蟲任務
   - 異步任務管理
   - 狀態監控

## 📊 效能特色

### 批量插入優化

系統採用批量插入策略，相比逐筆插入：

- **效能提升**: 減少資料庫連線次數
- **事務一致性**: 確保資料完整性
- **錯誤恢復**: 支援回退機制

### 排程器分離

- **模組化設計**: 排程器與 API 分離
- **生命周期管理**: 自動啟動與關閉
- **狀態監控**: 即時查看排程狀態

## 🐛 故障排除

### 常見問題

1. **資料庫連線失敗**
   ```bash
   # 檢查資料庫服務狀態
   sudo systemctl status postgresql
   
   # 檢查連線參數
   cat .env
   ```

2. **爬蟲執行失敗**
   ```bash
   # 查看詳細日誌
   pipenv run python unified_manager_orm.py ltn 1
   
   # 檢查網路連線
   curl -I https://news.ltn.com.tw
   ```

3. **API 無法啟動**
   ```bash
   # 檢查埠口是否被佔用
   lsof -i :8000
   
   # 使用不同埠口
   pipenv run uvicorn api.app:app --host 0.0.0.0 --port 8080
   ```

## 📝 日誌系統

系統會在 `logs/` 目錄下產生以下日誌檔案：

- `api.log`: API 服務日誌
- `scheduler.log`: 排程器日誌
- `scraper_*.log`: 各爬蟲日誌

日誌會自動按日輪轉，保留 7 天記錄。

## 🤝 貢獻指南

1. Fork 本專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📄 授權

本專案採用 MIT 授權 - 詳見 [LICENSE](LICENSE) 文件。

## 📞 聯絡資訊

- 作者: Timmy0618
- 專案連結: [https://github.com/Timmy0618/news_analyze](https://github.com/Timmy0618/news_analyze)

---

**注意**: 請確保在使用爬蟲功能時遵守各新聞網站的 robots.txt 規範和使用條款。