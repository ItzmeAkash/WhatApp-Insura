# # In a new file, e.g., services/document_processor.py
# import os
# import tempfile
# from services.conversation_manager import send_whatsapp_message
# from services.whatsapp import send_yes_no_options, send_interactive_options
# from utils.helpers import extract_image_info1, extract_pdf_info1, store_interaction

# # async def process_uploaded_document(from_id: str, document_data: bytes, mime_type: str, filename: str, user_states: dict) -> dict:
# #     # Map MIME types to file extensions
# #     mime_to_ext = {
# #         "application/pdf": ".pdf",
# #         "image/jpeg": ".jpg",
# #         "image/png": ".png"
# #     }
# #     file_ext = mime_to_ext.get(mime_type)
# #     if not file_ext:
# #         send_whatsapp_message(from_id, "Unsupported file type. Please upload a PDF, JPG, or PNG file.")
# #         return None

# #     # Save to temporary file
# #     with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
# #         temp_file.write(document_data)
# #         temp_file.flush()
# #         temp_path = temp_file.name

# #     try:
# #         # Call the appropriate extraction function
# #         if file_ext == ".pdf":
# #             extracted_info = await extract_pdf_info1(temp_path)
# #         else:  # .jpg or .png
# #             extracted_info = await extract_image_info1(temp_path)

# #         # Store the filename in user_states
# #         user_states[from_id]["document_name"] = filename
# #         return extracted_info
# #     finally:
# #         os.unlink(temp_path)  # Clean up temporary file
# # In services/document_processor.py
# async def process_uploaded_document(from_id: str, document_data: bytes, mime_type: str, filename: str, user_states: dict) -> dict:
#     mime_to_ext = {
#         "application/pdf": ".pdf",
#         "image/jpeg": ".jpg",
#         "image/png": ".png"
#     }
#     file_ext = mime_to_ext.get(mime_type)
#     if not file_ext:
#         send_whatsapp_message(from_id, "Unsupported file type. Please upload a PDF, JPG, or PNG file.")
#         return None

#     with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
#         temp_file.write(document_data)
#         temp_file.flush()
#         temp_path =temp_file.name

#     try:
#         if file_ext == ".pdf":
#             extracted_info = await extract_pdf_info1(temp_path)
#         else:
#             extracted_info = await extract_image_info1(temp_path)

#         if not extracted_info or all(value == "" for value in extracted_info.values()):
#             print(f"Extraction failed or returned empty for {filename}")
#             return None

#         user_states[from_id]["document_name"] = filename
#         return extracted_info
#     except Exception as e:
#         print(f"Error in process_uploaded_document: {e}")
#         return None
#     finally:
#         os.unlink(temp_path)




# # In services/document_processor.py
# async def verify_extracted_info(from_id: str, extracted_info: dict, user_states: dict):
#     # Define the order of fields to verify
#     fields_to_verify = [
#         "name", "id_number", "date_of_birth", "nationality", "issue_date",
#         "expiry_date", "gender", "card_number", "occupation", "employer", "issuing_place"
#     ]

#     # Initialize verification state
#     user_states[from_id]["extracted_info"] = extracted_info
#     user_states[from_id]["verification_index"] = 0
#     user_states[from_id]["stage"] = "verify_document_info"
#     user_states[from_id]["verified_info"] = {}

#     # Start verification with the first field
#     field = fields_to_verify[0]
#     question = f"Please confirm your {field.replace('_', ' ')}."
#     send_whatsapp_message(from_id, question)
#     send_yes_no_options(from_id, f"Is the {field.replace('_', ' ')} '{extracted_info.get(field, '')}' correct?", user_states)
#     store_interaction(from_id, f"Verification started for {field}", question, user_states)

# # New function to display all extracted information without verification
# async def display_extracted_info(from_id: str, extracted_info: dict, user_states: dict):
#     # Define the fields to display
#     fields_to_display = [
#         "name", "id_number", "date_of_birth", "nationality", "issue_date",
#         "expiry_date", "gender", "card_number", "occupation", "employer", "issuing_place"
#     ]

#     # Store the extracted info directly as verified info
#     user_states[from_id]["extracted_info"] = extracted_info
#     user_states[from_id]["verified_info"] = extracted_info

#     # Create a formatted message with all extracted information
#     message = "Here is the information from your document:\n\n"

#     for field in fields_to_display:
#         field_value = extracted_info.get(field, "")
#         if field_value:  # Only include fields that have values
#             message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

#     # Send the message with all extracted information
#     send_whatsapp_message(from_id, message)
#     store_interaction(from_id, "Document information displayed", message, user_states)

#     # Move to the next stage directly
#     user_states[from_id]["stage"] = "medical_marital_status"
#     user_states[from_id]["responses"]["member_name"] = extracted_info.get("name", "")
#     user_states[from_id]["responses"]["member_dob"] = extracted_info.get("date_of_birth", "")
#     user_states[from_id]["responses"]["member_gender"] = extracted_info.get("gender", "")

