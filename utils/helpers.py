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