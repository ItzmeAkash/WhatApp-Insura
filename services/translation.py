import asyncio
from langchain_groq.chat_models import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from config.settings import GROQ_API_KEY

# Language code mapping
LANGUAGE_MAPPING = {
    "english": "en",
    "arabic": "ar",
    "urdu": "ur",
    "hindi": "hi",
    "french": "fr",
    "spanish": "es",
    "en": "en",
    "ar": "ar",
    "ur": "ur",
    "hi": "hi",
    "fr": "fr",
    "es": "es",
}

# Default language
DEFAULT_LANGUAGE = "en"


def normalize_language(language_input: str) -> str:
    """Normalize language input to language code"""
    language_lower = language_input.lower().strip()
    return LANGUAGE_MAPPING.get(language_lower, DEFAULT_LANGUAGE)


def _build_translation_messages(text: str, target_language: str, source_language: str):
    # Language names for better translation
    language_names = {
        "ar": "Arabic",
        "en": "English",
        "ur": "Urdu",
        "hi": "Hindi",
        "fr": "French",
        "es": "Spanish",
    }

    target_lang_name = language_names.get(target_language, "Arabic")

    prompt = f"""Translate the following text from {source_language} to {target_language} ({target_lang_name}).
        
Translate accurately while maintaining the same meaning, tone, and context. 
Preserve any placeholders, numbers, URLs, or technical terms exactly as they are.
Only return the translated text, nothing else.

Text to translate:
{text}

Translated text:"""

    messages = [
        SystemMessage(
            content="You are a professional translator. Translate the given text accurately while preserving meaning, tone, and context. Only return the translated text."
        ),
        HumanMessage(content=prompt),
    ]
    return messages


async def translate_text(
    text: str, target_language: str = "ar", source_language: str = "en"
) -> str:
    """
    Translate text using LLM

    Args:
        text: Text to translate
        target_language: Target language code (e.g., 'ar' for Arabic)
        source_language: Source language code (default: 'en')

    Returns:
        Translated text
    """
    if target_language == "en" or target_language == source_language:
        return text

    if not text or not text.strip():
        return text

    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            api_key=GROQ_API_KEY,
            groq_proxy=None,
        )

        messages = _build_translation_messages(text, target_language, source_language)

        loop = asyncio.get_running_loop()
        translated_text = await loop.run_in_executor(
            None, lambda: llm.invoke(messages).content
        )

        return translated_text.strip()

    except Exception as e:
        print(f"Error translating text: {e}")
        # Return original text if translation fails
        return text


async def translate_list(
    items: list, target_language: str = "ar", source_language: str = "en"
) -> list:
    """
    Translate a list of items

    Args:
        items: List of strings to translate
        target_language: Target language code
        source_language: Source language code

    Returns:
        List of translated strings
    """
    if target_language == "en" or target_language == source_language:
        return items

    if not items:
        return items

    # Translate all items
    translated_items = []
    for item in items:
        translated = await translate_text(item, target_language, source_language)
        translated_items.append(translated)

    return translated_items


def translate_text_sync(
    text: str, target_language: str = "ar", source_language: str = "en"
) -> str:
    """Synchronous helper for translating text without awaiting"""
    if target_language == "en" or target_language == source_language:
        return text

    if not text or not text.strip():
        return text

    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            api_key=GROQ_API_KEY,
            groq_proxy=None,
        )
        messages = _build_translation_messages(text, target_language, source_language)
        translated_text = llm.invoke(messages).content
        return translated_text.strip()
    except Exception as e:
        print(f"Error translating text (sync): {e}")
        return text


def translate_list_sync(
    items: list, target_language: str = "ar", source_language: str = "en"
) -> list:
    """Synchronous helper for translating a list of strings"""
    if target_language == "en" or target_language == source_language:
        return items

    if not items:
        return items

    translated_items = []
    for item in items:
        translated_items.append(
            translate_text_sync(item, target_language, source_language)
        )
    return translated_items


