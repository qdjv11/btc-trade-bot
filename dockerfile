# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# railway.toml (Railway deployment config)
[build]
builder = "DOCKERFILE"

[deploy]
startCommand = "python live_trading_bot.py"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

# Install TA-Lib dependencies
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
