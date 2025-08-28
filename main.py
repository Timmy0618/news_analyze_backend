#!/usr/bin/env python3
"""
新聞分析系統主程式
啟動整合了 Scheduler 的 FastAPI 應用
"""

import argparse
import os
import uvicorn
from dotenv import load_dotenv
from api.app import app

# 載入環境變數
load_dotenv()

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="新聞分析系統主程式")
    parser.add_argument("--host", default="0.0.0.0", help="服務器主機")
    parser.add_argument("--port", type=int, default=8000, help="服務器端口")
    parser.add_argument("--interval", type=int, help="爬蟲執行間隔（小時）")
    parser.add_argument("--reload", action="store_true", help="開發模式：自動重載")
    parser.add_argument("--log-level", default="info", help="日誌級別")
    
    args = parser.parse_args()
    
    # 設定排程間隔環境變數
    if args.interval:
        os.environ['SCHEDULER_INTERVAL'] = str(args.interval)
        print(f"📅 設定爬蟲執行間隔: {args.interval} 小時")
    
    # 顯示啟動信息
    print("🚀 新聞分析系統")
    print("=" * 50)
    print(f"服務器地址: http://{args.host}:{args.port}")
    print(f"API 文檔: http://{args.host}:{args.port}/docs")
    print(f"排程間隔: {os.getenv('SCHEDULER_INTERVAL', '24')} 小時")
    print("=" * 50)
    
    # 啟動 FastAPI 應用（包含內建 Scheduler）
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True
    )

if __name__ == "__main__":
    main()