#     # Ask the next question in the flow using interactive options
#     marital_question = f"Please confirm the marital status of {extracted_info.get('name', 'the member')}"
#     send_interactive_options(from_id, marital_question, ["Single", "Married"], user_states)
#     store_interaction(from_id, "Bot asked for marital status", marital_question, user_states)
#     user_states[from_id]["responses"]["medical_question_marital_status"] = marital_question
    
    
import os
import tempfile
from services.conversation_manager import send_whatsapp_message
from services.whatsapp import send_yes_no_options, send_interactive_options
from utils.helpers import extract_image_info1, extract_pdf_info1, store_interaction

async def process_uploaded_document(from_id: str, document_data: bytes, mime_type: str, filename: str, user_states: dict) -> dict:
    mime_to_ext = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png"
    }
    file_ext = mime_to_ext.get(mime_type)
    if not file_ext:
        send_whatsapp_message(from_id, "Unsupported file type. Please upload a PDF, JPG, or PNG file.")
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        temp_file.write(document_data)
        temp_file.flush()
        temp_path = temp_file.name

    try:
        if file_ext == ".pdf":
            extracted_info = await extract_pdf_info1(temp_path)
        else:
            extracted_info = await extract_image_info1(temp_path)

        if not extracted_info or all(value == "" for value in extracted_info.values()):
            print(f"Extraction failed or returned empty for {filename}")
            return None

        user_states[from_id]["document_name"] = filename
        return extracted_info
    except Exception as e:
        print(f"Error in process_uploaded_document: {e}")
        return None
    finally:
        os.unlink(temp_path)

async def display_extracted_info(from_id: str, extracted_info: dict, user_states: dict):
    # Define the fields to display
    fields_to_display = [
        "name", "id_number", "date_of_birth", "nationality", "issue_date",
        "expiry_date", "gender", "card_number", "occupation", "employer", "issuing_place"
    ]

    # Store the extracted info
    user_states[from_id]["extracted_info"] = extracted_info
    user_states[from_id]["verified_info"] = extracted_info.copy()  # Create a copy that can be edited

    # Check if card_number is missing
    if not extracted_info.get("card_number"):
        # Ask for back side of Emirates ID
        message = "I need to see the back side of your Emirates ID to get the card number. Please upload a photo of the back side."
        send_whatsapp_message(from_id, message)
        store_interaction(from_id, "Bot requested back of Emirates ID", message, user_states)
        
        # Set the stage for waiting for back side upload
        user_states[from_id]["stage"] = "waiting_for_back_id"
        return
    
    # Create a formatted message with all extracted information
    message = "Here is the information from your document:\n\n"

    for field in fields_to_display:
        field_value = extracted_info.get(field, "")
        if field_value:  # Only include fields that have values
            message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

    # Send the message with all extracted information
    send_whatsapp_message(from_id, message)
    store_interaction(from_id, "Document information displayed", message, user_states)

    # Ask if the information is correct
    user_states[from_id]["stage"] = "document_info_confirmation"
    confirmation_question = "Is all the information correct?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(from_id, "Bot asked for information confirmation", confirmation_question, user_states)

# New function to merge information from front and back of ID
async def merge_id_information(from_id: str, back_extracted_info: dict, user_states: dict):
    # Retrieve the front side information
    front_info = user_states[from_id]["verified_info"]
    
    # Merge the information, prioritizing back side for missing fields
    # but front side for duplicated fields
    merged_info = {}
    
    # Start with all back info
    for key, value in back_extracted_info.items():
        if value:  # Only include non-empty values
            merged_info[key] = value
    
    # Add front info, preserving existing values
    for key, value in front_info.items():
        if value and key not in merged_info:  # Only add if not already present from back
            merged_info[key] = value
    
    # Update the verified_info with the merged data
    user_states[from_id]["verified_info"] = merged_info
    
    # Define the fields to display
    fields_to_display = [
        "name", "id_number", "date_of_birth", "nationality", "issue_date",
        "expiry_date", "gender", "card_number", "occupation", "employer", "issuing_place"
    ]
    
    # Create a formatted message with all extracted information
    message = "Here is the complete information from your Emirates ID:\n\n"

    for field in fields_to_display:
        field_value = merged_info.get(field, "")
        if field_value:  # Only include fields that have values
            message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

    # Send the message with all extracted information
    send_whatsapp_message(from_id, message)
    store_interaction(from_id, "Complete document information displayed", message, user_states)

    # Ask if the information is correct
    user_states[from_id]["stage"] = "document_info_confirmation"
    confirmation_question = "Is all the information correct?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(from_id, "Bot asked for information confirmation", confirmation_question, user_states)

