import os
import json
import sqlite3
import datetime
import re
import requests
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

# ==========================================
# CONFIGURACIONES Y CREDENCIALES
# ==========================================
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "entra_webhook_token_2026")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MI_WHATSAPP_NOTIFICACIONES = "573112338416"
URL_REGISTRO_WELTRADE = "https://gowt.net/ib62670"
URL_VIDEO_WELTRADE = "https://youtu.be/7CfHPBsIDC4"
URL_TELEGRAM_SOPORTE = "https://t.me/soportecomunidadentra"

# URLs de Activos Multimedia en GitHub (con nombres exactos de los archivos)
URL_IMG_PASO_1 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje1-bienvenida.jpg.jpeg"
URL_IMG_P2 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje2-beneficios.jpeg.jpeg"
URL_IMG_P3 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje3-guia-id.jpg.png"
URL_IMG_P4 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje4-telegram.jpg.png"
URL_AUDIO_P4 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/audio-bienvenida-telegram.mp3"
URL_VIDEO_1 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/video-seguimiento-1.mp4.mp4"
URL_VIDEO_2 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/video-seguimiento-2.mp4.mp4"

ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ==========================================
# BASE DE DATOS
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

def reiniciar_usuario(telefono):
    conn = sqlite3.connect("embudo_entra.db")
    c = conn.cursor()
    c.execute("DELETE FROM usuarios WHERE telefono = ?", (telefono,))
    conn.commit()
    conn.close()

# ==========================================
# ENVÍOS CON WHATSAPP API
# ==========================================
def enviar_peticion_whatsapp(payload):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Respuesta WhatsApp: {resp.status_code} - {resp.text}")
        return resp.json()
    except Exception as e:
        print(f"Error WhatsApp: {e}")
        return None

def enviar_texto(destinatario, texto):
    return enviar_peticion_whatsapp({
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "text",
        "text": {"body": texto}
    })

def enviar_imagen_con_caption(destinatario, url_imagen, caption_texto):
    # Envía la imagen con el texto integrado en el pie de foto
    return enviar_peticion_whatsapp({
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "image",
        "image": {
            "link": url_imagen,
            "caption": caption_texto
        }
    })

def enviar_audio(destinatario, url_audio):
    return enviar_peticion_whatsapp({
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "audio",
        "audio": {"link": url_audio}
    })

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
# MENSAJES EXACTOS DEL EMBUDO
# ==========================================
def despachar_paso_1(telefono, nombre):
    texto = (
        f"¡Hola! Te damos la bienvenida a ENTRA (Entrena Traders). 📊🚀\n\n"
        "Somos una comunidad enfocada en la formación práctica en trading de índices sintéticos.\n\n"
        "Para conocer tu punto de partida: ¿tienes alguna experiencia previa operando en los mercados o te gustaría aprender completamente desde cero?"
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P1, texto)
    actualizar_usuario(telefono, etapa=1)

def despachar_paso_2(telefono):
    texto = (
        "¡Excelente! En ENTRA te acompañamos paso a paso sin importar tu nivel.\n\n"
        "Formar parte de nuestra comunidad es completamente GRATUITO e incluye:\n"
        "🔹 Cursos educativos completos desde cero.\n"
        "🔹 6 sesiones y clases en vivo al día para aprender la operativa real.\n"
        "🔹 Acompañamiento y soporte continuo.\n"
        "🔹 Práctica en cuentas de demostración sin arriesgar tu capital.\n\n"
        "¿Te gustaría conocer el paso para unirte y habilitar todos tus accesos?"
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P2, texto)
    actualizar_usuario(telefono, etapa=2)

def despachar_paso_3(telefono):
    texto = (
        "Para asignarte tus accesos a la comunidad y a las sesiones en vivo, el único paso es registrarte en nuestro broker aliado Weltrade mediante nuestro enlace oficial:\n\n"
        f"🔗 Enlace de registro: {URL_REGISTRO_WELTRADE}\n\n"
        f"📺 Video guía paso a paso: {URL_VIDEO_WELTRADE}\n\n"
        "Instrucciones breves:\n"
        "1. Crea tu cuenta en Weltrade con tu correo.\n"
        "2. Abre tu cuenta de trading SyntX (puedes habilitar tanto la Real como la Demo para practicar).\n"
        "3. Recuerda que la formación es gratuita y operarás en Demo, no estás obligado a depositar.\n\n"
        "Una vez realizado, envíame por favor tu número de ID o una captura de pantalla donde se vea para verificarlo."
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P3, texto)
    actualizar_usuario(telefono, etapa=3)

