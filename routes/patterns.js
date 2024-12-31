const express = require('express');
const router = express.Router();
const talib = require('talib');

// Función para convertir datos a formato talib
const prepareData = (candles) => {
  return {
    open: candles.map(c => c.open),
    high: candles.map(c => c.high),
    low: candles.map(c => c.low),
    close: candles.map(c => c.close),
    volume: candles.map(c => c.volume)
  };
};

// Lista de patrones de velas que queremos detectar
const candlePatterns = [
  { name: 'CDL_ENGULFING', func: talib.CDL_ENGULFING },
  { name: 'CDL_HAMMER', func: talib.CDL_HAMMER },
  { name: 'CDL_SHOOTING_STAR', func: talib.CDL_SHOOTINGSTAR },
  { name: 'CDL_DOJI', func: talib.CDL_DOJI },
  { name: 'CDL_MORNING_STAR', func: talib.CDL_MORNINGSTAR },
  { name: 'CDL_EVENING_STAR', func: talib.CDL_EVENINGSTAR },
  { name: 'CDL_THREE_WHITE_SOLDIERS', func: talib.CDL_3WHITESOLDIERS },
  { name: 'CDL_THREE_BLACK_CROWS', func: talib.CDL_3BLACKCROWS }
];

router.get('/:symbol', async (req, res) => {
  try {
    const { symbol } = req.params;
    const { interval } = req.query;

    // Obtener datos históricos de Binance
    const candles = await fetchCandlestickData(symbol, interval);
    const data = prepareData(candles);

    const patterns = [];
    const lastIndex = data.close.length - 1;

    // Detectar patrones usando talib
    for (const pattern of candlePatterns) {
      const result = pattern.func(data);
      
      // Si se detectó un patrón en las últimas velas
      if (result[lastIndex] !== 0) {
        patterns.push({
          time: candles[lastIndex].time,
          name: pattern.name.replace('CDL_', ''),
          type: result[lastIndex] > 0 ? 'bullish' : 'bearish',
          strength: Math.abs(result[lastIndex])
        });
      }
    }

    res.json(patterns);
  } catch (error) {
    console.error('Error detecting patterns:', error);
    res.status(500).json({ error: 'Error detecting patterns' });
  }
});

module.exports = router;
