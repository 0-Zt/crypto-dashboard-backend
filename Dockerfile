### Etapa de compilación
FROM python:3.8-slim AS compile-image

RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc wget ca-certificates && rm -rf /var/lib/apt/lists/*

# Crear entorno virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar numpy primero
RUN pip install --upgrade pip
RUN pip install numpy

# Descargar y compilar TA-Lib desde SourceForge
RUN wget https://downloads.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/opt/venv && \
    make && \
    make install && \
    cd .. && rm -rf ta-lib-0.4.0 ta-lib-0.4.0-src.tar.gz

# Instalar TA-Lib Python desde pip, indicando la ruta de las libs
RUN pip install --global-option=build_ext --global-option="-L/opt/venv/lib" TA-Lib==0.4.24

# Instalar el resto de dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

### Etapa final
FROM python:3.8-slim AS build-image
COPY --from=compile-image /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV LD_LIBRARY_PATH="/opt/venv/lib"

WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
