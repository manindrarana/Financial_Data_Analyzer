FROM python:3.10-slim
LABEL maintainer="Manindra Rana"
LABEL description="Prefect orchestration server with pinned dependencies"
RUN pip install --no-cache-dir prefect==3.7.7 fastapi==0.136.3 asyncpg==0.30.0
EXPOSE 4200
