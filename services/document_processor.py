import os
import tempfile
from services.conversation_manager import send_whatsapp_message
from services.whatsapp import send_yes_no_options, send_interactive_options
from utils.helpers import (
    extract_image_driving_license,
    extract_image_info1,
    extract_image_mulkiya,
    extract_pdf_driving_license,
    extract_pdf_info1,
    extract_pdf_mulkiya,
    store_interaction,
)


async def process_uploaded_document(
    from_id: str,
    document_data: bytes,
    mime_type: str,
    filename: str,
    user_states: dict,
    flow_type: str = None,
) -> dict:
    mime_to_ext = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
    file_ext = mime_to_ext.get(mime_type)
    if not file_ext:
        send_whatsapp_message(
            from_id, "Unsupported file type. Please upload a PDF, JPG, or PNG file."
        )
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


async def display_extracted_info(
    from_id: str, extracted_info: dict, user_states: dict, flow_type: str = None
):
    # Define the fields to display
    fields_to_display = [
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

    # Store the extracted info
    user_states[from_id]["extracted_info"] = extracted_info
    user_states[from_id]["verified_info"] = (
        extracted_info.copy()
    )  # Create a copy that can be edited

    # Check if card_number is missing
    if not extracted_info.get("card_number"):
        # Ask for back side of Emirates ID
        message = "I need to see the back side of your Emirates ID to get the card number. Please upload a photo of the back side."
        send_whatsapp_message(from_id, message)
        store_interaction(
            from_id, "Bot requested back of Emirates ID", message, user_states
        )

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
    store_interaction(
        from_id,
        "Bot asked for information confirmation",
        confirmation_question,
        user_states,
    )


async def merge_id_information(
    from_id: str, back_extracted_info: dict, user_states: dict, flow_type: str = None
):
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
        if (
            value and key not in merged_info
        ):  # Only add if not already present from back
            merged_info[key] = value

    # Update the verified_info with the merged data
    user_states[from_id]["verified_info"] = merged_info

    # Define the fields to display
    fields_to_display = [
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

    # Create a formatted message with all extracted information
    message = "Here is the complete information from your Emirates ID:\n\n"

    for field in fields_to_display:
        field_value = merged_info.get(field, "")
        if field_value:  # Only include fields that have values
            message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

    # Send the message with all extracted information
    send_whatsapp_message(from_id, message)
    store_interaction(
        from_id, "Complete document information displayed", message, user_states
    )

    # Ask if the information is correct
    user_states[from_id]["stage"] = "document_info_confirmation"
    confirmation_question = "Is all the information correct?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(
        from_id,
        "Bot asked for information confirmation",
        confirmation_question,
        user_states,
    )


async def handle_document_edit(
    from_id: str, user_states: dict, field_to_edit=None, new_value=None
):
    # Define the fields that can be edited
    editable_fields = [
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

    # If we're just starting the editing process
    if field_to_edit is None and new_value is None:
        user_states[from_id]["stage"] = "select_field_to_edit"

        # Create a list of options that only includes fields that have values
        edit_options = []
        for field in editable_fields:
            if user_states[from_id]["verified_info"].get(field, ""):
                edit_options.append(field.replace("_", " ").title())

        select_field_message = "Which field would you like to edit? When you're finished editing, say 'Done'."
        send_interactive_options(
            from_id, select_field_message, edit_options, user_states
        )
        store_interaction(
            from_id, "Bot asked which field to edit", select_field_message, user_states
        )
        return

    # If user has selected a field to edit
    elif field_to_edit and new_value is None:
        # Convert display name back to field name
        field_key = field_to_edit.lower().replace(" ", "_")

        if field_key in editable_fields:
            user_states[from_id]["editing_field"] = field_key
            user_states[from_id]["stage"] = "entering_new_value"

            current_value = user_states[from_id]["verified_info"].get(field_key, "")
            edit_prompt = f"The current value for {field_to_edit} is: {current_value}\n\nPlease enter the new value:"

            # Special handling for gender field - use interactive options
            if field_key == "gender":
                send_interactive_options(
                    from_id, edit_prompt, ["Male", "Female"], user_states
                )
            else:
                send_whatsapp_message(from_id, edit_prompt)

            store_interaction(
                from_id,
                f"Bot asked for new value for {field_key}",
                edit_prompt,
                user_states,
            )
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
        store_interaction(
            from_id, "Bot asked if user wants to edit more", done_question, user_states
        )
        return


async def complete_document_editing(
    from_id: str, user_states: dict, flow_type: str = None
):
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
    store_interaction(
        from_id, "Bot asked for final confirmation", confirmation_question, user_states
    )


async def proceed_with_verified_document(from_id: str, user_states: dict):
    verified_info = user_states[from_id]["verified_info"]
    # flow_type = user_states.get("service_type")
    flow_type = user_states[from_id]["service_type"]
    print("fllow-----------------------------------", flow_type)
    # Update member information with the verified info
    if flow_type == "Medical Insurance":
        user_states[from_id]["responses"]["member_name"] = verified_info.get("name", "")
        user_states[from_id]["responses"]["member_dob"] = verified_info.get(
            "date_of_birth", ""
        )
        user_states[from_id]["responses"]["member_gender"] = verified_info.get(
            "gender", ""
        )
    elif flow_type == "Motor Insurance":
        user_states[from_id]["responses"]["motor_member_name"] = verified_info.get(
            "name", ""
        )
        user_states[from_id]["responses"]["motor_member_dob"] = verified_info.get(
            "date_of_birth", ""
        )
        user_states[from_id]["responses"]["motor_member_gender"] = verified_info.get(
            "gender", ""
        )

    # Send confirmation message
    confirmation = "Thank you for confirming. We'll proceed with this information."
    send_whatsapp_message(from_id, confirmation)
    store_interaction(
        from_id, "Document information confirmed", confirmation, user_states
    )

    # Move to the next stage in the flow
    if flow_type == "Medical Insurance":
        user_states[from_id]["stage"] = "medical_marital_status"
        marital_question = f"Please confirm the marital status of {verified_info.get('name', 'the member')}"
        send_interactive_options(
            from_id, marital_question, ["Single", "Married"], user_states
        )
        store_interaction(
            from_id, "Bot asked for marital status", marital_question, user_states
        )
        user_states[from_id]["responses"]["medical_question_marital_status"] = (
            marital_question
        )
    elif flow_type == "Motor Insurance":
        user_states[from_id]["stage"] = "motor_driving_license"
        license_question = f"Please Uplaod your Driving License"
        send_whatsapp_message(from_id, license_question)
        store_interaction(
            from_id, "Bot asked for vehicle info", license_question, user_states
        )
        user_states[from_id]["responses"]["motor_driving_license"] = license_question


async def proceed_without_edits(from_id: str, user_states: dict):
    verified_info = user_states[from_id]["verified_info"]
    flow_type = user_states[from_id]["service_type"]
    # flow_type = user_states.get("")
    # Update member information with the verified info
    if flow_type == "Medical Insurance":
        user_states[from_id]["responses"]["member_name"] = verified_info.get("name", "")
        user_states[from_id]["responses"]["member_dob"] = verified_info.get(
            "date_of_birth", ""
        )
        user_states[from_id]["responses"]["member_gender"] = verified_info.get(
            "gender", ""
        )
    elif flow_type == "Motor Insurance":
        user_states[from_id]["responses"]["motor_member_name"] = verified_info.get(
            "name", ""
        )
        user_states[from_id]["responses"]["motor_member_dob"] = verified_info.get(
            "date_of_birth", ""
        )
        user_states[from_id]["responses"]["motor_member_gender"] = verified_info.get(
            "gender", ""
        )

    # Move to the next stage in the flow without showing summary
    if flow_type == "Medical Insurance":
        user_states[from_id]["stage"] = "medical_marital_status"
        marital_question = f"Please confirm the marital status of {verified_info.get('name', 'the member')}"
        send_interactive_options(
            from_id, marital_question, ["Single", "Married"], user_states
        )
        store_interaction(
            from_id, "Bot asked for marital status", marital_question, user_states
        )
        user_states[from_id]["responses"]["medical_question_marital_status"] = (
            marital_question
        )

    elif flow_type == "Motor Insurance":
        user_states[from_id]["stage"] = "motor_driving_license"
        license_question = f"Please Uplaod your Driving License"
        send_whatsapp_message(from_id, license_question)
        store_interaction(
            from_id, "Bot asked for vehicle info", license_question, user_states
        )
        user_states[from_id]["responses"]["motor_driving_license"] = license_question


# ?TodoDriving License


async def process_uploaded_license_document(
    from_id: str,
    document_data: bytes,
    mime_type: str,
    filename: str,
    user_states: dict,
    flow_type: str = None,
) -> dict:
    mime_to_ext = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
    file_ext = mime_to_ext.get(mime_type)
    if not file_ext:
        send_whatsapp_message(
            from_id, "Unsupported file type. Please upload a PDF, JPG, or PNG file."
        )
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        temp_file.write(document_data)
        temp_file.flush()
        temp_path = temp_file.name

    try:
        if file_ext == ".pdf":
            extracted_info = await extract_pdf_driving_license(temp_path)
        else:
            extracted_info = await extract_image_driving_license(temp_path)

        if not extracted_info or all(value == "" for value in extracted_info.values()):
            print(f"Extraction failed or returned empty for {filename}")
            return None

        user_states[from_id]["motor_driving_license_document_name"] = filename
        return extracted_info
    except Exception as e:
        print(f"Error in process_uploaded_document: {e}")
        return None
    finally:
        os.unlink(temp_path)


async def display_license_extracted_info(
    from_id: str, extracted_info: dict, user_states: dict, flow_type: str = None
):
    # Define the fields to display
    fields_to_display = [
        "name",
        "license_no",
        "date_of_birth",
        "nationality",
        "issue_date",
        "expiry_date",
        "traffic_code_no",
        "place_of_issue",
        "permitted_vehicles",
    ]

    # Store the extracted info
    user_states[from_id]["motor_license_extracted_info"] = extracted_info
    user_states[from_id]["motor_license_verified_info"] = (
        extracted_info.copy()
    )  # Create a copy that can be edited

    # Create a formatted message with all extracted information
    message = "Here is the information from your driving license:\n\n"

    for field in fields_to_display:
        field_value = extracted_info.get(field, "")
        if field_value:  # Only include fields that have values
            message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

    # Send the message with all extracted information
    send_whatsapp_message(from_id, message)
    store_interaction(
        from_id, "License document information displayed", message, user_states
    )

    # Ask if the information is correct
    user_states[from_id]["stage"] = "lience_document_info_confirmation"
    confirmation_question = "Is all the information correct?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(
        from_id,
        "Bot asked for license information confirmation",
        confirmation_question,
        user_states,
    )


async def merge_id_license_information(
    from_id: str, back_extracted_info: dict, user_states: dict, flow_type: str = None
):
    # Retrieve the front side information
    front_info = user_states[from_id]["motor_license_verified_info"]

    # Merge the information, prioritizing back side for missing fields
    # but front side for duplicated fields
    merged_info = {}

    # Start with all back info
    for key, value in back_extracted_info.items():
        if value:  # Only include non-empty values
            merged_info[key] = value

    # Add front info, preserving existing values
    for key, value in front_info.items():
        if (
            value and key not in merged_info
        ):  # Only add if not already present from back
            merged_info[key] = value

    # Update the verified_info with the merged data
    user_states[from_id]["motor_license_verified_info"] = merged_info

    # Define the fields to display
    fields_to_display = [
        "name",
        "license_no",
        "date_of_birth",
        "nationality",
        "issue_date",
        "expiry_date",
        "traffic_code_no",
        "place_of_issue",
        "permitted_vehicles",
    ]

    # Create a formatted message with all extracted information
    message = "Here is the complete information from your Emirates ID:\n\n"

    for field in fields_to_display:
        field_value = merged_info.get(field, "")
        if field_value:  # Only include fields that have values
            message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

    # Send the message with all extracted information
    send_whatsapp_message(from_id, message)
    store_interaction(
        from_id, "Complete document information displayed", message, user_states
    )

    # Ask if the information is correct
    user_states[from_id]["stage"] = "lience_document_info_confirmation"
    confirmation_question = "Is all the information correct?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(
        from_id,
        "Bot asked for information confirmation",
        confirmation_question,
        user_states,
    )


