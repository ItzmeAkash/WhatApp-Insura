import re
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import uvicorn
import requests
import threading
import time
from dotenv import load_dotenv
import os
import json
from langchain_groq.chat_models import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from concurrent.futures import ThreadPoolExecutor
import base64
import tempfile
from pydub import AudioSegment
import speech_recognition as sr

load_dotenv()
app = FastAPI()

PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION")
WHATAPP_URL = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
WHATSAPP_TOKEN = os.getenv("ACCESS_TOKEN")
ENACT_API_URL = os.getenv("ENACT_API_URL", "https://your-enact-api-endpoint.com")

# Initialize LLM
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    api_key=os.getenv('GROQ_API_KEY'),
    groq_proxy=None
)

# Store user states (simple in-memory database)
user_states = {}

# Define the structured questions
INITIAL_QUESTIONS = [
    {
        "question": "What would you like to do today?",
        "options": [
            "Medical Insurance",
            "Motor Insurance",
            "Claim",
            "ENACT Services"  # Added ENACT option to the initial menu
        ]
    }
]

MEDICAL_QUESTIONS = [
    {
        "question": "Let's start with your Medical insurance details. Choose your Visa issued Emirate?",
        "options": [
            "Abudhabi",
            "Ajman", 
            "Dubai", 
            "Fujairah", 
            "Ras Al Khaimah", 
            "Sharjah", 
            "Umm Al Quwain"
        ]
    },
    {
        "question": "What type of plan are you looking for?",
        "options": [
            "Basic Plan", 
            "Enhanced Plan", 
            "Enhanced Plan Standalone", 
            "Flexi Plan"
        ]
    },
    {
        "question": "Now, let's move to the sponsor details, Could you let me know the sponsor's type?",
        "options": [
            "Employee",
            "Investors"
        ]
    }
]

# List of Emirates for ENACT flow
EMIRATES_LIST = [
    "Dubai", 
    "Abu Dhabi", 
    "Sharjah", 
    "Ajman", 
    "Fujairah", 
    "Ras Al Khaimah", 
    "Umm Al Quwain"
]

def send_whatsapp_message(to, message):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": message,
        }
    }
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Message sent to {to}, status code: {response.status_code}")
    return response.status_code == 200

def send_typing_indicator(to):
    """Send a typing indicator to the recipient"""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "recipient_type": "individual",
        "type": "reaction",
        "reaction": {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "type": "text",
            "text": { 
                "preview_url": False,
                "body": "<typing>"
            }
        }
    }
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Typing indicator sent to {to}, status code: {response.status_code}")
    return response.status_code == 200

async def process_message_with_llm(from_id, text):
    """Process the message with typing indicator while LLM is generating a response"""
    try:
        # Start typing indicator
        send_typing_indicator(from_id)
        
        # Create a message for the LLM with history context and get response
        prompt = f"user response: {text}. Please assist."
        
        messages = [SystemMessage(content="You are Insura, a friendly Insurance assistant created by CloudSubset. Your role is to assist with any inquiries using your vast knowledge base. Provide helpful, accurate, and user-friendly responses to all questions or requests. Do not mention being a large language model; you are Insura."),HumanMessage(content=prompt)]
        
        # Get the LLM's response (this could take some time)
        # Run this in a separate thread to not block
        def get_llm_response():
            return llm.invoke(messages).content
        
        # Use ThreadPoolExecutor to run the LLM call in the background
        loop = asyncio.get_running_loop()
        llm_response = await loop.run_in_executor(None, get_llm_response)
        
        # Send the response back to the user
        send_whatsapp_message(from_id, llm_response)
        
        # Store only the LLM generated text in conversation history
        if from_id in user_states:
            if "conversation_history" not in user_states[from_id]:
                user_states[from_id]["conversation_history"] = []
                
            # Store the user's question and only the LLM's generated response
            user_states[from_id]["conversation_history"].append({
                "question": text,
                "answer": llm_response,
                "timestamp": time.time()
            })
            
            # Create or update a dedicated field for storing only LLM responses
            if "llm_responses" not in user_states[from_id]:
                user_states[from_id]["llm_responses"] = []
            
            user_states[from_id]["llm_responses"].append({
                "response": llm_response,  # This already contains only the generated text
                "timestamp": time.time()
            })
            
        return llm_response
    except Exception as e:
        print(f"Error processing message with LLM: {e}")
        send_whatsapp_message(from_id, "I'm sorry, I couldn't process your request at the moment. Please try again later.")
        return "Error processing message"
    
