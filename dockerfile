FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
ENV PYTHONUNBUFFERED=1
LABEL maintainer="Manindra Rana"
LABEL description="Financial Data Analyzer - ELT Pipeline for Stock and Crypto Analysis"
LABEL version="1.0.0"
WORKDIR /app
RUN apt-get update && apt-get install -y python3 python3-pip python3-dev ca-certificates && ln -sf python3 /usr/bin/python && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "orchestration.orchestration"]
