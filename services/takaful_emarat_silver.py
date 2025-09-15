import asyncio
from datetime import datetime
from typing import Dict, Optional
from .whatsapp import send_whatsapp_message, send_yes_no_options
from .llm import initialize_llm
from utils.helpers import store_interaction
from langchain.schema import HumanMessage, SystemMessage

# Predefined Q&A for Takaful Emarat Silver (matching your website implementation)
TAKAFUL_EMARAT_SILVER_QA = {
    "pre_existing_chronic_conditions": {
        "question_variations": [
            "pre existing & chronic conditions",
            "pre-existing",
            "chronic conditions",
            "chronic",
            "pre existing",
        ],
        "answer": "Covered only if declared in the Application Form and the terms, and additional premium to be agreed.",
        "llm_rewrite": True,
    },
    "area_of_coverage": {
        "question_variations": [
            "area of coverage",
            "coverage area",
            "where covered",
            "geographical coverage",
        ],
        "answer": "Worldwide",
        "llm_rewrite": True,
    },
    "annual_medicine_limit": {
        "question_variations": [
            "annual medicine limit",
            "medicine limit",
            "annual medicine",
            "medicine coverage",
            "drug limit",
        ],
        "answer": "AED 5,000",
        "llm_rewrite": True,
    },
    "consultation_fee": {
        "question_variations": [
            "consultation fee",
            "fee",
            "consultation cost",
            "doctor fee",
            "consultation charge",
        ],
        "answer": "AED 50",
        "llm_rewrite": True,
    },
    "network": {
        "question_variations": [
            "network",
            "hospitals",
            "doctors",
            "clinics",
            "where can I go",
            "network providers",
        ],
        "answer": "Nextcare",
        "llm_rewrite": True,
    },
    "dental_treatment": {
        "question_variations": [
            "dental treatment",
            "dental",
            "dental care",
            "dental coverage",
            "tooth",
        ],
        "answer": "Routine Dental is not covered. Cover only Emergency, injury cases & surgeries.",
        "llm_rewrite": True,
    },
    "direct_access_hospital": {
        "question_variations": [
            "direct access",
            "hospital access",
            "direct hospital",
            "hospital direct",
            "direct to hospital",
        ],
        "answer": "Yes",
        "llm_rewrite": True,
    },
}

# Document URL for Takaful Emarat Silver
TAKAFUL_EMARAT_SILVER_DOCUMENT_URL = (
    "https://iinsura.ai/slver-plan/pdf-view/*"
)