async def handle_lience_document_edit(
    from_id: str, user_states: dict, field_to_edit=None, new_value=None
):
    # Define the fields that can be edited
    editable_fields = [
        "name",
        "license_no",
        "date_of_birth",
        "nationality",
        "issue_date",
        "expiry_date",
        "traffic_code_no",
        "place_of_issue",
        "permitted_vehicles",
    ]

    # If we're just starting the editing process
    if field_to_edit is None and new_value is None:
        user_states[from_id]["stage"] = "license_select_field_to_edit"

        # Create a list of options that only includes fields that have values
        edit_options = []
        for field in editable_fields:
            if user_states[from_id]["motor_license_verified_info"].get(field, ""):
                edit_options.append(field.replace("_", " ").title())

        select_field_message = "Which field would you like to edit? When you're finished editing, say 'Done'."
        send_interactive_options(
            from_id, select_field_message, edit_options, user_states
        )
        store_interaction(
            from_id, "Bot asked which field to edit", select_field_message, user_states
        )
        return

    # If user has selected a field to edit
    elif field_to_edit and new_value is None:
        # Convert display name back to field name
        field_key = field_to_edit.lower().replace(" ", "_")

        if field_key in editable_fields:
            user_states[from_id]["lience_editing_field"] = field_key
            user_states[from_id]["stage"] = "lience_entering_new_value"

            current_value = user_states[from_id]["motor_license_verified_info"].get(
                field_key, ""
            )
            edit_prompt = f"The current value for {field_to_edit} is: {current_value}\n\nPlease enter the new value:"

            # Special handling for gender field - use interactive options
            if field_key == "gender":
                send_interactive_options(
                    from_id, edit_prompt, ["Male", "Female"], user_states
                )
            else:
                send_whatsapp_message(from_id, edit_prompt)

            store_interaction(
                from_id,
                f"Bot asked for new value for {field_key}",
                edit_prompt,
                user_states,
            )
        return

    # If user has provided a new value
    elif new_value and user_states[from_id]["stage"] == "lience_entering_new_value":
        field_key = user_states[from_id]["lience_editing_field"]

        # Update the value in verified_info
        user_states[from_id]["motor_license_verified_info"][field_key] = new_value

        # Confirm the update to the user
        confirmation = f"Updated {field_key.replace('_', ' ').title()} to: {new_value}"
        send_whatsapp_message(from_id, confirmation)
        store_interaction(from_id, f"Updated {field_key}", confirmation, user_states)

        # Ask if they want to edit more or if they're done
        done_question = "Would you like to edit another field?"
        send_yes_no_options(from_id, done_question, user_states)
        user_states[from_id]["stage"] = "licnese_check_continue_editing"
        store_interaction(
            from_id, "Bot asked if user wants to edit more", done_question, user_states
        )
        return


