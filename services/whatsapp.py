import requests
from config.settings import WHATAPP_URL, WHATSAPP_TOKEN
from utils.helpers import store_interaction

def send_whatsapp_message(to: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Message sent to {to}, status code: {response.status_code}")
    return response.status_code == 200

def send_typing_indicator(to: str) -> bool:
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

def send_interactive_buttons(recipient: str, text: str, options: list, user_states: dict, max_buttons: int = 3) -> bool:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    button_options = options[:max_buttons]
    buttons = [
        {
            "type": "reply",
            "reply": {
                "id": f"button_{i+1}",
                "title": option
            }
        }
        for i, option in enumerate(button_options)
    ]
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {"buttons": buttons}
        }
    }
    
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Interactive message sent to {recipient}, status code: {response.status_code}")
    
    store_interaction(
        from_id=recipient,
        question=text,
        answer=f"[Interactive buttons: {', '.join(button_options)}]",
        user_states=user_states
    )
    
    return response.status_code == 200

def send_interactive_list(recipient: str, text: str, options: list, user_states: dict, list_title: str = "Options", section_title: str = "Available options") -> bool:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    rows = [
        {
            "id": f"option_{i+1}",
            "title": option,
        }
        for i, option in enumerate(options)
    ]
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text},
            "action": {
                "button": "View Options",
                "sections": [{"title": section_title, "rows": rows}]
            }
        }
    }
    
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Interactive list message sent to {recipient}, status code: {response.status_code}")
    
    store_interaction(
        from_id=recipient,
        question=text,
        answer=f"[Interactive list: {', '.join(options)}]",
        user_states=user_states
    )
    
    return response.status_code == 200

def send_interactive_options(recipient: str, text: str, options: list, user_states: dict, list_title: str = "Options", section_title: str = "Available options") -> bool:
    if len(options) <= 3:
        return send_interactive_buttons(recipient, text, options, user_states)
    else:
        return send_interactive_list(recipient, text, options, user_states, list_title, section_title)

def send_yes_no_options(recipient: str, text: str, user_states: dict) -> bool:
    return send_interactive_buttons(recipient, text, ["Yes", "No"], user_states)
