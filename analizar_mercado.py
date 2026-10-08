#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANÁLISIS PRE-MERCADO PARA OPERAR SPY INTRADÍA
=============================================
Ejecuta este script por la mañana (antes de las 9:30 ET) para obtener:

  1. Movimiento overnight de los futuros de EE.UU. (ES, NQ, YM, RTY) + VIX
  2. Alineación y divergencias entre ellos
  3. Contexto de Asia y Europa
  4. Correlaciones recientes
  5. Lectura del día (risk-on / risk-off / mixto)

TODOS los horarios se muestran en hora del Este (ET) de EE.UU.

Uso:
    python analizar_mercado.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    import yfinance as yf
except ImportError:
    print("\n[!] Falta la librería 'yfinance'.")
    print("    Instálala con:  pip install -r requirements.txt\n")
    sys.exit(1)


# ============================ CONFIGURACIÓN ============================

ET = ZoneInfo("America/New_York")

# Futuros de EE.UU.  ->  (etiqueta corta, nombre)
FUTUROS_USA = {
    "ES=F": ("/ES", "S&P 500"),
    "NQ=F": ("/NQ", "Nasdaq-100"),
    "YM=F": ("/YM", "Dow Jones"),
    "RTY=F": ("/RTY", "Russell 2000"),
}

TICKER_VIX = "^VIX"

# Índices globales  ->  (nombre, región)
INDICES_GLOBALES = {
    "^N225": ("Nikkei 225", "Japón"),
    "^HSI": ("Hang Seng", "Hong Kong"),
    "^GDAXI": ("DAX", "Alemania"),
    "^STOXX50E": ("Euro Stoxx 50", "Europa"),
    "^FTSE": ("FTSE 100", "Reino Unido"),
    "^FCHI": ("CAC 40", "Francia"),
}

TICKER_SPY = "SPY"

# Tu método: medias móviles
MA_5MIN_VENTANA = 200    # media de 200 en gráfico de 5 minutos
MA_15MIN_VENTANA = 75    # media de 75 en gráfico de 15 minutos

# Símbolos para la matriz de correlación
TICKERS_CORRELACION = ["ES=F", "NQ=F", "YM=F", "RTY=F", "^VIX"]
ETIQUETAS_CORRELACION = {
    "ES=F": "ES", "NQ=F": "NQ", "YM=F": "YM", "RTY=F": "RTY", "^VIX": "VX",
}

# Nombres en español para la fecha
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ============================== COLORES ===============================

class C:
    """Códigos ANSI para colorear la salida en la terminal."""
    VERDE = "\033[92m"
    ROJO = "\033[91m"
    AMARILLO = "\033[93m"
    AZUL = "\033[94m"
    GRIS = "\033[90m"
    NEGRITA = "\033[1m"
    FIN = "\033[0m"


def pintar(texto: str, codigo: str) -> str:
    return f"{codigo}{texto}{C.FIN}"


def flecha(cambio: float) -> str:
    if cambio > 0:
        return pintar("▲", C.VERDE)
    if cambio < 0:
        return pintar("▼", C.ROJO)
    return pintar("=", C.GRIS)


# ============================== DATOS =================================

def obtener_cotizacion(ticker: str):
    """
    Devuelve (precio_actual, cierre_previo, cambio_pct) o None si falla.
    Usa velas diarias: la última = hoy (parcial), la anterior = cierre previo.
    """
    try:
        hist = yf.Ticker(ticker).history(period="7d", interval="1d")
        if hist is None or len(hist) < 2:
            return None
        precio = float(hist["Close"].iloc[-1])
        previo = float(hist["Close"].iloc[-2])
        if previo == 0:
            return None
        cambio = (precio / previo - 1.0) * 100.0
        return precio, previo, cambio
    except Exception:
        return None


def medias_spy():
    """
    Calcula las medias móviles de SPY según el método del usuario.
    Devuelve dict con: precio, ma5m, ma15m  (o None en las que fallen).
    """
    resultado = {"precio": None, "ma5m": None, "ma15m": None}

    # Media de 200 en velas de 5 minutos
    try:
        h5 = yf.Ticker(TICKER_SPY).history(period="5d", interval="5m")
        if h5 is not None and len(h5) >= MA_5MIN_VENTANA:
            cierres = h5["Close"]
            resultado["precio"] = float(cierres.iloc[-1])
            resultado["ma5m"] = float(cierres.rolling(MA_5MIN_VENTANA).mean().iloc[-1])
    except Exception:
        pass

    # Media de 75 en velas de 15 minutos
    try:
        h15 = yf.Ticker(TICKER_SPY).history(period="10d", interval="15m")
        if h15 is not None and len(h15) >= MA_15MIN_VENTANA:
            cierres = h15["Close"]
            resultado["ma15m"] = float(cierres.rolling(MA_15MIN_VENTANA).mean().iloc[-1])
            if resultado["precio"] is None:
                resultado["precio"] = float(cierres.iloc[-1])
    except Exception:
        pass

    return resultado


