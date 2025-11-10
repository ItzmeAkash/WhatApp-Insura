import json
import requests
from config.settings import WHATAPP_URL, WHATSAPP_TOKEN, VERSION
from utils.helpers import store_interaction
from .translation import translate_text_sync, translate_list_sync


USER_LANGUAGE_PREFERENCES = {}


def _normalize_user_id(user_id: str) -> str:
    return user_id.lstrip("+") if user_id else user_id


def _sanitize_text(text: str, limit: int) -> str:
    if not text:
        return text
    sanitized = " ".join(text.strip().split())
    if len(sanitized) > limit:
        sanitized = sanitized[:limit].rstrip()
    return sanitized


def set_user_language(user_id: str, language: str):
    if not user_id:
        return
    USER_LANGUAGE_PREFERENCES[_normalize_user_id(user_id)] = language or "en"


def get_user_language(user_id: str) -> str:
    return USER_LANGUAGE_PREFERENCES.get(_normalize_user_id(user_id), "en")


def clear_user_language(user_id: str):
    USER_LANGUAGE_PREFERENCES.pop(_normalize_user_id(user_id), None)


def send_whatsapp_message(to: str, message: str) -> bool:
    language = get_user_language(to)
    if language != "en":
        message = translate_text_sync(message, language, "en")
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message},
    }
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Message sent to {to}, status code: {response.status_code}")
    return response.status_code == 200


def send_typing_indicator(to: str) -> bool:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
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
            "text": {"preview_url": False, "body": "<typing>"},
        },
    }
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Typing indicator sent to {to}, status code: {response.status_code}")
    return response.status_code == 200


def send_interactive_buttons(
    recipient: str, text: str, options: list, user_states: dict, max_buttons: int = 3
) -> bool:
    language = get_user_language(recipient)
    normalized_id = _normalize_user_id(recipient)
    state_key = recipient if recipient in user_states else normalized_id
    recipient_state = user_states.get(state_key)

    original_options = [opt.strip() for opt in options[:max_buttons]]
    translated_text = text
    translated_options = original_options

    if language != "en":
        translated_text = translate_text_sync(text, language, "en")
        translated_options = translate_list_sync(original_options, language, "en")

    sanitized_text = _sanitize_text(translated_text, 1024)
    sanitized_options = [_sanitize_text(option, 20) for option in translated_options]
    for idx, option in enumerate(sanitized_options):
        if not option:
            sanitized_options[idx] = f"Option {idx + 1}"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    buttons = [
        {
            "type": "reply",
            "reply": {
                "id": f"button_{i + 1}",
                "title": sanitized_options[i],
            },
        }
        for i in range(len(original_options))
    ]

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": sanitized_text},
            "action": {"buttons": buttons},
        },
    }

    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(
        f"Interactive message sent to {recipient}, status code: {response.status_code}"
    )

    store_interaction(
        from_id=recipient,
        question=translated_text,
        answer=f"[Interactive buttons: {', '.join(original_options)}]",
        user_states=user_states,
    )

    if recipient_state is not None:
        recipient_state["last_options_original"] = original_options
        recipient_state["last_option_id_map"] = {
            f"button_{i + 1}": option for i, option in enumerate(original_options)
        }
        title_map = {}
        for i, option in enumerate(original_options):
            canonical = option.strip().lower()
            title_map[canonical] = option
            translated_option = sanitized_options[i]
            title_map[translated_option.strip().lower()] = option
            title_map[f"button_{i + 1}"] = option
            title_map[str(i + 1)] = option
        state_saved_language = get_user_language(recipient)
        recipient_state["language"] = state_saved_language
        recipient_state["last_option_title_map"] = title_map
        recipient_state["last_option_display"] = sanitized_options

    return response.status_code == 200


