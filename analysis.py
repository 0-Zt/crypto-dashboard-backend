import pandas as pd
import talib
import logging
from fastapi import HTTPException
from typing import List, Dict

logger = logging.getLogger(__name__)

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
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)

    # Bollinger Bands
    df['sma20'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['sma20'] + (std * 2)
    df['bb_lower'] = df['sma20'] - (std * 2)

    # MACD
    df['macd'], df['signal'], df['macd_hist'] = talib.MACD(df['close'])

    # ATR
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

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

    # Detección de patrones de velas
    open_ = df['open']
    high_ = df['high']
    low_ = df['low']
    close_ = df['close']

    doji = talib.CDLDOJI(open_, high_, low_, close_)
    hammer = talib.CDLHAMMER(open_, high_, low_, close_)
    bullish_engulfing = talib.CDLENGULFING(open_, high_, low_, close_)

    patterns_found = []
    if doji.iloc[-1] != 0:
        patterns_found.append("Doji")
    if hammer.iloc[-1] != 0:
        patterns_found.append("Hammer")
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

def detect_candlestick_patterns(df: pd.DataFrame) -> List[Dict]:
    """
    Detecta patrones de velas usando TA-Lib
    """
    patterns = []
    
    # Lista de funciones de patrones de TA-Lib
    pattern_functions = {
        'CDL_ENGULFING': (talib.CDLENGULFING, 'Engulfing'),
        'CDL_HAMMER': (talib.CDLHAMMER, 'Hammer'),
        'CDL_SHOOTING_STAR': (talib.CDLSHOOTINGSTAR, 'Shooting Star'),
        'CDL_DOJI': (talib.CDLDOJI, 'Doji'),
        'CDL_MORNING_STAR': (talib.CDLMORNINGSTAR, 'Morning Star'),
        'CDL_EVENING_STAR': (talib.CDLEVENINGSTAR, 'Evening Star'),
        'CDL_THREE_WHITE_SOLDIERS': (talib.CDL3WHITESOLDIERS, 'Three White Soldiers'),
        'CDL_THREE_BLACK_CROWS': (talib.CDL3BLACKCROWS, 'Three Black Crows'),
        'CDL_HARAMI': (talib.CDLHARAMI, 'Harami'),
        'CDL_PIERCING': (talib.CDLPIERCING, 'Piercing')
    }
    
    for pattern_name, (pattern_func, pattern_display_name) in pattern_functions.items():
        try:
            result = pattern_func(df['open'].values, df['high'].values, 
                                df['low'].values, df['close'].values)
            
            # Buscar patrones en las últimas 3 velas
            for i in range(-3, 0):
                if result[i] != 0:
                    patterns.append({
                        'time': df.index[i],
                        'name': pattern_display_name,
                        'type': 'bullish' if result[i] > 0 else 'bearish',
                        'strength': abs(result[i])
                    })
        except Exception as e:
            logger.error(f"Error detecting pattern {pattern_name}: {str(e)}")
            continue
    
    return patterns

def find_key_levels(df: pd.DataFrame, period: int = 20) -> List[Dict]:
    """
    Encuentra niveles clave de soporte y resistencia
    """
    levels = []
    
    try:
        # Calcular pivots usando máximos y mínimos locales
        for i in range(period, len(df) - period):
            # Ventana de precios
            high_window = df['high'].iloc[i-period:i+period]
            low_window = df['low'].iloc[i-period:i+period]
            volume_window = df['volume'].iloc[i-period:i+period]
            
            # Detectar resistencia (máximo local)
            if df['high'].iloc[i] == high_window.max():
                # Calcular la fuerza del nivel basado en volumen y toques
                touches = sum(abs(df['high'] - df['high'].iloc[i]) < df['high'].iloc[i] * 0.001)
                avg_volume = volume_window.mean()
                strength = touches * avg_volume
                
                levels.append({
                    'type': 'resistance',
                    'price': float(df['high'].iloc[i]),
                    'strength': float(strength),
                    'touches': int(touches),
                    'start_time': str(df.index[i-period]),
                    'end_time': str(df.index[i+period])
                })
            
            # Detectar soporte (mínimo local)
            if df['low'].iloc[i] == low_window.min():
                touches = sum(abs(df['low'] - df['low'].iloc[i]) < df['low'].iloc[i] * 0.001)
                avg_volume = volume_window.mean()
                strength = touches * avg_volume
                
                levels.append({
                    'type': 'support',
                    'price': float(df['low'].iloc[i]),
                    'strength': float(strength),
                    'touches': int(touches),
                    'start_time': str(df.index[i-period]),
                    'end_time': str(df.index[i+period])
                })
    
        # Filtrar niveles cercanos y mantener los más fuertes
        filtered_levels = []
        sorted_levels = sorted(levels, key=lambda x: x['strength'], reverse=True)
        
        for level in sorted_levels:
            # Verificar si ya existe un nivel cercano
            nearby_level = False
            for filtered_level in filtered_levels:
                if abs(filtered_level['price'] - level['price']) / level['price'] < 0.005:  # 0.5% de diferencia
                    nearby_level = True
                    break
            
            if not nearby_level:
                filtered_levels.append(level)
            
            # Mantener solo los 6 niveles más fuertes
            if len(filtered_levels) >= 6:
                break
        
        return filtered_levels
    
    except Exception as e:
        logger.error(f"Error finding key levels: {str(e)}")
        return []

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
