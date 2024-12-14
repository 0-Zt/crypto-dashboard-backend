FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para compilar TA-Lib
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget build-essential gcc make autoconf automake libtool pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Descargar y descomprimir TA-Lib
RUN wget https://downloads.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    ls

# Cambiar al directorio de TA-Lib y compilar/instalar
WORKDIR /app/ta-lib-0.4.0
RUN ./configure --prefix=/usr && \
    make && \
    make install

# Limpiar archivos de instalación
WORKDIR /app
RUN rm -rf ta-lib-0.4.0 ta-lib-0.4.0-src.tar.gz

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación
COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
