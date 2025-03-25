import asyncio
import json
import time
from typing import Dict, Optional
from config.settings import INITIAL_QUESTIONS, MEDICAL_QUESTIONS
from .whatsapp import (
    send_whatsapp_message,
    send_interactive_options,
    send_yes_no_options
)
from utils.helpers import is_thank_you, store_interaction

async def process_conversation(
    from_id: str,
    text: str,
    user_states: Dict,
    profile_name: Optional[str] = None,
    interactive_response: Optional[Dict] = None
):
    if from_id not in user_states:
        user_states[from_id] = {
            "stage": "greeting",
            "name": profile_name,
            "responses": {},
            "question_index": 0,
            "selected_service": None,
            "conversation_history": [],
            "llm_conversation_count": 0
        }
    
    state = user_states[from_id]
    
    if state["stage"] == "waiting_for_new_query":
        selected_option = interactive_response.get("title") if interactive_response else None
        store_interaction(from_id, "Would you like assistance with anything else?", selected_option or text, user_states)
        
        if selected_option == "Yes" or text.lower() in ["yes", "yeah", "yep", "sure", "ok", "okay"]:
            user_states[from_id]["stage"] = "initial_question"
            user_states[from_id]["question_index"] = 0
            greeting_text = f"Great! {INITIAL_QUESTIONS[0]['question']}"
            send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states)
        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            thank_message = "Thank you for using our services. If you need assistance in the future, feel free to message us anytime!"
            send_whatsapp_message(from_id, thank_message)
            store_interaction(from_id, "User selected No for more assistance", thank_message, user_states)
            user_states[from_id]["stage"] = "ai_response"
            user_states[from_id]["llm_conversation_count"] = 0
            await asyncio.sleep(7)
            follow_up = "Feel free to ask me anything. I'm here to help!"
            send_whatsapp_message(from_id, follow_up)
            store_interaction(from_id, "Follow-up prompt", follow_up, user_states)
        else:
            from .llm import process_message_with_llm
            await process_message_with_llm( from_id=from_id, text=text, user_states=user_states)  # Note: LLM needs to be passed or initialized
            await asyncio.sleep(1)
            send_yes_no_options(from_id, "Would you like to purchase our insurance again?", user_states)
        return
    
    if state["stage"] == "ai_response":
        from .llm import process_message_with_llm
        await process_message_with_llm( from_id=from_id, text=text, user_states=user_states)  # Note: LLM needs to be passed or initialized
        user_states[from_id]["llm_conversation_count"] += 1
        if user_states[from_id]["llm_conversation_count"] >= 2:
            await asyncio.sleep(2)
            send_yes_no_options(from_id, "Would you like to purchase our insurance again?", user_states)
            user_states[from_id]["stage"] = "waiting_for_new_query"
            user_states[from_id]["llm_conversation_count"] = 0
        return
    
    if state["stage"] == "greeting":
        greeting = "Hi there! My name is Insura from Wehbe Insurance Broker, your AI insurance assistant. I will be happy to assist you with your insurance requirements."
        send_whatsapp_message(from_id, greeting)
        store_interaction(from_id, "Initial contact", greeting, user_states)
        await asyncio.sleep(1)
        if state["name"]:
            user_states[from_id]["stage"] = "initial_question"
            user_states[from_id]["responses"]["name"] = state["name"]
            greeting_text = f"Nice to meet you, {state['name']}! {INITIAL_QUESTIONS[0]['question']}"
            send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states)
        else:
            name_request = "Before we proceed, may I know your name please?"
            send_whatsapp_message(from_id, name_request)
            store_interaction(from_id, "Bot asked for name", name_request, user_states)
            user_states[from_id]["stage"] = "awaiting_name"
        return
    
    elif state["stage"] == "awaiting_name":
        name = text.strip()
        user_states[from_id]["name"] = name
        user_states[from_id]["responses"]["name"] = name
        store_interaction(from_id, "User provided name", f"Name received: {name}", user_states)
        user_states[from_id]["stage"] = "initial_question"
        greeting_text = f"Hi {name}, welcome to Insura! {INITIAL_QUESTIONS[0]['question']}"
        send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states)
        return
    
    elif state["stage"] == "initial_question":
        selected_option = interactive_response.get("title") if interactive_response else None
        if selected_option:
            user_states[from_id]["selected_service"] = selected_option
            user_states[from_id]["responses"]["service_type"] = selected_option
            store_interaction(from_id, INITIAL_QUESTIONS[0]["question"], f"Selected: {selected_option}", user_states)
            if "Medical Insurance" in selected_option:
                user_states[from_id]["stage"] = "medical_flow"
                user_states[from_id]["question_index"] = 0
                question = MEDICAL_QUESTIONS[0]["question"]
                options = MEDICAL_QUESTIONS[0]["options"]
                send_interactive_options(from_id, question, options, user_states)
            elif "Motor Insurance" in selected_option:
                user_states[from_id]["stage"] = "motor_insurance_flow"
                motor_intro = "Great! I see you're interested in Motor Insurance. Let me help you with that."
                send_whatsapp_message(from_id, motor_intro)
                store_interaction(from_id, "Service selection", motor_intro, user_states)
                await asyncio.sleep(1)
                vehicle_question = "What is the year, make and model of your vehicle?"
                send_whatsapp_message(from_id, vehicle_question)
                store_interaction(from_id, "Bot asked about vehicle", vehicle_question, user_states)
            elif "Claim" in selected_option:
                user_states[from_id]["stage"] = "claim_flow"
                claim_intro = "I understand you want to file a claim. I'll guide you through the process."
                send_whatsapp_message(from_id, claim_intro)
                store_interaction(from_id, "Service selection", claim_intro, user_states)
                await asyncio.sleep(1)
                claim_question = "What type of insurance policy are you filing a claim for? (Medical or Motor)"
                send_whatsapp_message(from_id, claim_question)
                store_interaction(from_id, "Bot asked about claim type", claim_question, user_states)
        else:
            from .llm import process_message_with_llm
            await process_message_with_llm(from_id=from_id, text=text, user_states=user_states)  # Note: LLM needs to be passed or initialized
            await asyncio.sleep(1)
            greeting_text = f"To continue with our guided assistance, please select one of the following options:"
            send_interactive_options(from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states)
        return
    
    elif state["stage"] == "medical_flow":
        question_index = state["question_index"]
        if question_index < len(MEDICAL_QUESTIONS):
            current_question = MEDICAL_QUESTIONS[question_index]["question"]
            response_value = interactive_response.get("title") if interactive_response else None
            if response_value:
                key = f"medical_q{question_index+1}"
                user_states[from_id]["responses"][key] = response_value
                store_interaction(from_id, current_question, f"Selected: {response_value}", user_states)
                q_key = f"medical_question{question_index+1}"
                user_states[from_id]["responses"][q_key] = current_question
                user_states[from_id]["question_index"] = question_index + 1
                if question_index + 1 < len(MEDICAL_QUESTIONS):
                    next_question = MEDICAL_QUESTIONS[question_index + 1]
                    send_interactive_options(from_id, next_question["question"], next_question["options"], user_states)
                elif question_index + 1 == len(MEDICAL_QUESTIONS):
                    salary_question = "Could you please tell me your monthly salary?"
                    send_whatsapp_message(from_id, salary_question)
                    store_interaction(from_id, "Bot asked about salary", salary_question, user_states)
                    user_states[from_id]["responses"]["medical_question_salary"] = salary_question
            else:
                from .llm import process_message_with_llm
                await process_message_with_llm(from_id=from_id, text=text, user_states=user_states)  # Note: LLM needs to be passed or initialized
                await asyncio.sleep(1)
                send_interactive_options(from_id, current_question, MEDICAL_QUESTIONS[question_index]["options"], user_states)
            return
        elif question_index == len(MEDICAL_QUESTIONS):
            salary_response = text.strip()
            user_states[from_id]["responses"]["monthly_salary"] = salary_response
            store_interaction(from_id, "Salary question", f"Response: {salary_response}", user_states)
            user_states[from_id]["stage"] = "completed"
            user_json = json.dumps(user_states[from_id]["responses"], indent=2)
            print(f"User data collected for {from_id}: {user_json}")
            thanks = "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry"
            send_whatsapp_message(from_id, thanks)
            store_interaction(from_id, "Completion confirmation", thanks, user_states)
            await asyncio.sleep(1)
            send_yes_no_options(from_id, "Would you like to purchase our insurance again?", user_states)
            user_states[from_id]["stage"] = "waiting_for_new_query"
            return
       
    # Handle Motor Insurance flow
    elif state["stage"] == "motor_insurance_flow":
        # Store vehicle information
        vehicle_info = text.strip()
        user_states[from_id]["responses"]["vehicle_info"] = vehicle_info
        store_interaction(from_id, "What is the year, make and model of your vehicle?", f"Response: {vehicle_info}",user_states)
        user_states[from_id]["responses"]["motor_question_vehicle"] = "What is the year, make and model of your vehicle?"
        
        user_states[from_id]["stage"] = "motor_insurance_driver"
        driving_question = "Thank you. How many years have you been driving?"
        send_whatsapp_message(from_id, driving_question)
        store_interaction(from_id, "Bot asked about driving experience", driving_question,user_states)
        user_states[from_id]["responses"]["motor_question_driving"] = driving_question
        return
        
    # Motor Insurance flow - driving experience
    elif state["stage"] == "motor_insurance_driver":
        driving_exp = text.strip()
        user_states[from_id]["responses"]["driving_experience"] = driving_exp
        store_interaction(from_id, "Driving experience question", f"Response: {driving_exp}",user_states)
        
        user_states[from_id]["stage"] = "motor_insurance_coverage"
        coverage_question = "What type of coverage are you looking for? (Comprehensive, Third Party Only, etc.)"
        send_whatsapp_message(from_id, coverage_question)
        store_interaction(from_id, "Bot asked about coverage", coverage_question,user_states)
        user_states[from_id]["responses"]["motor_question_coverage"] = coverage_question
        return
        
    # Motor Insurance flow - coverage type
    elif state["stage"] == "motor_insurance_coverage":
        coverage_type = text.strip()
        user_states[from_id]["responses"]["desired_coverage"] = coverage_type
        store_interaction(from_id, "Coverage type question", f"Response: {coverage_type}",user_states)
        
        user_states[from_id]["stage"] = "motor_insurance_contact"
        contact_question = "Thank you for providing that information. What's your phone number and preferred contact time?"
        send_whatsapp_message(from_id, contact_question)
        store_interaction(from_id, "Bot asked for contact details", contact_question)
        user_states[from_id]["responses"]["motor_question_contact"] = contact_question
        return
        
    # Motor Insurance flow - contact info and completion
    elif state["stage"] == "motor_insurance_contact":
        contact_info = text.strip()
        user_states[from_id]["responses"]["contact_info"] = contact_info
        store_interaction(from_id, "Contact info question", f"Response: {contact_info}")
        user_states[from_id]["stage"] = "completed"
        
        # Create a summary JSON of the user's responses
        user_json = json.dumps(user_states[from_id]["responses"], indent=2)
        print(f"User data collected for {from_id}: {user_json}")
        
        # Send confirmation to user
        confirmation1 = "Perfect! I've collected all the information we need for your Motor Insurance quote."
        send_whatsapp_message(from_id, confirmation1)
        store_interaction(from_id, "Completion confirmation", confirmation1)
        
        await asyncio.sleep(1)
        confirmation2 = "Our insurance specialist will contact you at your preferred time to discuss your options."
        send_whatsapp_message(from_id, confirmation2)
        store_interaction(from_id, "Next steps", confirmation2)
        
        await asyncio.sleep(1)
        send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
        user_states[from_id]["stage"] = "waiting_for_new_query"
        return
        
    # Handle Claim flow
    elif state["stage"] == "claim_flow":
        # Store claim type
        claim_type = text.strip()
        user_states[from_id]["responses"]["claim_type"] = claim_type
        store_interaction(from_id, "What type of insurance policy are you filing a claim for?", f"Response: {claim_type}")
        user_states[from_id]["responses"]["claim_question_type"] = "What type of insurance policy are you filing a claim for?"
        
        user_states[from_id]["stage"] = "claim_policy"
        policy_question = "Thank you. What is your policy number?"
        send_whatsapp_message(from_id, policy_question)
        store_interaction(from_id, "Bot asked for policy number", policy_question)
        user_states[from_id]["responses"]["claim_question_policy"] = policy_question
        return
        
    # Claim flow - policy number
    elif state["stage"] == "claim_policy":
        policy_number = text.strip()
        user_states[from_id]["responses"]["policy_number"] = policy_number
        store_interaction(from_id, "Policy number question", f"Response: {policy_number}")
        
        user_states[from_id]["stage"] = "claim_details"
        details_question = "Please briefly describe the incident for which you are filing a claim:"
        send_whatsapp_message(from_id, details_question)
        store_interaction(from_id, "Bot asked for incident details", details_question)
        user_states[from_id]["responses"]["claim_question_details"] = details_question
        return
        
    # Claim flow - incident details
    elif state["stage"] == "claim_details":
        incident_details = text.strip()
        user_states[from_id]["responses"]["incident_details"] = incident_details
        store_interaction(from_id, "Incident details question", f"Response: {incident_details}")
        
        user_states[from_id]["stage"] = "claim_date"
        date_question = "When did the incident occur? (Please provide the date)"
        send_whatsapp_message(from_id, date_question)
        store_interaction(from_id, "Bot asked for incident date", date_question)
        user_states[from_id]["responses"]["claim_question_date"] = date_question
        return
        
    # Claim flow - incident date and completion
    elif state["stage"] == "claim_date":
        incident_date = text.strip()
        user_states[from_id]["responses"]["incident_date"] = incident_date
        store_interaction(from_id, "Incident date question", f"Response: {incident_date}")
        user_states[from_id]["stage"] = "completed"
        
        # Create a summary JSON of the user's responses
        user_json = json.dumps(user_states[from_id]["responses"], indent=2)
        print(f"User data collected for {from_id}: {user_json}")
        
        # Send confirmation to user
        confirmation1 = "Thank you for providing the claim information."
        send_whatsapp_message(from_id, confirmation1)
        time.sleep(1)
        confirmation2 = "A claims specialist will contact you within 24 hours to process your claim and guide you through the next steps."
        send_whatsapp_message(from_id, confirmation2)
        time.sleep(1)
        send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
        user_states[from_id]["stage"] = "waiting_for_new_query"
        return

    # Add other stages (motor_insurance_flow, claim_flow, etc.) similarly...