# 資料庫遷移指南

## 環境配置說明

### 1. 開發環境 (SQLite)
```bash
# 使用預設的 .env 配置
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=./news.db
```

### 2. 生產環境 (PostgreSQL)
```bash
# 複製 PostgreSQL 配置
cp .env.postgresql .env

# 或手動修改 .env 文件中的 DATABASE_TYPE
DATABASE_TYPE=postgresql
```

## 資料庫遷移步驟

### SQLite → PostgreSQL

1. **備份 SQLite 資料**
```bash
# 使用 db_manager.py 匯出資料
pipenv run python3 db_manager.py export --format json --output backup.json
```

2. **設置 PostgreSQL**
```sql
-- 在 PostgreSQL 中創建資料庫和使用者
CREATE DATABASE news_analyze;
CREATE USER news_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE news_analyze TO news_user;
```

3. **切換配置**
```bash
# 使用 PostgreSQL 配置
cp .env.postgresql .env
# 或編輯 .env 將 DATABASE_TYPE 改為 postgresql
```

4. **創建表格結構**
```bash
# 執行資料庫遷移（建表）
pipenv run python3 -c "
from database_orm import create_tables
create_tables()
print('PostgreSQL 表格創建完成')
"
```

5. **匯入資料**
```bash
# 使用 db_manager.py 匯入資料
pipenv run python3 db_manager.py import --format json --input backup.json
```

### PostgreSQL → SQLite

1. **匯出 PostgreSQL 資料**
```bash
pipenv run python3 db_manager.py export --format json --output backup.json
```

2. **切換到 SQLite**
```bash
# 編輯 .env 或使用預設配置
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=./news.db
```

3. **匯入資料**
```bash
pipenv run python3 db_manager.py import --format json --input backup.json
```

## 配置管理

### 查看當前配置
```bash
pipenv run python3 db_manager.py config
```

### 測試資料庫連接
```bash
pipenv run python3 db_manager.py test
```

### 開發/生產環境快速切換
```bash
# 開發環境 (SQLite)
cp .env.example .env

# 生產環境 (PostgreSQL)  
cp .env.postgresql .env
```

## 注意事項

1. **依賴套件**: PostgreSQL 需要 `psycopg2-binary` 套件（已安裝）
2. **連接測試**: 切換資料庫後務必測試連接
3. **資料備份**: 遷移前請務必備份資料
4. **環境變數**: 確保 PostgreSQL 連接參數正確
5. **權限設定**: 確認 PostgreSQL 使用者權限足夠

## 故障排除

### PostgreSQL 連接失敗
- 檢查 PostgreSQL 服務是否運行
- 確認連接參數 (host, port, user, password)
- 檢查防火牆設定

### SQLite 文件權限
- 確保 SQLite 檔案路徑可寫
- 檢查目錄權限

### 配置載入問題
- 確認 .env 文件存在且格式正確
- 檢查環境變數是否正確設定
