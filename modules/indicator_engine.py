# modules/indicator_engine.py

from typing import List, Dict, Any, Optional
from datetime import datetime


# ============================================================
#  Low-level indicator helpers (JS fetchYahooData port)
# ============================================================

def _sma(series: List[float], n: int, k: int) -> Optional[float]:
    """
    Basit hareketli ortalama (SMA).
    JS'teki _sma(arr, n, k) ile aynı mantık:
    - k < n-1 ise None
    - Aksi halde son n değerin ortalaması.
    """
    if series is None or len(series) == 0:
        return None
    if k < n - 1 or k >= len(series):
        return None
    start = k - n + 1
    window = series[start : k + 1]
    return sum(float(x) for x in window) / float(n)


def _ema_series(series: List[float], n: int) -> List[Optional[float]]:
    """
    Exponential Moving Average serisi.
    JS _emaSeries ile aynı: ilk n değerden sonra EMA başlar.
    """
    length = len(series)
    out: List[Optional[float]] = [None] * length
    if length < n:
        return out

    k = 2.0 / (n + 1.0)
    # seed = ilk n değerin SMA'sı
    ema = sum(float(series[i]) for i in range(n)) / float(n)
    out[n - 1] = ema

    for i in range(n, length):
        v = float(series[i])
        ema = v * k + ema * (1.0 - k)
        out[i] = ema

    return out


def _ema_at(series: List[float], n: int, k: int) -> Optional[float]:
    """
    Belirli bir index için EMA(n) değeri.
    JS _emaAt(series, n, k) ile aynı davranış.
    """
    if k < 0 or k >= len(series):
        return None
    ema = _ema_series(series, n)
    val = ema[k]
    return float(val) if val is not None else None


def _macd_main_line(close_arr: List[float]) -> List[Optional[float]]:
    """
    MACD ana hattı = EMA12 - EMA26
    JS _macdMainLine ile aynı mantık.
    """
    ema12 = _ema_series(close_arr, 12)
    ema26 = _ema_series(close_arr, 26)
    length = len(close_arr)
    macd: List[Optional[float]] = [None] * length

    for i in range(length):
        e12 = ema12[i]
        e26 = ema26[i]
        if e12 is not None and e26 is not None:
            macd[i] = float(e12) - float(e26)
        else:
            macd[i] = None

    return macd


def _adx_series(high: List[float], low: List[float], close: List[float], n: int) -> List[Optional[float]]:
    """
    Wilder ADX serisi.
    JS _adxSeries(high, low, close, n) fonksiyonunun birebir portu.
    Not: JS kodunda ilk ADX değeri için DX'leri yanlış topladığı için
    efektif olarak out[i] = dx davranışı çıkıyor; burada da aynı sonucu
    verecek şekilde port ediliyor.
    """
    length = len(close)
    out: List[Optional[float]] = [None] * length
    if length < n + 1:
        return out

    tr_arr = [None] * length
    dm_pos = [None] * length
    dm_neg = [None] * length

    for i in range(1, length):
        up_move = float(high[i]) - float(high[i - 1])
        down_move = float(low[i - 1]) - float(low[i])
        dm_pos[i] = up_move if (up_move > 0 and up_move > down_move) else 0.0
        dm_neg[i] = down_move if (down_move > 0 and down_move > up_move) else 0.0

        tr1 = float(high[i]) - float(low[i])
        tr2 = abs(float(high[i]) - float(close[i - 1]))
        tr3 = abs(float(low[i]) - float(close[i - 1]))
        tr_arr[i] = max(tr1, tr2, tr3)

    # Wilder smoothing için ilk toplamlar
    tr_n = 0.0
    dm_pos_n = 0.0
    dm_neg_n = 0.0
    for i in range(1, n + 1):
        tr_n += float(tr_arr[i] or 0.0)
        dm_pos_n += float(dm_pos[i] or 0.0)
        dm_neg_n += float(dm_neg[i] or 0.0)

    dx_prev = None
    for i in range(n + 1, length):
        tr_n = tr_n - (tr_n / float(n)) + float(tr_arr[i] or 0.0)
        dm_pos_n = dm_pos_n - (dm_pos_n / float(n)) + float(dm_pos[i] or 0.0)
        dm_neg_n = dm_neg_n - (dm_neg_n / float(n)) + float(dm_neg[i] or 0.0)

        if tr_n == 0.0:
            di_pos = 0.0
            di_neg = 0.0
        else:
            di_pos = 100.0 * (dm_pos_n / tr_n)
            di_neg = 100.0 * (dm_neg_n / tr_n)

        denom = di_pos + di_neg
        if denom == 0.0:
            dx = 0.0
        else:
            dx = 100.0 * abs(di_pos - di_neg) / denom

        # JS'deki hataya sadık kalmak için:
        # i == n+1 olduğunda "son n dx" yerine aynı dx'i n kez topluyor → dx
        if i == n + 1:
            out[i] = dx
        else:
            prev = out[i - 1] if out[i - 1] is not None else dx_prev
            if prev is None:
                out[i] = dx
            else:
                out[i] = ((prev * (n - 1)) + dx) / float(n)
        dx_prev = dx

    return out