# Function to handle editing of document information
async def handle_document_edit(from_id: str, user_states: dict, field_to_edit=None, new_value=None):
    # Define the fields that can be edited
    editable_fields = [
        "name", "id_number", "date_of_birth", "nationality", "issue_date",
        "expiry_date", "gender", "card_number", "occupation", "employer", "issuing_place"
    ]
    
    # If we're just starting the editing process
    if field_to_edit is None and new_value is None:
        user_states[from_id]["stage"] = "select_field_to_edit"
        
        # Create a list of options that only includes fields that have values
        edit_options = []
        for field in editable_fields:
            if user_states[from_id]["verified_info"].get(field, ""):
                edit_options.append(field.replace('_', ' ').title())
        
        select_field_message = "Which field would you like to edit? When you're finished editing, say 'Done'."
        send_interactive_options(from_id, select_field_message, edit_options, user_states)
        store_interaction(from_id, "Bot asked which field to edit", select_field_message, user_states)
        return
    
    # If user has selected a field to edit
    elif field_to_edit and new_value is None:
        # Convert display name back to field name
        field_key = field_to_edit.lower().replace(' ', '_')
        
        if field_key in editable_fields:
            user_states[from_id]["editing_field"] = field_key
            user_states[from_id]["stage"] = "entering_new_value"
            
            current_value = user_states[from_id]["verified_info"].get(field_key, "")
            edit_prompt = f"The current value for {field_to_edit} is: {current_value}\n\nPlease enter the new value:"
            
            # Special handling for gender field - use interactive options
            if field_key == "gender":
                send_interactive_options(from_id, edit_prompt, ["Male", "Female"], user_states)
            else:
                send_whatsapp_message(from_id, edit_prompt)
            
            store_interaction(from_id, f"Bot asked for new value for {field_key}", edit_prompt, user_states)
        return
    
    # If user has provided a new value
    elif new_value and user_states[from_id]["stage"] == "entering_new_value":
        field_key = user_states[from_id]["editing_field"]
        
        # Update the value in verified_info
        user_states[from_id]["verified_info"][field_key] = new_value
        
        # Confirm the update to the user
        confirmation = f"Updated {field_key.replace('_', ' ').title()} to: {new_value}"
        send_whatsapp_message(from_id, confirmation)
        store_interaction(from_id, f"Updated {field_key}", confirmation, user_states)
        
        # Ask if they want to edit more or if they're done
        done_question = "Would you like to edit another field?"
        send_yes_no_options(from_id, done_question, user_states)
        user_states[from_id]["stage"] = "check_continue_editing"
        store_interaction(from_id, "Bot asked if user wants to edit more", done_question, user_states)
        return

# Function to complete the document editing process
async def complete_document_editing(from_id: str, user_states: dict):
    # Update member information with the verified info
    verified_info = user_states[from_id]["verified_info"]
    
    # Send a summary of the final information
    summary_message = "Here's the final information after your edits:\n\n"
    
    for field, value in verified_info.items():
        if value:  # Only include fields that have values
            summary_message += f"*{field.replace('_', ' ').title()}*: {value}\n"
    
    send_whatsapp_message(from_id, summary_message)
    store_interaction(from_id, "Document editing summary", summary_message, user_states)
    
    # Ask for final confirmation
    user_states[from_id]["stage"] = "final_document_confirmation"
    confirmation_question = "Is all the information correct now?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(from_id, "Bot asked for final confirmation", confirmation_question, user_states)

# Function to proceed with the workflow after final confirmation
async def proceed_with_verified_document(from_id: str, user_states: dict):
    verified_info = user_states[from_id]["verified_info"]
    
    # Update member information with the verified info
    user_states[from_id]["responses"]["member_name"] = verified_info.get("name", "")
    user_states[from_id]["responses"]["member_dob"] = verified_info.get("date_of_birth", "")
    user_states[from_id]["responses"]["member_gender"] = verified_info.get("gender", "")
    
    # Send confirmation message
    confirmation = "Thank you for confirming. We'll proceed with this information."
    send_whatsapp_message(from_id, confirmation)
    store_interaction(from_id, "Document information confirmed", confirmation, user_states)
    
    # Move to the next stage in the flow
    user_states[from_id]["stage"] = "medical_marital_status"
    
    # Ask the next question in the flow using interactive options
    marital_question = f"Please confirm the marital status of {verified_info.get('name', 'the member')}"
    send_interactive_options(from_id, marital_question, ["Single", "Married"], user_states)
    store_interaction(from_id, "Bot asked for marital status", marital_question, user_states)
    user_states[from_id]["responses"]["medical_question_marital_status"] = marital_question

# Function to proceed without edits
async def proceed_without_edits(from_id: str, user_states: dict):
    verified_info = user_states[from_id]["verified_info"]
    
    # Update member information with the verified info
    user_states[from_id]["responses"]["member_name"] = verified_info.get("name", "")
    user_states[from_id]["responses"]["member_dob"] = verified_info.get("date_of_birth", "")
    user_states[from_id]["responses"]["member_gender"] = verified_info.get("gender", "")
    
    # Move to the next stage in the flow without showing summarys
    user_states[from_id]["stage"] = "medical_marital_status"
    
    # Ask the next question in the flow using interactive optionss
    marital_question = f"Please confirm the marital status of {verified_info.get('name', 'the member')}"
    send_interactive_options(from_id, marital_question, ["Single", "Married"], user_states)
    store_interaction(from_id, "Bot asked for marital status", marital_question, user_states)
    user_states[from_id]["responses"]["medical_question_marital_status"] = marital_question