def send_interactive_list(
    recipient: str,
    text: str,
    options: list,
    user_states: dict,
    list_title: str = "Options",
    section_title: str = "Available options",
) -> bool:
    # Ensure phone number has + prefix
    if not recipient.startswith("+"):
        recipient = f"+{recipient}"

    language = get_user_language(recipient)
    normalized_id = _normalize_user_id(recipient)
    state_key = recipient if recipient in user_states else normalized_id
    recipient_state = user_states.get(state_key)

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    # Limit to 10 options and truncate titles to 24 characters
    limited_options = [opt.strip() for opt in options[:10]]
    translated_text = text
    translated_section_title = section_title
    translated_button = "View Options"
    translated_options = limited_options

    if language != "en":
        translated_text = translate_text_sync(text, language, "en")
        translated_section_title = translate_text_sync(section_title, language, "en")
        translated_button = translate_text_sync(translated_button, language, "en")
        translated_options = translate_list_sync(limited_options, language, "en")

    sanitized_text = _sanitize_text(translated_text, 1024)
    sanitized_section_title = _sanitize_text(translated_section_title, 24)
    sanitized_button = _sanitize_text(translated_button, 20) or "Options"
    sanitized_options = [
        _sanitize_text(option, 24) or f"Option {i + 1}"
        for i, option in enumerate(translated_options)
    ]

    display_options = sanitized_options
    rows = [
        {
            "id": f"option_{i + 1}",
            "title": display_options[i],  # Truncate to 24 chars
        }
        for i in range(len(limited_options))
    ]

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": sanitized_text},
            "action": {
                "button": sanitized_button,
                "sections": [
                    {"title": sanitized_section_title, "rows": rows}
                ],  # Ensure section title is <= 24 chars
            },
        },
    }

    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(
        f"Interactive list message sent to {recipient}, status code: {response.status_code}"
    )
    if response.status_code != 200:
        print(f"Error response: {response.text}")  # Log the error details

    store_interaction(
        from_id=recipient,
        question=translated_text,
        answer=f"[Interactive list: {', '.join(limited_options)}]",
        user_states=user_states,
    )

    if recipient_state is not None:
        recipient_state["last_options_original"] = limited_options
        recipient_state["last_option_id_map"] = {
            f"option_{i + 1}": option for i, option in enumerate(limited_options)
        }
        title_map = {}
        for i, option in enumerate(limited_options):
            canonical = option.strip().lower()
            title_map[canonical] = option
            display_option = display_options[i].strip().lower()
            if display_option:
                title_map[display_option] = option
            translated_option = sanitized_options[i].strip().lower()
            title_map[translated_option] = option
            title_map[f"option_{i + 1}"] = option
            title_map[str(i + 1)] = option
        recipient_state["last_option_title_map"] = title_map
        recipient_state["last_option_display"] = sanitized_options
        recipient_state["language"] = language

    return response.status_code == 200


def send_interactive_options(
    recipient: str,
    text: str,
    options: list,
    user_states: dict,
    list_title: str = "Options",
    section_title: str = "Available options",
) -> bool:
    if len(options) <= 3:
        return send_interactive_buttons(recipient, text, options, user_states)
    else:
        return send_interactive_list(
            recipient, text, options, user_states, list_title, section_title
        )


def send_yes_no_options(recipient: str, text: str, user_states: dict) -> bool:
    return send_interactive_buttons(recipient, text, ["Yes", "No"], user_states)


# Translation wrapper functions
async def send_whatsapp_message_translated(
    to: str, message: str, user_states: dict, target_language: str = None
) -> bool:
    """Send WhatsApp message with translation support"""
    if target_language is None:
        state = user_states.get(to) or user_states.get(_normalize_user_id(to), {})
        target_language = state.get("language", "en")

    set_user_language(to, target_language)
    return send_whatsapp_message(to, message)


async def send_interactive_options_translated(
    recipient: str,
    text: str,
    options: list,
    user_states: dict,
    list_title: str = "Options",
    section_title: str = "Available options",
    target_language: str = None,
) -> bool:
    """Send interactive options with translation support"""
    if target_language is None:
        state = user_states.get(recipient) or user_states.get(
            _normalize_user_id(recipient), {}
        )
        target_language = state.get("language", "en")

    set_user_language(recipient, target_language)
    return send_interactive_options(
        recipient, text, options, user_states, list_title, section_title
    )


async def send_yes_no_options_translated(
    recipient: str, text: str, user_states: dict, target_language: str = None
) -> bool:
    """Send Yes/No options with translation support"""
    if target_language is None:
        state = user_states.get(recipient) or user_states.get(
            _normalize_user_id(recipient), {}
        )
        target_language = state.get("language", "en")

    set_user_language(recipient, target_language)
    return send_yes_no_options(recipient, text, user_states)


