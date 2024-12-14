from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ccxt
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from typing import List, Dict
import logging
from datetime import datetime
import aiohttp

# Configurar logging más detallado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# URLs de la API pública de Binance
BASE_URL = "https://data.binance.com"
FUTURES_URL = "https://fapi.binance.com"

async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise HTTPException(status_code=response.status, detail=f"Error from Binance: {await response.text()}")
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

def get_interval_milliseconds(interval: str) -> int:
    units = {
        'm': 60 * 1000,
        'h': 60 * 60 * 1000,
        'd': 24 * 60 * 60 * 1000
    }
    unit = interval[-1]
    number = int(interval[:-1])
    return number * units[unit]

@app.get("/api/symbols")
async def get_symbols():
    try:
        url = f"{FUTURES_URL}/fapi/v1/exchangeInfo"
        exchange_info = await fetch_data(url)
        
        symbols = []
        for symbol in exchange_info['symbols']:
            if symbol['status'] == 'TRADING':
                symbols.append({
                    'symbol': symbol['symbol'],
                    'baseAsset': symbol['baseAsset'],
                    'quoteAsset': symbol['quoteAsset'],
                    'pricePrecision': symbol['pricePrecision'],
                    'quantityPrecision': symbol['quantityPrecision']
                })
        
        logger.info(f"Símbolos obtenidos exitosamente: {len(symbols)} símbolos")
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"Error en get_symbols: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str, interval: str = "1h"):
    try:
        # Calcular el tiempo para obtener 200 velas
        interval_ms = get_interval_milliseconds(interval)
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - (200 * interval_ms)
        
        url = f"{FUTURES_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=200"
        klines = await fetch_data(url)
        
        if not klines:
            raise HTTPException(status_code=404, detail="No data found")
            
        logger.info(f"Datos históricos obtenidos para {symbol}")
        
        # Convertir los datos a DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Convertir columnas a números
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
            
        analysis = calculate_indicators(df)
        suggestion = generate_trading_suggestion(analysis)
        
        return {
            "analysis": analysis,
            "suggestion": suggestion,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error al analizar {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def calculate_indicators(ohlcv_data: pd.DataFrame) -> Dict:
    if ohlcv_data is None or ohlcv_data.empty:
        raise HTTPException(status_code=500, detail="No se obtuvieron datos OHLCV de Binance")

    # Calcular indicadores
    ohlcv_data['ema21'] = ohlcv_data['close'].ewm(span=21, adjust=False).mean()
    ohlcv_data['ema50'] = ohlcv_data['close'].ewm(span=50, adjust=False).mean()
    ohlcv_data['ema200'] = ohlcv_data['close'].ewm(span=200, adjust=False).mean()

    # RSI
    delta = ohlcv_data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    ohlcv_data['rsi'] = 100 - (100 / (1 + rs))

    # Bandas de Bollinger
    ohlcv_data['sma20'] = ohlcv_data['close'].rolling(window=20).mean()
    std = ohlcv_data['close'].rolling(window=20).std()
    ohlcv_data['bb_upper'] = ohlcv_data['sma20'] + (std * 2)
    ohlcv_data['bb_lower'] = ohlcv_data['sma20'] - (std * 2)

    # MACD
    exp1 = ohlcv_data['close'].ewm(span=12, adjust=False).mean()
    exp2 = ohlcv_data['close'].ewm(span=26, adjust=False).mean()
    ohlcv_data['macd'] = exp1 - exp2
    ohlcv_data['signal'] = ohlcv_data['macd'].ewm(span=9, adjust=False).mean()
    ohlcv_data['macd_hist'] = ohlcv_data['macd'] - ohlcv_data['signal']

    # ATR
    high_low = ohlcv_data['high'] - ohlcv_data['low']
    high_close = abs(ohlcv_data['high'] - ohlcv_data['close'].shift())
    low_close = abs(ohlcv_data['low'] - ohlcv_data['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    ohlcv_data['atr'] = true_range.rolling(14).mean()

    # Obtener valores actuales
    current_price = float(ohlcv_data['close'].iloc[-1])
    current_ema21 = float(ohlcv_data['ema21'].iloc[-1])
    current_ema50 = float(ohlcv_data['ema50'].iloc[-1])
    current_ema200 = float(ohlcv_data['ema200'].iloc[-1])

    # Análisis de tendencia
    trend = "NEUTRAL"
    if current_price > current_ema21 > current_ema50 > current_ema200:
        trend = "STRONG_BULLISH"
    elif current_price > current_ema21 > current_ema50:
        trend = "BULLISH"
    elif current_price < current_ema21 < current_ema50 < current_ema200:
        trend = "STRONG_BEARISH"
    elif current_price < current_ema21 < current_ema50:
        trend = "BEARISH"

    # Análisis de RSI
    current_rsi = float(ohlcv_data['rsi'].iloc[-1])
    if current_rsi > 70:
        rsi_analysis = "Sobrecompra - Posible agotamiento alcista"
    elif current_rsi < 30:
        rsi_analysis = "Sobreventa - Posible agotamiento bajista"
    else:
        rsi_analysis = "Nivel neutral"

    # Análisis de Bandas de Bollinger
    if current_price > float(ohlcv_data['bb_upper'].iloc[-1]):
        bb_analysis = "Precio por encima de la banda superior - Posible sobrecompra"
    elif current_price < float(ohlcv_data['bb_lower'].iloc[-1]):
        bb_analysis = "Precio por debajo de la banda inferior - Posible sobreventa"
    else:
        bb_analysis = "Precio dentro de las bandas - Volatilidad normal"

    # Análisis de MACD
    current_macd = float(ohlcv_data['macd'].iloc[-1])
    current_signal = float(ohlcv_data['signal'].iloc[-1])
    if current_macd > current_signal:
        macd_analysis = "MACD por encima de la señal - Momentum alcista"
    else:
        macd_analysis = "MACD por debajo de la señal - Momentum bajista"

    return {
        "trend": trend,
        "price": current_price,
        "indicators": {
            "ema": {
                "ema21": current_ema21,
                "ema50": current_ema50,
                "ema200": current_ema200
            },
            "rsi": {
                "value": current_rsi,
                "analysis": rsi_analysis
            },
            "bollinger_bands": {
                "upper": float(ohlcv_data['bb_upper'].iloc[-1]),
                "middle": float(ohlcv_data['sma20'].iloc[-1]),
                "lower": float(ohlcv_data['bb_lower'].iloc[-1]),
                "analysis": bb_analysis
            },
            "macd": {
                "macd": current_macd,
                "signal": current_signal,
                "histogram": float(ohlcv_data['macd_hist'].iloc[-1]),
                "analysis": macd_analysis
            },
            "atr": float(ohlcv_data['atr'].iloc[-1])
        },
        "analysis": {
            "summary": f"El precio actual (${current_price:.2f}) está en una tendencia {trend.lower().replace('_', ' ')}.",
            "rsi": rsi_analysis,
            "bollinger": bb_analysis,
            "macd": macd_analysis
        }
    }

def generate_trading_suggestion(analysis):
    try:
        current_price = analysis["price"]
        ema_21 = analysis["indicators"]["ema"]["ema21"]
        ema_50 = analysis["indicators"]["ema"]["ema50"]
        rsi = analysis["indicators"]["rsi"]["value"]
        
        is_bullish = current_price > ema_21 and ema_21 > ema_50 and rsi > 40
        is_bearish = current_price < ema_21 and ema_21 < ema_50 and rsi < 60
        
        if is_bullish:
            return {
                "type": "LONG",
                "entry": round(current_price, 2),
                "stopLoss": round(current_price * 0.98, 2),
                "targets": [
                    round(current_price * 1.02, 2),
                    round(current_price * 1.04, 2),
                    round(current_price * 1.06, 2)
                ],
                "confidence": 75 if rsi < 70 else 60,
                "risk": "Moderado"
            }
        elif is_bearish:
            return {
                "type": "SHORT",
                "entry": round(current_price, 2),
                "stopLoss": round(current_price * 1.02, 2),
                "targets": [
                    round(current_price * 0.98, 2),
                    round(current_price * 0.96, 2),
                    round(current_price * 0.94, 2)
                ],
                "confidence": 75 if rsi > 30 else 60,
                "risk": "Moderado"
            }
        else:
            return {
                "type": "NEUTRAL",
                "message": "No hay señal clara de trading en este momento"
            }
    except Exception as e:
        logger.error(f"Error generando sugerencia de trading: {str(e)}")
        return {"type": "ERROR", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
