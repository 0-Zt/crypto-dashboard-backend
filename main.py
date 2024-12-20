from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from binance.um_futures import UMFutures
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from typing import List, Dict
import logging
import talib 

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

try:
    client = UMFutures()
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

def convert_timeframe(interval: str) -> str:
    if interval.endswith(('h', 'd')):
        return interval
    return f"{interval}m"

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

    # Función para determinar precisión de precio
    def get_price_precision(price):
        if price < 0.0001:
            return 8
        elif price < 0.01:
            return 6
        elif price < 1:
            return 4
        else:
            return 2

    # Calcular EMAs
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df['sma20'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['sma20'] + (std * 2)
    df['bb_lower'] = df['sma20'] - (std * 2)

    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['signal']

    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['atr'] = true_range.rolling(14).mean()

    current_price = float(df['close'].iloc[-1])
    price_precision = get_price_precision(current_price)

    current_ema21 = float(df['ema21'].iloc[-1])
    current_ema50 = float(df['ema50'].iloc[-1])
    current_ema200 = float(df['ema200'].iloc[-1])

    # Tendencia
    trend = "NEUTRAL"
    if current_price > current_ema21 > current_ema50 > current_ema200:
        trend = "STRONG_BULLISH"
    elif current_price > current_ema21 > current_ema50:
        trend = "BULLISH"
    elif current_price < current_ema21 < current_ema50 < current_ema200:
        trend = "STRONG_BEARISH"
    elif current_price < current_ema21 < current_ema50:
        trend = "BEARISH"

    # RSI analysis
    current_rsi = float(df['rsi'].iloc[-1])
    if current_rsi > 70:
        rsi_analysis = "Sobrecompra - Posible agotamiento alcista"
    elif current_rsi < 30:
        rsi_analysis = "Sobreventa - Posible agotamiento bajista"
    else:
        rsi_analysis = "Nivel neutral"

    # Bollinger analysis
    if current_price > float(df['bb_upper'].iloc[-1]):
        bb_analysis = "Precio por encima de la banda superior - Posible sobrecompra"
    elif current_price < float(df['bb_lower'].iloc[-1]):
        bb_analysis = "Precio por debajo de la banda inferior - Posible sobreventa"
    else:
        bb_analysis = "Precio dentro de las bandas - Volatilidad normal"

    # MACD analysis
    current_macd = float(df['macd'].iloc[-1])
    current_signal = float(df['signal'].iloc[-1])
    if current_macd > current_signal:
        macd_analysis = "MACD por encima de la señal - Momentum alcista"
    else:
        macd_analysis = "MACD por debajo de la señal - Momentum bajista"

    # Detección de patrones de velas con TA-Lib
    # Usaremos algunas funciones de ejemplo: Doji, Hammer, Engulfing
    open_ = df['open']
    high_ = df['high']
    low_ = df['low']
    close_ = df['close']

    doji = talib.CDLDOJI(open_, high_, low_, close_)
    hammer = talib.CDLHAMMER(open_, high_, low_, close_)
    bullish_engulfing = talib.CDLENGULFING(open_, high_, low_, close_)
    # Si quisiéramos detectar Bearish Engulfing:
    # CDLENGULFING da positivo (100) para bullish y negativo (-100) para bearish
    # Podemos verificar el último valor:
    patterns_found = []
    if doji.iloc[-1] != 0:
        patterns_found.append("Doji")
    if hammer.iloc[-1] != 0:
        patterns_found.append("Hammer")
    # bullish_engulfing: positivo es alcista, negativo es bajista
    last_engulf = bullish_engulfing.iloc[-1]
    if last_engulf > 0:
        patterns_found.append("Bullish Engulfing")
    elif last_engulf < 0:
        patterns_found.append("Bearish Engulfing")

    # Crear el diccionario final
    analysis = {
        "trend": trend,
        "price": {
            "value": current_price,
            "precision": price_precision
        },
        "indicators": {
            "ema": {
                "ema21": round(current_ema21, price_precision),
                "ema50": round(current_ema50, price_precision),
                "ema200": round(current_ema200, price_precision)
            },
            "rsi": {
                "value": round(current_rsi, 2),
                "analysis": rsi_analysis
            },
            "bollinger_bands": {
                "upper": round(float(df['bb_upper'].iloc[-1]), price_precision),
                "middle": round(float(df['sma20'].iloc[-1]), price_precision),
                "lower": round(float(df['bb_lower'].iloc[-1]), price_precision),
                "analysis": bb_analysis
            },
            "macd": {
                "macd": round(current_macd, price_precision),
                "signal": round(current_signal, price_precision),
                "histogram": round(float(df['macd_hist'].iloc[-1]), price_precision),
                "analysis": macd_analysis
            },
            "atr": round(float(df['atr'].iloc[-1]), price_precision)
        },
        "analysis": {
            "summary": f"El precio actual (${current_price:.{price_precision}f}) está en una tendencia {trend.lower().replace('_', ' ')}.",
            "rsi": rsi_analysis,
            "bollinger": bb_analysis,
            "macd": macd_analysis
        },
        "patterns": patterns_found
    }

    return analysis

def calculate_price_levels(price: float, is_long: bool, atr_value: float) -> dict:
    stop_loss_distance = atr_value * 1.5
    tp1_distance = atr_value * 2
    tp2_distance = atr_value * 3
    tp3_distance = atr_value * 4

    if is_long:
        return {
            "stop_loss": price - stop_loss_distance,
            "targets": [
                price + tp1_distance,
                price + tp2_distance,
                price + tp3_distance
            ]
        }
    else:
        return {
            "stop_loss": price + stop_loss_distance,
            "targets": [
                price - tp1_distance,
                price - tp2_distance,
                price - tp3_distance
            ]
        }

def generate_trading_suggestion(analysis):
    try:
        current_price = analysis["price"]["value"]
        price_precision = analysis["price"]["precision"]
        rsi = analysis["indicators"]["rsi"]["value"]
        atr = analysis["indicators"]["atr"]

        is_bullish = analysis["trend"] in ["BULLISH", "STRONG_BULLISH"]
        is_bearish = analysis["trend"] in ["BEARISH", "STRONG_BEARISH"]

        if is_bullish:
            levels = calculate_price_levels(current_price, True, atr)
            return {
                "type": "LONG",
                "entry": round(current_price, price_precision),
                "stopLoss": round(levels["stop_loss"], price_precision),
                "targets": [
                    round(target, price_precision)
                    for target in levels["targets"]
                ],
                "confidence": 75 if rsi < 70 else 60,
                "risk": "Moderado"
            }
        elif is_bearish:
            levels = calculate_price_levels(current_price, False, atr)
            return {
                "type": "SHORT",
                "entry": round(current_price, price_precision),
                "stopLoss": round(levels["stop_loss"], price_precision),
                "targets": [
                    round(target, price_precision)
                    for target in levels["targets"]
                ],
                "confidence": 75 if rsi > 30 else 60,
                "risk": "Moderado"
            }
        else:
            return {
                "type": "NEUTRAL",
                "message": "No hay señal clara de trading en este momento",
                "confidence": 0,
                "risk": "N/A"
            }
    except Exception as e:
        logger.error(f"Error generando sugerencia de trading: {str(e)}")
        return {
            "type": "ERROR",
            "message": "Error al generar sugerencia de trading",
            "confidence": 0,
            "risk": "N/A"
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
        logger.info(f"Analyzing {symbol} with interval {interval}")
        if client is None:
            logger.error("Binance client is not initialized")
            raise HTTPException(status_code=500, detail="No se pudo establecer conexión con Binance")
        
        binance_interval = convert_timeframe(interval)
        logger.info(f"Converting interval {interval} to Binance format: {binance_interval}")

        logger.info(f"Fetching klines data for {symbol}")
        klines = client.klines(symbol=symbol, interval=binance_interval, limit=200)
        logger.info(f"Successfully retrieved {len(klines)} klines for {symbol}")

        logger.info("Calculating indicators")
        analysis = calculate_indicators(klines)
        logger.info("Generating trading suggestion")
        suggestion = generate_trading_suggestion(analysis)

        return {
            "analysis": analysis,
            "suggestion": suggestion,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error al analizar {symbol}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