def send_interactive_buttons(recipient, text, options, max_buttons=3):
    """
    Send interactive button message with dynamic options
    Limited to 3 buttons per message due to WhatsApp limitations
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Limit to max_buttons (WhatsApp allows max 3)
    button_options = options[:max_buttons]
    
    buttons = []
    for i, option in enumerate(button_options):
        buttons.append({
            "type": "reply",
            "reply": {
                "id": f"button_{i+1}",
                "title": option
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": text
            },
            "action": {
                "buttons": buttons
            }
        }
    }
    
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Interactive message sent to {recipient}, status code: {response.status_code}")
    
    # Store this question in the conversation history
    if recipient in user_states:
        if "conversation_history" not in user_states[recipient]:
            user_states[recipient]["conversation_history"] = []
            
        user_states[recipient]["conversation_history"].append({
            "question": text,
            "answer": f"[Interactive buttons: {', '.join(button_options)}]",
            "timestamp": time.time()
        })
    
    return response.status_code == 200

def send_interactive_list(recipient, text, options, list_title="Options", section_title="Available options"):
    """
    Send interactive list message with dynamic options
    Useful when there are more than 3 options (WhatsApp button limit)
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Create rows for each option
    rows = []
    for i, option in enumerate(options):
        rows.append({
            "id": f"option_{i+1}",
            "title": option,
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": text
            },
            "action": {
                "button": "View Options",
                "sections": [
                    {
                        "title": section_title,
                        "rows": rows
                    }
                ]
            }
        }
    }
    
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Interactive list message sent to {recipient}, status code: {response.status_code}")
    
    # Store this question in the conversation history
    if recipient in user_states:
        if "conversation_history" not in user_states[recipient]:
            user_states[recipient]["conversation_history"] = []
            
        user_states[recipient]["conversation_history"].append({
            "question": text,
            "answer": f"[Interactive list: {', '.join(options)}]",
            "timestamp": time.time()
        })
    
    return response.status_code == 200

def send_interactive_options(recipient, text, options, list_title="Options", section_title="Available options"):
    """
    Send interactive options message with dynamic options
    Uses buttons for 3 or fewer options, list message for more than 3 options
    """
    # If we have 3 or fewer options, use buttons
    if len(options) <= 3:
        return send_interactive_buttons(recipient, text, options)
    # Otherwise use the list message format
    else:
        return send_interactive_list(recipient, text, options, list_title, section_title)

def send_yes_no_options(recipient, text):
    """
    Send Yes/No interactive buttons
    """
    return send_interactive_buttons(recipient, text, ["Yes", "No"])

def is_thank_you(text):
    """Check if the message is a thank you message"""
    thank_patterns = [
        r'thank(?:s| you)',
        r'thx',
        r'thnx',
        r'tysm',
        r'ty'
    ]
    
    text = text.lower()
    for pattern in thank_patterns:
        if re.search(pattern, text):
            return True
    return False

def store_interaction(from_id, question, answer):
    """Store the interaction in the user's conversation history"""
    if from_id in user_states:
        if "conversation_history" not in user_states[from_id]:
            user_states[from_id]["conversation_history"] = []
            
        user_states[from_id]["conversation_history"].append({
            "question": question,
            "answer": answer,
            "timestamp": time.time()
        })

