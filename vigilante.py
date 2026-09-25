import os
import urllib.request
import json
import datetime

# Credenciales de entorno
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Tu portafolio (Esto es lo único que actualizaremos cuando me pases la captura)
PORTAFOLIO = {
    'DIA.BA':  {'cantidad': 24, 'precio_compra': 41120.00},
    'NVDA.BA': {'cantidad': 65, 'precio_compra': 15022.31},
    'SPY.BA':  {'cantidad': 91, 'precio_compra': 20450.55},
    'TSM.BA':  {'cantidad': 11, 'precio_compra': 74450.00},
    'XLE.BA':  {'cantidad': 10, 'precio_compra': 50675.00}
}

def obtener_precio_yahoo(ticker):
    """Obtiene el último precio y volumen de Yahoo Finance de forma ligera (sin librerías pesadas)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            cierres = data['chart']['result'][0]['indicators']['quote'][0]['close']
            volumenes = data['chart']['result'][0]['indicators']['quote'][0]['volume']
            # Filtramos valores nulos
            cierres = [c for c in cierres if c is not None]
            volumenes = [v for v in volumenes if v is not None]
            
            if len(cierres) >= 2:
                precio_actual = cierres[-1]
                precio_anterior = cierres[-2]
                volumen_actual = volumenes[-1]
                volumen_promedio = sum(volumenes) / len(volumenes)
                return precio_actual, precio_anterior, volumen_actual, volumen_promedio
    except Exception as e:
        print(f"Error con {ticker}: {e}")
    return None, None, None, None

def calcular_rsi_simple(precios):
    """Cálculo simplificado de RSI (requiere más historial, aquí hacemos una aproximación para no cargar el servidor)."""
    # Para un vigilante ligero, nos basaremos en variaciones de precio fuerte en lugar de un RSI de 14 días complejos.
    pass

def analizar_mercado():
    print(f"Iniciando escaneo de mercado: {datetime.datetime.now()}")
    alertas_generadas = []
    
    for ticker, datos in PORTAFOLIO.items():
        precio_actual, precio_anterior, vol_actual, vol_promedio = obtener_precio_yahoo(ticker)
        
        if precio_actual:
            variacion_diaria = ((precio_actual - precio_anterior) / precio_anterior) * 100
            rendimiento_total = ((precio_actual - datos['precio_compra']) / datos['precio_compra']) * 100
            nombre_limpio = ticker.replace('.BA', '')
            
            # --- TÁCTICAS Y ESTRATEGIAS (Tus reglas) ---
            
            # 1. Alarma de Stop Loss / Toma de Ganancias
            if rendimiento_total < -5.0:
                alertas_generadas.append(f"🔴 *STOP LOSS SUGERIDO:* {nombre_limpio} ha caído un {rendimiento_total:.2f}% desde tu compra. Evaluar salida.")
            elif rendimiento_total > 15.0:
                alertas_generadas.append(f"🟢 *TOMA DE GANANCIAS:* {nombre_limpio} subió un {rendimiento_total:.2f}%. Considera ajustar Stop Loss hacia arriba (Trailing Stop).")
                
            # 2. Movimiento Brusco Diario (Posible piso/techo)
            if variacion_diaria < -3.0:
                alertas_generadas.append(f"📉 *CAÍDA FUERTE:* {nombre_limpio} bajó {variacion_diaria:.2f}% hoy. Revisar si tocó un soporte histórico para posible rebote.")
            elif variacion_diaria > 3.0:
                alertas_generadas.append(f"🚀 *SUBIDA FUERTE:* {nombre_limpio} subió {variacion_diaria:.2f}% hoy.")
                
            # 3. Flujo Institucional (Volumen)
            if vol_promedio > 0 and vol_actual > (vol_promedio * 1.5):
                alertas_generadas.append(f"📊 *VOLUMEN INUSUAL:* {nombre_limpio} está operando un 50% por encima de su promedio. Gran interés institucional hoy.")

    # Enviar notificaciones SOLO si hay alertas
    if alertas_generadas:
        mensaje = "⚠️ *VIGILANTE DE PORTAFOLIO: ALERTAS TÁCTICAS*\n\n"
        for alerta in alertas_generadas:
            mensaje += f"{alerta}\n\n"
            
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensaje, 'parse_mode': 'Markdown'}
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)
        print("Alertas enviadas a Telegram.")
    else:
        print("Mercado tranquilo. No hay alertas tácticas que reportar.")

if __name__ == "__main__":
    analizar_mercado()
