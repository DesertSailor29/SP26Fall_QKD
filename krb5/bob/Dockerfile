FROM debian:trixie-slim
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-gssapi \
    libkrb5-3 \
    krb5-user \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --break-system-packages \
    --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python3", "src/server.py"]
