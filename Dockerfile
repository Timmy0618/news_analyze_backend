FROM python:3.10-slim

# 1. 安裝必要的系統套件
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    gcc \
    g++ \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* 

# 2. 安裝 pipenv
RUN pip install pipenv

# 3. 設定工作目錄
WORKDIR /app

# 4. 複製 Pipfile 和 Pipfile.lock
COPY Pipfile Pipfile.lock ./

# 5. 設定 pipenv 環境變數（讓 pipenv 在系統 Python 環境中安裝套件）
ENV PIPENV_VENV_IN_PROJECT=1
ENV PIPENV_SYSTEM=1

# 6. 安裝依賴套件
RUN pipenv install --deploy --system

# 7. 複製專案程式碼
COPY . .

# 8. 透過 Python 直接啟動 FastAPI（會讀取環境變數配置）
CMD ["python", "main.py"]