def matriz_correlacion(periodo: str = "3mo"):
    """Devuelve un DataFrame de correlaciones de rendimientos diarios, o None."""
    try:
        datos = yf.download(
            list(TICKERS_CORRELACION), period=periodo, interval="1d",
            progress=False, auto_adjust=True,
        )
        if datos is None or datos.empty:
            return None
        closes = datos["Close"] if "Close" in datos.columns else datos
        retornos = closes.pct_change().dropna()
        corr = retornos.corr()
        # Ordenar para que se lea en el orden que usamos (ES, NQ, YM, RTY, VX)
        try:
            corr = corr.reindex(index=TICKERS_CORRELACION, columns=TICKERS_CORRELACION)
        except Exception:
            pass
        return corr
    except Exception:
        return None


# ============================== LÓGICA ================================

def analizar_alineacion(cambios: dict):
    """
    Recibe {'ES': cambio, 'NQ': ..., 'YM': ..., 'RTY': ...}
    Devuelve (estado, conteo_arriba, conteo_abajo).
    """
    arriba = sum(1 for v in cambios.values() if v is not None and v > 0)
    abajo = sum(1 for v in cambios.values() if v is not None and v < 0)
    total = sum(1 for v in cambios.values() if v is not None)

    if arriba == total and total > 0:
        return "TODOS AL ALZA", arriba, abajo
    if abajo == total and total > 0:
        return "TODOS A LA BAJA", arriba, abajo
    return "MIXTO / DIVERGENTE", arriba, abajo


def lectura_del_dia(cambios: dict, cambio_vix, spy: dict):
    """Genera una lectura razonada del día combinando futuros, VIX y las medias."""
    lineas = []
    estado, arriba, abajo = analizar_alineacion(cambios)

    # --- VIX ---
    vix_texto = ""
    if cambio_vix is not None:
        if cambio_vix < 0:
            vix_texto = "El VIX baja → confirma apetito de riesgo."
        elif cambio_vix > 0:
            vix_texto = "El VIX sube → hay tensión / aversión al riesgo."
        else:
            vix_texto = "El VIX plano → sin señal clara de riesgo."

    # --- Alineación ---
    if estado == "TODOS AL ALZA":
        lineas.append("Los 4 índices están alineados AL ALZA → sesgo de continuidad alcista.")
    elif estado == "TODOS A LA BAJA":
        lineas.append("Los 4 índices están alineados A LA BAJA → sesgo de continuidad bajista.")
    else:
        lineas.append(f"Índices divididos ({arriba} arriba / {abajo} abajo) → día de posible rango o chop.")
        lineas.append("Con señales divididas conviene reducir tamaño y esperar confirmación.")

    if vix_texto:
        lineas.append(vix_texto)

    # --- Divergencias NQ vs ES  y  RTY vs ES ---
    es = cambios.get("ES")
    nq = cambios.get("NQ")
    rty = cambios.get("RTY")
    if es is not None and nq is not None:
        dif = nq - es
        if abs(dif) >= 0.15:
            if dif > 0:
                lineas.append(f"NQ lidera sobre ES (+{dif:.2f}%) → empuje de tecnología.")
            else:
                lineas.append(f"NQ va por detrás de ES ({dif:.2f}%) → debilidad en tecnología.")
    if es is not None and rty is not None:
        dif = rty - es
        if abs(dif) >= 0.15:
            if dif > 0:
                lineas.append(f"Russell por delante de ES (+{dif:.2f}%) → el movimiento se amplía (sano).")
            else:
                lineas.append(f"Russell por detrás de ES ({dif:.2f}%) → rally estrecho, cuidado.")

    # --- Método del usuario (medias) ---
    precio, ma5, ma15 = spy["precio"], spy["ma5m"], spy["ma15m"]
    if precio is not None and ma5 is not None and ma15 is not None:
        sobre = precio > ma5 and precio > ma15
        debajo = precio < ma5 and precio < ma15
        if sobre:
            lineas.append("SPY cotiza POR ENCIMA de la MA200(5m) y MA75(15m) → sesgo CALLS según tu método.")
        elif debajo:
            lineas.append("SPY cotiza POR DEBAJO de la MA200(5m) y MA75(15m) → sesgo PUTS según tu método.")
        else:
            lineas.append("SPY está entre las dos medias → zona de indecisión, espera confirmación.")
    else:
        lineas.append("No se pudieron calcular las medias de SPY (poca liquidez o mercado cerrado).")

    # --- Aviso de solapamiento europeo ---
    ahora = datetime.now(ET)
    minutos = ahora.hour * 60 + ahora.minute
    if 11 * 60 + 5 <= minutos <= 11 * 60 + 35:
        lineas.append("⚠️ Cerca del cierre de Europa (11:30 ET): posible giro o calma.")

    return lineas


# ============================== REPORTE ===============================

def separador(caracter: str = "=", largo: int = 62) -> str:
    return caracter * largo


