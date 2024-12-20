FROM python:3.8-slim

# Instalar dependencias

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Descargar TA-Lib desde SourceForge y compilar
RUN --build=aarch64-unknown-linux-gnu
RUN curl -L "https://downloads.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz" -o ta-lib-0.4.0-src.tar.gz
RUN tar -xzf ta-lib-0.4.0-src.tar.gz
RUN cd ta-lib-0.4.0 && ./configure --prefix=/usr && make && make install
RUN rm -rf ta-lib-0.4.0 ta-lib-0.4.0-src.tar.gz

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
