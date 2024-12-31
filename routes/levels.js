const express = require('express');
const router = express.Router();
const talib = require('talib');

// Función para detectar niveles de soporte y resistencia
const findKeyLevels = (candles, period = 20) => {
  const levels = [];
  const priceData = {
    high: candles.map(c => c.high),
    low: candles.map(c => c.low),
    close: candles.map(c => c.close),
    volume: candles.map(c => c.volume)
  };

  // Encontrar pivots usando máximos y mínimos locales
  for (let i = period; i < candles.length - period; i++) {
    const windowHigh = priceData.high.slice(i - period, i + period);
    const windowLow = priceData.low.slice(i - period, i + period);
    
    // Detectar resistencia (máximo local)
    if (priceData.high[i] === Math.max(...windowHigh)) {
      levels.push({
        type: 'resistance',
        price: priceData.high[i],
        startTime: candles[i - period].time,
        endTime: candles[i + period].time,
        strength: calculateLevelStrength(candles, i, 'resistance')
      });
    }
    
    // Detectar soporte (mínimo local)
    if (priceData.low[i] === Math.min(...windowLow)) {
      levels.push({
        type: 'support',
        price: priceData.low[i],
        startTime: candles[i - period].time,
        endTime: candles[i + period].time,
        strength: calculateLevelStrength(candles, i, 'support')
      });
    }
  }

  // Filtrar niveles cercanos y mantener los más fuertes
  return filterNearbyLevels(levels);
};

// Calcular la fuerza del nivel basado en toques y volumen
const calculateLevelStrength = (candles, index, type) => {
  let touches = 0;
  let volumeAtTouches = 0;
  const price = type === 'resistance' ? candles[index].high : candles[index].low;
  const threshold = price * 0.001; // 0.1% de tolerancia

  candles.forEach(candle => {
    if (type === 'resistance') {
      if (Math.abs(candle.high - price) <= threshold) {
        touches++;
        volumeAtTouches += candle.volume;
      }
    } else {
      if (Math.abs(candle.low - price) <= threshold) {
        touches++;
        volumeAtTouches += candle.volume;
      }
    }
  });

  return {
    touches,
    averageVolume: volumeAtTouches / touches,
    score: touches * (volumeAtTouches / touches)
  };
};

// Filtrar niveles cercanos
const filterNearbyLevels = (levels) => {
  const filteredLevels = [];
  const sortedLevels = levels.sort((a, b) => b.strength.score - a.strength.score);

  sortedLevels.forEach(level => {
    // Verificar si ya existe un nivel cercano
    const nearbyLevel = filteredLevels.find(l => 
      Math.abs(l.price - level.price) / level.price < 0.005 // 0.5% de diferencia
    );

    if (!nearbyLevel) {
      filteredLevels.push(level);
    }
  });

  // Devolver solo los 6 niveles más fuertes
  return filteredLevels.slice(0, 6);
};

router.get('/:symbol', async (req, res) => {
  try {
    const { symbol } = req.params;
    const { interval } = req.query;

    // Obtener datos históricos de Binance
    const candles = await fetchCandlestickData(symbol, interval);
    
    // Encontrar niveles clave
    const levels = findKeyLevels(candles);

    res.json(levels);
  } catch (error) {
    console.error('Error finding key levels:', error);
    res.status(500).json({ error: 'Error finding key levels' });
  }
});

module.exports = router;