# New function to handle voice messages
async def process_voice_message(message_data, from_id, profile_name):
    """
    Process voice messages from WhatsApp
    1. Download the voice message
    2. Convert it to text using speech recognition
    3. Process the text as a regular message or ENACT flow
    """
    try:
        # Send message to let user know we're processing their voice message
        send_whatsapp_message(from_id, "I'm processing your voice message...")
        
        # Extract media ID
        media_id = message_data.get("id", "")
        if not media_id:
            print("Error: No media ID found in voice message")
            send_whatsapp_message(from_id, "Sorry, I couldn't process your voice message. Please try again.")
            return
            
        # Download the voice message using WhatsApp Cloud API
        media_url = f"https://graph.facebook.com/{VERSION}/{media_id}"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}"
        }
        
        response = requests.get(media_url, headers=headers)
        if response.status_code != 200:
            print(f"Error downloading voice message: {response.status_code} - {response.text}")
            send_whatsapp_message(from_id, "Sorry, I couldn't download your voice message. Please try again.")
            return
            
        # Get the URL for the actual media file
        media_url = response.json().get("url")
        if not media_url:
            print("Error: No media URL found in API response")
            send_whatsapp_message(from_id, "Sorry, I couldn't process your voice message. Please try again.")
            return
            
        # Download the audio file
        audio_response = requests.get(media_url, headers=headers)
        if audio_response.status_code != 200:
            print(f"Error downloading audio file: {audio_response.status_code}")
            send_whatsapp_message(from_id, "Sorry, I couldn't download your audio. Please try again.")
            return
            
        # Save the audio to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_file.write(audio_response.content)
            temp_file_path = temp_file.name
            
        # Convert OGG to WAV (speech_recognition works better with WAV)
        try:
            audio = AudioSegment.from_ogg(temp_file_path)
            wav_file_path = temp_file_path.replace(".ogg", ".wav")
            audio.export(wav_file_path, format="wav")
            
            # Use speech recognition to convert to text
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_file_path) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)  # Using Google's Speech Recognition
                
            print(f"Voice message transcribed: {text}")
            
            # Clean up temporary files
            os.remove(temp_file_path)
            os.remove(wav_file_path)
            
            # Send the transcribed text back to the user for confirmation
            send_whatsapp_message(from_id, f"I heard: \"{text}\"")
            
            # Check if the message contains "ENACT" keyword
            if re.search(r'\benact\b', text, re.IGNORECASE):
                # Start the ENACT flow
                handle_enact_keyword(from_id, profile_name)
            else:
                # Process as regular message
                await process_conversation(from_id, text, profile_name, None)
            
        except Exception as e:
            print(f"Error in audio processing: {e}")
            send_whatsapp_message(from_id, "Sorry, I couldn't transcribe your voice message. Please try again or type your message.")
            # Clean up temporary files if they exist
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return
            
    except Exception as e:
        print(f"General error processing voice message: {e}")
        send_whatsapp_message(from_id, "Sorry, I encountered an error processing your voice message. Please try again.")

# Function to handle ENACT keyword detection
def handle_enact_keyword(from_id, profile_name):
    """Start the ENACT flow when the keyword is detected"""
    # Initialize user state if not exists
    if from_id not in user_states:
        user_states[from_id] = {
            "stage": "greeting",
            "name": profile_name,
            "responses": {},
            "question_index": 0,
            "selected_service": None,
            "conversation_history": [],
            "llm_conversation_count": 0
        }
    
    # Set the stage to ENACT flow
    user_states[from_id]["stage"] = "enact_flow"
    user_states[from_id]["selected_service"] = "ENACT Services"
    
    # Check if we already have the user's name
    if user_states[from_id]["name"]:
        # We have the name, store it and ask for phone number
        user_states[from_id]["enact_name"] = user_states[from_id]["name"]
        ask_for_phone_number(from_id)
    else:
        # Ask for name first
        ask_for_name(from_id)

# Function to ask for the user's name in ENACT flow
def ask_for_name(from_id):
    """Ask for the user's name in the ENACT flow"""
    message = "I noticed you mentioned ENACT. To proceed, I'll need a few details. What is your name?"
    send_whatsapp_message(from_id, message)
    store_interaction(from_id, "ENACT flow started", message)
    user_states[from_id]["stage"] = "enact_awaiting_name"

# Function to ask for the user's phone number in ENACT flow
def ask_for_phone_number(from_id):
    """Ask for the user's phone number in the ENACT flow"""
    message = f"Thanks {user_states[from_id]['enact_name']}! Now, please provide your phone number."
    send_whatsapp_message(from_id, message)
    store_interaction(from_id, "Asked for phone number", message)
    user_states[from_id]["stage"] = "enact_awaiting_phone"

# Function to send the list of emirates in ENACT flow
def send_emirate_options(from_id):
    """Send interactive list of emirates to choose from"""
    message = "Great! Please select your emirate:"
    send_interactive_options(from_id, message, EMIRATES_LIST)
    store_interaction(from_id, "Asked for emirate selection", message)
    user_states[from_id]["stage"] = "enact_awaiting_emirate"

# Function to call external API and send link for ENACT flow
async def process_enact_submission(from_id, name, phone, emirate):
    """Submit ENACT details to external API and send link to user"""
    try:
        # Prepare the API request data
        api_data = {
            "name": name,
            "phone": phone,
            "emirate": emirate
        }
        
        # Make the API request
        send_whatsapp_message(from_id, "Processing your request, please wait a moment...")
        response = requests.post(ENACT_API_URL, json=api_data)
        
        if response.status_code == 200:
            link = response.json().get("link", "")
            if link:
                # Send the link to the user
                message = f"Thank you! Here's your ENACT link: {link}"
                send_whatsapp_message(from_id, message)
                store_interaction(from_id, "ENACT link sent", message)
                
                # After a short delay, ask if they need anything else
                await asyncio.sleep(2)
                send_yes_no_options(from_id, "Would you like assistance with anything else?")
                user_states[from_id]["stage"] = "waiting_for_new_query"
            else:
                send_whatsapp_message(from_id, "I received a response from our system but couldn't find your link. Please try again later.")
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            send_whatsapp_message(from_id, "I'm having trouble connecting to our system. Please try again later.")
    
    except Exception as e:
        print(f"Error in ENACT API submission: {e}")
        send_whatsapp_message(from_id, "I encountered an error while processing your request. Please try again later.")