def detect_language_change_request(text: str) -> tuple[bool, str]:
    """
    Detect if user wants to change language

    Args:
        text: User input text

    Returns:
        Tuple of (is_language_change_request, detected_language_code)
    """
    text_lower = text.lower().strip()

    # Common phrases for language change
    language_change_patterns = {
        "arabic": [
            "change to arabic",
            "switch to arabic",
            "arabic language",
            "speak arabic",
            "in arabic",
            "use arabic",
            "arabic please",
        ],
        "english": [
            "change to english",
            "switch to english",
            "english language",
            "speak english",
            "in english",
            "use english",
            "english please",
        ],
        "urdu": [
            "change to urdu",
            "switch to urdu",
            "urdu language",
            "speak urdu",
            "in urdu",
            "use urdu",
            "urdu please",
        ],
        "hindi": [
            "change to hindi",
            "switch to hindi",
            "hindi language",
            "speak hindi",
            "in hindi",
            "use hindi",
            "hindi please",
        ],
        "french": [
            "change to french",
            "switch to french",
            "french language",
            "speak french",
            "in french",
            "use french",
            "french please",
        ],
        "spanish": [
            "change to spanish",
            "switch to spanish",
            "spanish language",
            "speak spanish",
            "in spanish",
            "use spanish",
            "spanish please",
        ],
    }

    for language, patterns in language_change_patterns.items():
        for pattern in patterns:
            if pattern in text_lower:
                return True, normalize_language(language)

    # Check for direct language codes
    for lang_code in ["ar", "en", "ur", "hi", "fr", "es"]:
        if f"lang {lang_code}" in text_lower or f"language {lang_code}" in text_lower:
            return True, lang_code

    return False, "en"


async def detect_language_change_with_llm(text: str) -> tuple[bool, str]:
    """
    Use LLM to detect language change requests (more flexible)

    Args:
        text: User input text

    Returns:
        Tuple of (is_language_change_request, detected_language_code)
    """
    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            api_key=GROQ_API_KEY,
            groq_proxy=None,
        )

        prompt = f"""Analyze if the user EXPLICITLY wants to change the conversation language. Only return a language code if the user is CLEARLY requesting a language change.

User message: "{text}"

Available languages:
- English (code: en)
- Arabic (code: ar)
- Urdu (code: ur)
- Hindi (code: hi)
- French (code: fr)
- Spanish (code: es)

IMPORTANT: Only respond with a language code if the user EXPLICITLY requests a language change using phrases like:
- "change to [language]"
- "switch to [language]"
- "change language to [language]"
- "use [language]"
- "I want to use [language]"
- "[language] please" (when asking for language change)

If the user is just asking questions in a different language, or mentioning a language without requesting a change, respond with "no".

Examples:
- "change to arabic" → ar
- "switch to arabic" → ar
- "change language to arabic" → ar
- "I want to use arabic" → ar
- "arabic please" (when clearly requesting language change) → ar
- "What is insurance?" → no (even if in Arabic text)
- "Tell me about medical insurance" → no (even if in Arabic text)
- "I speak arabic" → no (just stating a fact, not requesting change)
- "Can you help me in arabic?" → no (asking if help is available, not requesting change)
- "Hello" → no (even if in Arabic script)
- "مرحبا" → no (greeting in Arabic, not a language change request)"""

        messages = [
            SystemMessage(
                content="You are a strict language detection assistant. ONLY detect language change when the user EXPLICITLY requests it with phrases like 'change to', 'switch to', 'change language to', 'use [language]'. Do NOT detect language change based on the language the user is typing in. If the user is just asking questions or having a conversation in a different language, respond with 'no'. Only respond with the language code (en, ar, ur, hi, fr, es) when there is an EXPLICIT language change request, otherwise respond with 'no'."
            ),
            HumanMessage(content=prompt),
        ]

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, lambda: llm.invoke(messages).content
        )

        result = response.strip().lower()

        if result == "no" or result not in ["en", "ar", "ur", "hi", "fr", "es"]:
            return False, "en"

        return True, result

    except Exception as e:
        print(f"Error in LLM language detection: {e}")
        # Fallback to simple pattern matching
        return detect_language_change_request(text)
