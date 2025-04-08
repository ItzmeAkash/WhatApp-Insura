from dotenv import load_dotenv
import os

load_dotenv()

PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION")
WHATAPP_URL = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
WHATSAPP_TOKEN = os.getenv("ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
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
        "question": "Great Choice! Let's start with your Medical insurance details. Choose your Visa issued Emirate?",
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
        "question": "Thank you! Now, Let's move on to: What type of plan are you looking for?",
        "options": [
            "Basic Plan", 
            "Enhanced Plan", 
            "Enhanced Plan Standalone", 
            "Flexi Plan"
        ]
    },
    {
        "question": "Thank you! Now, let's move to the sponsor details, Could you let me know the sponsor's type?",
        "options": [
            "Employee",
            "Investors"
        ]
    }
]


EMAF_INSURANCE_COMPANIES = [
    {
        "question":"Could you kindly confirm the name of your insurance company, please?",
    "options":["Takaful Emarat (Ecare)",
    "National Life & General Insurance (Innayah)",
    "Takaful Emarat (Aafiya)",
    "National Life & General Insurance (NAS)",
    "Orient UNB Takaful (Nextcare)",
    "Orient Mednet (Mednet)",
    "Al Sagr Insurance (Nextcare)",
    "RAK Insurance (Mednet)",
    "Dubai Insurance (Dubai Care)",
    "Fidelity United (Nextcare)",
    "Salama April International (Salama)",
    "Sukoon (Sukoon)",
    "Orient basic",
    "Daman",
    "Dubai insurance(Mednet)",
    "Takaful Emarat(NAS)",
    "Takaful emarat(Nextcare)"
    ]
    }
]

COMPANY_NUMBER_MAPPING = {
    "Takaful Emarat (Ecare)": 1,
    "National Life & General Insurance (Innayah)": 2,
    "Takaful Emarat (Aafiya)": 3,
    "National Life & General Insurance (NAS)": 4,
    "Orient UNB Takaful (Nextcare)": 6,
    "Orient Mednet (Mednet)": 7,
    "Al Sagr Insurance (Nextcare)": 8,
    "RAK Insurance (Mednet)": 9,
    "Dubai Insurance (Dubai Care)": 10,
    "Fidelity United (Nextcare)": 11,
    "Salama April International (Salama)": 12,
    "Sukoon (Sukoon)": 13,
    "Orient basic": 14,
    "Daman": 15,
    "Dubai insurance(Mednet)": 16,
    "Takaful Emarat(NAS)": 17,
    "Takaful emarat(Nextcare)": 18,
}