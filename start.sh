#!/bin/bash
# 安装依赖
pip install -r requirements.txt

# 如果数据库不存在，初始化（可选）
python -c "from database import create_connection; create_connection()"

# 启动 API
uvicorn main:app --host 0.0.0.0 --port 10000