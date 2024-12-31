from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from binance.um_futures import UMFutures
from binance import Client as Spot
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from typing import List, Dict
import logging
import talib
import requests
from fastapi.responses import JSONResponse
from config import get_settings
import portfolio_routes
from analysis import calculate_indicators, generate_trading_suggestion

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI()
settings = get_settings()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rutas
app.include_router(portfolio_routes.router, prefix="/api", tags=["portfolio"])

# Configurar clientes de Binance
futures_client = UMFutures()
spot_client = Spot()

def is_futures_symbol(symbol: str) -> bool:
    """Determina si un símbolo es de futuros basado en su formato"""
    try:
        # Los pares de futuros típicamente terminan en USDT o BUSD
        return symbol.endswith(('USDT', 'BUSD'))
    except Exception:
        return False

def get_all_futures_symbols():
    try:
        exchange_info = futures_client.exchange_info()
        return [symbol['symbol'] for symbol in exchange_info['symbols'] if symbol['status'] == 'TRADING']
    except Exception as e:
        logger.error(f"Error getting futures symbols: {e}")
        return []

@app.get("/symbols")
def get_symbols():
    try:
        symbols = get_all_futures_symbols()
        return symbols  # Devolver el array directamente, sin anidarlo
    except Exception as e:
        logger.error(f"Error in get_symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/{symbol}")
def get_analysis(symbol: str, interval: str = "1h"):
    try:
        # Determinar qué cliente usar basado en el símbolo
        client = futures_client if is_futures_symbol(symbol) else spot_client
        
        # Obtener datos históricos
        try:
            klines = client.klines(symbol, interval, limit=100)
        except Exception as e:
            logger.error(f"Error getting klines for {symbol}: {e}")
            # Si falla con un cliente, intentar con el otro
            client = spot_client if client == futures_client else futures_client
            klines = client.klines(symbol, interval, limit=100)
        
        # Calcular indicadores
        analysis = calculate_indicators(klines)
        
        # Generar sugerencia
        suggestion = generate_trading_suggestion(analysis)
        
        return {
            "symbol": symbol,
            "interval": interval,
            "analysis": analysis,
            "suggestion": suggestion
        }
    except Exception as e:
        logger.error(f"Error in get_analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/klines/{symbol}/{interval}")
async def get_klines(symbol: str, interval: str):
    try:
        # Determinar qué cliente usar
        client = futures_client if is_futures_symbol(symbol) else spot_client
        
        try:
            klines = client.klines(symbol=symbol, interval=interval, limit=1000)
        except Exception:
            # Si falla, intentar con el otro cliente
            client = spot_client if client == futures_client else futures_client
            klines = client.klines(symbol=symbol, interval=interval, limit=1000)
        
        # Convertir a formato esperado por el frontend
        formatted_klines = []
        for k in klines:
            formatted_klines.append({
                'time': k[0],
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5]),
                'closeTime': k[6],
                'quoteVolume': float(k[7]),
                'trades': k[8],
                'takerBaseVolume': float(k[9]),
                'takerQuoteVolume': float(k[10])
            })
        
        return formatted_klines
    except Exception as e:
        logger.error(f"Error getting klines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/top-cryptos")
def get_top_cryptos():
    try:
        # Obtener datos de CoinGecko
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "page": 1,
                "sparkline": False
            }
        )
        response.raise_for_status()
        
        # Procesar y devolver los datos
        data = response.json()
        
        # Transformar los datos al formato esperado
        formatted_data = []
        for coin in data:
            formatted_data.append({
                "symbol": coin["symbol"].upper(),
                "name": coin["name"],
                "price": coin["current_price"],
                "priceChange24h": coin["price_change_percentage_24h"],
                "marketCap": coin["market_cap"],
                "volume24h": coin["total_volume"],
                "image": coin["image"]
            })
        
        return {"data": formatted_data}  # Devolver los datos dentro de un objeto
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from CoinGecko: {e}")
        raise HTTPException(status_code=503, detail="Error al obtener datos de CoinGecko")
    except Exception as e:
        logger.error(f"Error in get_top_cryptos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Ruta para obtener patrones de velas
@app.get("/api/patterns/{symbol}")
async def get_patterns(symbol: str, interval: str = "1h"):
    try:
        klines = await get_klines(symbol, interval)
        if not klines:
            raise HTTPException(status_code=404, detail="No se encontraron datos para el símbolo")

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Convertir columnas numéricas
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # Establecer timestamp como índice
        df.set_index(pd.to_datetime(df['timestamp'], unit='ms'), inplace=True)

        patterns = detect_candlestick_patterns(df)
        return {"patterns": patterns}

    except Exception as e:
        logger.error(f"Error getting patterns: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Ruta para obtener niveles clave
@app.get("/api/levels/{symbol}")
async def get_levels(symbol: str, interval: str = "1h"):
    try:
        klines = await get_klines(symbol, interval)
        if not klines:
            raise HTTPException(status_code=404, detail="No se encontraron datos para el símbolo")

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Convertir columnas numéricas
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # Establecer timestamp como índice
        df.set_index(pd.to_datetime(df['timestamp'], unit='ms'), inplace=True)

        # Ajustar el período según el intervalo
        period = 20
        if interval in ['1m', '5m']:
            period = 10
        elif interval in ['15m', '30m']:
            period = 15

        levels = find_key_levels(df, period)
        return {"levels": levels}

    except Exception as e:
        logger.error(f"Error getting levels: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Ruta de prueba
@app.get("/")
def read_root():
    return {"status": "ok", "message": "API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