def _cci_series(tp: List[float], n: int) -> List[Optional[float]]:
    """
    CCI serisi. JS _cciSeries(tp, n) ile aynı mantık.
    """
    length = len(tp)
    out: List[Optional[float]] = [None] * length

    for i in range(length):
        sma = _sma(tp, n, i)
        if sma is None:
            out[i] = None
            continue

        # mean deviation
        start = i - n + 1
        dev = 0.0
        for j in range(start, i + 1):
            dev += abs(tp[j] - sma)
        md = dev / float(n)
        if md == 0.0:
            out[i] = 0.0
        else:
            out[i] = (tp[i] - sma) / (0.015 * md)

    return out


def _atr_from_candles(cndl: Dict[str, List[float]], period: int = 14) -> float:
    """
    JS _atrFromCandles(cndl, period) fonksiyonunun portu.
    Son bar için ATR(period) döndürür.
    """
    n = period
    h = cndl.get("h") or []
    l = cndl.get("l") or []
    c = cndl.get("c") or []
    if not h or not l or not c or len(h) < n + 1 or len(l) < n + 1 or len(c) < n + 1:
        raise ValueError("ATR verisi yetersiz")

    tr_list: List[float] = []
    for i in range(1, len(h)):
        tr = max(
            float(h[i]) - float(l[i]),
            abs(float(h[i]) - float(c[i - 1])),
            abs(float(l[i]) - float(c[i - 1])),
        )
        tr_list.append(tr)

    # ilk n TR'in ortalaması
    atr = sum(tr_list[0:n]) / float(n)
    # Wilder smoothing
    for i in range(n, len(tr_list)):
        atr = (atr * float(n - 1) + tr_list[i]) / float(n)
    return atr


def _compute_rsi14(close: List[float], k: int) -> Optional[float]:
    """
    JS içindeki RSI(14) hesaplamasının birebir portu.
    k index'indeki barı referans alır.
    """
    if k < 14 or k >= len(close):
        return None

    gains = 0.0
    losses = 0.0
    # i: k-14 .. k-1 → diff = c[i+1] - c[i]
    for i in range(k - 14, k):
        diff = float(close[i + 1]) - float(close[i])
        if diff > 0:
            gains += diff
        else:
            losses -= diff  # diff negatif ise mutlak değer ekleniyor

    avg_gain = gains / 14.0
    avg_loss = losses / 14.0

    if avg_loss != 0.0:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi
    elif avg_gain != 0.0:
        return 100.0
    else:
        return 50.0


def _compute_vol_trend(volumes: List[float], k: int) -> Optional[float]:
    """
    JS'teki vol_trend hesabı:
      vSma5 = SMA(5)
      vSma20 = SMA(20)
      vol_trend = (vSma5 / vSma20) - 1
    """
    v_sma5 = _sma(volumes, 5, k)
    v_sma20 = _sma(volumes, 20, k)
    if v_sma5 is None or v_sma20 is None or v_sma20 == 0:
        return None
    return (v_sma5 / v_sma20) - 1.0