def responder_objecion_fondos(telefono):
    texto = (
        "Es totalmente comprensible tu duda. Te confirmo que ser parte de nuestra comunidad, acceder a los cursos y participar en las 6 clases diarias en vivo es **100% GRATUITO**.\n\n"
        "Tampoco es obligatorio depositar dinero en el broker: puedes formarte, practicar y operar en cuenta DEMO de práctica todo el tiempo que desees.\n\n"
        "Si en el futuro tú decides operar con dinero real para monetizar, el depósito mínimo parte desde apenas $10 USD, pero esa decisión es totalmente tuya cuando te sientas preparado.\n\n"
        f"Puedes crear tu cuenta aquí: {URL_REGISTRO_WELTRADE} y enviarme tu número de ID cuando la tengas lista."
    )
    enviar_texto(telefono, texto)

def despachar_paso_4(telefono, id_weltrade, nombre):
    # Alerta a tu WhatsApp personal
    alerta_personal = (
        f"🔔 *NUEVO PROSPECTO PENDIENTE DE VALIDACIÓN*\n"
        f"👤 Nombre: {nombre}\n"
        f"📱 Teléfono: +{telefono}\n"
        f"🆔 ID Weltrade: {id_weltrade}\n\n"
        f"Verifícalo en tu panel: https://gowt.net"
    )
    enviar_texto(MI_WHATSAPP_NOTIFICACIONES, alerta_personal)

    # Imagen + Audio + Texto
    texto_telegram = (
        "¡Perfecto! Ya validamos tu información y quiero darte la bienvenida oficial a nuestra comunidad.\n\n"
        "A partir de este momento continuamos todo el proceso a través de Telegram, donde te entregaré el acceso a los cursos, sesiones en vivo y beneficios.\n\n"
        f"👉 Únete aquí a nuestro canal de soporte: {URL_TELEGRAM_SOPORTE}\n\n"
        "⚠️ *Importante:* Al ingresar a Telegram, compárteme estos 3 datos para habilitar tus accesos:\n"
        "1. Tu nombre\n"
        "2. Tu país\n"
        f"3. Código de vinculación: *{id_weltrade}*"
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P4, texto_telegram)
    enviar_audio(telefono, URL_AUDIO_P4)
    actualizar_usuario(telefono, etapa=4, id_weltrade=id_weltrade)

# ==========================================
# UTILIDADES
# ==========================================
def extraer_id_texto(texto):
    match = re.search(r'\b(\d{6,8})\b', texto)
    return match.group(1) if match else None

def es_pregunta_costos(texto):
    t = texto.lower()
    terminos = ["cuanto", "cuánto", "pagar", "costo", "vale", "precio", "cobran", "depositar", "deposito", "dinero", "gratis"]
    return any(term in t for term in terminos)

def procesar_con_gemini_seguro(prompt):
    if not ai_client:
        return None
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Gemini fallback activado: {e}")
        return None

# ==========================================
# WEBHOOK
# ==========================================
@app.route("/webhook", methods=["GET"])
def verificar():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Error", 403

