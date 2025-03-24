from pydantic import BaseModel
from typing import Dict, List, Optional

class UserState(BaseModel):
    stage: str
    name: Optional[str] = None
    responses: Dict = {}
    question_index: int = 0
    selected_service: Optional[str] = None
    conversation_history: List[Dict] = []
    llm_conversation_count: int = 0
    llm_responses: List[Dict] = []