def download_whatsapp_audio(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
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
            print(
                f"Failed to download audio: {audio_response.status_code}, Response: {audio_response.text}"
            )
            return None
    else:
        print(
            f"Failed to get media URL: {response.status_code}, Response: {response.text}"
        )
        return None


# In services/whatsapp.py
def download_whatsapp_media(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
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
            print(
                f"Failed to download media: {download_response.status_code}, Response: {download_response.text}"
            )
            return None
    else:
        print(
            f"Failed to get media URL: {response.status_code}, Response: {response.text}"
        )
        return None


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
        "Content-Type": "application/json",
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
                            "text": "Verify Your Document Information",
                        },
                        {
                            "type": "TextBody",
                            "text": "We've extracted the following information from your document. Please review and update if needed.",
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Full Name",
                            "default_value": flow_data.get("data", {}).get(
                                "fullName", ""
                            ),
                            "name": "fullName",
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "ID Number",
                            "default_value": flow_data.get("data", {}).get(
                                "idNumber", ""
                            ),
                            "name": "idNumber",
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Date of Birth",
                            "default_value": flow_data.get("data", {}).get(
                                "dateOfBirth", ""
                            ),
                            "name": "dateOfBirth",
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Nationality",
                            "default_value": flow_data.get("data", {}).get(
                                "nationality", ""
                            ),
                            "name": "nationality",
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Issue Date",
                            "default_value": flow_data.get("data", {}).get(
                                "issueDate", ""
                            ),
                            "name": "issueDate",
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Expiry Date",
                            "default_value": flow_data.get("data", {}).get(
                                "expiryDate", ""
                            ),
                            "name": "expiryDate",
                        },
                        {
                            "type": "RadioButtons",
                            "name": "gender",
                            "label": "Gender",
                            "default_option": flow_data.get("data", {}).get(
                                "gender", "male"
                            ),
                            "options": [
                                {"id": "male", "text": "Male"},
                                {"id": "female", "text": "Female"},
                            ],
                        },
                        {
                            "type": "TextInput",
                            "required": True,
                            "label": "Card Number",
                            "default_value": flow_data.get("data", {}).get(
                                "cardNumber", ""
                            ),
                            "name": "cardNumber",
                        },
                        {
                            "type": "TextInput",
                            "required": False,
                            "label": "Occupation",
                            "default_value": flow_data.get("data", {}).get(
                                "occupation", ""
                            ),
                            "name": "occupation",
                        },
                        {
                            "type": "TextInput",
                            "required": False,
                            "label": "Employer",
                            "default_value": flow_data.get("data", {}).get(
                                "employer", ""
                            ),
                            "name": "employer",
                        },
                        {
                            "type": "TextInput",
                            "required": False,
                            "label": "Issuing Place",
                            "default_value": flow_data.get("data", {}).get(
                                "issuingPlace", ""
                            ),
                            "name": "issuingPlace",
                        },
                        {
                            "type": "Footer",
                            "label": "Submit",
                            "on-click-action": {"name": "complete", "payload": {}},
                        },
                    ],
                },
                "title": "Document Verification",
            }
        ],
    }

    # Construct the payload for the WhatsApp API
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "template",
        "template": {
            "name": "document_verification",  # This template must be pre-registered in WhatsApp Business Platform
            "language": {"code": "en_US"},
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
                                "flow_action_data": flow_data.get("data", {}),
                            },
                        }
                    ],
                }
            ],
        },
    }

    # Make the API request
    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Flow message sent to {to}, status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response: {response.text}")

    return response.status_code == 200


def send_link_button(
    to: str, message: str, button_text: str, url: str, user_states: dict
) -> bool:
    """
    Send a message with a clickable button that opens a URL

    Args:
        to (str): The recipient's WhatsApp ID
        message (str): The message text to send
        button_text (str): Text to display on the button
        url (str): URL to open when the button is clicked
        user_states (dict): User states dictionary for logging

    Returns:
        bool: True if the message was sent successfully
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    language = get_user_language(to)
    translated_message = message
    translated_button = button_text
    if language != "en":
        translated_message = translate_text_sync(message, language, "en")
        translated_button = translate_text_sync(button_text, language, "en")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": translated_message},
            "action": {
                "name": "cta_url",
                "parameters": {"display_text": translated_button, "url": url},
            },
        },
    }

    response = requests.post(WHATAPP_URL, headers=headers, json=payload)
    print(f"Link button message sent to {to}, status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response: {response.text}")

    store_interaction(
        from_id=to,
        question=translated_message,
        answer=f"[Link button: {button_text} -> {url}]",
        user_states=user_states,
    )

    return response.status_code == 200
