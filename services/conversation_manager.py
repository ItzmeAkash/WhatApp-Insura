import asyncio
import json
import time
from typing import Dict, Optional

import requests
from config.settings import (
    INITIAL_QUESTIONS,
    MEDICAL_QUESTIONS,
    COMPANY_NUMBER_MAPPING,
    EMAF_INSURANCE_COMPANIES,
)
from .whatsapp import (
    send_whatsapp_message,
    send_interactive_options,
    send_yes_no_options,
)
from utils.helpers import emaf_document, is_thank_you, store_interaction
from .takaful_emarat_silver import takaful_emarat_silver_flow


async def process_conversation(
    from_id: str,
    text: str,
    user_states: Dict,
    profile_name: Optional[str] = None,
    interactive_response: Optional[Dict] = None,
):
    if from_id not in user_states:
        user_states[from_id] = {
            "stage": "greeting",
            "name": profile_name,
            "responses": {},
            "question_index": 0,
            "selected_service": None,
            "conversation_history": [],
            "llm_conversation_count": 0,
        }
    fields_to_verify = [
        "name",
        "id_number",
        "date_of_birth",
        "nationality",
        "issue_date",
        "expiry_date",
        "gender",
        "card_number",
        "occupation",
        "employer",
        "issuing_place",
    ]

    state = user_states[from_id]

    # Check for Takaful Emarat Silver trigger first
    if takaful_emarat_silver_flow.detect_takaful_emarat_silver_trigger(text):
        await takaful_emarat_silver_flow.start_takaful_emarat_silver_flow(
            from_id, user_states
        )
        return

    # Handle Takaful Emarat Silver Q&A flow
    if state["stage"] == "takaful_emarat_silver_qa":
        if await takaful_emarat_silver_flow.process_takaful_question(
            from_id, text, user_states
        ):
            return
        else:
            # If not a Takaful question, use LLM
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            await takaful_emarat_silver_flow.ask_followup_question(from_id, user_states)
            return

    # Handle Takaful Emarat Silver follow-up responses
    if state["stage"] == "takaful_emarat_silver_followup":
        await takaful_emarat_silver_flow.handle_followup_response(
            from_id, text, user_states, interactive_response
        )
        return

    # Check for other Takaful questions (only if Takaful Emarat Silver was asked first)
    if state.get("takaful_emarat_asked", False):
        if await takaful_emarat_silver_flow.process_takaful_question(
            from_id, text, user_states
        ):
            return

    if (
        "emaf" in text.lower()
        or "emf" in text.lower()
        and state["stage"] not in ["emaf_name", "emaf_phone", "emaf_company"]
    ):
        user_states[from_id]["stage"] = "emaf_name"
        name_request = "May I know your name, please?"
        send_whatsapp_message(from_id, name_request)
        store_interaction(
            from_id, "Bot asked for name (EMAF)", name_request, user_states
        )
        return
    if state["stage"] == "emaf_name":
        name = text.strip()
        user_states[from_id]["responses"]["May I know your name, please?"] = name
        store_interaction(
            from_id, "User provided name (EMAF)", f"Name received: {name}", user_states
        )
        user_states[from_id]["stage"] = "emaf_phone"
        phone_request = "May I kindly ask for your phone number, please?"
        send_whatsapp_message(from_id, phone_request)
        store_interaction(
            from_id, "Bot asked for phone number (EMAF)", phone_request, user_states
        )
        return

    # EMAF Flow: Awaiting Phone Number
    if state["stage"] == "emaf_phone":
        phone = text.strip()
        user_states[from_id]["responses"][
            "May I kindly ask for your phone number, please?"
        ] = phone
        store_interaction(
            from_id,
            "User provided phone number (EMAF)",
            f"Phone received: {phone}",
            user_states,
        )
        user_states[from_id]["stage"] = "emaf_company"
        company_request = (
            "Could you kindly confirm the name of your insurance company, please?"
        )
        send_interactive_options(
            from_id,
            company_request,
            EMAF_INSURANCE_COMPANIES[0]["options"],
            user_states,
        )
        store_interaction(
            from_id,
            "Bot asked for insurance company (EMAF)",
            company_request,
            user_states,
        )

        return

    # EMAF Flow: Awaiting Insurance Company Selection
    if state["stage"] == "emaf_company":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        # In services/conversation_manager.py, within the "emaf_company" elif block
        if selected_option in COMPANY_NUMBER_MAPPING:
            company_id = COMPANY_NUMBER_MAPPING[selected_option]
            user_states[from_id]["responses"]["emaf_company_id"] = company_id
            store_interaction(
                from_id,
                "User selected insurance company (EMAF)",
                f"Selected: {selected_option} (ID: {company_id})",
                user_states,
            )

            # Call emaf_document with the responses dictionary
            emaf_id = emaf_document(user_states[from_id]["responses"])
            if emaf_id:
                url = f"https://www.insuranceclub.ae/medical_form/view/{emaf_id}"
                send_whatsapp_message(
                    from_id,
                    f"Thank you for sharing the details. Please find the link below to view your emaf document: {url}",
                )
                store_interaction(from_id, "EMAF URL provided", url, user_states)
            else:
                send_whatsapp_message(
                    from_id,
                    "Sorry, there was an issue generating your link. Please try again later.",
                )
                store_interaction(
                    from_id, "EMAF URL generation failed", "Error", user_states
                )

            user_states[from_id]["stage"] = "waiting_for_new_query"
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_interactive_options(
                from_id,
                "Could you kindly confirm the name of your insurance company, please?",
                EMAF_INSURANCE_COMPANIES,
                user_states,
            )
        return

    if state["stage"] == "waiting_for_new_query":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        store_interaction(
            from_id,
            "Would you like assistance with anything else?",
            selected_option or text,
            user_states,
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            user_states[from_id]["stage"] = "initial_question"
            user_states[from_id]["question_index"] = 0
            greeting_text = f"Great! {INITIAL_QUESTIONS[0]['question']}"
            send_interactive_options(
                from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states
            )
        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            thank_message = "Thank you for using our services. If you need assistance in the future, feel free to message us anytime!"
            send_whatsapp_message(from_id, thank_message)
            store_interaction(
                from_id,
                "User selected No for more assistance",
                thank_message,
                user_states,
            )
            user_states[from_id]["stage"] = "ai_response"
            user_states[from_id]["llm_conversation_count"] = 0
            await asyncio.sleep(7)
            follow_up = "Feel free to ask me anything. I'm here to help!"
            send_whatsapp_message(from_id, follow_up)
            store_interaction(from_id, "Follow-up prompt", follow_up, user_states)
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )
        return

    if state["stage"] == "ai_response":
        from .llm import process_message_with_llm

        await process_message_with_llm(
            from_id=from_id, text=text, user_states=user_states
        )
        user_states[from_id]["llm_conversation_count"] += 1
        if user_states[from_id]["llm_conversation_count"] >= 2:
            await asyncio.sleep(2)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )
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
            greeting_text = (
                f"Nice to meet you, {state['name']}! {INITIAL_QUESTIONS[0]['question']}"
            )
            send_interactive_options(
                from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states
            )
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
        store_interaction(
            from_id, "User provided name", f"Name received: {name}", user_states
        )
        user_states[from_id]["stage"] = "initial_question"
        greeting_text = (
            f"Hi {name}, welcome to Insura! {INITIAL_QUESTIONS[0]['question']}"
        )
        send_interactive_options(
            from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states
        )
        return

    elif state["stage"] == "initial_question":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        if selected_option:
            user_states[from_id]["selected_service"] = selected_option
            user_states[from_id]["responses"]["service_type"] = selected_option
            store_interaction(
                from_id,
                INITIAL_QUESTIONS[0]["question"],
                f"Selected: {selected_option}",
                user_states,
            )

            if "Medical Insurance" in selected_option:
                state["service_type"] = selected_option
                user_states[from_id]["stage"] = "medical_flow"
                user_states[from_id]["question_index"] = 0
                question = MEDICAL_QUESTIONS[0]["question"]
                options = MEDICAL_QUESTIONS[0]["options"]
                send_interactive_options(from_id, question, options, user_states)
                user_states[from_id] = state

            elif "Motor Insurance" in selected_option:
                state["service_type"] = selected_option
                user_states[from_id]["stage"] = "motor_insurance_vehicle_type"
                vehicle_type_question = "What would you like to do today?"
                send_interactive_options(
                    from_id,
                    vehicle_type_question,
                    ["Car Insurance", "Bike Insurance"],
                    user_states,
                )
                store_interaction(
                    from_id,
                    "Bot asked about vehicle type",
                    vehicle_type_question,
                    user_states,
                )
                user_states[from_id] = state

            elif "Claim" in selected_option:
                user_states[from_id]["stage"] = "claim_flow"
                claim_intro = "I understand you want to file a claim. I'll guide you through the process."
                send_whatsapp_message(from_id, claim_intro)
                store_interaction(
                    from_id, "Service selection", claim_intro, user_states
                )
                await asyncio.sleep(1)
                claim_question = "What type of insurance policy are you filing a claim for? (Medical or Motor)"
                send_whatsapp_message(from_id, claim_question)
                store_interaction(
                    from_id, "Bot asked about claim type", claim_question, user_states
                )
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            greeting_text = f"To continue with our guided assistance, please select one of the following options:"
            send_interactive_options(
                from_id, greeting_text, INITIAL_QUESTIONS[0]["options"], user_states
            )
        return

    elif state["stage"] == "motor_insurance_vehicle_type":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option in ["Car Insurance", "Bike Insurance"]:
            vehicle_type = selected_option
            user_states[from_id]["responses"]["vehicle_type"] = vehicle_type
            store_interaction(
                from_id,
                "Vehicle type selection",
                f"Selected: {vehicle_type}",
                user_states,
            )

            if vehicle_type == "Car Insurance":
                user_states[from_id]["stage"] = "motor_registration_city"
                registration_question = "Great choice! Let's start with your motor insurance details. Select the city of registration:"

                emirate_options = [
                    "Abudhabi",
                    "Ajman",
                    "Dubai",
                    "Fujairah",
                    "Ras Al Khaimah",
                    "Sharjah",
                    "Umm Al Quwain",
                ]

                send_interactive_options(
                    from_id, registration_question, emirate_options, user_states
                )
                store_interaction(
                    from_id,
                    "Bot asked about registration city",
                    registration_question,
                    user_states,
                )

            else:  # Bike
                user_states[from_id]["stage"] = "motor_bike_registration_city"
                registration_question = "Great choice! Let's start with your motor insurance details. Select the city of registration:"

                emirate_options = [
                    "Abudhabi",
                    "Ajman",
                    "Dubai",
                    "Fujairah",
                    "Ras Al Khaimah",
                    "Sharjah",
                    "Umm Al Quwain",
                ]

                send_interactive_options(
                    from_id, registration_question, emirate_options, user_states
                )
                store_interaction(
                    from_id,
                    "Bot asked about registration city",
                    registration_question,
                    user_states,
                )
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            vehicle_type_question = "What would you like to do today?"
            send_interactive_options(
                from_id,
                vehicle_type_question,
                ["Car Insurance", "Bike Insurance"],
                user_states,
            )
        return

    elif state["stage"] == "medical_flow":
        question_index = state["question_index"]
        if question_index < len(MEDICAL_QUESTIONS):
            current_question = MEDICAL_QUESTIONS[question_index]["question"]
            response_value = (
                interactive_response.get("title") if interactive_response else None
            )
            if response_value:
                key = f"medical_q{question_index + 1}"
                user_states[from_id]["responses"][key] = response_value
                store_interaction(
                    from_id,
                    current_question,
                    f"Selected: {response_value}",
                    user_states,
                )
                q_key = f"medical_question{question_index + 1}"
                user_states[from_id]["responses"][q_key] = current_question
                user_states[from_id]["question_index"] = question_index + 1
                if question_index + 1 < len(MEDICAL_QUESTIONS):
                    next_question = MEDICAL_QUESTIONS[question_index + 1]
                    send_interactive_options(
                        from_id,
                        next_question["question"],
                        next_question["options"],
                        user_states,
                    )
                elif question_index + 1 == len(MEDICAL_QUESTIONS):
                    salary_question = "Thank you. Now, let's move on to: Could you please tell me your monthly salary?"
                    send_whatsapp_message(from_id, salary_question)
                    store_interaction(
                        from_id, "Bot asked about salary", salary_question, user_states
                    )
                    user_states[from_id]["responses"]["medical_question_salary"] = (
                        salary_question
                    )
            else:
                from .llm import process_message_with_llm

                await process_message_with_llm(
                    from_id=from_id, text=text, user_states=user_states
                )  # Note: LLM needs to be passed or initialized
                await asyncio.sleep(1)
                send_interactive_options(
                    from_id,
                    current_question,
                    MEDICAL_QUESTIONS[question_index]["options"],
                    user_states,
                )
            return
        elif question_index == len(MEDICAL_QUESTIONS):
            # Handle salary response and move to sponsor phone
            salary_response = text.strip()
            user_states[from_id]["responses"]["monthly_salary"] = salary_response
            store_interaction(
                from_id, "Salary question", f"Response: {salary_response}", user_states
            )

            sponsor_phone_question = "Thank you for providing your salary.Now let's move on to: May I have the sponsor's mobile number, please?"
            send_whatsapp_message(from_id, sponsor_phone_question)
            store_interaction(
                from_id,
                "Bot asked for sponsor's phone",
                sponsor_phone_question,
                user_states,
            )
            user_states[from_id]["responses"]["medical_question_sponsor_phone"] = (
                sponsor_phone_question
            )
            user_states[from_id]["stage"] = "medical_sponsor_phone"
            return
        elif question_index == len(MEDICAL_QUESTIONS):
            salary_response = text.strip()
            user_states[from_id]["responses"]["monthly_salary"] = salary_response
            store_interaction(
                from_id, "Salary question", f"Response: {salary_response}", user_states
            )
            user_states[from_id]["stage"] = "completed"
            user_json = json.dumps(user_states[from_id]["responses"], indent=2)
            print(f"User data collected for {from_id}: {user_json}")
            thanks = "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry"
            send_whatsapp_message(from_id, thanks)
            store_interaction(from_id, "Completion confirmation", thanks, user_states)
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )
            user_states[from_id]["stage"] = "waiting_for_new_query"
            return
    # New stage for sponsor phone
    elif state["stage"] == "medical_sponsor_phone":
        sponsor_phone = text.strip()
        # Basic phone number validation (adjust regex as needed)
        import re

        phone_pattern = re.compile(
            r"^\+?\d{9,15}$"
        )  # Accepts 9-15 digits with optional +

        if phone_pattern.match(sponsor_phone):
            user_states[from_id]["responses"]["sponsor_phone"] = sponsor_phone
            store_interaction(
                from_id,
                "Sponsor phone question",
                f"Response: {sponsor_phone}",
                user_states,
            )

            sponsor_email_question = "Thank you for providing the mobile number. Now, let's move on to: May I have the sponsor's Email Address, please?"
            send_whatsapp_message(from_id, sponsor_email_question)
            store_interaction(
                from_id,
                "Bot asked for sponsor's email",
                sponsor_email_question,
                user_states,
            )
            user_states[from_id]["responses"]["medical_question_sponsor_email"] = (
                sponsor_email_question
            )
            user_states[from_id]["stage"] = "medical_sponsor_email"
        else:
            error_message = "Please provide a valid phone number (e.g., +971501234567 or 0501234567)"
            send_whatsapp_message(from_id, error_message)
            store_interaction(
                from_id, "Invalid phone number", error_message, user_states
            )
            await asyncio.sleep(1)
            sponsor_phone_question = "May I have the sponsor's mobile number, please?"
            send_whatsapp_message(from_id, sponsor_phone_question)
            store_interaction(
                from_id,
                "Bot re-asked for sponsor's phone",
                sponsor_phone_question,
                user_states,
            )
        return

    # New stage for sponsor email
    elif state["stage"] == "medical_sponsor_email":
        sponsor_email = text.strip()
        # Basic email validation
        import re

        email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        if email_pattern.match(sponsor_email):
            user_states[from_id]["responses"]["sponsor_email"] = sponsor_email
            store_interaction(
                from_id,
                "Sponsor email question",
                f"Response: {sponsor_email}",
                user_states,
            )

            member_question = "Thank you for providing the sponsor's email. Now,let's move on to:Next, we need the details of the member. Would you like to upload their Emirates ID or manually enter the information?"
            send_yes_no_options(from_id, member_question, user_states)
            store_interaction(
                from_id,
                "Bot asked about member details method",
                member_question,
                user_states,
            )
            user_states[from_id]["stage"] = "medical_member_input_method"
            # user_json = json.dumps(user_states[from_id]["responses"], indent=2)
            # print(f"User data collected for {from_id}: {user_json}")

        else:
            error_message = (
                "Please provide a valid email address (e.g., example@email.com)"
            )
            send_whatsapp_message(from_id, error_message)
            store_interaction(from_id, "Invalid email", error_message, user_states)
            await asyncio.sleep(1)
            sponsor_email_question = "May I have the sponsor's Email Address, please?"
            send_whatsapp_message(from_id, sponsor_email_question)
            store_interaction(
                from_id,
                "Bot re-asked for sponsor's email",
                sponsor_email_question,
                user_states,
            )
        return
    elif state["stage"] == "medical_member_input_method":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        if selected_option == "Yes":
            upload_question = "Please Upload Your Document"
            send_whatsapp_message(from_id, upload_question)
            store_interaction(
                from_id, "Bot requested document upload", upload_question, user_states
            )
            user_states[from_id]["stage"] = "medical_upload_document"
        elif selected_option == "No":
            name_question = "Next, we need the details of the member for whom the policy is being purchased. Please provide Name"
            send_whatsapp_message(from_id, name_question)
            store_interaction(
                from_id, "Bot asked for member name", name_question, user_states
            )
            user_states[from_id]["responses"]["medical_question_member_name"] = (
                name_question
            )
            user_states[from_id]["stage"] = "medical_member_name"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            member_question = "Next, we need the details of the member. Would you like to upload their Emirates ID or manually enter the information?"
            send_yes_no_options(from_id, member_question, user_states)
        return
    # New stage for document upload
    elif state["stage"] == "medical_upload_document":
        # This stage acts as a waiting state; actual document processing is handled by the webhook
        send_whatsapp_message(
            from_id,
            "Thank you for uploading your document. I'm processing it now, please wait a moment...",
        )
        store_interaction(
            from_id, "Document upload received", "Processing started", user_states
        )
        # No further action here; the webhook will handle the document and transition to verification
        return

    elif state["stage"] == "medical_member_dob":
        member_dob = text.strip()
        user_states[from_id]["responses"]["member_dob"] = member_dob
        store_interaction(
            from_id, "Member DOB question", f"Response: {member_dob}", user_states
        )

        gender_question = f"Thanks!Lets's continue.Please confirm the gender of {user_states[from_id]['responses']['member_name']}"
        send_interactive_options(
            from_id, gender_question, ["Male", "Female"], user_states
        )
        store_interaction(
            from_id, "Bot asked for member gender", gender_question, user_states
        )
        user_states[from_id]["responses"]["medical_question_member_gender"] = (
            gender_question
        )
        user_states[from_id]["stage"] = "medical_member_gender"
        return

    elif state["stage"] == "medical_member_gender":
        selected_gender = (
            interactive_response.get("title") if interactive_response else None
        )
        if selected_gender in ["Male", "Female"]:
            user_states[from_id]["responses"]["member_gender"] = selected_gender
            store_interaction(
                from_id,
                "Member gender question",
                f"Selected: {selected_gender}",
                user_states,
            )

            marital_question = f"Please Confirm the marital status of {user_states[from_id]['responses']['member_name']}"
            send_interactive_options(
                from_id, marital_question, ["Single", "Married"], user_states
            )
            store_interaction(
                from_id, "Bot asked for marital status", marital_question, user_states
            )
            user_states[from_id]["responses"]["medical_question_marital_status"] = (
                marital_question
            )
            user_states[from_id]["stage"] = "medical_marital_status"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            gender_question = f"Please confirm the gender of {user_states[from_id]['responses']['member_name']}"
            send_interactive_options(
                from_id, gender_question, ["Male", "Female"], user_states
            )
        return

    # New stage for marital status
    elif state["stage"] == "medical_marital_status":
        selected_marital = (
            interactive_response.get("title") if interactive_response else None
        )
        if selected_marital in ["Single", "Married"]:
            user_states[from_id]["responses"]["marital_status"] = selected_marital
            store_interaction(
                from_id,
                "Marital status question",
                f"Selected: {selected_marital}",
                user_states,
            )

            relationship_question = f"Thank you Next,let's discuss.Could you kindly share your {user_states[from_id]['responses']['member_name']} relationship with the sponsor?"
            send_interactive_options(
                from_id,
                relationship_question,
                [
                    "Investor",
                    "Employee",
                    "Spouse",
                    "Child",
                    "4th Child",
                    "Parent",
                    "Domestic",
                ],
                user_states,
            )
            store_interaction(
                from_id,
                "Bot asked for relationship",
                relationship_question,
                user_states,
            )
            user_states[from_id]["responses"]["medical_question_relationship"] = (
                relationship_question
            )
            user_states[from_id]["stage"] = "medical_relationship"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            marital_question = f"Please Confirm the marital status of {user_states[from_id]['name'] or 'the member'}"
            send_interactive_options(
                from_id, marital_question, ["Single", "Married"], user_states
            )
        return

    # New stage for relationship
    elif state["stage"] == "medical_relationship":
        selected_relationship = (
            interactive_response.get("title") if interactive_response else None
        )
        valid_relationships = [
            "Investor",
            "Employee",
            "Spouse",
            "Child",
            "4th Child",
            "Parent",
            "Domestic",
        ]
        if selected_relationship in valid_relationships:
            user_states[from_id]["responses"]["relationship_with_sponsor"] = (
                selected_relationship
            )
            store_interaction(
                from_id,
                "Relationship question",
                f"Selected: {selected_relationship}",
                user_states,
            )

            advisor_question = "Thank you for providing the relationship.let's proceed with: Do you have an Insurance Advisor code?"
            send_yes_no_options(from_id, advisor_question, user_states)
            store_interaction(
                from_id, "Bot asked for advisor code", advisor_question, user_states
            )
            user_states[from_id]["responses"]["medical_question_advisor_code"] = (
                advisor_question
            )
            user_states[from_id]["stage"] = "medical_advisor_code"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            relationship_question = (
                "Could you kindly share your relationship with the sponsor?"
            )
            send_interactive_options(
                from_id, relationship_question, valid_relationships, user_states
            )
        return

    # New stage for advisor code
    elif state["stage"] == "medical_advisor_code":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        if selected_option == "Yes":
            code_question = "Thank you for the responses! Now,Please enter your Insurance Advisor code for assigning your enquiry for further assistance"
            send_whatsapp_message(from_id, code_question)
            store_interaction(
                from_id,
                "Bot asked for advisor code details",
                code_question,
                user_states,
            )
            user_states[from_id]["responses"][
                "medical_question_advisor_code_details"
            ] = code_question
            user_states[from_id]["stage"] = "medical_advisor_code_details"
        elif selected_option == "No":
            user_states[from_id]["responses"]["has_advisor_code"] = "No"
            store_interaction(
                from_id, "Advisor code question", "Selected: No", user_states
            )

            user_states[from_id]["stage"] = "completed"
            user_json = json.dumps(user_states[from_id]["responses"], indent=2)
            print(f"User data collected for {from_id}: {user_json}")

            thanks = "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry"
            send_whatsapp_message(from_id, thanks)
            store_interaction(from_id, "Completion confirmation", thanks, user_states)
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )
            user_states[from_id]["stage"] = "waiting_for_new_query"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            advisor_question = "Do you have an Insurance Advisor code?"
            send_yes_no_options(from_id, advisor_question, user_states)
        return

    # New stage for advisor code details
    elif state["stage"] == "medical_advisor_code_details":
        advisor_code = text.strip()
        # Validate that the advisor code is exactly 4 digits
        if advisor_code.isdigit() and len(advisor_code) == 4:
            user_states[from_id]["responses"]["advisor_code"] = advisor_code
            user_states[from_id]["responses"]["has_advisor_code"] = "Yes"
            store_interaction(
                from_id,
                "Advisor code details",
                f"Response: {advisor_code}",
                user_states,
            )

            # Construct the payload with all collected responses
            responses_dict = user_states[from_id]["responses"]
            print(responses_dict)

            def convert_gender(gender_str):
                gender_str = gender_str.lower()
                if gender_str in ["m", "male"]:
                    return "Male"
                elif gender_str in ["f", "female"]:
                    return "Female"
                return gender_str

            payload = {
                "visa_issued_emirates": responses_dict.get(
                    "medical_q1", ""
                ).capitalize(),
                "plan": responses_dict.get("medical_q2", "").capitalize(),
                "monthly_salary": responses_dict.get("monthly_salary", ""),
                "sponsor_type": responses_dict.get("medical_q3", "").capitalize(),
                "sponsor_mobile": responses_dict.get("sponsor_phone", ""),
                "sponsor_email": responses_dict.get("sponsor_email", "").lower(),
                "members": [
                    {
                        "name": responses_dict.get("member_name", "").capitalize(),
                        "dob": responses_dict.get(
                            "member_dob", ""
                        ),  # Assuming date format is handled elsewhere or as-is
                        "gender": convert_gender(
                            responses_dict.get("member_gender", "")
                        ),
                        "marital_status": responses_dict.get("marital_status", ""),
                        "relation": responses_dict.get(
                            "relationship_with_sponsor", ""
                        ).capitalize(),
                    }
                ],
            }
            print(payload)
            # API call to medical_insert
            api = "https://www.insuranceclub.ae/Api/medical_insert"
            try:
                res = requests.post(api, json=payload, timeout=10)
                res.raise_for_status()
                medical_detail_response = res.json()["id"]
                print(f"Payload sent: {json.dumps(payload, indent=2)}")
                print(f"API response ID: {medical_detail_response}")

                # Check if response is an integer ID and send the link
                if isinstance(medical_detail_response, int):
                    link = f"https://insuranceclub.ae/customer_plan/{medical_detail_response}"
                    thanks = f"Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry. Please find the link below to view your quotation: {link}"
                    send_whatsapp_message(from_id, thanks)
                    store_interaction(
                        from_id,
                        "Completion confirmation with link",
                        thanks,
                        user_states,
                    )

                    # Add a delay before sending the review request
                    await asyncio.sleep(2)

                    # Send the review request with a clickable button
                    from .whatsapp import send_link_button

                    review_link = "https://www.google.com/search?client=ms-android-samsung-ss&sca_esv=4eb717e6f42bf628&sxsrf=AHTn8zprabdPVFL3C2gXo4guY8besI3jqQ:1744004771562&q=wehbe+insurance+services+llc+reviews&uds=ABqPDvy-z0dcsfm2PY76_gjn-YWou9-AAVQ4iWjuLR6vmDV0vf3KpBMNjU5ZkaHGmSY0wBrWI3xO9O55WuDmXbDq6a3SqlwKf2NJ5xQAjebIw44UNEU3t4CpFvpLt9qFPlVh2F8Gfv8sMuXXSo2Qq0M_ZzbXbg2c323G_bE4tVi7Ue7d_sW0CrnycpJ1CvV-OyrWryZw_TeQ3gLGDgzUuHD04MpSHquYZaSQ0_mIHLWjnu7fu8c7nb6_aGDb_H1Q-86fD2VmWluYA5jxRkC9U2NsSwSSXV4FPW9w1Q2T_Wjt6koJvLgtikd66MqwYiJPX2x9MwLhoGYlpTbKtkJuHwE9eM6wQgieChskow6tJCVjQ75I315dT8n3tUtasGdBkprOlUK9ibPrYr9HqRz4AwzEQaxAq9_EDcsSG_XW0CHuqi2lRKHw592MlGlhjyQibXKSZJh-v3KW4wIVqa-2x0k1wfbZdpaO3BZaKYCacLOxwUKTnXPbQqDPLQDeYgDBwaTLvaCN221H&si=APYL9bvoDGWmsM6h2lfKzIb8LfQg_oNQyUOQgna9TyfQHAoqUvvaXjJhb-NHEJtDKiWdK3OqRhtZNP2EtNq6veOxTLUq88TEa2J8JiXE33-xY1b8ohiuDLBeOOGhuI1U6V4mDc9jmZkDoxLC9b6s6V8MAjPhY-EC_g%3D%3D&sa=X&sqi=2&ved=2ahUKEwi05JSHnMWMAxUw8bsIHRRCDd0Qk8gLegQIHxAB&ictx=1&stq=1&cs=0&lei=o2bzZ_SGIrDi7_UPlIS16A0#ebo=1"
                    review_message = "If you are satisfied with Wehbe(Broker) services, please leave a review for sharing happiness to others!!😊"
                    send_link_button(
                        from_id, review_message, "Click Here", review_link, user_states
                    )
                    store_interaction(
                        from_id,
                        "Review request sent",
                        f"Review link: {review_link}",
                        user_states,
                    )
                    del user_states[from_id]

                else:
                    send_whatsapp_message(
                        from_id,
                        "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry. Please wait for further assistance. If you have any questions, please contact support@insuranceclub.ae.",
                    )
                    store_interaction(
                        from_id, "API error", "Failed to get valid ID", user_states
                    )

            except requests.RequestException as e:
                print(f"Error calling medical_insert API: {e}")
                send_whatsapp_message(
                    from_id,
                    "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry. Please wait for further assistance. If you have any questions, please contact support@insuranceclub.ae.",
                )
                store_interaction(from_id, "API error", str(e), user_states)

            # Transition to next stage
            user_states[from_id]["stage"] = "waiting_for_new_query"
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )

        else:
            # If advisor code is invalid, prompt again
            error_message = "Please provide a valid 4-digit Insurance Advisor code."
            send_whatsapp_message(from_id, error_message)
            store_interaction(
                from_id, "Invalid advisor code", error_message, user_states
            )
            await asyncio.sleep(1)
            code_question = "Please provide your Insurance Advisor code:"
            send_whatsapp_message(from_id, code_question)
            store_interaction(
                from_id, "Bot re-asked for advisor code", code_question, user_states
            )
        return
    # Handle Motor Insurance flow
    # elif state["stage"] == "motor_insurance_flow":
    #     # Store vehicle information
    #     vehicle_info = text.strip()
    #     user_states[from_id]["responses"]["vehicle_info"] = vehicle_info
    #     store_interaction(from_id, "What is the year, make and model of your vehicle?", f"Response: {vehicle_info}",user_states)
    #     user_states[from_id]["responses"]["motor_question_vehicle"] = "What is the year, make and model of your vehicle?"

    #     user_states[from_id]["stage"] = "motor_insurance_driver"
    #     driving_question = "Thank you. How many years have you been driving?"
    #     send_whatsapp_message(from_id, driving_question)
    #     store_interaction(from_id, "Bot asked about driving experience", driving_question,user_states)
    #     user_states[from_id]["responses"]["motor_question_driving"] = driving_question
    #     return

    # # Motor Insurance flow - driving experience
    # elif state["stage"] == "motor_insurance_driver":
    #     driving_exp = text.strip()
    #     user_states[from_id]["responses"]["driving_experience"] = driving_exp
    #     store_interaction(from_id, "Driving experience question", f"Response: {driving_exp}",user_states)

    #     user_states[from_id]["stage"] = "motor_insurance_coverage"
    #     coverage_question = "What type of coverage are you looking for? (Comprehensive, Third Party Only, etc.)"
    #     send_whatsapp_message(from_id, coverage_question)
    #     store_interaction(from_id, "Bot asked about coverage", coverage_question,user_states)
    #     user_states[from_id]["responses"]["motor_question_coverage"] = coverage_question
    #     return

    # # Motor Insurance flow - coverage type
    # elif state["stage"] == "motor_insurance_coverage":
    #     coverage_type = text.strip()
    #     user_states[from_id]["responses"]["desired_coverage"] = coverage_type
    #     store_interaction(from_id, "Coverage type question", f"Response: {coverage_type}",user_states)

    #     user_states[from_id]["stage"] = "motor_insurance_contact"
    #     contact_question = "Thank you for providing that information. What's your phone number and preferred contact time?"
    #     send_whatsapp_message(from_id, contact_question)
    #     store_interaction(from_id, "Bot asked for contact details", contact_question)
    #     user_states[from_id]["responses"]["motor_question_contact"] = contact_question
    #     return

    # # Motor Insurance flow - contact info and completion
    # elif state["stage"] == "motor_insurance_contact":
    #     contact_info = text.strip()
    #     user_states[from_id]["responses"]["contact_info"] = contact_info
    #     store_interaction(from_id, "Contact info question", f"Response: {contact_info}")
    #     user_states[from_id]["stage"] = "completed"

    #     # Create a summary JSON of the user's responses
    #     user_json = json.dumps(user_states[from_id]["responses"], indent=2)
    #     print(f"User data collected for {from_id}: {user_json}")

    #     # Send confirmation to user
    #     confirmation1 = "Perfect! I've collected all the information we need for your Motor Insurance quote."
    #     send_whatsapp_message(from_id, confirmation1)
    #     store_interaction(from_id, "Completion confirmation", confirmation1)

    #     await asyncio.sleep(1)
    #     confirmation2 = "Our insurance specialist will contact you at your preferred time to discuss your options."
    #     send_whatsapp_message(from_id, confirmation2)
    #     store_interaction(from_id, "Next steps", confirmation2)

    #     await asyncio.sleep(1)
    #     send_yes_no_options(from_id, "Would you like to purchase our insurance again?")
    #     user_states[from_id]["stage"] = "waiting_for_new_query"
    #     return

    # Handle Claim flow
    elif state["stage"] == "claim_flow":
        # Store claim type
        claim_type = text.strip()
        user_states[from_id]["responses"]["claim_type"] = claim_type
        store_interaction(
            from_id,
            "What type of insurance policy are you filing a claim for?",
            f"Response: {claim_type}",
        )
        user_states[from_id]["responses"]["claim_question_type"] = (
            "What type of insurance policy are you filing a claim for?"
        )

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
        store_interaction(
            from_id, "Policy number question", f"Response: {policy_number}"
        )

        user_states[from_id]["stage"] = "claim_details"
        details_question = (
            "Please briefly describe the incident for which you are filing a claim:"
        )
        send_whatsapp_message(from_id, details_question)
        store_interaction(from_id, "Bot asked for incident details", details_question)
        user_states[from_id]["responses"]["claim_question_details"] = details_question
        return

    # Claim flow - incident details
    elif state["stage"] == "claim_details":
        incident_details = text.strip()
        user_states[from_id]["responses"]["incident_details"] = incident_details
        store_interaction(
            from_id, "Incident details question", f"Response: {incident_details}"
        )

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
        store_interaction(
            from_id, "Incident date question", f"Response: {incident_date}"
        )
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
    elif state["stage"] == "medical_member_name":
        member_name = text.strip()
        user_states[from_id]["responses"]["member_name"] = member_name
        store_interaction(
            from_id, "Member name question", f"Response: {member_name}", user_states
        )

        dob_question = "Date of Birth (DOB)"
        send_whatsapp_message(from_id, dob_question)
        store_interaction(
            from_id, "Bot asked for member DOB", dob_question, user_states
        )
        user_states[from_id]["responses"]["medical_question_member_dob"] = dob_question
        user_states[from_id]["stage"] = "medical_member_dob"
        return
    # Todo Update

    # After document upload and information display, handle confirmation
    elif state["stage"] == "document_info_confirmation":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "Document information confirmation",
                "User confirmed information is correct",
                user_states,
            )

            # Skip editing and proceed to next stage without showing summary
            from services.document_processor import proceed_without_edits

            await proceed_without_edits(from_id, user_states)

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id,
                "Document information confirmation",
                "User indicated information needs editing",
                user_states,
            )

            # Start the editing process
            from services.document_processor import handle_document_edit

            await handle_document_edit(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(from_id, "Is all the information correct?", user_states)

        return

    # Handle selection of field to edit
    elif state["stage"] == "select_field_to_edit":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Done Editing":
            # Complete the editing process and move forward
            store_interaction(
                from_id,
                "Field selection for editing",
                "User completed editing",
                user_states,
            )
            from services.document_processor import complete_document_editing

            await complete_document_editing(from_id, user_states)

        elif selected_option:
            # User selected a field to edit
            store_interaction(
                from_id,
                "Field selection for editing",
                f"User selected: {selected_option}",
                user_states,
            )
            from services.document_processor import handle_document_edit

            await handle_document_edit(from_id, user_states, selected_option)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)

            # Re-show the editing options
            from services.document_processor import handle_document_edit

            await handle_document_edit(from_id, user_states)
        return

    # Handle user entering a new value for the field
    elif state["stage"] == "entering_new_value":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        new_value = selected_option if selected_option else text

        store_interaction(
            from_id,
            f"New value for {state.get('editing_field', 'field')}",
            f"User entered: {new_value}",
            user_states,
        )
        from services.document_processor import handle_document_edit

        await handle_document_edit(from_id, user_states, None, new_value)
        return

    # Handle final confirmation after editing is complete
    elif state["stage"] == "final_document_confirmation":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "Final document confirmation",
                "User confirmed information is correct",
                user_states,
            )

            # Proceed with the verified information
            from services.document_processor import proceed_with_verified_document

            await proceed_with_verified_document(from_id, user_states)
        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id,
                "Final document confirmation",
                "User indicated information still needs editing",
                user_states,
            )

            # Go back to editing
            from services.document_processor import handle_document_edit

            await handle_document_edit(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Is all the information correct now?", user_states
            )

        user_states[from_id] = state  # Persist state changes
        return

    # Handler for checking if user wants to continue editing
    elif state["stage"] == "check_continue_editing":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "Continue editing check",
                "User wants to edit more fields",
                user_states,
            )
            from services.document_processor import handle_document_edit

            await handle_document_edit(from_id, user_states)

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id, "Continue editing check", "User is done editing", user_states
            )
            from services.document_processor import complete_document_editing

            await complete_document_editing(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to edit another field?", user_states
            )
        return

    # New stage for motor registration city (for cars only)
    elif state["stage"] == "motor_registration_city":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        emirate_options = [
            "Abudhabi",
            "Ajman",
            "Dubai",
            "Fujairah",
            "Ras Al Khaimah",
            "Sharjah",
            "Umm Al Quwain",
        ]

        if selected_option in emirate_options:
            user_states[from_id]["responses"]["registration_city"] = selected_option
            store_interaction(
                from_id,
                "Registration city selection",
                f"Selected: {selected_option}",
                user_states,
            )

            # Move to ID upload or manual entry, similar to medical flow
            user_states[from_id]["stage"] = "motor_member_input_method"
            member_question = "Thank you! Now, we need the details of the car owner. Would you like to upload their Emirates ID or manually enter the information?"
            send_yes_no_options(from_id, member_question, user_states)
            store_interaction(
                from_id,
                "Bot asked about ID upload/manual entry",
                member_question,
                user_states,
            )
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            registration_question = "Please select the city of registration:"
            send_interactive_options(
                from_id, registration_question, emirate_options, user_states
            )
        return

    # New stage for motor owner ID input method selection

    elif state["stage"] == "motor_member_input_method":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        if selected_option == "Yes":
            upload_question = "Please Upload Your Document"
            send_whatsapp_message(from_id, upload_question)
            store_interaction(
                from_id, "Bot requested document upload", upload_question, user_states
            )
            user_states[from_id]["stage"] = "motor_upload_document"
        elif selected_option == "No":
            name_question = "Next, we need the details of the member for whom the policy is being purchased. Please provide Name"
            send_whatsapp_message(from_id, name_question)
            store_interaction(
                from_id, "Bot asked for member name", name_question, user_states
            )
            user_states[from_id]["responses"]["motor_question_member_name"] = (
                name_question
            )
            user_states[from_id]["stage"] = "motor_member_name"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            member_question = "Next, we need the details of the member. Would you like to upload their Emirates ID or manually enter the information?"
            send_yes_no_options(from_id, member_question, user_states)
        return

    elif state["stage"] == "motor_upload_document":
        # This stage acts as a waiting state; actual document processing is handled by the webhook
        send_whatsapp_message(
            from_id,
            "Thank you for uploading your document. I'm processing it now, please wait a moment...",
        )
        store_interaction(
            from_id, "Document upload received", "Processing started", user_states
        )
        # No further action here; the webhook will handle the document and transition to verification
        return

    elif state["stage"] == "motor_member_name":
        member_name = text.strip()
        user_states[from_id]["responses"]["member_name"] = member_name
        store_interaction(
            from_id, "Member name question", f"Response: {member_name}", user_states
        )

        dob_question = "Date of Birth (DOB)"
        send_whatsapp_message(from_id, dob_question)
        store_interaction(
            from_id, "Bot asked for member DOB", dob_question, user_states
        )
        user_states[from_id]["responses"]["motor_question_member_dob"] = dob_question
        user_states[from_id]["stage"] = "motor_member_dob"
        return

    elif state["stage"] == "motor_member_dob":
        motor_member_dob = text.strip()
        user_states[from_id]["responses"]["motor_member_dob"] = motor_member_dob
        store_interaction(
            from_id, "Member DOB question", f"Response: {motor_member_dob}", user_states
        )

        gender_question = f"Thanks!Lets's continue.Please confirm the gender of {user_states[from_id]['responses']['motor_member_name']}"
        send_interactive_options(
            from_id, gender_question, ["Male", "Female"], user_states
        )
        store_interaction(
            from_id, "Bot asked for member gender", gender_question, user_states
        )
        user_states[from_id]["responses"]["motor_question_member_gender"] = (
            gender_question
        )
        user_states[from_id]["stage"] = "motor_member_gender"
        return

    elif state["stage"] == "motor_member_gender":
        selected_gender = (
            interactive_response.get("title") if interactive_response else None
        )
        if selected_gender in ["Male", "Female"]:
            user_states[from_id]["responses"]["motor_member_gender"] = selected_gender
            store_interaction(
                from_id,
                "Member gender question",
                f"Selected: {selected_gender}",
                user_states,
            )

            license_question = f"Thank you for uploading the document,Now,Let's move on to: Please Uplaod your Driving License"
            send_interactive_options(from_id, marital_question, user_states)
            store_interaction(
                from_id, "Bot asked for upload driving license", user_states
            )
            user_states[from_id]["responses"]["motor_driving_license"] = (
                license_question
            )
            user_states[from_id]["stage"] = "motor_driving_license"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            gender_question = f"Please confirm the gender of {user_states[from_id]['responses']['member_name']}"
            send_interactive_options(
                from_id, gender_question, ["Male", "Female"], user_states
            )
        return

    elif state["stage"] == "motor_driving_license":
        # This stage acts as a waiting state; actual document processing is handled by the webhook
        send_whatsapp_message(
            from_id,
            "Thank you for uploading your driving license. I'm processing it now, please wait a moment...",
        )
        store_interaction(
            from_id, "Document upload received", "Processing started", user_states
        )
        # No further action here; the webhook will handle the document and transition to verification
        return

    # Todo
    # After document upload and information display, handle confirmation
    elif state["stage"] == "lience_document_info_confirmation":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "License document information confirmation",
                "User confirmed information is correct",
                user_states,
            )

            # Skip editing and proceed to next stage without showing summary
            from services.document_processor import proceed__license_without_edits

            await proceed__license_without_edits(from_id, user_states, "motor")

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id,
                "License document information confirmation",
                "User indicated information needs editing",
                user_states,
            )

            # Start the editing process
            from services.document_processor import handle_lience_document_edit

            await handle_lience_document_edit(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(from_id, "Is all the information correct?", user_states)
        return

    # Handle selection of field to edit
    elif state["stage"] == "license_select_field_to_edit":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Done Editing":
            # Complete the editing process and move forward
            store_interaction(
                from_id,
                "Field selection for editing",
                "User completed editing",
                user_states,
            )
            from services.document_processor import complete_licence_document_editing

            await complete_licence_document_editing(from_id, user_states)

        elif selected_option:
            # User selected a field to edit
            store_interaction(
                from_id,
                "Field selection for editing",
                f"User selected: {selected_option}",
                user_states,
            )
            from services.document_processor import handle_lience_document_edit

            await handle_lience_document_edit(from_id, user_states, selected_option)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)

            # Re-show the editing options
            from services.document_processor import handle_lience_document_edit

            await handle_lience_document_edit(from_id, user_states)
        return

    # Handle user entering a new value for the field
    elif state["stage"] == "lience_entering_new_value":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        new_value = selected_option if selected_option else text

        store_interaction(
            from_id,
            f"New value for {state.get('lience_editing_field', 'field')}",
            f"User entered: {new_value}",
            user_states,
        )
        from services.document_processor import handle_lience_document_edit

        await handle_lience_document_edit(from_id, user_states, None, new_value)
        return

    # Handle final confirmation after editing is complete
    elif state["stage"] == "lience_final_document_confirmation":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "Final document confirmation",
                "User confirmed information is correct",
                user_states,
            )

            # Proceed with the verified information
            from services.document_processor import (
                proceed_with_license_verified_document,
            )

            await proceed_with_license_verified_document(from_id, user_states)

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id,
                "Final document confirmation",
                "User indicated information still needs editing",
                user_states,
            )

            # Go back to editing
            from services.document_processor import handle_lience_document_edit

            await handle_lience_document_edit(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Is all the information correct now?", user_states
            )
        return

    # Handler for checking if user wants to continue editing
    elif state["stage"] == "licnese_check_continue_editing":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "Continue editing check",
                "User wants to edit more fields",
                user_states,
            )
            from services.document_processor import handle_lience_document_edit

            await handle_lience_document_edit(from_id, user_states)

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id, "Continue editing check", "User is done editing", user_states
            )
            from services.document_processor import complete_licence_document_editing

            await complete_licence_document_editing(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to edit another field?", user_states
            )
        return

    # Todo Mulkiya
    elif state["stage"] == "motor_vechile_mulkiya":
        # This stage acts as a waiting state; actual document processing is handled by the webhook
        send_whatsapp_message(
            from_id,
            "Thank you for uploading your Mulkiya. I'm processing it now, please wait a moment...",
        )
        store_interaction(
            from_id, "Document upload received", "Processing started", user_states
        )
        # No further action here; the webhook will handle the document and transition to verification
        return

    # After document upload and information display, handle confirmation
    elif state["stage"] == "mulkiya_document_info_confirmation":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "License document information confirmation",
                "User confirmed information is correct",
                user_states,
            )

            # Skip editing and proceed to next stage without showing summary
            from services.document_processor import proceed__mulkiya_without_edits

            await proceed__mulkiya_without_edits(from_id, user_states, "motor")

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id,
                "Vehcile Mulkiya document information confirmation",
                "User indicated information needs editing",
                user_states,
            )

            # Start the editing process
            from services.document_processor import handle_mulkiya_document_edit

            await handle_mulkiya_document_edit(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(from_id, "Is all the information correct?", user_states)
        return

    # Handle selection of field to edit
    elif state["stage"] == "mulkiya_select_field_to_edit":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Done Editing":
            # Complete the editing process and move forward
            store_interaction(
                from_id,
                "Field selection for editing",
                "User completed editing",
                user_states,
            )
            from services.document_processor import complete_mulkiya_document_editing

            await complete_mulkiya_document_editing(from_id, user_states)

        elif selected_option:
            # User selected a field to edit
            store_interaction(
                from_id,
                "Field selection for editing",
                f"User selected: {selected_option}",
                user_states,
            )
            from services.document_processor import handle_mulkiya_document_edit

            await handle_mulkiya_document_edit(from_id, user_states, selected_option)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)

            # Re-show the editing options
            from services.document_processor import handle_mulkiya_document_edit

            await handle_mulkiya_document_edit(from_id, user_states)
        return

    # Handle user entering a new value for the field
    elif state["stage"] == "mulkiya_entering_new_value":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )
        new_value = selected_option if selected_option else text

        store_interaction(
            from_id,
            f"New value for {state.get('mulkiya_editing_field', 'field')}",
            f"User entered: {new_value}",
            user_states,
        )
        from services.document_processor import handle_mulkiya_document_edit

        await handle_mulkiya_document_edit(from_id, user_states, None, new_value)
        return

    # Handle final confirmation after editing is complete
    elif state["stage"] == "mulkiya_final_document_confirmation":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "Final document confirmation",
                "User confirmed information is correct",
                user_states,
            )

            # Proceed with the verified information
            from services.document_processor import (
                proceed_with_mulkiya_verified_document,
            )

            await proceed_with_mulkiya_verified_document(from_id, user_states)

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id,
                "Final document confirmation",
                "User indicated information still needs editing",
                user_states,
            )

            # Go back to editing
            from services.document_processor import handle_mulkiya_document_edit

            await handle_mulkiya_document_edit(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Is all the information correct now?", user_states
            )
        return

    # Handler for checking if user wants to continue editing
    elif state["stage"] == "mulkiya_check_continue_editing":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        if selected_option == "Yes" or text.lower() in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
        ]:
            store_interaction(
                from_id,
                "Continue editing check",
                "User wants to edit more fields",
                user_states,
            )
            from services.document_processor import handle_mulkiya_document_edit

            await handle_mulkiya_document_edit(from_id, user_states)

        elif selected_option == "No" or text.lower() in ["no", "nope", "nah"]:
            store_interaction(
                from_id, "Continue editing check", "User is done editing", user_states
            )
            from services.document_processor import complete_mulkiya_document_editing

            await complete_mulkiya_document_editing(from_id, user_states)

        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to edit another field?", user_states
            )
        return

    elif state["stage"] == "motor_vehicle_wish_to_buy":
        selected_wish_to_buy = (
            interactive_response.get("title") if interactive_response else None
        )
        valid_wish_to_buy = ["Comprehensive", "Third Party"]
        # Normalize text input for fallback case
        text_response = text.strip().lower()
        if text_response in ["comprehensive", "third party"]:
            selected_wish_to_buy = (
                "Comprehensive" if text_response == "comprehensive" else "Third Party"
            )

        if selected_wish_to_buy in valid_wish_to_buy:
            user_states[from_id]["responses"]["motor_vehicle_wish_to_buy"] = (
                selected_wish_to_buy
            )
            store_interaction(
                from_id,
                "Motor wish to buy question",
                f"Selected: {selected_wish_to_buy}",
                user_states,
            )
            user_states[from_id]["stage"] = "completed"
            user_json = json.dumps(user_states[from_id]["responses"], indent=2)
            print(f"User data collected for {from_id}: {user_json}")
            thanks = "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry.Please wait for further  assistance. if you have any questions,Please contact support@insuranceclub.ae"
            send_whatsapp_message(from_id, thanks)
            store_interaction(from_id, "Completion confirmation", thanks, user_states)
            del user_states[from_id]
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )
            user_states[from_id]["stage"] = "waiting_for_new_query"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            wish_to_buy_question = "What type of insurance would you like to buy?"
            send_interactive_options(
                from_id, wish_to_buy_question, valid_wish_to_buy, user_states
            )
            store_interaction(
                from_id,
                "Bot re-asked for wish to buy",
                wish_to_buy_question,
                user_states,
            )
        return

    # New stage for motor registration city (for cars only)
    elif state["stage"] == "motor_bike_registration_city":
        selected_option = (
            interactive_response.get("title") if interactive_response else None
        )

        emirate_options = [
            "Abudhabi",
            "Ajman",
            "Dubai",
            "Fujairah",
            "Ras Al Khaimah",
            "Sharjah",
            "Umm Al Quwain",
        ]

        if selected_option in emirate_options:
            user_states[from_id]["responses"]["registration_city"] = selected_option
            store_interaction(
                from_id,
                "Registration city selection",
                f"Selected: {selected_option}",
                user_states,
            )

            user_states[from_id]["stage"] = "completed"
            user_json = json.dumps(user_states[from_id]["responses"], indent=2)
            print(f"User data collected for {from_id}: {user_json}")
            thanks = "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry.Please wait for further  assistance. if you have any questions,Please contact support@insuranceclub.ae"
            send_whatsapp_message(from_id, thanks)
            store_interaction(from_id, "Completion confirmation", thanks, user_states)
            del user_states[from_id]
            await asyncio.sleep(1)
            send_yes_no_options(
                from_id, "Would you like to purchase our insurance again?", user_states
            )
            user_states[from_id]["stage"] = "waiting_for_new_query"
        else:
            from .llm import process_message_with_llm

            await process_message_with_llm(
                from_id=from_id, text=text, user_states=user_states
            )
            await asyncio.sleep(1)
            wish_to_buy_question = "What type of insurance would you like to buy?"
            send_interactive_options(
                from_id, wish_to_buy_question, valid_wish_to_buy, user_states
            )
            store_interaction(
                from_id,
                "Bot re-asked for wish to buy",
                wish_to_buy_question,
                user_states,
            )
        return
