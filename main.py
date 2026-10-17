import os
import json
import sqlite3
import datetime
import requests
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

# ==========================================
# CONFIGURACIONES Y VARIABLES DE ENTORNO
# ==========================================
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "entra_webhook_token_2026")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MI_WHATSAPP_NOTIFICACIONES = "573112338416"
URL_REGISTRO_WELTRADE = "https://gowt.net/ib62670"
URL_VIDEO_WELTRADE = "https://youtu.be/7CfHPBsIDC4"
URL_TELEGRAM_SOPORTE = "https://t.me/soportecomunidadentra"

# URLs de Activos Multimedia en GitHub
URL_IMG_P1 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje1-bienvenida.jpg"
URL_IMG_P2 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje2-beneficios.jpeg"
URL_IMG_P3 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje3-guia-id.jpg"
URL_IMG_P4 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje4-telegram.jpg"
URL_AUDIO_P4 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/audio-bienvenida-telegram.mp3"
URL_VIDEO_1 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/video-seguimiento-1.mp4"
URL_VIDEO_2 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/video-seguimiento-2.mp4"

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# GESTIÓN DE BASE DE DATOS (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect("embudo_entra.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            telefono TEXT PRIMARY KEY,
            nombre TEXT,
            etapa INTEGER DEFAULT 0,
            id_weltrade TEXT,
            ultimo_contacto TIMESTAMP,
            seguimiento_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def obtener_usuario(telefono, nombre=""):
    conn = sqlite3.connect("embudo_entra.db")
    c = conn.cursor()
    c.execute("SELECT telefono, nombre, etapa, id_weltrade, ultimo_contacto, seguimiento_count FROM usuarios WHERE telefono = ?", (telefono,))
    row = c.fetchone()
    ahora = datetime.datetime.now().isoformat()
    if not row:
        c.execute("INSERT INTO usuarios (telefono, nombre, etapa, id_weltrade, ultimo_contacto, seguimiento_count) VALUES (?, ?, ?, ?, ?, ?)",
                  (telefono, nombre, 0, None, ahora, 0))
        conn.commit()
        usuario = {"telefono": telefono, "nombre": nombre, "etapa": 0, "id_weltrade": None, "ultimo_contacto": ahora, "seguimiento_count": 0}
    else:
        usuario = {"telefono": row[0], "nombre": row[1] if row[1] else nombre, "etapa": row[2], "id_weltrade": row[3], "ultimo_contacto": row[4], "seguimiento_count": row[5]}
    conn.close()
    return usuario

def actualizar_usuario(telefono, **kwargs):
    conn = sqlite3.connect("embudo_entra.db")
    c = conn.cursor()
    campos = []
    valores = []
    for k, v in kwargs.items():
        campos.append(f"{k} = ?")
        valores.append(v)
    valores.append(datetime.datetime.now().isoformat())
    valores.append(telefono)
    sql = f"UPDATE usuarios SET {', '.join(campos)}, ultimo_contacto = ? WHERE telefono = ?"
    c.execute(sql, tuple(valores))
    conn.commit()
    conn.close()

# ==========================================
# ENVÍO DE MENSAJES WHATSAPP CLOUD API
# ==========================================
def enviar_peticion_whatsapp(payload):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"Error enviando mensaje WhatsApp: {e}")
        return None

def enviar_texto(destinatario, texto):
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "text",
        "text": {"body": texto}
    }
    return enviar_peticion_whatsapp(payload)

def enviar_imagen(destinatario, url_imagen, caption=""):
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "image",
        "image": {"link": url_imagen}
    }
    if caption:
        payload["image"]["caption"] = caption
    return enviar_peticion_whatsapp(payload)

def enviar_audio(destinatario, url_audio):
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "audio",
        "audio": {"link": url_audio}
    }
    return enviar_peticion_whatsapp(payload)

def enviar_video(destinatario, url_video, caption=""):
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "video",
        "video": {"link": url_video}
    }
    if caption:
        payload["video"]["caption"] = caption
    return enviar_peticion_whatsapp(payload)

