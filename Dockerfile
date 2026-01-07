# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 系统依赖（按需增减；比如你用 psycopg2 连接 postgres）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*


# 先拷贝依赖文件，利用 docker layer cache
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 再拷贝项目代码
COPY . /app/

# 收集静态文件（生产推荐）
# 注意：这里需要 settings 能在构建时正常加载（不要依赖运行时才有的敏感变量）
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# 直接启动 gunicorn（替换 your_project.wsgi 为你的项目名）
CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
