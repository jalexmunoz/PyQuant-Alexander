import requests
import time

# URL de tu proyecto en Render (según tus notas anteriores)
# Si cambiaste la ruta en webhook_receiver.py, ajusta "/tradingview" por "/webhook"
RENDER_URL = "https://pyquant-alexander.onrender.com/tradingview"

payload = {
    "ticker": "BTCUSDT",           # <--- Ticker real que está en tu portafolio
    "price": 95000,
    "sma50": 96000,                # <--- SMA50 > SMA200 = señal ON (cruce alcista)
    "sma200": 88000,               # <--- Para que sea cross ON, necesitamos sma50 > sma200
    "signal": "ON",                # <--- ON = cruce alcista (SMA50 cruzó arriba de SMA200)
    "event_type": "cross",         # <--- Tipo de evento: cross
    "secret": "pyquant_shadow_2025_xyz123", # (La que empieza con pyquant...)
    "strategy": "CES_v1_Shadow",
    "time": "2026-01-18T16:00:00Z"
}

print(f"🚀 Enviando misil de prueba a: {RENDER_URL}")

try:
    # Simulamos lo que hace TradingView (POST request)
    response = requests.post(RENDER_URL, json=payload, timeout=10)
    
    print(f"📡 Estado HTTP: {response.status_code}")
    print(f"📄 Respuesta: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ Render recibió el mensaje. Ahora revisa Supabase...")
        print("Busca en la tabla 'raw_events' un registro con ticker 'PROD_TEST_BTC'.")
    else:
        print("\n⚠️ Render rechazó la conexión. Revisa los logs en el dashboard de Render.")

except Exception as e:
    print(f"\n❌ Error de conexión: {e}")