async def complete_licence_document_editing(
    from_id: str, user_states: dict, flow_type: str = None
):
    # Update member information with the verified info
    motor_license_verified_info = user_states[from_id]["motor_license_verified_info"]

    # Send a summary of the final information
    summary_message = "Here's the final information after your edits:\n\n"

    for field, value in motor_license_verified_info.items():
        if value:  # Only include fields that have values
            summary_message += f"*{field.replace('_', ' ').title()}*: {value}\n"

    send_whatsapp_message(from_id, summary_message)
    store_interaction(from_id, "Document editing summary", summary_message, user_states)

    # Ask for final confirmation
    user_states[from_id]["stage"] = "lience_final_document_confirmation"
    confirmation_question = "Is all the information correct now?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(
        from_id, "Bot asked for final confirmation", confirmation_question, user_states
    )


async def proceed_with_license_verified_document(
    from_id: str, user_states: dict, flow_type: str = None
):
    motor_license_verified_info = user_states[from_id]["motor_license_verified_info"]

    # Update member information with the verified info

    user_states[from_id]["responses"]["motor_licence_name"] = (
        motor_license_verified_info.get("name", "")
    )
    user_states[from_id]["responses"]["motor_licence_dob"] = (
        motor_license_verified_info.get("date_of_birth", "")
    )
    user_states[from_id]["responses"]["motor_licence_license_no"] = (
        motor_license_verified_info.get("license_no", "")
    )

    # Send confirmation message
    confirmation = "Thank you for confirming. We'll proceed with this information."
    send_whatsapp_message(from_id, confirmation)
    store_interaction(
        from_id, "Document information confirmed", confirmation, user_states
    )


