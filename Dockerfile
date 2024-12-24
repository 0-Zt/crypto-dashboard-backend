FROM python:3.8-slim AS compile-image

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc wget ca-certificates && rm -rf /var/lib/apt/lists/*

# Crear entorno virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar numpy primero (requerido por TA-Lib)
RUN pip install --upgrade pip
RUN pip install numpy

# Descargar y compilar TA-Lib (C) en /opt/venv
RUN wget https://downloads.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/opt/venv && \
    make && \
    make install && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Exportar las rutas para que pip encuentre las libs
ENV LD_LIBRARY_PATH="/opt/venv/lib"
ENV LIBRARY_PATH="/opt/venv/lib"
ENV CPATH="/opt/venv/include"
ENV LDFLAGS="-L/opt/venv/lib"

# Instalar wrapper python TA-Lib
RUN pip install TA-Lib==0.4.26

# Instalar el resto de dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Etapa final
FROM python:3.8-slim AS build-image
COPY --from=compile-image /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV LD_LIBRARY_PATH="/opt/venv/lib"

WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
