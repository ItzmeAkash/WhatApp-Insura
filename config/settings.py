from dotenv import load_dotenv
import os

load_dotenv()

PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION")
WHATAPP_URL = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
WHATSAPP_TOKEN = os.getenv("ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Structured questions
INITIAL_QUESTIONS = [
    {
        "question": "What would you like to do today?",
        "options": [
            "Medical Insurance",
            "Motor Insurance",
            "Claim"
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