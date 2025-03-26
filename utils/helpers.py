import re
import time

def is_thank_you(text: str) -> bool:
    thank_patterns = [r'thank(?:s| you)', r'thx', r'thnx', r'tysm', r'ty']
    text = text.lower()
    return any(re.search(pattern, text) for pattern in thank_patterns)

def store_interaction(from_id: str, question: str, answer: str, user_states: dict):
    if from_id in user_states:
        if "conversation_history" not in user_states[from_id]:
            user_states[from_id]["conversation_history"] = []
        user_states[from_id]["conversation_history"].append({
            "question": question,
            "answer": answer,
            "timestamp": time.time()
        })
        
# utils/helpers.py
import requests

def emaf_document(response_dict):
    payload = {
        "name": response_dict.get("May I know your name, please?"),
        "network_id": response_dict.get("emaf_company_id"),
        "phone": response_dict.get("May I kindly ask for your phone number, please?"),
    }
    emaf_api = "https://www.insuranceclub.ae/Api/emaf"
    try:
        respond = requests.post(emaf_api, json=payload, timeout=10)
        respond.raise_for_status()
        emaf_id = respond.json()["id"]
        return emaf_id
    except requests.RequestException as e:
        print(f"Error calling EMAF API: {e}")
        return None