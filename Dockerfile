FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget build-essential gcc make autoconf automake libtool pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Descargar y compilar TA-Lib
RUN wget https://downloads.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib-0.4.0 && \
    ./configure --prefix=/usr && \
    make && make install && \
    cd .. && rm -rf ta-lib-0.4.0 ta-lib-0.4.0-src.tar.gz

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