async def proceed__license_without_edits(
    from_id: str, user_states: dict, flow_type: str = None
):
    motor_license_verified_info = user_states[from_id]["motor_license_verified_info"]

    # Store the verified license information in responses
    user_states[from_id]["responses"]["motor_licence_name"] = (
        motor_license_verified_info.get("name", "")
    )
    user_states[from_id]["responses"]["motor_licence_dob"] = (
        motor_license_verified_info.get("date_of_birth", "")
    )
    user_states[from_id]["responses"]["motor_licence_license_no"] = (
        motor_license_verified_info.get("license_no", "")
    )

    # Send confirmation message to user
    confirmation_message = "Thank you for confirming your driving license information."
    send_whatsapp_message(from_id, confirmation_message)
    store_interaction(
        from_id, "License information confirmed", confirmation_message, user_states
    )

    # Proceed to mulkiya upload stage
    user_states[from_id]["stage"] = "motor_vechile_mulkiya"
    mulkiya_question = "Now,Let's move on to: Please Uplaod your Vehicle Mulkiya"
    send_whatsapp_message(from_id, mulkiya_question)
    store_interaction(
        from_id, "Bot asked for vehicle mulkiya", mulkiya_question, user_states
    )
    user_states[from_id]["responses"]["motor_vechile_mulkiya"] = mulkiya_question