async def process_conversation(from_id, text, profile_name=None, interactive_response=None):
    """
    Handle the conversation flow with the user
    """
    # Initialize user state if not exists
    if from_id not in user_states:
        user_states[from_id] = {
            "stage": "greeting",
            "name": profile_name,  # Store the profile name if available
            "responses": {},  # Field to store user responses
            "question_index": 0,  # Track which question we're on
            "selected_service": None,  # Store which service the user selected
            "conversation_history": [],  # New field to store all Q&A interactions
            "llm_conversation_count": 0  # New counter for LLM conversations
        }
    
    state = user_states[from_id]
    
    # Handle ENACT flow states
    if state["stage"] == "enact_awaiting_name":
        name = text.strip()
        user_states[from_id]["enact_name"] = name
        user_states[from_id]["name"] = name  # Also store in main name field
        store_interaction(from_id, "User provided name for ENACT", f"Name: {name}")
        
        # Now ask for phone number
        ask_for_phone_number(from_id)
        return
        
    elif state["stage"] == "enact_awaiting_phone":
        phone = text.strip()
        user_states[from_id]["enact_phone"] = phone
        user_states[from_id]["responses"]["phone_number"] = phone  # Also store in responses
        store_interaction(from_id, "User provided phone for ENACT", f"Phone: {phone}")
        
        # Now ask for emirate selection
        send_emirate_options(from_id)
        return
        
    elif state["stage"] == "enact_awaiting_emirate":
        # Check if this is an interactive response
        selected_emirate = None
        if interactive_response:
            button_title = interactive_response.get("title")
            if button_title:
                selected_emirate = button_title
        else:
            # They typed an emirate instead of clicking
            selected_emirate = text.strip()
        
        if selected_emirate:
            user_states[from_id]["enact_emirate"] = selected_emirate
            user_states[from_id]["responses"]["selected_emirate"] = selected_emirate
            store_interaction(from_id, "User selected emirate for ENACT", f"Emirate: {selected_emirate}")
            
            # Now process the ENACT submission and send link
            await process_enact_submission(
                from_id, 
                user_states[from_id]["enact_name"],
                user_states[from_id]["enact_phone"],
                selected_emirate
            )
        else:
            # If they sent an invalid response, ask again
            send_emirate_options(from_id)
        return
    
    # Handle waiting for a new query with Yes/No buttons
    if state["stage"] == "waiting_for_new_query":
        # Check if this is an interactive response
        selected_option = None
        if interactive_response:
            button_title = interactive_response.get("title")
            if button_title:
                selected_option = button_title
        
        # Store this interaction
        store_interaction(from_id, "Would you like assistance with anything else?", selected_option or text)
        
        # If they clicked yes, restart the flow
        if selected_option == "Yes" or text.lower() in ["yes", "yeah", "yep", "sure", "ok", "okay"]:
            # If yes, show options again
            user_states[from_id]["stage"] = "initial_question"
            user_states[from_id]["question_index"] = 0
            
            # Keep the conversation history but restart the flow
            # We don't reset responses completely now, just add to them
            greeting_text = f"Great! {INITIAL_QUESTIONS[0]['question']}"
            send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"])
        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            # If no, thank them but keep conversation open for LLM responses
            thank_message = "Thank you for using our services. If you need assistance in the future, feel free to message us anytime!"
            send_whatsapp_message(from_id, thank_message)
            store_interaction(from_id, "User selected No for more assistance", thank_message)
            
            # Set state to free-form AI conversation
            user_states[from_id]["stage"] = "ai_response"
            # Reset LLM conversation counter
            user_states[from_id]["llm_conversation_count"] = 0
            
            # After a delay, offer to help with general insurance questions
            await asyncio.sleep(7)  # Wait 7 seconds before sending another message
            
            follow_up = "Feel free to ask me anything. I'm here to help!"
            send_whatsapp_message(from_id, follow_up)
            store_interaction(from_id, "Follow-up prompt", follow_up)
        else:
            # For any other message, process with LLM and stay in this state
            await process_message_with_llm(from_id, text)
            # After LLM response, ask if they want to restart guided flow
            await asyncio.sleep(1)
            send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
        return
    
    # Stage for handling any messages after the conversation is "completed"
    if state["stage"] == "ai_response":
        # Respond to whatever the user says with an AI-style response
        await process_message_with_llm(from_id, text)
        
        # Increment the LLM conversation counter
        user_states[from_id]["llm_conversation_count"] += 1
        
        # Only ask if they want to restart after 15 LLM exchanges
        if user_states[from_id]["llm_conversation_count"] >= 2:
            # After a delay, ask if they want to restart the structured flow
            await asyncio.sleep(2)
            send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
            user_states[from_id]["stage"] = "waiting_for_new_query"
            # Reset the counter
            user_states[from_id]["llm_conversation_count"] = 0
        return
    
    # Stage: Initial greeting
    if state["stage"] == "greeting":
        greeting = "Hi there! My name is Insura from Wehbe Insurance Broker, your AI insurance assistant. I will be happy to assist you with your insurance requirements."
        send_whatsapp_message(from_id, greeting)
        store_interaction(from_id, "Initial contact", greeting)
        
        await asyncio.sleep(1)  # Small delay between messages
        
        # If we already have the name from the profile, use it
        if state["name"]:
            user_states[from_id]["stage"] = "initial_question"
            user_states[from_id]["responses"]["name"] = state["name"]
            greeting_text = f"Nice to meet you, {state['name']}! {INITIAL_QUESTIONS[0]['question']}"
            send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"])
        else:
            # Otherwise ask for the name
            name_request = "Before we proceed, may I know your name please?"
            send_whatsapp_message(from_id, name_request)
            store_interaction(from_id, "Bot asked for name", name_request)
            user_states[from_id]["stage"] = "awaiting_name"
        return
    
    # Stage: User has provided their name
    elif state["stage"] == "awaiting_name":
        name = text.strip()
        user_states[from_id]["name"] = name
        user_states[from_id]["responses"]["name"] = name  # Store in responses
        store_interaction(from_id, "User provided name", f"Name received: {name}")
        
        user_states[from_id]["stage"] = "initial_question"
        greeting_text = f"Hi {name}, welcome to Insura! {INITIAL_QUESTIONS[0]['question']}"
        send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"])
        return
    
    # Stage: Initial question about what service they want
    elif state["stage"] == "initial_question":
        # Check if this is an interactive response
        selected_option = None
        if interactive_response:
            button_id = interactive_response.get("id")
            button_title = interactive_response.get("title")
            if button_title:
                selected_option = button_title
                
        # If we got a selection from buttons
        if selected_option:
            user_states[from_id]["selected_service"] = selected_option
            user_states[from_id]["responses"]["service_type"] = selected_option
            store_interaction(from_id, INITIAL_QUESTIONS[0]["question"], f"Selected: {selected_option}")
            
            # Set the next stage based on the selected service
            if "Medical Insurance" in selected_option:
                user_states[from_id]["stage"] = "medical_flow"
                user_states[from_id]["question_index"] = 0  # Start with the first medical question
                
                # Send the first medical insurance question
                question = MEDICAL_QUESTIONS[0]["question"]
                options = MEDICAL_QUESTIONS[0]["options"]
                send_interactive_options(from_id, question, options)
                
            elif "Motor Insurance" in selected_option:
                user_states[from_id]["stage"] = "motor_insurance_flow"
                motor_intro = f"Great! I see you're interested in Motor Insurance. Let me help you with that."
                send_whatsapp_message(from_id, motor_intro)
                store_interaction(from_id, "Service selection", motor_intro)
                await asyncio.sleep(1)
                vehicle_question = "What is the year, make and model of your vehicle?"
                send_whatsapp_message(from_id, vehicle_question)
                store_interaction(from_id, "Bot asked about vehicle", vehicle_question)
                
            elif "Claim" in selected_option:
                user_states[from_id]["stage"] = "claim_flow"
                claim_intro = f"I understand you want to file a claim. I'll guide you through the process."
                send_whatsapp_message(from_id, claim_intro)
                store_interaction(from_id, "Service selection", claim_intro)
                
                await asyncio.sleep(1)
                claim_question = "What type of insurance policy are you filing a claim for? (Medical or Motor)"
                send_whatsapp_message(from_id, claim_question)
                store_interaction(from_id, "Bot asked about claim type", claim_question)
        else:
            # User typed a message instead of selecting an option
            # Process with LLM
            await process_message_with_llm(from_id, text)
            # After LLM response, show the options again
            await asyncio.sleep(1)
            greeting_text = f"To continue with our guided assistance, please select one of the following options:"
            send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"])
           
        return
    
    # Medical insurance flow with structured questions
    elif state["stage"] == "medical_flow":
        question_index = state["question_index"]
        
        # If this is a response to a current question, process it and move to next question
        if question_index < len(MEDICAL_QUESTIONS):
            current_question = MEDICAL_QUESTIONS[question_index]["question"]
            
            # Store the response (either from interactive button or text)
            response_value = None
            if interactive_response:
                response_value = interactive_response.get("title")
            else:
                # If it's a text message instead of button selection, use LLM
                await process_message_with_llm(from_id, text)
                # After LLM response, show the current question options again
                await asyncio.sleep(1)
                send_interactive_options(from_id, current_question, MEDICAL_QUESTIONS[question_index]["options"])
                return
                
            if response_value:
                # Create a key for the response based on the question
                key = f"medical_q{question_index+1}"
                user_states[from_id]["responses"][key] = response_value
                store_interaction(from_id, current_question, f"Selected: {response_value}")
                
                # Store the question itself in the responses for complete Q&A history
                q_key = f"medical_question{question_index+1}"
                user_states[from_id]["responses"][q_key] = current_question
                
                # Move to the next question
                user_states[from_id]["question_index"] = question_index + 1
                
                # If there are more questions, ask the next one
                if question_index + 1 < len(MEDICAL_QUESTIONS):
                    next_question = MEDICAL_QUESTIONS[question_index + 1]
                    send_interactive_options(from_id, next_question["question"], next_question["options"])
                elif question_index + 1 == len(MEDICAL_QUESTIONS):
                    # If we've reached the special salary question (not in the array)
                    salary_question = "Could you please tell me your monthly salary?"
                    send_whatsapp_message(from_id, salary_question)
                    store_interaction(from_id, "Bot asked about salary", salary_question)
                    user_states[from_id]["responses"]["medical_question_salary"] = salary_question
                return
            
        # Handle salary question (after all structured questions)
        elif question_index == len(MEDICAL_QUESTIONS):
            # Store salary info
            salary_response = text.strip()
            user_states[from_id]["responses"]["monthly_salary"] = salary_response
            store_interaction(from_id, "Salary question", f"Response: {salary_response}")
            
            # After collecting salary, move directly to the completion stage
            user_states[from_id]["stage"] = "completed"
            
            # Create a summary JSON of the user's responses
            user_json = json.dumps(user_states[from_id]["responses"], indent=2)
            print(f"User data collected for {from_id}: {user_json}")
            
            # Send confirmation to user
            thanks = "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry"
            send_whatsapp_message(from_id, thanks)
            store_interaction(from_id, "Completion confirmation", thanks)
            
            
            await asyncio.sleep(1)
            send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
            user_states[from_id]["stage"] = "waiting_for_new_query"
            return
    
    # Handle Motor Insurance flow
    elif state["stage"] == "motor_insurance_flow":
        # Store vehicle information
        vehicle_info = text.strip()
        user_states[from_id]["responses"]["vehicle_info"] = vehicle_info
        store_interaction(from_id, "What is the year, make and model of your vehicle?", f"Response: {vehicle_info}")
        user_states[from_id]["responses"]["motor_question_vehicle"] = "What is the year, make and model of your vehicle?"
        
        user_states[from_id]["stage"] = "motor_insurance_driver"
        driving_question = "Thank you. How many years have you been driving?"
        send_whatsapp_message(from_id, driving_question)
        store_interaction(from_id, "Bot asked about driving experience", driving_question)
        user_states[from_id]["responses"]["motor_question_driving"] = driving_question
        return
        
    # Motor Insurance flow - driving experience
    elif state["stage"] == "motor_insurance_driver":
        driving_exp = text.strip()
        user_states[from_id]["responses"]["driving_experience"] = driving_exp
        store_interaction(from_id, "Driving experience question", f"Response: {driving_exp}")
        
        user_states[from_id]["stage"] = "motor_insurance_coverage"
        coverage_question = "What type of coverage are you looking for? (Comprehensive, Third Party Only, etc.)"
        send_whatsapp_message(from_id, coverage_question)
        store_interaction(from_id, "Bot asked about coverage", coverage_question)
        user_states[from_id]["responses"]["motor_question_coverage"] = coverage_question
        return
        
    # Motor Insurance flow - coverage type
    elif state["stage"] == "motor_insurance_coverage":
        coverage_type = text.strip()
        user_states[from_id]["responses"]["desired_coverage"] = coverage_type
        store_interaction(from_id, "Coverage type question", f"Response: {coverage_type}")
        
        user_states[from_id]["stage"] = "motor_insurance_contact"
        contact_question = "Thank you for providing that information. What's your phone number and preferred contact time?"
        send_whatsapp_message(from_id, contact_question)
        store_interaction(from_id, "Bot asked for contact details", contact_question)
        user_states[from_id]["responses"]["motor_question_contact"] = contact_question
        return
        
    # Motor Insurance flow - contact info and completion
    elif state["stage"] == "motor_insurance_contact":
        contact_info = text.strip()
        user_states[from_id]["responses"]["contact_info"] = contact_info
        store_interaction(from_id, "Contact info question", f"Response: {contact_info}")
        user_states[from_id]["stage"] = "completed"
        
        # Create a summary JSON of the user's responses
        user_json = json.dumps(user_states[from_id]["responses"], indent=2)
        print(f"User data collected for {from_id}: {user_json}")
        
        # Send confirmation to user
        confirmation1 = "Perfect! I've collected all the information we need for your Motor Insurance quote."
        send_whatsapp_message(from_id, confirmation1)
        store_interaction(from_id, "Completion confirmation", confirmation1)
        
        await asyncio.sleep(1)
        confirmation2 = "Our insurance specialist will contact you at your preferred time to discuss your options."
        send_whatsapp_message(from_id, confirmation2)
        store_interaction(from_id, "Next steps", confirmation2)
        
        await asyncio.sleep(1)
        send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
        user_states[from_id]["stage"] = "waiting_for_new_query"
        return
        
    # Handle Claim flow
    elif state["stage"] == "claim_flow":
        # Store claim type
        claim_type = text.strip()
        user_states[from_id]["responses"]["claim_type"] = claim_type
        store_interaction(from_id, "What type of insurance policy are you filing a claim for?", f"Response: {claim_type}")
        user_states[from_id]["responses"]["claim_question_type"] = "What type of insurance policy are you filing a claim for?"
        
        user_states[from_id]["stage"] = "claim_policy"
        policy_question = "Thank you. What is your policy number?"
        send_whatsapp_message(from_id, policy_question)
        store_interaction(from_id, "Bot asked for policy number", policy_question)
        user_states[from_id]["responses"]["claim_question_policy"] = policy_question
        return
        
    # Claim flow - policy number
    elif state["stage"] == "claim_policy":
        policy_number = text.strip()
        user_states[from_id]["responses"]["policy_number"] = policy_number
        store_interaction(from_id, "Policy number question", f"Response: {policy_number}")
        
        user_states[from_id]["stage"] = "claim_details"
        details_question = "Please briefly describe the incident for which you are filing a claim:"
        send_whatsapp_message(from_id, details_question)
        store_interaction(from_id, "Bot asked for incident details", details_question)
        user_states[from_id]["responses"]["claim_question_details"] = details_question
        return
        
    # Claim flow - incident details
    elif state["stage"] == "claim_details":
        incident_details = text.strip()
        user_states[from_id]["responses"]["incident_details"] = incident_details
        store_interaction(from_id, "Incident details question", f"Response: {incident_details}")
        
        user_states[from_id]["stage"] = "claim_date"
        date_question = "When did the incident occur? (Please provide the date)"
        send_whatsapp_message(from_id, date_question)
        store_interaction(from_id, "Bot asked for incident date", date_question)
        user_states[from_id]["responses"]["claim_question_date"] = date_question
        return
        
    # Claim flow - incident date and completion
    elif state["stage"] == "claim_date":
        incident_date = text.strip()
        user_states[from_id]["responses"]["incident_date"] = incident_date
        store_interaction(from_id, "Incident date question", f"Response: {incident_date}")
        user_states[from_id]["stage"] = "completed"
        
        # Create a summary JSON of the user's responses
        user_json = json.dumps(user_states[from_id]["responses"], indent=2)
        print(f"User data collected for {from_id}: {user_json}")
        
        # Send confirmation to user
        confirmation1 = "Thank you for providing the claim information."
        send_whatsapp_message(from_id, confirmation1)
        time.sleep(1)
        confirmation2 = "A claims specialist will contact you within 24 hours to process your claim and guide you through the next steps."
        send_whatsapp_message(from_id, confirmation2)
        time.sleep(1)
        send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
        user_states[from_id]["stage"] = "waiting_for_new_query"
        return

