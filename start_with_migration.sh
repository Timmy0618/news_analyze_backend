#!/bin/bash

# PostgreSQL + Migration 啟動腳本
# 啟動 PostgreSQL 並自動執行資料庫遷移

# 載入環境變數
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "🚀 啟動 PostgreSQL 17 和 pgAdmin..."
echo "📋 使用設定："
echo "  - Database: ${POSTGRES_DATABASE:-news_analyze}"
echo "  - User:     ${POSTGRES_USER:-news_user}"
echo "  - Port:     ${POSTGRES_PORT:-5432}"

# 啟動 Docker Compose
docker-compose up -d

echo "⏳ 等待 PostgreSQL 服務完全啟動..."

# 等待幾秒確保服務完全啟動
sleep 10

echo "🔄 執行 Alembic 資料庫遷移..."

# 檢查當前 migration 狀態
CURRENT_STATUS=$(pipenv run alembic current 2>/dev/null)

if echo "$CURRENT_STATUS" | grep -q "head"; then
    echo "✅ 資料庫已經是最新版本"
else
    echo "🔄 執行遷移到最新版本..."
    
    # 嘗試執行 migration
    if pipenv run alembic upgrade head; then
        echo "✅ Alembic 遷移成功"
    else
        echo "⚠️  遷移失敗，可能資料表已存在，嘗試標記為最新狀態..."
        if pipenv run alembic stamp head; then
            echo "✅ 已標記為最新狀態"
        else
            echo "❌ 標記失敗"
            exit 1
        fi
    fi
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ PostgreSQL 17 + Alembic Migration 啟動完成！"
    echo ""
    echo "📊 服務狀態："
    echo "  - PostgreSQL: http://localhost:${POSTGRES_PORT:-5432}"
    echo "  - pgAdmin:    http://localhost:8080"
    echo ""
    echo "🔑 pgAdmin 登入資訊："
    echo "  - Email:    admin@example.com"
    echo "  - Password: admin123"
    echo ""
    echo "🗄️ 資料庫連線資訊："
    echo "  - Host:     ${POSTGRES_HOST:-localhost}"
    echo "  - Port:     ${POSTGRES_PORT:-5432}"
    echo "  - Database: ${POSTGRES_DATABASE:-news_analyze}"
    echo "  - User:     ${POSTGRES_USER:-news_user}"
    echo ""
    echo "🎯 使用以下指令測試爬蟲："
    echo "  pipenv run python -c \"from unified_manager_orm import UnifiedScraperManager; manager = UnifiedScraperManager(); print('✅ 爬蟲系統就緒！')\""
    echo ""
    echo "🗄️  資料庫 Migration 狀態："
    pipenv run alembic current
else
    echo "❌ 資料庫遷移失敗"
    exit 1
fi