# ToDOMulkiya


async def process_uploaded_mulkiya_document(
    from_id: str,
    document_data: bytes,
    mime_type: str,
    filename: str,
    user_states: dict,
    flow_type: str = None,
) -> dict:
    mime_to_ext = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
    file_ext = mime_to_ext.get(mime_type)
    if not file_ext:
        send_whatsapp_message(
            from_id, "Unsupported file type. Please upload a PDF, JPG, or PNG file."
        )
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        temp_file.write(document_data)
        temp_file.flush()
        temp_path = temp_file.name

    try:
        if file_ext == ".pdf":
            extracted_info = await extract_pdf_mulkiya(temp_path)
        else:
            extracted_info = await extract_image_mulkiya(temp_path)

        if not extracted_info or all(value == "" for value in extracted_info.values()):
            print(f"Extraction failed or returned empty for {filename}")
            return None

        user_states[from_id]["motor_driving_mulkiya_document_name"] = filename
        return extracted_info
    except Exception as e:
        print(f"Error in process_uploaded_document: {e}")
        return None
    finally:
        os.unlink(temp_path)


async def display_mulkiya_extracted_info(
    from_id: str, extracted_info: dict, user_states: dict, flow_type: str = None
):
    # Define the fields to display
    fields_to_display = [
        "owner",
        "traffic_plate_no",
        "tc_no",
        "nationality",
        "reg_date",
        "expiry_date",
        "ins_exp",
        "policy_no",
        "place_of_issue",
        "model_no",
        "number_of_pass",
        "origin",
        "vehicle_type",
        "empty_weight",
        "engine_no",
        "chassis_no",
        "gvw",
    ]

    # Store the extracted info
    user_states[from_id]["motor_mulkiya_extracted_info"] = extracted_info
    user_states[from_id]["motor_mulkiya_verified_info"] = (
        extracted_info.copy()
    )  # Create a copy that can be edited

    # Create a formatted message with all extracted information
    message = "Here is the information from your Vehicle Mulkiya:\n\n"

    for field in fields_to_display:
        field_value = extracted_info.get(field, "")
        if field_value:  # Only include fields that have values
            message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

    # Send the message with all extracted information
    send_whatsapp_message(from_id, message)
    store_interaction(
        from_id, "Mulkiya document information displayed", message, user_states
    )

    # Ask if the information is correct
    user_states[from_id]["stage"] = "mulkiya_document_info_confirmation"
    confirmation_question = "Is all the information correct?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(
        from_id,
        "Bot asked for mulkiya information confirmation",
        confirmation_question,
        user_states,
    )


