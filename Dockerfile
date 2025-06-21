FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    netbase \
    python3-aiohttp

COPY requirements.txt /temp/requirements.txt
COPY . .

RUN /bin/sh
