FROM python:3.12-slim

# Python environment (unbuffered logs, no .pyc files)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY bot.py .

# SQLite database lives in /data (persistent volume mounted from host)
ENV DELPHI_DB_PATH=/data/delphi.db
VOLUME ["/data"]

# Non-root user for security
RUN useradd -m -u 1000 delphi && \
    mkdir -p /data && \
    chown -R delphi:delphi /app /data
USER delphi

CMD ["python", "-u", "bot.py"]