async def merge_id_mulkiya_information(
    from_id: str, back_extracted_info: dict, user_states: dict, flow_type: str = None
):
    # Retrieve the front side information
    front_info = user_states[from_id]["motor_mulkiya_verified_info"]

    # Merge the information, prioritizing back side for missing fields
    # but front side for duplicated fields
    merged_info = {}

    # Start with all back info
    for key, value in back_extracted_info.items():
        if value:  # Only include non-empty values
            merged_info[key] = value

    # Add front info, preserving existing values
    for key, value in front_info.items():
        if (
            value and key not in merged_info
        ):  # Only add if not already present from back
            merged_info[key] = value

    # Update the verified_info with the merged data
    user_states[from_id]["motor_mulkiya_verified_info"] = merged_info

    # Define the fields to display
    fields_to_display = [
        "owner",
        "traffic_plate_no",
        "tc_no",
        "nationality",
        "reg_date",
        "expiry_date",
        "ins_exp",
        "policy_no",
        "place_of_issue",
        "model_no",
        "number_of_pass",
        "origin",
        "vehicle_type",
        "empty_weight",
        "engine_no",
        "chassis_nogvw",
    ]

    # Create a formatted message with all extracted information
    message = "Here is the complete information from your Vechile Mulkiya:\n\n"

    for field in fields_to_display:
        field_value = merged_info.get(field, "")
        if field_value:  # Only include fields that have values
            message += f"*{field.replace('_', ' ').title()}*: {field_value}\n"

    # Send the message with all extracted information
    send_whatsapp_message(from_id, message)
    store_interaction(
        from_id, "Complete document information displayed", message, user_states
    )

    # Ask if the information is correct
    user_states[from_id]["stage"] = "mulkiya_document_info_confirmation"
    confirmation_question = "Is all the information correct?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(
        from_id,
        "Bot asked for information confirmation",
        confirmation_question,
        user_states,
    )


async def handle_mulkiya_document_edit(
    from_id: str, user_states: dict, field_to_edit=None, new_value=None
):
    # Define the fields that can be edited
    editable_fields = [
        "owner",
        "traffic_plate_no",
        "tc_no",
        "nationality",
        "reg_date",
        "expiry_date",
        "ins_exp",
        "policy_no",
        "place_of_issue",
        "model_no",
        "number_of_pass",
        "origin",
        "vehicle_type",
        "empty_weight",
        "engine_no",
        "chassis_no",
        "gvw",
    ]

    # If we're just starting the editing process
    if field_to_edit is None and new_value is None:
        user_states[from_id]["stage"] = "mulkiya_select_field_to_edit"

        # Create a list of options that only includes fields that have values
        edit_options = []
        for field in editable_fields:
            if user_states[from_id]["motor_mulkiya_verified_info"].get(field, ""):
                edit_options.append(field.replace("_", " ").title())

        select_field_message = "Which field would you like to edit? When you're finished editing, say 'Done'."
        send_interactive_options(
            from_id, select_field_message, edit_options, user_states
        )
        store_interaction(
            from_id, "Bot asked which field to edit", select_field_message, user_states
        )
        return

    # If user has selected a field to edit
    elif field_to_edit and new_value is None:
        # Convert display name back to field name
        field_key = field_to_edit.lower().replace(" ", "_")

        if field_key in editable_fields:
            user_states[from_id]["mulkiya_editing_field"] = field_key
            user_states[from_id]["stage"] = "mulkiya_entering_new_value"

            current_value = user_states[from_id]["motor_mulkiya_verified_info"].get(
                field_key, ""
            )
            edit_prompt = f"The current value for {field_to_edit} is: {current_value}\n\nPlease enter the new value:"

            # Special handling for gender field - use interactive options
            if field_key == "gender":
                send_interactive_options(
                    from_id, edit_prompt, ["Male", "Female"], user_states
                )
            else:
                send_whatsapp_message(from_id, edit_prompt)

            store_interaction(
                from_id,
                f"Bot asked for new value for {field_key}",
                edit_prompt,
                user_states,
            )
        return

    # If user has provided a new value
    elif new_value and user_states[from_id]["stage"] == "mulkiya_entering_new_value":
        field_key = user_states[from_id]["mulkiya_editing_field"]

        # Update the value in mulkiya_info
        user_states[from_id]["motor_mulkiya_verified_info"][field_key] = new_value

        # Confirm the update to the user
        confirmation = f"Updated {field_key.replace('_', ' ').title()} to: {new_value}"
        send_whatsapp_message(from_id, confirmation)
        store_interaction(from_id, f"Updated {field_key}", confirmation, user_states)

        # Ask if they want to edit more or if they're done
        done_question = "Would you like to edit another field?"
        send_yes_no_options(from_id, done_question, user_states)
        user_states[from_id]["stage"] = "mulkiya_check_continue_editing"
        store_interaction(
            from_id, "Bot asked if user wants to edit more", done_question, user_states
        )
        return


