FROM python:3.12-slim

# Variables d'environnement Python (logs non bufferisés, pas de .pyc)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dépendances en premier (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif
COPY bot.py .

# La base SQLite vit dans /data (volume persistant monté côté hôte)
ENV DELPHI_DB_PATH=/data/delphi.db
VOLUME ["/data"]

# Utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 delphi && \
    mkdir -p /data && \
    chown -R delphi:delphi /app /data
USER delphi

CMD ["python", "-u", "bot.py"]
