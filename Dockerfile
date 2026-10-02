FROM python:3.11-slim

# Evitar que python genere archivos .pyc y forzar salida stdout/stderr sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar tgcrypto y conectores async
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system bot && \
    useradd --system --gid bot --home-dir /app --no-create-home bot && \
    mkdir -p /app/sessions /app/assets && \
    chown -R bot:bot /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente del proyecto
COPY --chown=bot:bot . .

USER bot

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,time,sys; p='/tmp/bot-health'; sys.exit(0 if os.path.exists(p) and time.time()-os.path.getmtime(p)<60 else 1)"

# Comando de inicio del bot
CMD ["python", "-m", "bot.main"]
