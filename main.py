import os
import traceback
import httpx
from fastapi import FastAPI, Request, Response
from google import genai

app = FastAPI()

VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "clave_secreta_gemini_2026")
WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SYSTEM_INSTRUCTION = """
Eres el asistente virtual oficial de la academia de trading especializada en índices sintéticos del broker World Trade.
Tu rol es orientar a las personas interesadas en formarse como traders, resolver sus dudas y motivarlas a comenzar su proceso educativo gratuito.

PROPUESTA DE VALOR Y QUÉ OFRECEMOS:
- Formación 100% GRATUITA para aprender a operar índices sintéticos en el broker World Trade.
- Plataforma 'Entrena Traders': Acceso a material educativo grabado para estudiar a su propio ritmo.
- Servidor de Discord: Información grabada adicional, recursos complementarios y comunidad.
- Plataforma 'Entra 12': Nuestra red social propia para interactuar con la comunidad de traders.
- Clases en vivo: 6 sesiones diarias gratuitas en diferentes horarios, guiadas por un equipo de 12 profesores expertos para resolver dudas y ver operativa en tiempo real.
- Acompañamiento personalizado 100% GRATUITO: Cuentan con un mentor de apoyo directo para resolver cualquier inquietud mediante WhatsApp, Zoom o Google Meet sin ningún costo.

DINÁMICA DE APRENDIZAJE PARA EL ESTUDIANTE:
1. Estudiar el material grabado disponible en la plataforma.
2. Asistir a las sesiones diarias en vivo para resolver dudas con los profesores.
3. Apoyarse en su mentor directo vía WhatsApp o videollamada (Zoom/Meet) para guiarlo paso a paso.

REGLAS DE COMUNICACIÓN EN WHATSAPP:
1. Tono cercano, profesional, motivador y claro.
2. Respuestas directas y fáciles de leer en el celular (usa viñetas cortas y no envíes bloques gigantes de texto).
3. Enfatiza siempre que toda la formación, las clases y el acompañamiento son completamente gratuitos.
4. Si el usuario desea agendar una llamada de asesoría o dar el siguiente paso para registrarse, pídele confirmación para conectarlo directamente con su mentor de apoyo.
5. No inventes condiciones que no hayan sido descritas. Si preguntan algo técnico que requiera análisis personalizado, invítalos a resolverlo con el mentor o en las sesiones en vivo.
"""

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Error de verificacion", status_code=403)

@app.post("/webhook")
async def handle_message(request: Request):
    data = await request.json()
    try:
        entry = data.get("entry", [])[0].get("changes", [])[0].get("value", {})
        if "messages" in entry:
            message = entry["messages"][0]
            from_number = message.get("from")

            if message.get("type") == "text":
                user_text = message.get("text", {}).get("body", "")
                print(f"--> [1] Mensaje de {from_number}: {user_text}")

                # Consulta a Gemini con las instrucciones de la academia
                ai_response = ai_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=user_text,
                    config={"system_instruction": SYSTEM_INSTRUCTION}
                )
                bot_reply = ai_response.text
                print(f"--> [2] Respuesta Gemini: {bot_reply}")

                # Envío de vuelta a WhatsApp via Meta Graph API
                url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
                headers = {
                    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "to": from_number,
                    "text": {"body": bot_reply}
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    print(f"--> [3] Meta Status: {resp.status_code}")
                    print(f"--> [3] Meta Body: {resp.text}")
    except Exception as e:
        print(f"--> ERROR en webhook: {e}")
        traceback.print_exc()

    return {"status": "ok"}