@app.route("/webhook", methods=["POST"])
def recibir():
    data = request.get_json()
    if not data or "entry" not in data:
        return jsonify({"status": "ok"}), 200

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

                # Comando especial para resetear la prueba
                if tipo_msg == "text":
                    cuerpo = msg.get("text", {}).get("body", "").strip()
                    if cuerpo.upper() in ["RESET", "REINICIAR"]:
                        reiniciar_usuario(remitente)
                        enviar_texto(remitente, "🔄 Conversación reiniciada. Envía un mensaje como 'Hola' para comenzar desde el Paso 1 con su imagen.")
                        return jsonify({"status": "reset"}), 200

                usuario = obtener_usuario(remitente, nombre_contacto)

                # --- 1. RECEPCIÓN DE IMÁGENES (CAPTURA DEL BROKER) ---
                if tipo_msg == "image":
                    image_id = msg.get("image", {}).get("id")
                    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                    media_meta = requests.get(f"https://graph.facebook.com/v19.0/{image_id}", headers=headers).json()
                    media_url = media_meta.get("url")
                    img_data = requests.get(media_url, headers=headers).content

                    id_extraido = None
                    if ai_client:
                        try:
                            prompt_ocr = "Identifica el número de ID de usuario en esta captura de Weltrade. Devuelve únicamente el número o null."
                            resp = ai_client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=[types.Part.from_bytes(data=img_data, mime_type="image/jpeg"), prompt_ocr]
                            )
                            match = re.search(r'\b(\d{6,8})\b', resp.text)
                            if match:
                                id_extraido = match.group(1)
                        except Exception as e:
                            print(f"Error OCR: {e}")

                    if id_extraido:
                        despachar_paso_4(remitente, id_extraido, usuario["nombre"])
                    else:
                        texto_aclaracion = (
                            "Veo tu captura, pero no logramos distinguir con claridad tu número de ID de registro.\n\n"
                            "Por favor escribe tu número de ID aquí en texto para activarte los accesos."
                        )
                        enviar_texto(remitente, texto_aclaracion)
                    return jsonify({"status": "ok"}), 200

                # --- 2. RECEPCIÓN DE TEXTO ---
                if tipo_msg == "text":
                    texto_usuario = msg.get("text", {}).get("body", "").strip()
                    id_encontrado = extraer_id_texto(texto_usuario)

                    # Si el usuario envió su ID en texto
                    if id_encontrado and usuario["etapa"] >= 2:
                        despachar_paso_4(remitente, id_encontrado, usuario["nombre"])
                        return jsonify({"status": "ok"}), 200

                    # Etapa 0: Primer contacto -> Paso 1 (con imagen)
                    if usuario["etapa"] == 0:
                        despachar_paso_1(remitente, usuario["nombre"])
                        return jsonify({"status": "ok"}), 200

                    # Pregunta sobre dinero / costos / depósitos
                    if es_pregunta_costos(texto_usuario):
                        responder_objecion_fondos(remitente)
                        return jsonify({"status": "ok"}), 200

                    # Respondió al Paso 1 (Experiencia) -> Avanza al Paso 2 (con imagen)
                    if usuario["etapa"] == 1:
                        despachar_paso_2(remitente)
                        return jsonify({"status": "ok"}), 200

                    # Respondió al Paso 2 (Interés / Sí) -> Avanza al Paso 3 (con imagen)
                    if usuario["etapa"] == 2:
                        despachar_paso_3(remitente)
                        return jsonify({"status": "ok"}), 200

                    # Etapa 3: Ya recibió el enlace y hace otra pregunta
                    if usuario["etapa"] == 3:
                        respuesta_ia = procesar_con_gemini_seguro(
                            f"Eres el soporte de ENTRA. Responde brevemente a: {texto_usuario} y recuérdale que para acceder gratis debe crear su cuenta en {URL_REGISTRO_WELTRADE} y mandar su ID."
                        )
                        if respuesta_ia:
                            enviar_texto(remitente, respuesta_ia)
                        else:
                            enviar_texto(remitente, f"Para darte el acompañamiento y resolver todas tus dudas, regístrate gratis aquí: {URL_REGISTRO_WELTRADE} y compárteme tu ID.")
                        return jsonify({"status": "ok"}), 200

                    # Etapa 4: Recordatorio de Telegram
                    if usuario["etapa"] == 4:
                        enviar_texto(remitente, f"¡Hola! Recuerda que todo tu soporte y las clases en vivo las estamos activando directamente en Telegram:\n👉 {URL_TELEGRAM_SOPORTE}")
                        return jsonify({"status": "ok"}), 200

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error general en webhook: {e}")
        return jsonify({"status": "error"}), 500

# ==========================================
# SEGUIMIENTOS AUTOMÁTICOS
# ==========================================
@app.route("/ejecutar-seguimientos", methods=["GET"])
def ejecutar_seguimientos():
    conn = sqlite3.connect("embudo_entra.db")
    c = conn.cursor()
    c.execute("SELECT telefono, nombre, etapa, ultimo_contacto, seguimiento_count FROM usuarios WHERE etapa BETWEEN 1 AND 3")
    usuarios = c.fetchall()
    conn.close()

    ahora = datetime.datetime.now()

    for u in usuarios:
        telefono, nombre, etapa, ultimo_contacto_str, seg_count = u
        ultimo_contacto = datetime.datetime.fromisoformat(ultimo_contacto_str)
        horas = (ahora - ultimo_contacto).total_seconds() / 3600.0

        if horas >= 4.0:
            if etapa == 1 and seg_count == 0:
                despachar_paso_2(telefono)
                actualizar_usuario(telefono, seguimiento_count=1)
            elif etapa == 2 and seg_count < 2:
                despachar_paso_3(telefono)
                actualizar_usuario(telefono, seguimiento_count=2)
            elif etapa == 3:
                if seg_count == 2:
                    enviar_video(telefono, URL_VIDEO_1, caption="Aprender trading en solitario puede ser difícil. En ENTRA cuentas con todo el apoyo en cuenta Demo desde cero.")
                    actualizar_usuario(telefono, seguimiento_count=3)
                elif seg_count == 3 and horas >= 8.0:
                    enviar_video(telefono, URL_VIDEO_2, caption="Ya somos más de 10.000 miembros formándonos juntos. Si estás listo para iniciar, responde con la palabra ENTRA.")
                    actualizar_usuario(telefono, seguimiento_count=4)

    return jsonify({"status": "seguimientos completados"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
