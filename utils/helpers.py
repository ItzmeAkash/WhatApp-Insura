import re
import time
import logging
import re
from typing import Dict, Any, Optional
from fastapi import HTTPException
from langchain_groq import ChatGroq
from langchain.chains import create_extraction_chain
from langchain_core.messages import HumanMessage
from langchain_core.pydantic_v1 import BaseModel, Field

from PIL import Image,ImageFilter
import os
import io
import base64
import json

from .VisionModel import DocumentVisionOCR
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
        
# utils/helpers.py
import requests

def emaf_document(response_dict):
    payload = {
        "name": response_dict.get("May I know your name, please?"),
        "network_id": response_dict.get("emaf_company_id"),
        "phone": response_dict.get("May I kindly ask for your phone number, please?"),
    }
    emaf_api = "https://www.insuranceclub.ae/Api/emaf"
    try:
        respond = requests.post(emaf_api, json=payload, timeout=10)
        respond.raise_for_status()
        emaf_id = respond.json()["id"]
        return emaf_id
    except requests.RequestException as e:
        print(f"Error calling EMAF API: {e}")
        return None
    


async def extract_image_info1(file_path: str) -> Dict:
    """
    Extract information from  document and return as JSON
    
    Args:
        file_path (str): Path to the image file
        
    Returns:
        Dict: Structured information extracted from the document
    """
    try:
        # Preprocess the image
        image = Image.open(file_path)
        image = image.convert('L')  # Convert to grayscale
        image = image.resize((image.width * 2, image.height * 2))  # Resize to improve OCR accuracy
        image = image.filter(ImageFilter.SHARPEN)  # Sharpen the image to improve OCR accuracy
        
        # Extract text from JPG image
        vision_model = DocumentVisionOCR()
        
        # Create a specialized prompt for license documents
        license_prompt = """
        Extract ALL English text from this license.
        Pay special attention to:
        - Name
        - Id Number
        - Date of Birth
        - Nationality
        - Issuing Date
        - Expiry Date
        - Sex
        - Card Number
        - Occupation
        - Employer
        - Issuing Place
        
        Capture all text exactly as shown, preserving numbers and codes precisely.
        If any mentioned information is missing, recheck and extract everything accurately.
        """
        
        # Use the extract_text_from_image method with the preprocessed image
        vision_text = vision_model.extract_text_from_image(image, prompt=license_prompt)
        logging.info("Extracted text from license document")
        
        # Initialize LLM and create extraction chain
        llm = ChatGroq(
            model=os.getenv('LLM_MODEL'),
            temperature=0,
            api_key=os.getenv('GROQ_API_KEY')
        )
        
        # Enhanced extraction prompt to ensure structured JSON output
        extraction_prompt = f"""
        Extract the following information from this document.
        Respond with ONLY a valid JSON object - no explanations, no markdown formatting.
        
        For dates, use format DD-MM-YYYY if possible.
        For numbers and codes, preserve exact formatting including any special characters.
        If a piece of information is not found, use an empty string.
        
        Text to extract from:
        {vision_text}
        
        JSON format:
        {{
                "name": "",
                "id_number": "",
                "date_of_birth": "",
                "nationality": "",
                "issue_date": "",
                "expiry_date": "",
                "gender": "",
                "card_number": "",
                "occupation": "",
                "employer": "",
                "issuing_place": "",
            }}
        
        
        IMPORTANT: Return ONLY the JSON object with no additional text, code blocks, or explanations.
        """
        
        # Directly use the LLM to extract structured information
        extraction_response = llm.invoke(extraction_prompt)
        extracted_content = extraction_response.content
        logging.info("LLM extraction completed")
        
        # Create default empty result structure
        default_result = {
                "name": "",
                "id_number": "",
                "date_of_birth": "",
                "nationality": "",
                "issue_date": "",
                "expiry_date": "",
                "gender": "",
                "card_number": "",
                "occupation": "",
                "employer": "",
                "issuing_place": "",
            }
        
        # Try to parse the response as JSON
        try:
            # First, attempt to parse as a JSON string
            result = json.loads(extracted_content)
            logging.info("Successfully parsed JSON response")
        except json.JSONDecodeError as e:
            logging.warning(f"Direct JSON parsing failed: {e}")
            try:
                # Find JSON-like content between curly braces
                start = extracted_content.find('{')
                end = extracted_content.rfind('}') + 1
                
                if start >= 0 and end > start:
                    cleaned_content = extracted_content[start:end]
                    # Replace potential newlines, tabs and fix common JSON format issues
                    cleaned_content = cleaned_content.replace('\n', ' ').replace('\t', ' ')
                    cleaned_content = re.sub(r',\s*}', '}', cleaned_content)  # Remove trailing commas
                    
                    result = json.loads(cleaned_content)
                    logging.info("Successfully parsed JSON after cleaning")
                else:
                    raise ValueError("No valid JSON structure found")
            except (ValueError, json.JSONDecodeError) as e:
                logging.warning(f"JSON parsing failed: {e}. Creating empty structure.")
                result = default_result
        
        # Ensure all expected keys are present in the result
        for key in default_result:
            if key not in result:
                result[key] = ""
        
        return result
    except Exception as e:
        logging.error(f"Error in extract_image_driving_license: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


async def extract_pdf_info1(file_path: str) -> Dict:
    """
    Extract information from JPG License document and return as JSON
    
    Args:
        file_path (str): Path to the image file
        
    Returns:
        Dict: Structured information extracted from the driving license document
    """
    try:
        # Preprocess the image
       
        # Extract text from JPG image
        vision_model = DocumentVisionOCR()
        
        # Create a specialized prompt for license documents
        emirate_prompt = """
        Extract all English text from this license. 

        Pay special attention to the following details:
        - Name  
        - ID Number (Ensure the ID number starts in the format: 784-YYYY-123456-9. This is an example.)  
        - Date of Birth  
        - Nationality  
        - Issuing Date  
        - Expiry Date  
        - Sex  
        - Card Number  
        - Occupation  
        - Employer  
        - Issuing Place  

        Capture all text exactly as shown, preserving numbers and codes precisely.  
        Ensure that all the listed details are extracted from the given document.  
        If any mentioned information is missing, recheck and extract everything accurately.
        """

        
        # Use the extract_text_from_image method with the preprocessed image
        vision_text = vision_model.extract_text_to_string(file_path, prompt=emirate_prompt)
        logging.info("Extracted text from license document")
        
        # Initialize LLM and create extraction chain
        llm = ChatGroq(
            model=os.getenv('LLM_MODEL'),
            temperature=0,
            api_key=os.getenv('GROQ_API_KEY')
        )
        
        # Enhanced extraction prompt to ensure structured JSON output
        extraction_prompt = f"""
        Extract the following information from this Emirate document
        Respond with ONLY a valid JSON object - no explanations, no markdown formatting.
        
        For dates, use format DD-MM-YYYY if possible.
        For numbers and codes, preserve exact formatting including any special characters.
        If a piece of information is not found, use an empty string.
        
        Text to extract from:
        {vision_text}
        
        JSON format:
       {{
                "name": "",
                "id_number": "",
                "date_of_birth": "",
                "nationality": "",
                "issue_date": "",
                "expiry_date": "",
                "gender": "",
                "card_number": "",
                "occupation": "",
                "employer": "",
                "issuing_place": "",
            }}
        
        IMPORTANT: Return ONLY the JSON object with no additional text, code blocks, or explanations.
        """
        
        # Directly use the LLM to extract structured information
        extraction_response = llm.invoke(extraction_prompt)
        extracted_content = extraction_response.content
        logging.info("LLM extraction completed")
        
        # Create default empty result structure
        default_result =  {
                "name": "",
                "id_number": "",
                "date_of_birth": "",
                "nationality": "",
                "issue_date": "",
                "expiry_date": "",
                "gender": "",
                "card_number": "",
                "occupation": "",
                "employer": "",
                "issuing_place": "",
            }
        
        # Try to parse the response as JSON
        try:
            # First, attempt to parse as a JSON string
            result = json.loads(extracted_content)
            logging.info("Successfully parsed JSON response")
        except json.JSONDecodeError as e:
            logging.warning(f"Direct JSON parsing failed: {e}")
            try:
                # Find JSON-like content between curly braces
                start = extracted_content.find('{')
                end = extracted_content.rfind('}') + 1
                
                if start >= 0 and end > start:
                    cleaned_content = extracted_content[start:end]
                    # Replace potential newlines, tabs and fix common JSON format issues
                    cleaned_content = cleaned_content.replace('\n', ' ').replace('\t', ' ')
                    cleaned_content = re.sub(r',\s*}', '}', cleaned_content)  # Remove trailing commas
                    
                    result = json.loads(cleaned_content)
                    logging.info("Successfully parsed JSON after cleaning")
                else:
                    raise ValueError("No valid JSON structure found")
            except (ValueError, json.JSONDecodeError) as e:
                logging.warning(f"JSON parsing failed: {e}. Creating empty structure.")
                result = default_result
        
        # Ensure all expected keys are present in the result
        for key in default_result:
            if key not in result:
                result[key] = ""
        
        return result
    except Exception as e:
        logging.error(f"Error in extract_image_driving_license: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")




async def extract_image_driving_license(file_path: str) -> Dict:
    """
    Extract information from JPG License document and return as JSON
    
    Args:
        file_path (str): Path to the image file
        
    Returns:
        Dict: Structured information extracted from the driving license document
    """
    try:
        # Preprocess the image
        image = Image.open(file_path)
        image = image.convert('L')  # Convert to grayscale
        image = image.resize((image.width * 2, image.height * 2))  # Resize to improve OCR accuracy
        image = image.filter(ImageFilter.SHARPEN)  # Sharpen the image to improve OCR accuracy
        
        # Extract text from JPG image
        vision_model = DocumentVisionOCR()
        
        # Create a specialized prompt for license documents
        license_prompt = """
        Extract ALL English text from this license.
        Pay special attention to:
        - Name
        - License No
        - Date of Birth
        - Issue Date
        - Expiry Date
        - Nationality
        - Place of Issue
        - Traffic Code No
        - Permitted Vehicles
        
        Capture all text exactly as shown, preserving numbers and codes precisely.
        If any mentioned information is missing, recheck and extract everything accurately.
        """
        
        # Use the extract_text_from_image method with the preprocessed image
        vision_text = vision_model.extract_text_from_image(image, prompt=license_prompt)
        logging.info("Extracted text from license document")
        
        # Initialize LLM and create extraction chain
        llm = ChatGroq(
            model=os.getenv('LLM_MODEL'),
            temperature=0,
            api_key=os.getenv('GROQ_API_KEY')
        )
        
        # Enhanced extraction prompt to ensure structured JSON output
        extraction_prompt = f"""
        Extract the following information from this Driving License.
        Respond with ONLY a valid JSON object - no explanations, no markdown formatting.
        
        For dates, use format DD-MM-YYYY if possible.
        For numbers and codes, preserve exact formatting including any special characters.
        If a piece of information is not found, use an empty string.
        
        Text to extract from:
        {vision_text}
        
        JSON format:
        {{
            "name": "",
            "license_no": "",
            "date_of_birth": "",
            "nationality": "",
            "issue_date": "",
            "expiry_date": "",
            "traffic_code_no": "",
            "place_of_issue": "",
            "permitted_vehicles": ""
        }}
        
        IMPORTANT: Return ONLY the JSON object with no additional text, code blocks, or explanations.
        """
        
        # Directly use the LLM to extract structured information
        extraction_response = llm.invoke(extraction_prompt)
        extracted_content = extraction_response.content
        logging.info("LLM extraction completed")
        
        # Create default empty result structure
        default_result = {
            "name": "",
            "license_no": "",
            "date_of_birth": "",
            "nationality": "",
            "issue_date": "",
            "expiry_date": "",
            "traffic_code_no": "",
            "place_of_issue": "",
            "permitted_vehicles": ""
        }
        
        # Try to parse the response as JSON
        try:
            # First, attempt to parse as a JSON string
            result = json.loads(extracted_content)
            logging.info("Successfully parsed JSON response")
        except json.JSONDecodeError as e:
            logging.warning(f"Direct JSON parsing failed: {e}")
            try:
                # Find JSON-like content between curly braces
                start = extracted_content.find('{')
                end = extracted_content.rfind('}') + 1
                
                if start >= 0 and end > start:
                    cleaned_content = extracted_content[start:end]
                    # Replace potential newlines, tabs and fix common JSON format issues
                    cleaned_content = cleaned_content.replace('\n', ' ').replace('\t', ' ')
                    cleaned_content = re.sub(r',\s*}', '}', cleaned_content)  # Remove trailing commas
                    
                    result = json.loads(cleaned_content)
                    logging.info("Successfully parsed JSON after cleaning")
                else:
                    raise ValueError("No valid JSON structure found")
            except (ValueError, json.JSONDecodeError) as e:
                logging.warning(f"JSON parsing failed: {e}. Creating empty structure.")
                result = default_result
        
        # Ensure all expected keys are present in the result
        for key in default_result:
            if key not in result:
                result[key] = ""
        
        return result
    except Exception as e:
        logging.error(f"Error in extract_image_driving_license: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
    
    
    

#Todo
async def extract_pdf_driving_license(file_path: str) -> Dict:
    """
    Extract information from JPG License document and return as JSON
    
    Args:
        file_path (str): Path to the image file
        
    Returns:
        Dict: Structured information extracted from the driving license document
    """
    try:
        # Preprocess the image
       
        # Extract text from JPG image
        vision_model = DocumentVisionOCR()
        
        # Create a specialized prompt for license documents
        license_prompt = """
        Extract ALL English text from this license.
        Pay special attention to:
        - Name
        - License No
        - Date of Birth
        - Issue Date
        - Expiry Date
        - Nationality
        - Place of Issue
        - Traffic Code No
        - Permitted Vehicles
        
        Capture all text exactly as shown, preserving numbers and codes precisely.
        make sure to extract all provided information in the give document
        If any mentioned information is missing, recheck and extract everything accurately.
        """
        
        # Use the extract_text_from_image method with the preprocessed image
        vision_text = vision_model.extract_text_to_string(file_path, prompt=license_prompt)
        logging.info("Extracted text from license document")
        
        # Initialize LLM and create extraction chain
        llm = ChatGroq(
            model=os.getenv('LLM_MODEL'),
            temperature=0,
            api_key=os.getenv('GROQ_API_KEY')
        )
        
        # Enhanced extraction prompt to ensure structured JSON output
        extraction_prompt = f"""
        Extract the following information from this Driving License.
        Respond with ONLY a valid JSON object - no explanations, no markdown formatting.
        
        For dates, use format DD-MM-YYYY if possible.
        For numbers and codes, preserve exact formatting including any special characters.
        If a piece of information is not found, use an empty string.
        
        Text to extract from:
        {vision_text}
        
        JSON format:
        {{
            "name": "",
            "license_no": "",
            "date_of_birth": "",
            "nationality": "",
            "issue_date": "",
            "expiry_date": "",
            "traffic_code_no": "",
            "place_of_issue": "",
            "permitted_vehicles": ""
        }}
        
        IMPORTANT: Return ONLY the JSON object with no additional text, code blocks, or explanations.
        """
        
        # Directly use the LLM to extract structured information
        extraction_response = llm.invoke(extraction_prompt)
        extracted_content = extraction_response.content
        logging.info("LLM extraction completed")
        
        # Create default empty result structure
        default_result = {
            "name": "",
            "license_no": "",
            "date_of_birth": "",
            "nationality": "",
            "issue_date": "",
            "expiry_date": "",
            "traffic_code_no": "",
            "place_of_issue": "",
            "permitted_vehicles": ""
        }
        
        # Try to parse the response as JSON
        try:
            # First, attempt to parse as a JSON string
            result = json.loads(extracted_content)
            logging.info("Successfully parsed JSON response")
        except json.JSONDecodeError as e:
            logging.warning(f"Direct JSON parsing failed: {e}")
            try:
                # Find JSON-like content between curly braces
                start = extracted_content.find('{')
                end = extracted_content.rfind('}') + 1
                
                if start >= 0 and end > start:
                    cleaned_content = extracted_content[start:end]
                    # Replace potential newlines, tabs and fix common JSON format issues
                    cleaned_content = cleaned_content.replace('\n', ' ').replace('\t', ' ')
                    cleaned_content = re.sub(r',\s*}', '}', cleaned_content)  # Remove trailing commas
                    
                    result = json.loads(cleaned_content)
                    logging.info("Successfully parsed JSON after cleaning")
                else:
                    raise ValueError("No valid JSON structure found")
            except (ValueError, json.JSONDecodeError) as e:
                logging.warning(f"JSON parsing failed: {e}. Creating empty structure.")
                result = default_result
        
        # Ensure all expected keys are present in the result
        for key in default_result:
            if key not in result:
                result[key] = ""
        
        return result
    except Exception as e:
        logging.error(f"Error in extract_image_driving_license: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
    
    
    
