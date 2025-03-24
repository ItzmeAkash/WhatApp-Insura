import asyncio
from langchain_groq.chat_models import ChatGroq
from langchain.schema import HumanMessage,SystemMessage
from config.settings import GROQ_API_KEY
from .whatsapp import send_whatsapp_message, send_typing_indicator
from utils.helpers import store_interaction

def initialize_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        api_key=GROQ_API_KEY,
        groq_proxy=None
    )

async def process_message_with_llm(from_id: str, text: str, user_states: dict):
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        api_key=GROQ_API_KEY,
        groq_proxy=None
    )
    try:
        send_typing_indicator(from_id)
        
        prompt = f"user response: {text}. Please assist."
        messages = [
            SystemMessage(content="You are Insura, a friendly Insurance assistant created by CloudSubset. Your role is to assist with any inquiries using your vast knowledge base. Provide helpful, accurate, and user-friendly responses to all questions or requests. Do not mention being a large language model; you are Insura."),
            HumanMessage(content=prompt)
        ]
        
        loop = asyncio.get_running_loop()
        llm_response = await loop.run_in_executor(None, lambda: llm.invoke(messages).content)
        
        send_whatsapp_message(from_id, llm_response)
        
        if from_id in user_states:
            if "conversation_history" not in user_states[from_id]:
                user_states[from_id]["conversation_history"] = []
            user_states[from_id]["conversation_history"].append({
                "question": text,
                "answer": llm_response,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            if "llm_responses" not in user_states[from_id]:
                user_states[from_id]["llm_responses"] = []
            user_states[from_id]["llm_responses"].append({
                "response": llm_response,
                "timestamp": asyncio.get_event_loop().time()
            })
        
        return llm_response
    except Exception as e:
        print(f"Error processing message with LLM: {e}")
        send_whatsapp_message(from_id, "I'm sorry, I couldn't process your request at the moment. Please try again later.")
        return "Error processing message"