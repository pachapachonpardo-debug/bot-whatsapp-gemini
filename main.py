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
URL_VIDEO_WELTRADE = "https://youtu.be/qxDRiJFAaKs"
URL_TELEGRAM_SOPORTE = "https://t.me/soportecomunidadentra"

# URLs de Activos Multimedia en GitHub
URL_IMG_PASO_1 = "https://raw.githubusercontent.com/pachapachonpardo-debug/bot-whatsapp-gemini/main/mensaje1-bienvenida.jpg.jpeg"
URL_IMG_P1 = URL_IMG_PASO_1
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
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Respuesta WhatsApp: {resp.status_code} - {resp.text}")
        return resp
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
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "image",
        "image": {
            "link": url_imagen,
            "caption": caption_texto
        }
    }
    resp = enviar_peticion_whatsapp(payload)
    if (resp is None or resp.status_code != 200) and caption_texto:
        print("Fallo en entrega de imagen, enviando texto de respaldo...")
        enviar_texto(destinatario, caption_texto)
    return resp

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
# MENSAJES EXACTOS DEL EMBUDO (HECTOR BARRERO)
# ==========================================
def despachar_paso_1(telefono):
    texto = (
        "Hola como te encuentras el día de hoy, mucho gusto, mi nombre es *Hector Barrero*, bienvenido a *_ENTRA ( Entrena Traders )_*.\n\n"
        "La Primera Comunidad de Entrenamiento y Formación en Índices Sintéticos totalmente *Gratuita*.\n\n"
        "*¿ Te gustaría ser parte de nuestra comunidad ?*\n\n"
        "🙂 Quedo atento a tu respuesta para poder seguir dándote más información., no olvides agregarme a tus contactos, esto para que te llegue toda la información completa.\n\n"
        "¿ Me recuerdas tu nombre por favor ?\n\n"
        "Y cuéntame ¿ Tienes experiencia en trading ?"
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P1, texto)
    actualizar_usuario(telefono, etapa=1)

def despachar_paso_2(telefono, nombre):
    nombre_mostrar = f"*{nombre}*,\n\n" if nombre else ""
    texto = (
        f"{nombre_mostrar}Con nosotros tendrás *Totalmente Gratis*:\n\n"
        "📍 Entrenamiento de fundamentos en Índices Sintéticos\n"
        "📍 Sesiones en vivo 🌞 8 horas al día 🌚 divididas en 4 sesiones.\n"
        "📍 Señales\n"
        "📍 Bono\n"
        "📍 Beneficios de comunidad.\n\n"
        "Siempre te daremos beneficios extras como *Academia* y como *Aliados* de nuestro *Bróker* 😎\n\n"
        "¿ Te gustaría continuar con el proceso ?\n\n"
        "_Quedo atento a tu respuesta para darte más información_\n\n"
        "*Saludos*"
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P2, texto)
    actualizar_usuario(telefono, etapa=2)

def despachar_paso_3(telefono, nombre):
    nombre_mostrar = f"Hola *{nombre}*,\n\n" if nombre else ""
    texto = (
        f"{nombre_mostrar}En nuestra comunidad vas a tener clases, cursos, con todos los fundamentos en *Índices Sintéticos* para empezar a operar este mercado y seguir la operativa en vivo que hacemos de lunes a viernes, 8 horas al día, en cuatro diferentes sesiones.\n\n"
        "_Para darte el acceso a la comunidad, a las sesiones en vivo solo debes registrarte en el siguiente bróker a través de este enlace:_\n\n"
        f"*{URL_REGISTRO_WELTRADE}*\n\n"
        "Luego creas una cuenta en SyntX (para operar sintéticos) *REAL* y *DEMO*\n\n"
        "Una vez realices el registro no olvides enviarme una captura de pantalla de tu registro o tu número de ID.\n\n"
        f"📺 *Video guía paso a paso:*\n{URL_VIDEO_WELTRADE}\n\n"
        "_Como Crear tu cuenta en Weltrade de Índices Sintéticos ( SYNTX ) y como vincularla en MT5_\n\n"
        "Si presentas dificultades con el registro o necesitas apoyo para hacerlo no dudes en preguntarme.\n\n"
        "Quedo al pendiente para darte acceso a la comunidad *GRATUITA* más grande del mundo en habla hispana. 👊"
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P3, texto)
    actualizar_usuario(telefono, etapa=3)

def responder_objecion_fondos(telefono):
    texto = (
        "Es totalmente comprensible tu duda. Te confirmo que ser parte de nuestra comunidad, acceder a los cursos y participar en las 4 sesiones diarias en vivo es **100% GRATUITO**.\n\n"
        "Tampoco es obligatorio depositar dinero en el bróker: puedes formarte, practicar y operar en cuenta DEMO de práctica todo el tiempo que desees.\n\n"
        "Si en el futuro tú decides operar con dinero real para monetizar, el depósito mínimo parte desde apenas $10 USD, pero esa decisión es totalmente tuya cuando te sientas preparado.\n\n"
        f"Puedes crear tu cuenta aquí: *{URL_REGISTRO_WELTRADE}* y enviarme tu número de ID cuando la tengas lista."
    )
    enviar_texto(telefono, texto)

