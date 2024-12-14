FROM python:3.11-slim

# Instalar dependencias para compilar
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget build-essential gcc make autoconf automake libtool pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Descargar y descomprimir TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz

# Cambiar al directorio TA-Lib
WORKDIR /app/ta-lib-0.4.0

# Configurar, compilar e instalar
RUN ./configure --prefix=/usr && make && make install

# Limpiar
WORKDIR /app
RUN rm -rf ta-lib-0.4.0 ta-lib-0.4.0-src.tar.gz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
