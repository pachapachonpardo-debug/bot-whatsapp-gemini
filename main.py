import os
import httpx
from fastapi import FastAPI, Request, Response
from google import genai

app = FastAPI()

VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "clave_secreta_gemini_2026")
WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

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
            from_number = message["from"]

            if message.get("type") == "text":
                user_text = message["text"]["body"]

                # Consulta a Gemini
                ai_response = ai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=user_text,
                    config={"system_instruction": "Eres el asistente oficial de atencion al cliente de Creaciones Mi Pacha en WhatsApp. Responde de forma cordial, clara y concisa en espanol."}
                )
                bot_reply = ai_response.text

                # Respuesta a WhatsApp via Meta Graph API
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
                    await client.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Error procesando mensaje: {e}")

    return {"status": "ok"}