def dar_contacto_humano(telefono):
    texto = (
        "¡Con gusto! Puedes comunicarte directamente conmigo por llamada o mensaje a mi WhatsApp personal de soporte:\n\n"
        f"📲 *+{MI_WHATSAPP_NOTIFICACIONES}*\n\n"
        "Con gusto resolveré tus dudas de manera personalizada."
    )
    enviar_texto(telefono, texto)

def despachar_paso_4(telefono, id_weltrade, nombre):
    alerta_personal = (
        f"🔔 *NUEVO PROSPECTO PENDIENTE DE VALIDACIÓN*\n"
        f"👤 Nombre: {nombre}\n"
        f"📱 Teléfono: +{telefono}\n"
        f"🆔 ID Weltrade: {id_weltrade}\n\n"
        f"Verifícalo en tu panel: https://gowt.net"
    )
    enviar_texto(MI_WHATSAPP_NOTIFICACIONES, alerta_personal)

    texto_telegram = (
        f"Hola *{nombre}*,\n\n"
        "¡Excelente! Ya validamos tu registro y te doy la bienvenida a la comunidad.\n\n"
        f"👉 Únete aquí a nuestro canal oficial de Telegram: {URL_TELEGRAM_SOPORTE}\n\n"
        "⚠️ *Importante:* Al ingresar a Telegram, compárteme estos 3 datos para habilitar tus accesos:\n"
        "1. Tu nombre\n"
        "2. Tu país\n"
        f"3. Código de vinculación: *{id_weltrade}*"
    )
    enviar_imagen_con_caption(telefono, URL_IMG_P4, texto_telegram)
    enviar_audio(telefono, URL_AUDIO_P4)
    actualizar_usuario(telefono, etapa=4, id_weltrade=id_weltrade)

# ==========================================
# UTILIDADES Y DETECCIONES
# ==========================================
def extraer_id_texto(texto):
    match = re.search(r'\b(\d{6,8})\b', texto)
    return match.group(1) if match else None

def es_pregunta_costos(texto):
    t = texto.lower()
    terminos = ["cuanto", "cuánto", "pagar", "costo", "vale", "precio", "cobran", "depositar", "deposito", "dinero", "gratis"]
    return any(term in t for term in terminos)

def pide_asesor_humano(texto):
    t = texto.lower()
    terminos = ["persona real", "humano", "asesor", "alguien real", "hablar con alguien", "llamada", "contáctame", "contactame"]
    return any(term in t for term in terminos)

