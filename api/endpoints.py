import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from services.document_processor import (
    display_license_extracted_info,
    display_mulkiya_extracted_info,
    merge_id_information,
    process_uploaded_document,
    display_extracted_info,
    process_uploaded_license_document,
    process_uploaded_mulkiya_document,
)
from services.voiceText import transcribe_audio
from services.whatsapp import (
    download_whatsapp_audio,
    download_whatsapp_media,
    send_whatsapp_message,
)
from services.conversation_manager import process_conversation
from services.llm import initialize_llm, process_message_with_llm
from config.settings import VERIFY_TOKEN
from langchain.schema import HumanMessage, SystemMessage

app = FastAPI()
llm = initialize_llm()
user_states = {}
# Dictionary to store locks for each user to prevent concurrent processing
user_locks = {}


async def process_with_lock(
    from_id: str, text: str, profile_name: str = None, interactive_response: dict = None
):
    """
    Process conversation with a lock to prevent concurrent processing for the same user
    """
    # Get or create a lock for this user
    if from_id not in user_locks:
        user_locks[from_id] = asyncio.Lock()

    # Acquire the lock for this user
    async with user_locks[from_id]:
        await process_conversation(
            from_id, text, user_states, profile_name, interactive_response
        )


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
        if (
            "object" in data
            and "entry" in data
            and data["object"] == "whatsapp_business_account"
        ):
            for entry in data["entry"]:
                changes = entry.get("changes", [])
                if changes:
                    value = changes[0].get("value", {})
                    if "messages" in value:
                        messages = value["messages"]
                        from_id = messages[0].get("from")
                        msg_type = messages[0].get("type")
                        profile_name = (
                            value.get("contacts", [{}])[0]
                            .get("profile", {})
                            .get("name")
                        )

                        if msg_type == "text":
                            text = messages[0].get("text", {}).get("body", "")
                            if from_id and text:
                                asyncio.create_task(
                                    process_with_lock(from_id, text, profile_name, None)
                                )

                        elif msg_type == "interactive":
                            interactive_data = messages[0].get("interactive", {})
                            interactive_type = interactive_data.get("type")
                            interactive_response = interactive_data.get(
                                "button_reply"
                                if interactive_type == "button_reply"
                                else "list_reply",
                                {},
                            )
                            if interactive_response:
                                asyncio.create_task(
                                    process_with_lock(
                                        from_id,
                                        "",
                                        profile_name,
                                        interactive_response,
                                    )
                                )

                        elif msg_type == "audio":  # Handle voice messages
                            media_id = messages[0].get("audio", {}).get("id")
                            if media_id:
                                audio_data = download_whatsapp_audio(media_id)
                                if audio_data:
                                    transcribed_text = await transcribe_audio(
                                        audio_data
                                    )
                                    if transcribed_text:
                                        print(
                                            f"Transcribed voice message from {from_id}: {transcribed_text}"
                                        )
                                        asyncio.create_task(
                                            process_with_lock(
                                                from_id,
                                                transcribed_text,
                                                profile_name,
                                                None,
                                            )
                                        )
                                    else:
                                        send_whatsapp_message(
                                            from_id,
                                            "Sorry, I couldn’t understand your voice message. Could you please try again or type your request?",
                                        )
                                else:
                                    send_whatsapp_message(
                                        from_id,
                                        "Sorry, I couldn’t retrieve your voice message. Please try again.",
                                    )
                        # elif msg_type == "document":
                        #     media_id = messages[0].get("document", {}).get("id")
                        #     mime_type = messages[0].get("document", {}).get("mime_type")
                        #     filename = messages[0].get("document", {}).get("filename", "unknown")
                        #     if media_id:
                        #         print(f"Received document from {from_id}: {filename}, MIME: {mime_type}")
                        #         # Check if user is in the correct stage; if not, inform them
                        #         if user_states[from_id]["stage"] != "medical_upload_document":
                        #             send_whatsapp_message(from_id, "I wasn’t expecting a document right now. Please let me know how I can assist you!")
                        #             return {"status": "success"}
                        #         # Download and process the document
                        #         document_data = download_whatsapp_media(media_id)
                        #         if document_data:
                        #             try:
                        #                 send_whatsapp_message(from_id, "Received your document. Processing now, please wait...")
                        #                 extracted_info = await process_uploaded_document(from_id, document_data, mime_type, filename, user_states)
                        #                 if extracted_info:
                        #                     print(f"Extracted info: {extracted_info}")
                        #                     # Use the new function to display all information at once without verification
                        #                     asyncio.create_task(display_extracted_info(from_id, extracted_info, user_states))
                        #                     user_states[from_id]["stage"] = "medical_marital_status"
                        #                 else:
                        #                     send_whatsapp_message(from_id, "Sorry, I couldn’t extract information from your document. Please try again or enter the details manually.")
                        #             except Exception as e:
                        #                 print(f"Error processing document: {e}")
                        #                 send_whatsapp_message(from_id, "An error occurred while processing your document. Please try again.")
                        #         else:
                        #             send_whatsapp_message(from_id, "Sorry, I couldn’t retrieve your document. Please try again.")
                        # Tododclea
                        elif msg_type in ["document", "image"]:
                            # Get media ID and mime type based on message type
                            if msg_type == "document":
                                media_id = messages[0].get("document", {}).get("id")
                                mime_type = (
                                    messages[0].get("document", {}).get("mime_type")
                                )
                                filename = (
                                    messages[0]
                                    .get("document", {})
                                    .get("filename", "unknown")
                                )
                            else:  # image
                                media_id = messages[0].get("image", {}).get("id")
                                mime_type = (
                                    "image/jpeg"  # WhatsApp typically sends JPEGs
                                )
                                filename = f"{msg_type}-{media_id}.jpg"

                            if media_id:
                                print(f"Received {msg_type} from {from_id}: {filename}")

                                # Determine the flow type based on stage
                                flow_type = None
                                if from_id in user_states:
                                    if user_states[from_id]["stage"] in [
                                        "medical_upload_document",
                                        "waiting_for_back_id",
                                    ]:
                                        flow_type = "medical"
                                    elif user_states[from_id]["stage"] in [
                                        "motor_upload_document",
                                        "waiting_for_back_id",
                                    ]:
                                        flow_type = "motor"

                                # Check if we're waiting for back side of Emirates ID
                                if (
                                    from_id in user_states
                                    and user_states[from_id]["stage"]
                                    == "waiting_for_back_id"
                                ):
                                    media_data = download_whatsapp_media(media_id)
                                    if media_data:
                                        try:
                                            send_whatsapp_message(
                                                from_id,
                                                f"Received the back side of your Emirates ID. Processing now, please wait...",
                                            )
                                            back_extracted_info = (
                                                await process_uploaded_document(
                                                    from_id,
                                                    media_data,
                                                    mime_type,
                                                    filename,
                                                    user_states,
                                                    flow_type,
                                                )
                                            )
                                            if back_extracted_info:
                                                print(
                                                    f"Extracted info from back side: {back_extracted_info}"
                                                )
                                                # Merge information from front and back sides
                                                asyncio.create_task(
                                                    merge_id_information(
                                                        from_id,
                                                        back_extracted_info,
                                                        user_states,
                                                        flow_type,
                                                    )
                                                )
                                            else:
                                                send_whatsapp_message(
                                                    from_id,
                                                    "Sorry, I couldn't extract information from the back side of your ID. Let's proceed with the information we have.",
                                                )
                                                # Display front side information only
                                                asyncio.create_task(
                                                    display_extracted_info(
                                                        from_id,
                                                        user_states[from_id][
                                                            "verified_info"
                                                        ],
                                                        user_states,
                                                        flow_type,
                                                    )
                                                )
                                        except Exception as e:
                                            print(
                                                f"Error processing back side {msg_type}: {e}"
                                            )
                                            send_whatsapp_message(
                                                from_id,
                                                "An error occurred while processing the back side of your ID. Let's proceed with the information we have.",
                                            )
                                            # Display front side information only
                                            asyncio.create_task(
                                                display_extracted_info(
                                                    from_id,
                                                    user_states[from_id][
                                                        "verified_info"
                                                    ],
                                                    user_states,
                                                    flow_type,
                                                )
                                            )
                                    else:
                                        send_whatsapp_message(
                                            from_id,
                                            "Sorry, I couldn't retrieve the back side of your ID. Let's proceed with the information we have.",
                                        )
                                        # Display front side information only
                                        asyncio.create_task(
                                            display_extracted_info(
                                                from_id,
                                                user_states[from_id]["verified_info"],
                                                user_states,
                                                flow_type,
                                            )
                                        )
                                    return {"status": "success"}

                                # Check if user is in the stage for document upload
                                elif from_id in user_states and user_states[from_id][
                                    "stage"
                                ] in [
                                    "medical_upload_document",
                                    "motor_upload_document",
                                ]:
                                    media_data = download_whatsapp_media(media_id)
                                    if media_data:
                                        try:
                                            send_whatsapp_message(
                                                from_id,
                                                f"Received your Emirates ID. Processing now, please wait...",
                                            )
                                            extracted_info = (
                                                await process_uploaded_document(
                                                    from_id,
                                                    media_data,
                                                    mime_type,
                                                    filename,
                                                    user_states,
                                                    flow_type,
                                                )
                                            )
                                            if extracted_info:
                                                print(
                                                    f"Extracted info: {extracted_info}"
                                                )
                                                # Check if card_number is missing and handle accordingly
                                                asyncio.create_task(
                                                    display_extracted_info(
                                                        from_id,
                                                        extracted_info,
                                                        user_states,
                                                        flow_type,
                                                    )
                                                )
                                            else:
                                                send_whatsapp_message(
                                                    from_id,
                                                    f"Sorry, I couldn't extract information from your {msg_type}. Please try again or enter the details manually.",
                                                )
                                        except Exception as e:
                                            print(f"Error processing {msg_type}: {e}")
                                            send_whatsapp_message(
                                                from_id,
                                                f"An error occurred while processing your {msg_type}. Please try again.",
                                            )
                                    else:
                                        send_whatsapp_message(
                                            from_id,
                                            f"Sorry, I couldn't retrieve your {msg_type}. Please try again.",
                                        )

                                elif from_id in user_states and user_states[from_id][
                                    "stage"
                                ] in ["motor_driving_license"]:
                                    media_data = download_whatsapp_media(media_id)
                                    if media_data:
                                        try:
                                            send_whatsapp_message(
                                                from_id,
                                                f"Received your Driving License. Processing now, please wait...",
                                            )
                                            extracted_info = (
                                                await process_uploaded_license_document(
                                                    from_id,
                                                    media_data,
                                                    mime_type,
                                                    filename,
                                                    user_states,
                                                    flow_type,
                                                )
                                            )
                                            if extracted_info:
                                                print(
                                                    f"Extracted info: {extracted_info}"
                                                )
                                                # Check if card_number is missing and handle accordingly
                                                asyncio.create_task(
                                                    display_license_extracted_info(
                                                        from_id,
                                                        extracted_info,
                                                        user_states,
                                                        flow_type,
                                                    )
                                                )
                                            else:
                                                send_whatsapp_message(
                                                    from_id,
                                                    f"Sorry, I couldn't extract information from your {msg_type}. Please try again or enter the details manually.",
                                                )
                                        except Exception as e:
                                            print(f"Error processing {msg_type}: {e}")
                                            send_whatsapp_message(
                                                from_id,
                                                f"An error occurred while processing your {msg_type}. Please try again.",
                                            )
                                    else:
                                        send_whatsapp_message(
                                            from_id,
                                            f"Sorry, I couldn't retrieve your {msg_type}. Please try again.",
                                        )

                                elif from_id in user_states and user_states[from_id][
                                    "stage"
                                ] in ["motor_vechile_mulkiya"]:
                                    media_data = download_whatsapp_media(media_id)
                                    if media_data:
                                        try:
                                            send_whatsapp_message(
                                                from_id,
                                                f"Received your Vechile Mulkiya. Processing now, please wait...",
                                            )
                                            extracted_info = (
                                                await process_uploaded_mulkiya_document(
                                                    from_id,
                                                    media_data,
                                                    mime_type,
                                                    filename,
                                                    user_states,
                                                    flow_type,
                                                )
                                            )
                                            if extracted_info:
                                                print(
                                                    f"Extracted info: {extracted_info}"
                                                )
                                                # Check if card_number is missing and handle accordingly
                                                asyncio.create_task(
                                                    display_mulkiya_extracted_info(
                                                        from_id,
                                                        extracted_info,
                                                        user_states,
                                                        flow_type,
                                                    )
                                                )
                                            else:
                                                send_whatsapp_message(
                                                    from_id,
                                                    f"Sorry, I couldn't extract information from your {msg_type}. Please try again or enter the details manually.",
                                                )
                                        except Exception as e:
                                            print(f"Error processing {msg_type}: {e}")
                                            send_whatsapp_message(
                                                from_id,
                                                f"An error occurred while processing your {msg_type}. Please try again.",
                                            )
                                    else:
                                        send_whatsapp_message(
                                            from_id,
                                            f"Sorry, I couldn't retrieve your {msg_type}. Please try again.",
                                        )

                    elif "statuses" in value:
                        status_info = value["statuses"][0]
                        print(
                            f"Message to {status_info.get('recipient_id', 'unknown')} is now {status_info.get('status', 'unknown')}"
                        )
        return {"status": "success"}


@app.get("/send-greeting/{phone_number}")
async def send_greeting(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    success = send_whatsapp_message(
        phone_number,
        "Hi there! My name is Insura from Wehbe Insurance Broker, your AI insurance assistant. I will be happy to assist you with your insurance requirements.",
    )
    if success:
        return {"status": "success", "message": f"Greeting sent to {phone_number}"}
    raise HTTPException(status_code=500, detail="Failed to send message")


@app.get("/reset-conversation/{phone_number}")
async def reset_conversation(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    if phone_number in user_states:
        user_states.pop(phone_number)
        return {
            "status": "success",
            "message": f"Conversation reset for {phone_number}",
        }
    return {
        "status": "warning",
        "message": f"No active conversation found for {phone_number}",
    }


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
        response = llm.invoke([
            SystemMessage(content="You are Insura..."),
            HumanMessage(content=message),
        ]).content
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