# ==========================================
# ANÁLISIS CON GEMINI Y REENFOQUE
# ==========================================
def procesar_respuesta_gemini(usuario, mensaje_usuario):
    prompt_sistema = f"""
    Eres el asistente oficial de ENTRA (Entrena Traders).
    El usuario actual se llama {usuario['nombre']} y se encuentra en la etapa {usuario['etapa']} del embudo.

    ETAPAS DEL EMBUDO:
    - Etapa 0: Apenas ingresa. Esperamos saludarlo y saber si tiene experiencia en trading.
    - Etapa 1: Ya saludó. Debemos presentarle los beneficios de la comunidad gratuita.
    - Etapa 2: Mostramos beneficios. El siguiente paso es invitarlo a registrarse en Weltrade con el link oficial ({URL_REGISTRO_WELTRADE}), abrir su cuenta demo/real SyntX y pedirle su ID.
    - Etapa 3: Esperamos que envíe su ID de Weltrade (o captura). Si tiene objeción de fondos, recuerda que el registro y la formación son 100% gratuitos, que opera en DEMO sin arriesgar dinero, y si algún día decide monetizar en real, el depósito es opcional desde $10 USD.
    - Etapa 4: Ya envió su ID, fue notificado y debe pasar a Telegram ({URL_TELEGRAM_SOPORTE}).

    INSTRUCCIONES:
    1. Si el usuario hace preguntas generales (ej. ¿qué es trading?, ¿qué son índices sintéticos?, ¿por qué ese broker?, ¿es gratis?), responde con amabilidad, solidez y brevedad (máximo 2 párrafos).
    2. SIEMPRE reenfoca al usuario a completar la acción de su etapa actual con un llamado claro a la acción.
    3. Si el usuario te indica su nivel de experiencia, valida amablemente y anímalo a ver los beneficios.
    4. Detecta si el usuario está enviando un ID de Weltrade (usualmente un número entero entre 6 y 8 dígitos). Responde en JSON con la siguiente estructura:
       {{
         "es_id": true/false,
         "id_detectado": "el_numero_o_null",
         "respuesta_texto": "texto_de_respuesta_o_reenfoque"
       }}
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{prompt_sistema}\nMensaje del usuario: {mensaje_usuario}",
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error procesando con Gemini: {e}")
        return {"es_id": False, "id_detectado": None, "respuesta_texto": "Cuéntame, ¿pudiste revisar el paso anterior para continuar con tus accesos?"}

def procesar_imagen_gemini(image_bytes):
    prompt_ocr = """
    Analiza esta captura de pantalla de la plataforma de Weltrade o SyntX.
    Debes identificar si en la imagen aparece el 'ID' del usuario (antepuesto de la palabra ID: o cerca de su perfil/cuenta).
    NO lo confundas con el número de cuenta de trading de SyntX (que suele ser largo y diferente).
    Devuelve un JSON con:
    {
      "es_valida": true/false,
      "id_extraido": "numero_o_null",
      "motivo": "explicacion_breve"
    }
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt_ocr
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error OCR con Gemini: {e}")
        return {"es_valida": False, "id_extraido": None, "motivo": "Error leyendo imagen"}

# ==========================================
# LÓGICA DEL EMBUDO (DISPARO DE MENSAJES)
# ==========================================
def despachar_paso_1(telefono, nombre):
    enviar_imagen(telefono, URL_IMG_P1)
    texto = (
        f"¡Hola {nombre}! Te saluda el equipo de ENTRA (Entrena Traders). 📊🚀\n\n"
        "Te damos una bienvenida oficial. Estamos aquí para acompañarte paso a paso en tu proceso de formación en índices sintéticos.\n\n"
        "Para brindarte la mejor orientación: ¿tienes alguna experiencia previa operando los mercados o estás empezando completamente desde cero?"
    )
    enviar_texto(telefono, texto)
    actualizar_usuario(telefono, etapa=1)

def despachar_paso_2(telefono):
    enviar_imagen(telefono, URL_IMG_P2)
    texto = (
        "¡Excelente! En ENTRA te acompañamos desde lo más básico hasta niveles avanzados.\n\n"
        "Te recuerdo todo lo que recibes de forma 100% gratuita al ser parte de nuestra comunidad:\n"
        "🔹 Cursos educativos organizados paso a paso.\n"
        "🔹 6 clases y sesiones en vivo al día para aprender la operativa real.\n"
        "🔹 Acompañamiento y soporte continuo.\n"
        "🔹 Acceso a operar en cuentas de demostración sin arriesgar tu dinero.\n\n"
        "¿Deseas que te comparta el enlace oficial para habilitar tus accesos?"
    )
    enviar_texto(telefono, texto)
    actualizar_usuario(telefono, etapa=2)

