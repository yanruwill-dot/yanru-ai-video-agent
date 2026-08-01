FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIDEO_AGENT_FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8788
CMD ["sh", "-c", "python3 app.py --host 0.0.0.0 --port ${PORT:-8788}"]