class TakafulEmaratSilverFlow:
    def __init__(self):
        self.llm = initialize_llm()

    def detect_takaful_emarat_silver_trigger(self, text: str) -> bool:
        """Detect if user is asking about Takaful Emarat Silver using LLM"""
        try:
            # First try simple keyword matching for common cases
            text_lower = text.lower()
            trigger_keywords = [
                "takaful emarat silver",
                "takaful emarat",
                "emarat silver",
                "takaful silver",
                "silver plan",
                "emarat insurance",
                "takaful insurance",
            ]

            if any(keyword in text_lower for keyword in trigger_keywords):
                return True

            # Use LLM for smart detection of related terms
            return self.detect_takaful_trigger_with_llm(text)

        except Exception as e:
            print(f"Error in trigger detection: {e}")
            # Fallback to simple keyword matching
            text_lower = text.lower()
            trigger_keywords = [
                "takaful emarat silver",
                "takaful emarat",
                "emarat silver",
                "takaful silver",
                "silver plan",
                "emarat insurance",
                "takaful insurance",
            ]
            return any(keyword in text_lower for keyword in trigger_keywords)

    def detect_takaful_trigger_with_llm(self, text: str) -> bool:
        """Use LLM to detect if user is asking about Takaful Emarat Silver"""
        try:
            prompt = f"""You are an expert insurance assistant. Analyze if the user's message is asking about Takaful Emarat Silver insurance plan.

The user might ask about:
- Takaful Emarat Silver plan
- Silver insurance plan
- Emarat insurance
- Takaful insurance
- Silver coverage
- Emarat coverage
- Any variation of these terms

User message: "{text}"

Respond with ONLY "yes" if the user is asking about Takaful Emarat Silver or related insurance plan, or "no" if they are asking about something else.

Examples:
- "Tell me about silver insurance" → yes
- "What is takaful emarat?" → yes
- "I want to know about emarat plan" → yes
- "Silver coverage details" → yes
- "How much does it cost?" → no (too generic)
- "What is health insurance?" → no (too generic)
- "Tell me about car insurance" → no (different type)"""

            response = self.llm.invoke([
                SystemMessage(
                    content="You are an expert insurance assistant. Analyze if user messages are asking about Takaful Emarat Silver insurance plan. Respond with only 'yes' or 'no'."
                ),
                HumanMessage(content=prompt),
            ])

            result = response.content.strip().lower()
            return result == "yes"

        except Exception as e:
            print(f"Error in LLM trigger detection: {e}")
            return False

    async def start_takaful_emarat_silver_flow(self, from_id: str, user_states: Dict):
        """Start the Takaful Emarat Silver conversation flow"""
        user_states[from_id]["stage"] = "takaful_emarat_silver_qa"
        user_states[from_id]["takaful_emarat_asked"] = True
        user_states[from_id]["last_takaful_query_time"] = datetime.now()
        user_states[from_id]["awaiting_takaful_followup"] = True
        user_states[from_id]["takaful_qa_count"] = 0

        # Generate AI welcome message (matching your website implementation)
        welcome_message = await self.generate_welcome_message()
        send_whatsapp_message(from_id, welcome_message)
        store_interaction(
            from_id, "Takaful Emarat Silver Welcome", welcome_message, user_states
        )

    async def generate_welcome_message(self) -> str:
        """Generate AI-powered welcome message for Takaful Emarat Silver (matching website implementation)"""
        try:
            welcome_prompt = "Rewrite this welcome message in a friendly, conversational way as if a real insurance agent is greeting a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: 'Welcome to the Takaful Emarat Silver plan! What do you need to know about the Takaful Emarat Silver plan? Please let me know, I am here to help you!'"

            messages = [
                SystemMessage(
                    content="You are Insura, a friendly Insurance assistant created by CloudSubset. Your role is to greet customers warmly and make them feel welcome and comfortable. Keep responses short (1-3 lines) and maintain the exact same information while making it sound natural."
                ),
                HumanMessage(content=welcome_prompt),
            ]

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: self.llm.invoke(messages).content
            )
            return response.strip()
        except Exception as e:
            print(f"Error generating welcome message: {e}")
            return "Welcome to the Takaful Emarat Silver plan! What do you need to know about the Takaful Emarat Silver plan? Please let me know, I am here to help you!"

    def find_matching_qa(self, user_question: str) -> Optional[Dict]:
        """Find the best matching Q&A based on user question using LLM"""
        try:
            # First try LLM-based detection
            llm_match = self.detect_qa_with_llm(user_question)
            if llm_match:
                return llm_match

            # Fallback to simple keyword matching if LLM doesn't find a match
            return self.find_matching_qa_simple(user_question)

        except Exception as e:
            print(f"Error in LLM QA detection: {e}")
            # Fallback to simple keyword matching
            return self.find_matching_qa_simple(user_question)

    def detect_qa_with_llm(self, user_question: str) -> Optional[Dict]:
        """Use LLM to detect which QA category the user question belongs to"""
        try:
            # Create a prompt with all available QA categories
            qa_categories = []
            for qa_key, qa_data in TAKAFUL_EMARAT_SILVER_QA.items():
                variations = ", ".join(qa_data["question_variations"])
                qa_categories.append(f"- {qa_key}: {variations}")

            categories_text = "\n".join(qa_categories)

            prompt = f"""You are an expert insurance assistant. Analyze the user's question and determine which Takaful Emarat Silver category it belongs to.

Available categories:
{categories_text}

User question: "{user_question}"

Respond with ONLY the category key (e.g., "consultation_fee", "area_of_coverage", etc.) if the question matches any category. If the question doesn't match any category, respond with "none".

Examples:
- "How much does it cost to see a doctor?" → consultation_fee
- "What hospitals can I visit?" → network
- "Is dental covered?" → dental_treatment
- "Can I go directly to hospital?" → direct_access_hospital
- "What's the medicine limit?" → annual_medicine_limit
- "Where am I covered?" → area_of_coverage
- "Do you cover pre-existing conditions?" → pre_existing_chronic_conditions
- "How much for consultation?" → consultation_fee
- "Which network do you use?" → network
- "Dental care included?" → dental_treatment"""

            response = self.llm.invoke([
                SystemMessage(
                    content="You are an expert insurance assistant. Analyze questions and match them to the correct insurance category. Respond with only the category key or 'none'."
                ),
                HumanMessage(content=prompt),
            ])

            detected_category = response.content.strip().lower()

            # Check if the detected category exists in our QA data
            if detected_category in TAKAFUL_EMARAT_SILVER_QA:
                return TAKAFUL_EMARAT_SILVER_QA[detected_category]

            return None

        except Exception as e:
            print(f"Error in LLM QA detection: {e}")
            return None

    def find_matching_qa_simple(self, user_question: str) -> Optional[Dict]:
        """Fallback simple keyword matching for QA detection"""
        user_question_lower = user_question.lower()

        best_match = None
        best_score = 0

        for qa_key, qa_data in TAKAFUL_EMARAT_SILVER_QA.items():
            for variation in qa_data["question_variations"]:
                if variation in user_question_lower:
                    score = len(variation)  # Simple scoring based on keyword length
                    if score > best_score:
                        best_score = score
                        best_match = qa_data

        return best_match

    async def process_takaful_question(
        self, from_id: str, text: str, user_states: Dict
    ) -> bool:
        """Process user question about Takaful Emarat Silver (matching website implementation)"""
        # Check if user has already asked about Takaful Emarat Silver first
        if not user_states[from_id].get("takaful_emarat_asked", False):
            # If Takaful Emarat Silver wasn't asked first, provide a general response
            general_response = "I'd be happy to help you with information about this topic. However, to provide you with the most accurate and specific information, could you please first ask about the Takaful Emarat Silver plan? This will help me give you the most relevant details for your situation."
            send_whatsapp_message(from_id, general_response)
            store_interaction(
                from_id, "Takaful General Response", general_response, user_states
            )
            return True

        matching_qa = self.find_matching_qa(text)

        if matching_qa:
            user_states[from_id]["takaful_qa_count"] += 1
            user_states[from_id]["awaiting_takaful_followup"] = True

            if matching_qa.get("llm_rewrite", False):
                # Use LLM to rewrite the answer (matching website implementation)
                answer = await self.rewrite_answer_with_llm(matching_qa["answer"], text)
            else:
                answer = matching_qa["answer"]

            send_whatsapp_message(from_id, answer)
            store_interaction(
                from_id,
                f"Takaful QA #{user_states[from_id]['takaful_qa_count']}",
                answer,
                user_states,
            )

            # After answering, send document
            await asyncio.sleep(2)
            await self.send_takaful_document(from_id, user_states)

            return True

        return False

    async def rewrite_answer_with_llm(
        self, base_answer: str, user_question: str
    ) -> str:
        """Use LLM to rewrite the answer based on user's specific question (matching website implementation)"""
        try:
            # Create specific prompts for each type of question (matching your website implementation)
            if (
                "pre existing" in user_question.lower()
                or "chronic" in user_question.lower()
            ):
                prompt = f"Rewrite this exact information about pre-existing and chronic conditions coverage in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"
            elif "area of coverage" in user_question.lower():
                prompt = f"Rewrite this exact information about area of coverage in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"
            elif "medicine limit" in user_question.lower():
                prompt = f"Rewrite this exact information about annual medicine limit in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"
            elif (
                "consultation fee" in user_question.lower()
                or "fee" in user_question.lower()
            ):
                prompt = f"Rewrite this exact information about consultation fee in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"
            elif "network" in user_question.lower():
                prompt = f"Rewrite this exact information about network in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"
            elif "dental" in user_question.lower():
                prompt = f"Rewrite this exact information about dental treatment coverage in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"
            elif (
                "direct access" in user_question.lower()
                or "hospital access" in user_question.lower()
            ):
                prompt = f"Rewrite this exact information about direct access to hospital in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"
            else:
                prompt = f"Rewrite this exact information in a friendly, conversational way as if a real insurance agent is speaking to a customer. Keep the same content but make it sound natural and warm. Use only 1-3 lines maximum: This is the content(answer)'{base_answer}'"

            messages = [
                SystemMessage(
                    content="You are Insura, a friendly Insurance assistant created by CloudSubset. Your role is to explain insurance terms in a warm, conversational manner. Keep responses short (1-3 lines) and maintain the exact same information while making it sound natural."
                ),
                HumanMessage(content=prompt),
            ]

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: self.llm.invoke(messages).content
            )
            return response.strip()
        except Exception as e:
            print(f"Error rewriting answer: {e}")
            return base_answer

    async def send_takaful_document(self, from_id: str, user_states: Dict):
        """Send the Takaful Emarat Silver document"""
        document_message = f"Here's the detailed brochure for Takaful Emarat Silver plan: {TAKAFUL_EMARAT_SILVER_DOCUMENT_URL}"
        send_whatsapp_message(from_id, document_message)
        store_interaction(
            from_id, "Takaful Document Sent", document_message, user_states
        )

        # After document, ask follow-up question
        await asyncio.sleep(2)
        await self.ask_followup_question(from_id, user_states)

    async def ask_followup_question(self, from_id: str, user_states: Dict):
        """Ask follow-up question with Yes/No options"""
        followup_message = "Is there anything else you want me to help you with related to Takaful Emarat Silver?"
        send_yes_no_options(from_id, followup_message, user_states)
        store_interaction(
            from_id, "Takaful Follow-up Question", followup_message, user_states
        )

        user_states[from_id]["stage"] = "takaful_emarat_silver_followup"

    async def generate_followup_question(self) -> str:
        """Generate AI-powered follow-up question"""
        try:
            from langchain.schema import HumanMessage, SystemMessage

            system_prompt = """You are Insura, a friendly insurance assistant. Generate a natural follow-up question after someone has asked about Takaful Emarat Silver and received information. 
            The question should encourage them to ask more questions or show interest in the plan. Make it conversational and helpful. Keep it under 80 words."""

            human_prompt = "Generate a follow-up question for someone who just asked about Takaful Emarat Silver plan"

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ]

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: self.llm.invoke(messages).content
            )
            return response.strip()
        except Exception as e:
            print(f"Error generating follow-up question: {e}")
            return "I'm all ears and here to help - what would you like to know about the Takaful Emarat Silver plan? Just ask away and I'll give you the most accurate info. Do you need to know anything else related Takaful Emarat Silver plan?"

    async def handle_followup_response(
        self,
        from_id: str,
        text: str,
        user_states: Dict,
        interactive_response: Optional[Dict] = None,
    ):
        """Handle user response to follow-up question with Yes/No options"""
        # Check for interactive response first (button click)
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes":
            # User clicked Yes - continue in Takaful flow
            await self.continue_takaful_conversation(from_id, user_states)
        elif selected_option == "No":
            # User clicked No - exit to original flow
            await self.exit_takaful_conversation(from_id, user_states)
        else:
            # Fallback to text-based detection
            continue_keywords = [
                "yes",
                "yeah",
                "yep",
                "sure",
                "ok",
                "okay",
                "more",
                "continue",
                "another",
            ]
            exit_keywords = [
                "no",
                "nope",
                "nah",
                "done",
                "finished",
                "that's all",
                "nothing else",
            ]

            text_lower = text.lower()

            if any(keyword in text_lower for keyword in continue_keywords):
                # User wants to continue
                await self.continue_takaful_conversation(from_id, user_states)
            elif any(keyword in text_lower for keyword in exit_keywords):
                # User wants to exit
                await self.exit_takaful_conversation(from_id, user_states)
            else:
                # Try to process as another question
                if not await self.process_takaful_question(from_id, text, user_states):
                    # If not a Takaful question, use LLM
                    from .llm import process_message_with_llm

                    await process_message_with_llm(
                        from_id=from_id, text=text, user_states=user_states
                    )
                    await asyncio.sleep(1)
                    await self.ask_followup_question(from_id, user_states)

    async def continue_takaful_conversation(self, from_id: str, user_states: Dict):
        """Continue the Takaful conversation"""
        continue_message = await self.generate_continue_message()
        send_whatsapp_message(from_id, continue_message)
        store_interaction(
            from_id, "Takaful Continue Message", continue_message, user_states
        )

        user_states[from_id]["stage"] = "takaful_emarat_silver_qa"

    async def generate_continue_message(self) -> str:
        """Generate continue message (matching website implementation)"""
        return "There's anything else Please ask, I am here to help you. related to Takaful Emarat Silver"

    async def exit_takaful_conversation(self, from_id: str, user_states: Dict):
        """Exit the Takaful conversation and return to main flow"""
        exit_message = "Thank you for your interest in Takaful Emarat Silver! If you have any more questions in the future, feel free to ask. Is there anything else I can help you with today?"
        send_whatsapp_message(from_id, exit_message)
        store_interaction(from_id, "Takaful Exit Message", exit_message, user_states)

        # Reset to main flow - clear Takaful flags and return to initial question stage
        user_states[from_id]["stage"] = "initial_question"
        user_states[from_id]["takaful_qa_count"] = 0
        user_states[from_id]["takaful_emarat_asked"] = False
        user_states[from_id]["awaiting_takaful_followup"] = False

        # Send the main menu options
        from .whatsapp import send_interactive_options
        from config.settings import INITIAL_QUESTIONS

        await asyncio.sleep(1)
        greeting_text = f"Great! {INITIAL_QUESTIONS[0]['question']}"
        send_interactive_options(
            from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states
        )


# Global instance
takaful_emarat_silver_flow = TakafulEmaratSilverFlow()
