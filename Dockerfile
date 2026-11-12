FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 WABOT_DB_PATH=/data/wabot.db

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY modamayor ./modamayor
COPY wabot ./wabot
COPY groundtruth ./groundtruth
RUN pip install --default-timeout=60 --retries=5 -e .

RUN useradd --system --uid 10001 wabot && mkdir /data && chown wabot /data
USER wabot
VOLUME /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "wabot.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