def despachar_paso_3(telefono):
    texto = (
        "Para vincularte a nuestra comunidad y asignarte todos tus accesos gratuitos, el único requisito es abrir tu cuenta en nuestro broker aliado Weltrade a través de este enlace:\n\n"
        f"🔗 Registro oficial: {URL_REGISTRO_WELTRADE}\n\n"
        f"📺 Video guía paso a paso: {URL_VIDEO_WELTRADE}\n\n"
        "Pasos rápidos:\n"
        "1. Regístrate en el enlace con tu correo.\n"
        "2. Crea tu cuenta de trading SyntX (puedes activar tanto la Real como la Demo de práctica).\n"
        "3. Recuerda que la formación es gratuita y operarás en DEMO; no estás obligado a depositar.\n\n"
        "A continuación te comparto una imagen que te muestra exactamente dónde encuentras tu ID."
    )
    enviar_texto(telefono, texto)
    enviar_imagen(telefono, URL_IMG_P3, caption="El ID es el número que aparece junto a tu nombre de usuario en la parte superior.")
    actualizar_usuario(telefono, etapa=3)

def despachar_paso_4(telefono, id_weltrade, nombre):
    # 1. Alerta a tu WhatsApp personal
    alerta_personal = (
        f"🔔 *NUEVO PROSPECTO PENDIENTE DE VALIDACIÓN*\n"
        f"👤 Nombre: {nombre}\n"
        f"📱 Teléfono: {telefono}\n"
        f"🆔 ID Weltrade: {id_weltrade}\n\n"
        f"Verifícalo en tu panel de socios: https://gowt.net"
    )
    enviar_texto(MI_WHATSAPP_NOTIFICACIONES, alerta_personal)

    # 2. Despacho al usuario: Imagen + Audio + Texto Telegram
    enviar_imagen(telefono, URL_IMG_P4)
    enviar_audio(telefono, URL_AUDIO_P4)
    
    mensaje_telegram = (
        "¡Perfecto! Ya validamos tu información y quiero darte la bienvenida oficial a nuestra comunidad.\n\n"
        "A partir de este momento continuamos todo el proceso a través de Telegram, donde te entregaré el acceso a los cursos, sesiones en vivo y beneficios.\n\n"
        f"👉 Únete aquí a nuestro canal de soporte: {URL_TELEGRAM_SOPORTE}\n\n"
        "⚠️ *Importante:* Al ingresar a Telegram, compárteme estos 3 datos para habilitar tus accesos:\n"
        "1. Tu nombre\n"
        "2. Tu país\n"
        f"3. Código de vinculación: *{id_weltrade}*"
    )
    enviar_texto(telefono, mensaje_telegram)
    actualizar_usuario(telefono, etapa=4, id_weltrade=id_weltrade)

# ==========================================
# WEBHOOK DE WHATSAPP (RECEPCIÓN)
# ==========================================
@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Error de verificación", 403

