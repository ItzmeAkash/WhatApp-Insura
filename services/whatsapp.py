import json
import requests
from config.settings import WHATAPP_URL, WHATSAPP_TOKEN,VERSION
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
    # Ensure phone number has + prefix
    if not recipient.startswith("+"):
        recipient = f"+{recipient}"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Limit to 10 options and truncate titles to 24 characters
    limited_options = options[:10]
    rows = [
        {
            "id": f"option_{i+1}",
            "title": option[:24],  # Truncate to 24 chars
        }
        for i, option in enumerate(limited_options)
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
                "sections": [{"title": section_title[:24], "rows": rows}]  # Ensure section title is <= 24 chars
            }
        }
    }
    
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Interactive list message sent to {recipient}, status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response: {response.text}")  # Log the error details
    
    store_interaction(
        from_id=recipient,
        question=text,
        answer=f"[Interactive list: {', '.join(limited_options)}]",
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



def download_whatsapp_audio(media_id: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }
    media_url = f"https://graph.facebook.com/{VERSION}/{media_id}"
    print(f"Requesting media URL: {media_url}")
    print(f"Using token (first 10 chars): {WHATSAPP_TOKEN[:10]}...")
    response = requests.get(media_url, headers=headers)
    
    if response.status_code == 200:
        audio_url = response.json().get("url")
        print(f"Retrieved audio URL: {audio_url}")
        audio_response = requests.get(audio_url, headers=headers)
        if audio_response.status_code == 200:
            print(f"Audio downloaded, size: {len(audio_response.content)} bytes")
            return audio_response.content
        else:
            print(f"Failed to download audio: {audio_response.status_code}, Response: {audio_response.text}")
            return None
    else:
        print(f"Failed to get media URL: {response.status_code}, Response: {response.text}")
        return None
    

# In services/whatsapp.py
def download_whatsapp_media(media_id: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }
    media_url = f"https://graph.facebook.com/{VERSION}/{media_id}"
    print(f"Requesting media URL: {media_url}")
    response = requests.get(media_url, headers=headers)
    
    if response.status_code == 200:
        download_url = response.json().get("url")
        print(f"Retrieved download URL: {download_url}")
        download_response = requests.get(download_url, headers=headers)
        if download_response.status_code == 200:
            print(f"Media downloaded, size: {len(download_response.content)} bytes")
            return download_response.content
        else:
            print(f"Failed to download media: {download_response.status_code}, Response: {download_response.text}")
            return None
    else:
        print(f"Failed to get media URL: {response.status_code}, Response: {response.text}")
        return None



def send_flow_message(to: str,  flow_data: dict) -> bool:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "header": {
                "type": "text",
                "text": "Verify Your Document Details"
            },
            "body": {
                "text": "Please review the extracted information below and confirm or edit as needed."
            },
            "footer": {
                "text": "Tap 'Submit' when done"
            },
            "action": {
                "name": "flow",
                "parameters": {
                    # Your pre-created Flow ID from WhatsApp Business Platform
                    "mode": "draft",  # Use "draft" for testing, "published" for live
                    "flow_data": flow_data  # Data to pre-fill the Flow form
                }
            }
        }
    }
    
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Flow message sent to {to}, status code: {response.status_code}")
    return response.status_code == 200


def send_flow_message(to: str, flow_data: dict) -> bool:
    """
    Send a WhatsApp Flow with editable document information
    
    Args:
        to (str): The recipient's WhatsApp ID
        flow_data (dict): The data to pre-fill in the flow
        
    Returns:
        bool: True if message was sent successfully
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Define the flow JSON structure with editable fields
    flow_json = {
        "version": "5.0",
        "screens": [
            {
                "id": "DOCUMENT_VERIFICATION",
                "layout": {
                    "type": "SingleColumnLayout",
                    "children": [
                        {
                            "type": "TextHeading",
                            "text": "Verify Your Document Information"
                        },
                        {
                            "type": "TextBody",
                            "text": "We've extracted the following information from your document. Please review and update if needed."
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Full Name",
                            "default_value": flow_data.get("data", {}).get("fullName", ""),
                            "name": "fullName"
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "ID Number",
                            "default_value": flow_data.get("data", {}).get("idNumber", ""),
                            "name": "idNumber"
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Date of Birth",
                            "default_value": flow_data.get("data", {}).get("dateOfBirth", ""),
                            "name": "dateOfBirth"
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Nationality",
                            "default_value": flow_data.get("data", {}).get("nationality", ""),
                            "name": "nationality"
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Issue Date",
                            "default_value": flow_data.get("data", {}).get("issueDate", ""),
                            "name": "issueDate"
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Expiry Date",
                            "default_value": flow_data.get("data", {}).get("expiryDate", ""),
                            "name": "expiryDate"
                        },
                        {
                            "type": "RadioButtons",
                            "name": "gender",
                            "label": "Gender",
                            "default_option": flow_data.get("data", {}).get("gender", "male"),
                            "options": [
                                {"id": "male", "text": "Male"},
                                {"id": "female", "text": "Female"}
                            ]
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Card Number",
                            "default_value": flow_data.get("data", {}).get("cardNumber", ""),
                            "name": "cardNumber"
                        },
                        {
                            "type": "TextInput",
                            "required": False,
                            "label": "Occupation",
                            "default_value": flow_data.get("data", {}).get("occupation", ""),
                            "name": "occupation"
                        },
                        {
                            "type": "TextInput",
                            "required": False,
                            "label": "Employer",
                            "default_value": flow_data.get("data", {}).get("employer", ""),
                            "name": "employer"
                        },
                        {
                            "type": "TextInput",
                            "required": False,
                            "label": "Issuing Place",
                            "default_value": flow_data.get("data", {}).get("issuingPlace", ""),
                            "name": "issuingPlace"
                        },
                        {
                            "type": "Footer",
                            "label": "Submit",
                            "on-click-action": {
                                "name": "complete",
                                "payload": {}
                            }
                        }
                    ]
                },
                "title": "Document Verification"
            }
        ]
    }
    
    # Construct the payload for the WhatsApp API
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "template",
        "template": {
            "name": "document_verification",  # This template must be pre-registered in WhatsApp Business Platform
            "language": {
                "code": "en_US"
            },
            "components": [
                {
                    "type": "button",
                    "sub_type": "flow",
                    "index": "0",
                    "parameters": [
                        {
                            "type": "action",
                            "action": {
                                "flow_token": "document_verification_token",  # This should be a valid token
                                "flow_json": json.dumps(flow_json),
                                "flow_action_data": flow_data.get("data", {})
                            }
                        }
                    ]
                }
            ]
        }
    }
    
    # Make the API request
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Flow message sent to {to}, status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response: {response.text}")
    
    return response.status_code == 200