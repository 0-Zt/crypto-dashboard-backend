FROM python:3.11-slim

# Instalar dependencias del sistema para TA-Lib
RUN apt-get update && apt-get install -y wget build-essential gcc ta-lib && rm -rf /var/lib/apt/lists/*

# Instalar las dependencias de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Exponer el puerto por defecto que usará uvicorn
ENV PORT=8000
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