@app.route("/webhook", methods=["POST"])
def recibir_webhook():
    data = request.get_json()
    if not data or "entry" not in data:
        return jsonify({"status": "ignored"}), 200

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                contacts = value.get("contacts", [])

                if not messages:
                    continue

                msg = messages[0]
                remitente = msg.get("from")
                nombre_contacto = contacts[0].get("profile", {}).get("name", "amigo") if contacts else "amigo"
                tipo_msg = msg.get("type")

                usuario = obtener_usuario(remitente, nombre_contacto)

                # --- 1. SI EL USUARIO ENVÍA UNA IMAGEN ---
                if tipo_msg == "image":
                    image_id = msg.get("image", {}).get("id")
                    # Descargar URL de la imagen de WhatsApp
                    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                    media_meta = requests.get(f"https://graph.facebook.com/v19.0/{image_id}", headers=headers).json()
                    media_url = media_meta.get("url")
                    img_data = requests.get(media_url, headers=headers).content

                    resultado_ocr = procesar_imagen_gemini(img_data)
                    if resultado_ocr.get("es_valida") and resultado_ocr.get("id_extraido"):
                        despachar_paso_4(remitente, resultado_ocr["id_extraido"], usuario["nombre"])
                    else:
                        texto_aclaracion = (
                            "Veo la imagen que enviaste, pero no logramos identificar el número de ID de registro.\n\n"
                            "Ten en cuenta que necesitamos el número de ID principal que aparece en la parte superior junto a tu nombre (no el número de cuenta SyntX). Revisa la imagen guía que te compartí arriba."
                        )
                        enviar_texto(remitente, texto_aclaracion)
                    return jsonify({"status": "ok"}), 200

                # --- 2. SI EL USUARIO ENVÍA TEXTO ---
                if tipo_msg == "text":
                    texto_usuario = msg.get("text", {}).get("body", "").strip()

                    # Si es la primera interacción (Etapa 0)
                    if usuario["etapa"] == 0:
                        despachar_paso_1(remitente, usuario["nombre"])
                        return jsonify({"status": "ok"}), 200

                    # Procesar con Gemini para interpretar intención, dudas o ID
                    analisis = procesar_respuesta_gemini(usuario, texto_usuario)

                    if analisis.get("es_id") and analisis.get("id_detectado"):
                        despachar_paso_4(remitente, analisis["id_detectado"], usuario["nombre"])
                        return jsonify({"status": "ok"}), 200

                    # Avanzar etapas según flujo natural si no es una duda dispersa
                    if usuario["etapa"] == 1:
                        # Si respondió a su experiencia, enviamos beneficios
                        enviar_texto(remitente, analisis.get("respuesta_texto"))
                        despachar_paso_2(remitente)
                    elif usuario["etapa"] == 2:
                        # Si mostró interés en seguir, entregamos el link de registro
                        despachar_paso_3(remitente)
                    elif usuario["etapa"] == 3:
                        # Si está en etapa de registro y no envió ID, Gemini responde a su duda/objeción y reenfoca
                        enviar_texto(remitente, analisis.get("respuesta_texto"))
                    elif usuario["etapa"] == 4:
                        # Recordatorio amable de Telegram si vuelve a escribir en WhatsApp
                        texto_t = f"¡Hola! Recuerda que todo tu proceso y tus accesos los estamos activando en Telegram:\n👉 {URL_TELEGRAM_SOPORTE}"
                        enviar_texto(remitente, texto_t)

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error procesando webhook: {e}")
        return jsonify({"status": "error"}), 500

# ==========================================
# RUTINA DE SEGUIMIENTOS (FOLLOW-UPS)
# ==========================================
@app.route("/ejecutar-seguimientos", methods=["GET"])
def ejecutar_seguimientos():
    """
    Ruta para ser ejecutada por un cron job (ej. cron-job.org) cada 30 o 60 minutos.
    Revisa prospectos con más de 4 horas de inactividad dentro de la ventana de 24 horas.
    """
    conn = sqlite3.connect("embudo_entra.db")
    c = conn.cursor()
    c.execute("SELECT telefono, nombre, etapa, ultimo_contacto, seguimiento_count FROM usuarios WHERE etapa BETWEEN 1 AND 3")
    usuarios = c.fetchall()
    conn.close()

    ahora = datetime.datetime.now()

    for u in usuarios:
        telefono, nombre, etapa, ultimo_contacto_str, seg_count = u
        ultimo_contacto = datetime.datetime.fromisoformat(ultimo_contacto_str)
        horas_transcurridas = (ahora - ultimo_contacto).total_seconds() / 3600.0

        # Si han pasado más de 4 horas sin respuesta
        if horas_transcurridas >= 4.0:
            if etapa == 1 and seg_count == 0:
                despachar_paso_2(telefono)
                actualizar_usuario(telefono, seguimiento_count=1)
            elif etapa == 2 and seg_count < 2:
                despachar_paso_3(telefono)
                actualizar_usuario(telefono, seguimiento_count=2)
            elif etapa == 3:
                if seg_count == 2:
                    # Video 1: Sentirse solo vs Comunidad
                    enviar_video(telefono, URL_VIDEO_1, caption="Aprender trading en solitario puede ser difícil. En ENTRA cuentas con todo el apoyo en cuenta Demo desde cero.")
                    actualizar_usuario(telefono, seguimiento_count=3)
                elif seg_count == 3 and horas_transcurridas >= 8.0:
                    # Video 2: Remate final (más de 10.000 miembros y palabra ENTRA)
                    enviar_video(telefono, URL_VIDEO_2, caption="Ya somos más de 10.000 miembros formándonos juntos. Si estás listo para iniciar, responde con la palabra ENTRA.")
                    actualizar_usuario(telefono, seguimiento_count=4)

    return jsonify({"status": "seguimientos ejecutados"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
