from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from binance.um_futures import UMFutures
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from typing import List, Dict
import logging

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
    allow_origins=["*"],  # Ajusta a tu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Inicializar cliente de Binance con mejor manejo de errores
try:
    client = UMFutures()
    # Probar la conexión
    client.ping()
    logger.info("Conexión exitosa con Binance")
except Exception as e:
    logger.error(f"Error al conectar con Binance: {str(e)}")
    client = None

def get_all_futures_symbols() -> List[Dict]:
    try:
        logger.info("Obteniendo información de exchange...")
        exchange_info = client.exchange_info()
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
        logger.info(f"Símbolos procesados exitosamente: {len(symbols)} símbolos activos")
        return symbols
    except Exception as e:
        logger.error(f"Error en get_all_futures_symbols: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def calculate_indicators(klines: List) -> Dict:
    if not klines:
        raise HTTPException(status_code=500, detail="No se obtuvieron datos de klines de Binance")

    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col])

    if len(df) == 0:
        raise HTTPException(status_code=500, detail="No se pudo formar el DataFrame con los datos de klines")

    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    df['sma20'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['sma20'] + (std * 2)
    df['bb_lower'] = df['sma20'] - (std * 2)

    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['signal']

    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['atr'] = true_range.rolling(14).mean()

    current_price = float(df['close'].iloc[-1])
    current_ema21 = float(df['ema21'].iloc[-1])
    current_ema50 = float(df['ema50'].iloc[-1])
    current_ema200 = float(df['ema200'].iloc[-1])

    trend = "NEUTRAL"
    if current_price > current_ema21 > current_ema50 > current_ema200:
        trend = "STRONG_BULLISH"
    elif current_price > current_ema21 > current_ema50:
        trend = "BULLISH"
    elif current_price < current_ema21 < current_ema50 < current_ema200:
        trend = "STRONG_BEARISH"
    elif current_price < current_ema21 < current_ema50:
        trend = "BEARISH"

    current_rsi = float(df['rsi'].iloc[-1])
    if current_rsi > 70:
        rsi_analysis = "Sobrecompra - Posible agotamiento alcista"
    elif current_rsi < 30:
        rsi_analysis = "Sobreventa - Posible agotamiento bajista"
    else:
        rsi_analysis = "Nivel neutral"

    if current_price > float(df['bb_upper'].iloc[-1]):
        bb_analysis = "Precio por encima de la banda superior - Posible sobrecompra"
    elif current_price < float(df['bb_lower'].iloc[-1]):
        bb_analysis = "Precio por debajo de la banda inferior - Posible sobreventa"
    else:
        bb_analysis = "Precio dentro de las bandas - Volatilidad normal"

    current_macd = float(df['macd'].iloc[-1])
    current_signal = float(df['signal'].iloc[-1])
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
                "upper": float(df['bb_upper'].iloc[-1]),
                "middle": float(df['sma20'].iloc[-1]),
                "lower": float(df['bb_lower'].iloc[-1]),
                "analysis": bb_analysis
            },
            "macd": {
                "macd": current_macd,
                "signal": current_signal,
                "histogram": float(df['macd_hist'].iloc[-1]),
                "analysis": macd_analysis
            },
            "atr": float(df['atr'].iloc[-1])
        },
        "analysis": {
            "summary": f"El precio actual (${current_price:.2f}) está en una tendencia {trend.lower().replace('_', ' ')}.",
            "rsi": rsi_analysis,
            "bollinger": bb_analysis,
            "macd": macd_analysis
        }
    }

@app.get("/api/symbols")
async def get_symbols():
    try:
        if client is None:
            raise HTTPException(status_code=500, detail="No se pudo establecer conexión con Binance")
        
        symbols = get_all_futures_symbols()
        logger.info(f"Símbolos obtenidos exitosamente: {len(symbols)} símbolos encontrados")
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"Error en get_symbols: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str, interval: str = "1h"):
    try:
        if client is None:
            raise HTTPException(status_code=500, detail="No se pudo establecer conexión con Binance")
        
        klines = client.klines(symbol=symbol, interval=interval, limit=200)
        logger.info(f"Datos históricos obtenidos para {symbol}.")
        
        analysis = calculate_indicators(klines)
        suggestion = generate_trading_suggestion(analysis)
        
        return {
            "analysis": analysis,
            "suggestion": suggestion,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error al analizar {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