@app.get("/")
def welcome():
    return {"message": "Hello, Welcome to Insura!"}

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

@app.api_route("/webhook", methods=["GET", "POST"])
async def webhook(request: Request):
    # Handle GET request (Webhook verification)
    if request.method == "GET":
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            return PlainTextResponse(content="error", status_code=403)
    
    # Handle POST request (Receiving messages)
    if request.method == "POST":
        data = await request.json()
        print("Webhook received data:", data)
        
        if "object" in data and "entry" in data:
            if data["object"] == "whatsapp_business_account":
                for entry in data["entry"]:
                    changes = entry.get("changes", [])
                    if changes:
                        value = changes[0].get("value", {})
                        
                        # Handle incoming messages
                        if "messages" in value:
                            messages = value["messages"]
                            from_id = messages[0].get("from")
                            msg_type = messages[0].get("type")
                            
                            # Extract profile name from contacts if available
                            profile_name = None
                            contacts = value.get("contacts", [])
                            if contacts and len(contacts) > 0:
                                first_contact = contacts[0]
                                profile = first_contact.get("profile", {})
                                profile_name = profile.get("name")
                                print(f"Profile name from WhatsApp: {profile_name}")
                            
                            # Handle text messages
                            if msg_type == "text":
                                text = messages[0].get("text", {}).get("body", "")
                                if from_id and text:
                                    # Process the conversation asynchronously
                                    asyncio.create_task(process_conversation(from_id, text, profile_name, None))
                            
                            # Handle interactive responses (button clicks or list selections)
                            elif msg_type == "interactive":
                                interactive_data = messages[0].get("interactive", {})
                                interactive_type = interactive_data.get("type")
                                
                                interactive_response = None
                                
                                if interactive_type == "button_reply":
                                    button_reply = interactive_data.get("button_reply", {})
                                    interactive_response = button_reply
                                    print(f"Button clicked: {button_reply.get('id')} - {button_reply.get('title')}")
                                
                                elif interactive_type == "list_reply":
                                    list_reply = interactive_data.get("list_reply", {})
                                    interactive_response = list_reply
                                    print(f"List item selected: {list_reply.get('id')} - {list_reply.get('title')}")
                                
                                if interactive_response:
                                    # Process the interactive response asynchronously
                                    asyncio.create_task(process_conversation(from_id, "", profile_name, interactive_response))
                        
                        # Handle message status updates (optional)
                        elif "statuses" in value:
                            status_info = value["statuses"][0]
                            message_status = status_info.get("status", "unknown")
                            recipient_id = status_info.get("recipient_id", "unknown")
                            print(f"Message to {recipient_id} is now {message_status}")
        
        return {"status": "success"}