async def complete_mulkiya_document_editing(
    from_id: str, user_states: dict, flow_type: str = None
):
    # Update member information with the verified info
    motor_mulkiya_verified_info = user_states[from_id]["motor_mulkiya_verified_info"]

    # Send a summary of the final information
    summary_message = "Here's the final information after your edits:\n\n"

    for field, value in motor_mulkiya_verified_info.items():
        if value:  # Only include fields that have values
            summary_message += f"*{field.replace('_', ' ').title()}*: {value}\n"

    send_whatsapp_message(from_id, summary_message)
    store_interaction(from_id, "Document editing summary", summary_message, user_states)

    # Ask for final confirmation
    user_states[from_id]["stage"] = "mulkiya_final_document_confirmation"
    confirmation_question = "Is all the information correct now?"
    send_yes_no_options(from_id, confirmation_question, user_states)
    store_interaction(
        from_id, "Bot asked for final confirmation", confirmation_question, user_states
    )


async def proceed_with_mulkiya_verified_document(
    from_id: str, user_states: dict, flow_type: str = None
):
    motor_mulkiya_verified_info = user_states[from_id]["motor_mulkiya_verified_info"]

    # Update member information with the verified info

    user_states[from_id]["responses"]["motor_mulkiya_owner_name"] = (
        motor_mulkiya_verified_info.get("owner", "")
    )
    user_states[from_id]["responses"]["motor_mulkiya_traffic_plate_no"] = (
        motor_mulkiya_verified_info.get("traffic_plate_no", "")
    )
    user_states[from_id]["responses"]["motor_mulkiya_tc_no"] = (
        motor_mulkiya_verified_info.get("tc_no", "")
    )
    user_states[from_id]["responses"]["motor_mulkiya_nationality"] = (
        motor_mulkiya_verified_info.get("nationality", "")
    )

    # Send confirmation message
    confirmation = "Thank you for confirming. We'll proceed with this information."
    send_whatsapp_message(from_id, confirmation)
    store_interaction(
        from_id, "Document information confirmed", confirmation, user_states
    )


async def proceed__mulkiya_without_edits(
    from_id: str, user_states: dict, flow_type: str = None
):
    try:
        # Store verified mulkiya information
        motor_mulkiya_verified_info = user_states[from_id][
            "motor_mulkiya_verified_info"
        ]
        user_states[from_id]["responses"]["motor_mulkiya_owner_name"] = (
            motor_mulkiya_verified_info.get("owner", "")
        )
        user_states[from_id]["responses"]["motor_mulkiya_traffic_plate_no"] = (
            motor_mulkiya_verified_info.get("traffic_plate_no", "")
        )
        user_states[from_id]["responses"]["motor_mulkiya_tc_no"] = (
            motor_mulkiya_verified_info.get("tc_no", "")
        )
        user_states[from_id]["responses"]["motor_mulkiya_nationality"] = (
            motor_mulkiya_verified_info.get("nationality", "")
        )

        # Send confirmation message
        confirmation_message = (
            "Thank you for confirming your Vehicle Mulkiya information."
        )
        send_success = send_whatsapp_message(from_id, confirmation_message)
        store_interaction(
            from_id, "Mulkiya information confirmed", confirmation_message, user_states
        )

        if not send_success:
            print(f"Failed to send confirmation message to {from_id}")
            send_whatsapp_message(
                from_id,
                "There was an issue processing your request. Please try again later.",
            )
            return

        # Set the stage to motor_vehicle_wish_to_buy
        user_states[from_id]["stage"] = "motor_vehicle_wish_to_buy"
        print(f"Stage set to motor_vehicle_wish_to_buy for user {from_id}")

        # Send interactive options for insurance type
        wish_to_buy_question = "Now,let's move on to You Wish to Buy"
        valid_wish_to_buy = ["Comprehensive", "Third Party"]
        options_success = send_interactive_options(
            from_id, wish_to_buy_question, valid_wish_to_buy, user_states
        )

        if options_success:
            store_interaction(
                from_id,
                "Bot asked for insurance type to buy",
                wish_to_buy_question,
                user_states,
            )
            print(
                f"Interactive options sent successfully to {from_id}: {valid_wish_to_buy}"
            )
        else:
            print(f"Failed to send interactive options to {from_id}")
            # Fallback: Send a text prompt to keep the flow moving
            fallback_message = "Please reply with the type of insurance  You Wish to Buy: 'Comprehensive' or 'Third Party'."
            send_whatsapp_message(from_id, fallback_message)
            store_interaction(
                from_id,
                "Fallback prompt for insurance type",
                fallback_message,
                user_states,
            )

    except Exception as e:
        print(f"Error in proceed__mulkiya_without_edits for user {from_id}: {str(e)}")
        error_message = "An error occurred while processing your mulkiya information. Please try again or contact support."
        send_whatsapp_message(from_id, error_message)
        store_interaction(
            from_id, "Error in mulkiya processing", f"Error: {str(e)}", user_states
        )


