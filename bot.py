import os
import io
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import ta

# 1. Configuración de API Keys desde Variables de Entorno (Seguridad)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# Memoria temporal para tu portafolio
portafolio_actual = {}

# 2. Funciones de Análisis Técnico (Evaluación Tickers)
def analizar_ticker(ticker_symbol):
    """
    Aplica las reglas de análisis técnico al activo.
    """
    try:
        # Descargamos los últimos 60 días para tener datos suficientes para RSI y Medias Móviles
        datos = yf.Ticker(ticker_symbol).history(period="60d")
        if datos.empty or len(datos) < 20:
            return None
        
        # Último precio
        precio_actual = datos['Close'].iloc[-1]
        
        # Calcular RSI (14 periodos)
        datos['RSI'] = ta.momentum.RSIIndicator(datos['Close'], window=14).rsi()
        rsi_actual = datos['RSI'].iloc[-1]
        
        # Análisis de Volumen Inusual (Volumen actual vs Promedio de 20 días)
        volumen_actual = datos['Volume'].iloc[-1]
        volumen_promedio_20d = datos['Volume'].rolling(window=20).mean().iloc[-2] # Día anterior
        
        alertas = []
        
        # Regla 1: RSI en zona extrema
        if rsi_actual < 30:
            alertas.append(f"⚠️ *Sobrevendido* (RSI: {rsi_actual:.1f}). Posible oportunidad de rebote.")
        elif rsi_actual > 70:
            alertas.append(f"🔥 *Sobrecomprado* (RSI: {rsi_actual:.1f}). Evaluar toma de ganancias.")
            
        # Regla 2: Flujo Institucional (Volumen un 50% superior a la media)
        if volumen_actual > (volumen_promedio_20d * 1.5):
            alertas.append(f"📊 *Volumen Inusual* detectado. Flujo fuerte.")
            
        return {
            'precio': precio_actual,
            'alertas': alertas
        }
    except Exception as e:
        print(f"Error analizando {ticker_symbol}: {e}")
        return None

# 3. Interacciones de Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respuesta inicial del bot."""
    mensaje = (
        "🤖 ¡Hola! Soy tu bot de portafolio y análisis.\n\n"
        "Envíame una captura de pantalla de InvertirOnline y extraeré los datos automáticamente.\n"
        "Puedes usar /analizar en cualquier momento para revisar el mercado."
    )
    await update.message.reply_text(mensaje)

async def recibir_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la imagen enviada por el usuario usando Gemini Vision."""
    await update.message.reply_text("📸 Imagen recibida. Analizando tu portafolio con IA...")
    
    try:
        # Descargar la imagen de Telegram
        photo_file = await update.message.photo[-1].get_file()
        photo_byte_array = await photo_file.download_as_bytearray()
        
        # Preparar la imagen para Gemini
        imagen = {
            "mime_type": "image/jpeg",
            "data": photo_byte_array
        }
        
        # Instrucción para Gemini
        prompt = (
            "Eres un analista financiero. Lee esta captura de pantalla de un portafolio de InvertirOnline. "
            "Devuélveme SOLO una lista de los CEDEARs o acciones (ej. DIA, NVDA, SPY) junto con la cantidad "
            "y el precio promedio de compra. Ignora los fondos mutuos o el efectivo. "
            "El formato exacto de tu respuesta debe ser así (sin comillas ni texto adicional): "
            "TICKER,CANTIDAD,PRECIO_COMPRA. Un activo por línea."
        )
        
        # Consultar a Gemini 1.5 Flash (Rápido y económico para visión)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, imagen])
        
        # Procesar la respuesta de Gemini y guardarla en la memoria del bot
        global portafolio_actual
        portafolio_actual.clear()
        
        lineas = response.text.strip().split('\n')
        for linea in lineas:
            if ',' in linea:
                partes = linea.split(',')
                if len(partes) == 3:
                    ticker = partes[0].strip() + '.BA' # Aseguramos formato argentino
                    try:
                        cantidad = float(partes[1].strip())
                        precio_compra = float(partes[2].strip())
                        portafolio_actual[ticker] = {'cantidad': cantidad, 'precio': precio_compra}
                    except ValueError:
                        continue
        
        if portafolio_actual:
            activos_encontrados = ", ".join(portafolio_actual.keys()).replace('.BA', '')
            await update.message.reply_text(f"✅ ¡Portafolio actualizado!\nDetecté: {activos_encontrados}")
        else:
            await update.message.reply_text("⚠️ No pude encontrar activos legibles en la imagen. Intenta con una captura más clara.")
            
    except Exception as e:
         await update.message.reply_text(f"❌ Ocurrió un error al procesar la imagen: {e}")

async def comando_analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ejecuta el análisis técnico de los activos en memoria."""
    if not portafolio_actual:
        await update.message.reply_text("🤷‍♂️ Aún no tengo tu portafolio. ¡Envíame una captura primero!")
        return
        
    await update.message.reply_text("🔍 Ejecutando análisis técnico sobre tus activos...")
    
    mensaje_final = "📈 *Resultados del Análisis Técnico*\n\n"
    hubo_alertas = False
    
    for ticker, datos in portafolio_actual.items():
        nombre_limpio = ticker.replace('.BA', '')
        analisis = analizar_ticker(ticker)
        
        if analisis:
            if analisis['alertas']:
                hubo_alertas = True
                mensaje_final += f"*{nombre_limpio}* (Precio: ${analisis['precio']:.2f})\n"
                for alerta in analisis['alertas']:
                    mensaje_final += f"  {alerta}\n"
                mensaje_final += "\n"
    
    if hubo_alertas:
        await update.message.reply_text(mensaje_final, parse_mode='Markdown')
    else:
        await update.message.reply_text("✅ Análisis completo. Ninguno de tus activos presenta alertas técnicas críticas (RSI extremo o volumen inusual) en este momento.")

# 4. Inicialización del Servidor
def main():
    if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
        print("ERROR: Faltan claves de API en las variables de entorno.")
        return

    # Construir la aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Agregar comandos y manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analizar", comando_analizar))
    app.add_handler(MessageHandler(filters.PHOTO, recibir_imagen))
    
    # Iniciar el bot de forma continua
    print("Bot iniciando en servidor...")
    app.run_polling(poll_interval=3)

if __name__ == '__main__':
    main()