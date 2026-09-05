FROM python:3.10-slim
LABEL maintainer="Manindra Rana"
LABEL description="MLflow tracking server with pinned dependencies"
RUN pip install --no-cache-dir mlflow==3.15.2 anyio==4.14.2 gunicorn==26.2.0
EXPOSE 5000