# Endpoint to manually send a greeting message
@app.get("/send-greeting/{phone_number}")
async def send_greeting(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    
    success = send_whatsapp_message(
        phone_number,
        "Hi there! My name is Insura from Wehbe Insurance Broker, your AI insurance assistant. I will be happy to assist you with your insurance requirements."
    )
    
    if success:
        return {"status": "success", "message": f"Greeting sent to {phone_number}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send message")

# Endpoint to reset a user's conversation
@app.get("/reset-conversation/{phone_number}")
async def reset_conversation(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    
    if phone_number in user_states:
        user_states.pop(phone_number)
        return {"status": "success", "message": f"Conversation reset for {phone_number}"}
    else:
        return {"status": "warning", "message": f"No active conversation found for {phone_number}"}

# New endpoint to retrieve user data
@app.get("/get-user-data/{phone_number}")
async def get_user_data(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    
    if phone_number in user_states:
        return user_states[phone_number].get("responses", {})
    else:
        raise HTTPException(status_code=404, detail="User not found")

# New endpoint to test LLM response directlys
@app.get("/test-llm/{message}")
async def test_llm(message: str):
    try:
        response = llm.invoke([SystemMessage(content="You are Insura, a friendly Insurance assistant created by CloudSubset. Your role is to assist with any inquiries using your vast knowledge base. Provide helpful, accurate, and user-friendly responses to all questions or requests. Do not mention being a large language model; you are Insura."),HumanMessage(content=message)]).content
        return {"status": "success", "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# New endpoint to retrieve only LLM responses for a user
@app.get("/get-llm-responses/{phone_number}")
async def get_llm_responses(phone_number: str):
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    
    if phone_number in user_states:
        # Return just the LLM responses if they exist
        if "llm_responses" in user_states[phone_number]:
            return {"responses": user_states[phone_number]["llm_responses"]}
        else:
            # Alternatively, extract only the answers from conversation history
            if "conversation_history" in user_states[phone_number]:
                llm_responses = [
                    {"response": item["answer"], "timestamp": item["timestamp"]} 
                    for item in user_states[phone_number]["conversation_history"] 
                    # Filter out interactive responses (they contain "[" which indicates button/list options)
                    if not item["answer"].startswith("[Interactive")
                ]
                return {"responses": llm_responses}
            else:
                return {"responses": []}
    else:
        raise HTTPException(status_code=404, detail="User not found")
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)