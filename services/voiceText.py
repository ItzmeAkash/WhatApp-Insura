# services/deepgram.py
from deepgram import Deepgram
from config.settings import DEEPGRAM_API_KEY
import asyncio

async def transcribe_audio(audio_data: bytes) -> str:
    dg_client = Deepgram(DEEPGRAM_API_KEY)
    
    try:
        # Configure Deepgram options (e.g., language, model)
        options = {
            "model": "nova-2",  # High-accuracy model
            "language": "en",   # Adjust based on your use case
            "punctuate": True,
            "diarize": False    # Set to True if you want speaker detection
        }
        
        # Transcribe the audio
        response = await dg_client.transcription.prerecorded(
            {"buffer": audio_data, "mimetype": "audio/ogg"},  # WhatsApp voice messages are typically OGG
            options
        )
        
        # Extract the transcribed text
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript
    except Exception as e:
        print(f"Error transcribing audio with Deepgram: {e}")
        return None