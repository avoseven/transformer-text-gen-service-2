# docker/Dockerfile
FROM python:3.10-slim

WORKDIR /code

# System依存関係のInstall
RUN apt-get update && \
    # 最低限必要なパッケージだけをインストールし、推奨パッケージはインストールしません
    apt-get install -y --no-install-recommends \
    # git \
    gcc \
    && rm -rf /var/lib/apt/lists/*  # updateにより保存された不要Packagesを削除してImage sizeを小さくする

# Python依存関係のInstall
COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port解放
EXPOSE 8000

# 起動Command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
