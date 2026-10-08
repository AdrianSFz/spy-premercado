# SPY Pre-Mercado — Análisis intradía

Script en Python que analiza el mercado cada mañana antes de la apertura de Wall Street,
para ayudar a definir el sesgo de operación en **SPY**.

## Qué analiza

1. **Futuros de EE.UU.**: ES, NQ, YM, RTY y el VIX — movimiento overnight.
2. **Alineación y divergencias**: NQ vs ES, RTY vs ES.
3. **Contexto global**: Nikkei, Hang Seng, DAX, Euro Stoxx 50, FTSE 100 y CAC 40.
4. **Método de medias**: SPY contra la MA200 (5 min) y la MA75 (15 min) → sesgo calls/puts.
5. **Correlaciones** recientes entre los futuros y el VIX.
6. **Lectura del día**: risk-on, risk-off o mixto.

Todos los horarios se muestran en **hora del Este (ET)** de EE.UU.

## Instalación

Requisitos: **Python 3.10+**

```bash
pip install -r requirements.txt