def imprimir_reporte():
    ahora = datetime.now(ET)
    fecha = f"{DIAS_SEMANA[ahora.weekday()]} {ahora.day} de {MESES[ahora.month - 1]} de {ahora.year}"
    hora = ahora.strftime("%H:%M ET")

    print()
    print(separador())
    print(pintar("  ANÁLISIS PRE-MERCADO — SPY INTRADÍA", C.NEGRITA))
    print(f"  {fecha} · {hora}")
    print(separador())

    # ---------- Futuros EE.UU. ----------
    print("\n" + pintar("▶ FUTUROS EE.UU.", C.AZUL))
    cambios = {}
    for ticker, (etiqueta, nombre) in FUTUROS_USA.items():
        dato = obtener_cotizacion(ticker)
        if dato is None:
            print(f"  {etiqueta:5s} {nombre:14s}  (sin datos)")
            continue
        precio, _, cambio = dato
        cambios[etiqueta] = cambio
        print(f"  {etiqueta:5s} {nombre:14s} {precio:>12,.2f}   {cambio:+6.2f}%  {flecha(cambio)}")

    # ---------- VIX ----------
    print("\n" + pintar("▶ VOLATILIDAD (VIX)", C.AZUL))
    dato_vix = obtener_cotizacion(TICKER_VIX)
    cambio_vix = None
    if dato_vix is not None:
        precio_vix, _, cambio_vix = dato_vix
        nivel = "bajo" if precio_vix < 15 else ("medio" if precio_vix < 22 else "alto")
        print(f"  /VX   VIX           {precio_vix:>12,.2f}   {cambio_vix:+6.2f}%  {flecha(cambio_vix)}  (nivel {nivel})")
    else:
        print("  (sin datos)")

    # ---------- Alineación ----------
    print("\n" + pintar("▶ ALINEACIÓN", C.AZUL))
    estado, arriba, abajo = analizar_alineacion(cambios)
    if estado == "TODOS AL ALZA":
        print("  " + pintar(f"✔ {estado}", C.VERDE))
    elif estado == "TODOS A LA BAJA":
        print("  " + pintar(f"✔ {estado}", C.ROJO))
    else:
        print("  " + pintar(f"⚠ {estado} ({arriba} arriba / {abajo} abajo)", C.AMARILLO))

    # ---------- Contexto global ----------
    print("\n" + pintar("▶ CONTEXTO GLOBAL (Asia / Europa)", C.AZUL))
    for ticker, (nombre, region) in INDICES_GLOBALES.items():
        dato = obtener_cotizacion(ticker)
        if dato is None:
            print(f"  {nombre:16s} ({region:11s})  (sin datos)")
            continue
        _, _, cambio = dato
        print(f"  {nombre:16s} ({region:11s}) {cambio:+6.2f}%  {flecha(cambio)}")

    # ---------- Tu método ----------
    print("\n" + pintar("▶ TU MÉTODO (SPY vs medias)", C.AZUL))
    spy = medias_spy()
    if spy["precio"] is not None:
        print(f"  SPY (último precio): {spy['precio']:.2f}")
    if spy["ma5m"] is not None:
        marca = "POR ENCIMA ✔" if spy["precio"] and spy["precio"] > spy["ma5m"] else "POR DEBAJO ✘"
        print(f"  MA200 (5 min):       {spy['ma5m']:.2f}   → precio {marca}")
    else:
        print("  MA200 (5 min):       (sin datos suficientes)")
    if spy["ma15m"] is not None:
        marca = "POR ENCIMA ✔" if spy["precio"] and spy["precio"] > spy["ma15m"] else "POR DEBAJO ✘"
        print(f"  MA75  (15 min):      {spy['ma15m']:.2f}   → precio {marca}")
    else:
        print("  MA75  (15 min):      (sin datos suficientes)")

    # ---------- Correlaciones ----------
    print("\n" + pintar("▶ CORRELACIONES (últimos 3 meses, aprox.)", C.AZUL))
    corr = matriz_correlacion()
    if corr is not None:
        etiquetas = [ETIQUETAS_CORRELACION.get(t, t) for t in corr.columns]
        encabezado = "      " + "".join(f"{e:>8s}" for e in etiquetas)
        print("  " + encabezado)
        for fila, etiqueta in zip(corr.values, etiquetas):
            valores = "".join(f"{v:>8.2f}" for v in fila)
            print(f"  {etiqueta:>4s} {valores}")
    else:
        print("  (no se pudieron calcular)")

    # ---------- Lectura del día ----------
    print("\n" + separador("-"))
    print(pintar("▶ LECTURA DEL DÍA", C.NEGRITA))
    print(separador("-"))
    for linea in lectura_del_dia(cambios, cambio_vix, spy):
        print(f"  • {linea}")

    print("\n" + separador())
    print(pintar("  Datos con retraso (~15 min). Confirma niveles en thinkorswim.", C.GRIS))
    print(pintar("  Este análisis es de contexto, no una recomendación de inversión.", C.GRIS))
    print(separador())
    print()


if __name__ == "__main__":
    imprimir_reporte()
