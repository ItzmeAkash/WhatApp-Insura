import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from services.voiceText import transcribe_audio
from services.whatsapp import download_whatsapp_audio, send_whatsapp_message
from services.conversation_manager import process_conversation
from services.llm import initialize_llm, process_message_with_llm
from config.settings import VERIFY_TOKEN
from langchain.schema import HumanMessage,SystemMessage

app = FastAPI()
llm = initialize_llm()
user_states = {}

@app.get("/")
def welcome():
    return {"message": "Hello, Welcome to Insura!"}
@app.api_route("/webhook", methods=["GET", "POST"])
async def webhook(request: Request):
    if request.method == "GET":
        # Handle the verification request
        verify_token = request.query_params.get("hub.verify_token")
        mode = request.query_params.get("hub.mode")
        challenge = request.query_params.get("hub.challenge")
        
        if mode and verify_token:
            if mode == "subscribe" and verify_token == VERIFY_TOKEN:
                print("WEBHOOK_VERIFIED")
                return PlainTextResponse(challenge)
            else:
                raise HTTPException(status_code=403, detail="Verification failed")
                
    elif request.method == "POST":
        data = await request.json()
        print("Webhook received data:", data)
        if "object" in data and "entry" in data and data["object"] == "whatsapp_business_account":
            for entry in data["entry"]:
                changes = entry.get("changes", [])
                if changes:
                    value = changes[0].get("value", {})
                    if "messages" in value:
                        messages = value["messages"]
                        from_id = messages[0].get("from")
                        msg_type = messages[0].get("type")
                        profile_name = value.get("contacts", [{}])[0].get("profile", {}).get("name")
                        
                        if msg_type == "text":
                            text = messages[0].get("text", {}).get("body", "")
                            if from_id and text:
                                asyncio.create_task(process_conversation(from_id, text, user_states, profile_name, None))
                        
                        elif msg_type == "interactive":
                            interactive_data = messages[0].get("interactive", {})
                            interactive_type = interactive_data.get("type")
                            interactive_response = interactive_data.get("button_reply" if interactive_type == "button_reply" else "list_reply", {})
                            if interactive_response:
                                asyncio.create_task(process_conversation(from_id, "", user_states, profile_name, interactive_response))
                        
                        elif msg_type == "audio":  # Handle voice messages
                            media_id = messages[0].get("audio", {}).get("id")
                            if media_id:
                                audio_data = download_whatsapp_audio(media_id)
                                if audio_data:
                                    transcribed_text = await transcribe_audio(audio_data)
                                    if transcribed_text:
                                        print(f"Transcribed voice message from {from_id}: {transcribed_text}")
                                        asyncio.create_task(process_conversation(from_id, transcribed_text, user_states, profile_name, None))
                                    else:
                                        send_whatsapp_message(from_id, "Sorry, I couldn’t understand your voice message. Could you please try again or type your request?")
                                else:
                                    send_whatsapp_message(from_id, "Sorry, I couldn’t retrieve your voice message. Please try again.")
                    elif "statuses" in value:
                        status_info = value["statuses"][0]
                        print(f"Message to {status_info.get('recipient_id', 'unknown')} is now {status_info.get('status', 'unknown')}")
        return {"status": "success"}

@app.get("/send-greeting/{phone_number}")
async def send_greeting(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    success = send_whatsapp_message(phone_number, "Hi there! My name is Insura from Wehbe Insurance Broker, your AI insurance assistant. I will be happy to assist you with your insurance requirements.")
    if success:
        return {"status": "success", "message": f"Greeting sent to {phone_number}"}
    raise HTTPException(status_code=500, detail="Failed to send message")

@app.get("/reset-conversation/{phone_number}")
async def reset_conversation(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    if phone_number in user_states:
        user_states.pop(phone_number)
        return {"status": "success", "message": f"Conversation reset for {phone_number}"}
    return {"status": "warning", "message": f"No active conversation found for {phone_number}"}

@app.get("/get-user-data/{phone_number}")
async def get_user_data(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    if phone_number in user_states:
        return user_states[phone_number].get("responses", {})
    raise HTTPException(status_code=404, detail="User not found")

@app.get("/test-llm/{message}")
async def test_llm(message: str):
    try:
        response = llm.invoke([SystemMessage(content="You are Insura..."), HumanMessage(content=message)]).content
        return {"status": "success", "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/get-llm-responses/{phone_number}")
async def get_llm_responses(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    if phone_number in user_states:
        if "llm_responses" in user_states[phone_number]:
            return {"responses": user_states[phone_number]["llm_responses"]}
        elif "conversation_history" in user_states[phone_number]:
            llm_responses = [
                {"response": item["answer"], "timestamp": item["timestamp"]}
                for item in user_states[phone_number]["conversation_history"]
                if not item["answer"].startswith("[Interactive")
            ]
            return {"responses": llm_responses}
        return {"responses": []}
    raise HTTPException(status_code=404, detail="User not found")