def _macro_color_from_atr(
    atr_pct_decimal: Optional[float],
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """
    JS _macroColorFromAtr(atrPctDecimal) fonksiyonunun backend portu.

    - cfg içinden RISK_ATR_GREEN_MAX / RISK_ATR_YELLOW_MAX okunabilir.
    - Yoksa default: 0.03 / 0.06
    - Eğer eşikler ≥1 ise yüzde olarak girilmiş kabul edilip /100 yapılır.
    """
    try:
        if atr_pct_decimal is None:
            return ""
        if not isinstance(atr_pct_decimal, (int, float)):
            return ""
        if atr_pct_decimal < 0:
            return ""

        cfg = cfg or {}
        g_max = cfg.get("RISK_ATR_GREEN_MAX", 0.03)
        y_max = cfg.get("RISK_ATR_YELLOW_MAX", 0.06)

        try:
            g_max = float(g_max)
        except Exception:
            g_max = 0.03
        try:
            y_max = float(y_max)
        except Exception:
            y_max = 0.06

        # Yüzde girildiyse normalize et (örn 3 → 0.03)
        if g_max >= 1.0:
            g_max = g_max / 100.0
        if y_max >= 1.0:
            y_max = y_max / 100.0

        # Güvenlik: sıralama bozuksa düzelt
        if g_max <= 0.0:
            g_max = 0.03
        if y_max <= g_max:
            y_max = max(0.06, g_max + 0.01)

        if atr_pct_decimal <= g_max:
            return "GREEN"
        if atr_pct_decimal <= y_max:
            return "YELLOW"
        return "RED"
    except Exception:
        # Backend tarafında log_write ile loglamak istersen burada kullanabilirsin.
        return ""


# ============================================================
#  Symbol-level indicator computation
# ============================================================

def compute_indicators_for_symbol(
    symbol: str,
    candles: Dict[str, List[float]],
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Tek bir sembol için:
      - ATR(14) ve atr_pct
      - mom_5d, mom_20d
      - vol_z20
      - rsi_14
      - ema20, ema50
      - adx14
      - macd (EMA12 - EMA26)
      - cci20
      - vol_trend
      - risk_color

    JS fetchYahooData içindeki hesap mantarının birebir backend portu.
    Burada BIST kapanış saati / 'dünkü bar' mantığı YOK:
    - fetch_engine candle dizisini zaten "etkin bar" ile uyumlu şekilde verecek.
    - Biz her zaman son barı (k = n-1) kullanıyoruz.
    """
    t = candles.get("t") or []
    o = candles.get("o") or []
    h = candles.get("h") or []
    l = candles.get("l") or []
    c = candles.get("c") or []
    v = candles.get("v") or []

    n = len(c)
    if n == 0:
        raise ValueError(f"No candle data for symbol {symbol}")

    k = n - 1  # etkin bar index'i (son eleman)

    close_k = float(c[k])
    high_k = float(h[k])
    low_k = float(l[k])
    vol_k = float(v[k]) if v and len(v) > k else None

    # ATR(14) & ATR%
    atr14 = _atr_from_candles({"h": h, "l": l, "c": c}, period=14)
    atr_pct_decimal: Optional[float]
    if close_k > 0:
        atr_pct_decimal = atr14 / close_k
    else:
        atr_pct_decimal = None

    # Momentum 5/20
    mom5: Optional[float] = None
    if k >= 5 and close_k:
        c5 = float(c[k - 5])
        if c5:
            mom5 = (close_k / c5) - 1.0

    mom20: Optional[float] = None
    if k >= 20 and close_k:
        c20 = float(c[k - 20])
        if c20:
            mom20 = (close_k / c20) - 1.0

    # Hacim z-skoru (vol_z20)
    vol_z20: Optional[float] = None
    if v and vol_k is not None and k >= 20:
        last20 = [float(x) for x in v[k - 20 : k]]  # k dahil değil → JS ile aynı
        if last20:
            mean = sum(last20) / float(len(last20))
            if len(last20) > 0:
                var = sum((x - mean) ** 2 for x in last20) / float(len(last20))
            else:
                var = 0.0
            sd = var ** 0.5
            if sd != 0.0:
                vol_z20 = (vol_k - mean) / sd
            else:
                vol_z20 = 0.0

    # RSI(14)
    rsi14 = _compute_rsi14(c, k)

    # EMA20 / EMA50
    ema20 = _ema_at(c, 20, k)
    ema50 = _ema_at(c, 50, k)

    # ADX(14)
    adx14: Optional[float] = None
    if k >= 14:
        adx_arr = _adx_series(h, l, c, 14)
        val = adx_arr[k]
        adx14 = float(val) if val is not None else None

    # MACD (EMA12 - EMA26)
    macd_val: Optional[float] = None
    if k >= 26:
        macd_arr = _macd_main_line(c)
        val = macd_arr[k]
        macd_val = float(val) if val is not None else None

    # CCI(20)
    cci20: Optional[float] = None
    if k >= 19:
        tp = [
            (float(h[i]) + float(l[i]) + float(c[i])) / 3.0
            for i in range(len(c))
        ]
        cci_arr = _cci_series(tp, 20)
        val = cci_arr[k]
        cci20 = float(val) if val is not None else None

    # vol_trend
    vol_trend = _compute_vol_trend(v, k) if v else None

    # risk_color (ATR%'ye göre)
    risk_color = _macro_color_from_atr(atr_pct_decimal, cfg=cfg)

    # Tarih string'i: t dizisinden üret (varsayılan: UNIX epoch saniye)
    date_str: str
    if t and len(t) > k:
        ts = t[k]
        try:
            # Eğer ts saniye cinsinden epoch ise:
            dt = datetime.utcfromtimestamp(float(ts))
        except Exception:
            # Aksi halde bugün UTC
            dt = datetime.utcnow()
        date_str = dt.strftime("%Y-%m-%d")
    else:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    indicators: Dict[str, Any] = {
        "atr_pct": atr_pct_decimal,
        "mom5": mom5,
        "mom20": mom20,
        "vol_z20": vol_z20,
        "rsi14": rsi14,
        "ema20": ema20,
        "ema50": ema50,
        "adx14": adx14,
        "macd": macd_val,
        "cci20": cci20,
        "vol_trend": vol_trend,
        "risk_color": risk_color,
        "close": close_k,
        "high": high_k,
        "low": low_k,
        "volume": vol_k,
    }

    return {
        "symbol": symbol,
        "date": date_str,
        "indicators": indicators,
    }


# ============================================================
#  Public entrypoint – run_indicator_engine
# ============================================================

def run_indicator_engine(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Indicator engine:

    MOD 1 – GERÇEK MOD (tercih edilen):
      context beklenenler:
        - "symbols": List[str]
        - "candles_by_symbol": {
              "AKBNK.IS": {"t": [...], "o": [...], "h": [...], "l": [...], "c": [...], "v": [...]},
              ...
          }
        - opsiyonel: "config": {...}  # ATR risk eşiği vb.

      dönüş:
        {
          "radar_candidates": [
            {
              "symbol": "SASA.IS",
              "date": "2025-12-01",
              "indicators": {
                "atr_pct": ...,
                "mom5": ...,
                "mom20": ...,
                "vol_z20": ...,
                "rsi14": ...,
                "ema20": ...,
                "ema50": ...,
                "adx14": ...,
                "macd": ...,
                "cci20": ...,
                "vol_trend": ...,
                "risk_color": ...,
                "close": ...,
                "high": ...,
                "low": ...,
                "volume": ...
              }
            },
            ...
          ]
        }

    MOD 2 – DUMMY MOD (geçici, geriye dönük uyumluluk):
      - Eğer "candles_by_symbol" yoksa eski davranış çalışır
      - Şu anki dummy pipeline testleri kırılmasın diye korunuyor.
    """
    symbols: List[str] = context.get("symbols", []) or []
    candles_by_symbol: Optional[Dict[str, Any]] = context.get("candles_by_symbol")
    cfg: Dict[str, Any] = context.get("config", {}) or {}

    # ========================================================
    # MOD 1 – GERÇEK MOD
    # ========================================================
    if candles_by_symbol:
        radar_candidates: List[Dict[str, Any]] = []

        for sym in symbols:
            candles = candles_by_symbol.get(sym)
            if not candles:
                # Candle verisi yoksa şimdilik atla (istersen burada flag'li satır üretebilirsin)
                continue

            try:
                info = compute_indicators_for_symbol(sym, candles, cfg=cfg)
                radar_candidates.append(info)
            except Exception as e:
                # Burada istersen log_write ile loglayabiliriz; şimdilik "error" alanı ile döndürelim.
                radar_candidates.append({
                    "symbol": sym,
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "indicators": {},
                    "error": str(e),
                })

        return {
            "radar_candidates": radar_candidates
        }

    # ========================================================
    # MOD 2 – DUMMY MOD (eski davranış, simulate_pipeline_run için)
    # ========================================================
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    radar_candidates_dummy: List[Dict[str, Any]] = []
    # Şimdilik: ilk 10 sembolden dummy candidate üret
    for i, sym in enumerate(symbols[:10]):
        radar_candidates_dummy.append({
            "date": today_str,
            "symbol": sym,
            "indicators": {
                "volume": 2_000_000 + i * 100_000,  # LIQ_MIN üzerinde
                "atr_pct": 0.08,                    # %8 ATR
                "mom5": 0.02 + 0.001 * i,           # %2 civarı kısa vade momentum
                "mom20": 0.05 + 0.001 * i,          # %5 civarı orta vade momentum
                "vol_z20": 1.5,
                "rsi14": 55.0,
                "macd": 0.5,
                "adx14": 22.0,
                "cci20": 100.0,
                "vol_trend": 0.5,
                "close": 100.0 + i,
                "ema20": 98.0 + i,
                "ema50": 95.0 + i,
                "risk_color": "YELLOW",
            }
        })

    return {
        "radar_candidates": radar_candidates_dummy
    }