async def extract_excel_sme_census(file_path: str) -> dict:
    """
    Extract information from SME Census Excel sheet and return as JSON

    Args:
        file_path (str): Path to the Excel file

    Returns:
        Dict: Structured information extracted from the Excel sheet with list of employee records
    """
    try:
        import pandas as pd
        import logging

        # Read the Excel file
        df = pd.read_excel(file_path)
        logging.info(
            f"Successfully read Excel file with {len(df)} rows and {len(df.columns)} columns"
        )

        # Convert DataFrame to list of dictionaries
        employees_list = []

        for index, row in df.iterrows():
            employee_record = {
                "sr_no": str(row.get("SR No.", "")).strip()
                if pd.notna(row.get("SR No."))
                else "",
                "first_name": str(row.get("First Name ", "")).strip()
                if pd.notna(row.get("First Name "))
                else "",
                "gender": str(row.get("Gender", "")).strip()
                if pd.notna(row.get("Gender"))
                else "",
                "date_of_birth": str(row.get("Date Of Birth ", "")).strip()
                if pd.notna(row.get("Date Of Birth "))
                else "",
                "nationality": str(row.get("Nationality", "")).strip()
                if pd.notna(row.get("Nationality"))
                else "",
                "marital_status": str(row.get("Marital Status", "")).strip()
                if pd.notna(row.get("Marital Status"))
                else "",
                "relation": str(row.get("Relation", "")).strip()
                if pd.notna(row.get("Relation"))
                else "",
                "visa_issued_location": str(row.get("Visa Issued Location", "")).strip()
                if pd.notna(row.get("Visa Issued Location"))
                else "",
            }
            employees_list.append(employee_record)

        # Create the final result structure
        result = {
            "total_employees": len(employees_list),
            "employees": employees_list,
            "columns_found": df.columns.tolist(),
            "file_processed": True,
        }

        logging.info(
            f"Successfully extracted {len(employees_list)} employee records from Excel file"
        )
        return result

    except Exception as e:
        import logging
        from fastapi import HTTPException

        logging.error(f"Error in extract_excel_sme_census: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


async def process_sme_excel(
    from_id: str, document_data: bytes, filename: str, user_states: dict
):
    """
    Process SME Census Excel file
    """
    try:
        # Save the Excel file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(document_data)
            temp_file.flush()
            temp_path = temp_file.name

        # Extract Excel data
        excel_data = await extract_excel_sme_census(temp_path)

        # Store the Excel data in user_states
        user_states[from_id]["sme_excel_data"] = excel_data

        # Send acknowledgment
        ack_message = "Excel file uploaded successfully!"
        send_whatsapp_message(from_id, ack_message)
        store_interaction(
            from_id, "Excel upload acknowledgment", ack_message, user_states
        )

        import asyncio

        await asyncio.sleep(1)

        # Send completion message
        completion_message = "Thank you for sharing the details. We will inform Shafeeque Shanavas from Wehbe Insurance to assist you further with your enquiry. Please wait for further assistance. If you have any questions, please contact support@insuranceclub.ae"
        send_whatsapp_message(from_id, completion_message)
        store_interaction(
            from_id, "SME completion confirmation", completion_message, user_states
        )

        # Clean up temporary file
        os.unlink(temp_path)

        # Transition to next stage
        await asyncio.sleep(1)
        from services.whatsapp import send_yes_no_options

        send_yes_no_options(
            from_id, "Would you like to purchase our insurance again?", user_states
        )
        user_states[from_id]["stage"] = "waiting_for_new_query"

        return excel_data

    except Exception as e:
        print(f"Error processing Excel file: {e}")
        if "temp_path" in locals():
            os.unlink(temp_path)
        send_whatsapp_message(
            from_id,
            "Sorry, there was an error processing your Excel file. Please ensure it's in the correct format and try again.",
        )
        return None
