# 基础镜像
FROM node:18-alpine AS builder

# 设置工作目录
WORKDIR /app

# 安装 Python
RUN apk add --no-cache python3 py3-pip

# 复制前端代码
COPY web-app/package*.json ./
COPY web-app/vite.config.ts ./
COPY web-app/tsconfig*.json ./
COPY web-app/index.html ./
COPY web-app/postcss.config.js ./
COPY web-app/tailwind.config.js ./
COPY web-app/src ./src

# 安装前端依赖
RUN npm install

# 构建前端
RUN npm run build


# 第二阶段：运行镜像
FROM python:3.11-slim

# 安装Node.js运行时
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制后端代码
COPY backend/ ./backend/
COPY web-app/dist ./web-app/dist

# 安装Python依赖
WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8000 3000

# 启动命令
CMD ["sh", "-c", "python run.py"]