def extraer_nombre_primer_mensaje(texto):
    t = texto.strip()
    match = re.search(r'(?:me llamo|mi nombre es|soy)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)', t, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    palabras = t.split()
    if len(palabras) == 1 and palabras[0].isalpha() and len(palabras[0]) > 2:
        if palabras[0].lower() not in ["hola", "buenas", "buenos", "tarde", "noches", "si", "sí", "no"]:
            return palabras[0].capitalize()
    return ""

def responder_duda_con_gemini(texto_usuario, nombre_usuario):
    if not ai_client:
        return None
    prompt = f"""
    Eres Hector Barrero, fundador de ENTRA (Entrena Traders), una comunidad de trading en índices sintéticos 100% gratuita.
    Usuario: {nombre_usuario if nombre_usuario else 'prospecto'}.
    El usuario te escribió: "{texto_usuario}".
    
    Instrucciones estrictas:
    1. Si pregunta qué es el ID: Explica que es el número de cuenta de 6 a 8 dígitos que le da el bróker Weltrade al registrarse (en SyntX), el cual aparece en el menú principal de Weltrade.
    2. Si pregunta qué es trading o índices sintéticos (o palabras parecidas por autocorrector como "tradición"): Explica de forma clara, sencilla y motivadora en 2 frases.
    3. Si dice que no entiende nada: Sé muy amable, dale tranquilidad y dile que no se preocupe, que precisamente por eso la academia enseña desde cero con clases en vivo y acompañamiento.
    4. Siempre recuérdale que el registro en Weltrade ({URL_REGISTRO_WELTRADE}) es gratuito, en cuenta Demo, y que si prefiere hablar directamente puede escribirte al WhatsApp +{MI_WHATSAPP_NOTIFICACIONES}.
    5. No repitas siempre las mismas palabras, habla natural, profesional y cercano como un mentor. Máximo 3 o 4 líneas.
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Error Gemini: {e}")
        return None

# ==========================================
# WEBHOOK
# ==========================================
@app.route("/", methods=["GET", "HEAD"])
def inicio():
    return "Bot WhatsApp Gemini Activo", 200

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
                nombre_perfil = contacts[0].get("profile", {}).get("name", "") if contacts else ""
                tipo_msg = msg.get("type")

                # Comando manual para reiniciar
                if tipo_msg == "text":
                    cuerpo = msg.get("text", {}).get("body", "").strip()
                    if cuerpo.upper() in ["RESET", "REINICIAR"]:
                        reiniciar_usuario(remitente)
                        enviar_texto(remitente, "🔄 Conversación reiniciada. Envía un 'Hola' para iniciar.")
                        return jsonify({"status": "reset"}), 200

                usuario = obtener_usuario(remitente, nombre_perfil)

                # 1. RECEPCIÓN DE IMÁGENES (CAPTURA DEL REGISTRO/ID)
                if tipo_msg == "image":
                    image_id = msg.get("image", {}).get("id")
                    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                    media_meta = requests.get(f"https://graph.facebook.com/v21.0/{image_id}", headers=headers).json()
                    media_url = media_meta.get("url")
                    img_data = requests.get(media_url, headers=headers).content

                    id_extraido = None
                    if ai_client:
                        try:
                            prompt_ocr = "Identifica el número de cuenta o ID (6 a 8 dígitos) en esta captura de Weltrade / SyntX. Devuelve solo los dígitos o null."
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
                            "Veo tu captura, pero no logro distinguir claramente los números de tu ID.\n\n"
                            "Por favor escribe aquí tu número de ID en texto para activarte el acceso de inmediato."
                        )
                        enviar_texto(remitente, texto_aclaracion)
                    return jsonify({"status": "ok"}), 200

                # 2. RECEPCIÓN DE MENSAJES DE TEXTO
                if tipo_msg == "text":
                    texto_usuario = msg.get("text", {}).get("body", "").strip()
                    id_encontrado = extraer_id_texto(texto_usuario)

                    # Si el usuario pide hablar con una persona real
                    if pide_asesor_humano(texto_usuario):
                        dar_contacto_humano(remitente)
                        return jsonify({"status": "ok"}), 200

                    # Si envió el ID en texto
                    if id_encontrado and usuario["etapa"] >= 2:
                        despachar_paso_4(remitente, id_encontrado, usuario["nombre"])
                        return jsonify({"status": "ok"}), 200

                    # Etapa 0: Primer contacto -> Paso 1 (Bienvenida de Hector Barrero)
                    if usuario["etapa"] == 0:
                        nombre_detectado = extraer_nombre_primer_mensaje(texto_usuario)
                        if nombre_detectado:
                            actualizar_usuario(remitente, nombre=nombre_detectado)
                        despachar_paso_1(remitente)
                        return jsonify({"status": "ok"}), 200

                    # Preguntas sobre dinero / costo / depósito
                    if es_pregunta_costos(texto_usuario):
                        responder_objecion_fondos(remitente)
                        return jsonify({"status": "ok"}), 200

                    # Etapa 1: Respondió con su nombre / experiencia -> Pasa al Paso 2
                    if usuario["etapa"] == 1:
                        nombre_detectado = extraer_nombre_primer_mensaje(texto_usuario)
                        if nombre_detectado and (not usuario["nombre"] or usuario["nombre"] == nombre_perfil):
                            actualizar_usuario(remitente, nombre=nombre_detectado)
                            usuario["nombre"] = nombre_detectado
                        despachar_paso_2(remitente, usuario["nombre"])
                        return jsonify({"status": "ok"}), 200

                    # Etapa 2: Respondió afirmativo -> Pasa al Paso 3 (Registro Weltrade)
                    if usuario["etapa"] == 2:
                        # Si hace una pregunta en lugar de decir sí
                        if "¿" in texto_usuario or "?" in texto_usuario or len(texto_usuario.split()) > 6:
                            resp = responder_duda_con_gemini(texto_usuario, usuario["nombre"])
                            if resp:
                                enviar_texto(remitente, resp)
                                return jsonify({"status": "ok"}), 200
                        despachar_paso_3(remitente, usuario["nombre"])
                        return jsonify({"status": "ok"}), 200

                    # Etapa 3: En proceso de registro / preguntas libres
                    if usuario["etapa"] == 3:
                        resp_ia = responder_duda_con_gemini(texto_usuario, usuario["nombre"])
                        if resp_ia:
                            enviar_texto(remitente, resp_ia)
                        else:
                            enviar_texto(
                                remitente,
                                f"Para guiarte paso a paso, recuerda abrir tu cuenta gratuita en {URL_REGISTRO_WELTRADE} o comunicarte a mi WhatsApp directo +{MI_WHATSAPP_NOTIFICACIONES}."
                            )
                        return jsonify({"status": "ok"}), 200

                    # Etapa 4: Ya validado
                    if usuario["etapa"] == 4:
                        enviar_texto(
                            remitente,
                            f"¡Hola {usuario['nombre']}! Recuerda que todo el soporte y las 4 clases en vivo las estamos activando en Telegram:\n👉 {URL_TELEGRAM_SOPORTE}\nO a mi número directo +{MI_WHATSAPP_NOTIFICACIONES}."
                        )
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
                despachar_paso_2(telefono, nombre)
                actualizar_usuario(telefono, seguimiento_count=1)
            elif etapa == 2 and seg_count < 2:
                despachar_paso_3(telefono, nombre)
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
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=puerto)
