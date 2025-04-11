from json import load
import logging
import os
import base64
import io
import mimetypes
from pathlib import Path

# Import libraries
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from PIL import Image
import fitz  # PyMuPDF for PDF processing
from dotenv import load_dotenv

load_dotenv()
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
class DocumentVisionOCR:
    def __init__(self, api_key=None, model=None, max_tokens=1000, temperature=0.2):
        """
        Initialize Document OCR client that handles both images and PDFs
        
        Args:
            api_key (str, optional): Groq API key. If None, gets from environment.
            model (str, optional): Model name. If None, gets from environment.
            max_tokens (int, optional): Maximum tokens in response. Defaults to 1000.
            temperature (float, optional): Temperature for response. Defaults to 0.2.
        """
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found. Please provide an API key.")
            
        self.model = model or os.getenv('VISION_MODEL')
        if not self.model:
            raise ValueError("VISION_MODEL not found. Please specify a model.")
        
        self.chat = ChatGroq(
            groq_api_key=self.api_key,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        logging.info(f"Initialized DocumentVisionOCR with model: {self.model}")
        
    def encode_image(self, image, max_size=(1000, 1000), quality=85):
        """Encode image to base64 with resizing if needed"""
        # Resize if image is too large
        if image.width > max_size[0] or image.height > max_size[1]:
            image = image.resize(
                (min(image.width, max_size[0]), 
                min(image.height, max_size[1])),
                Image.LANCZOS
            )
        
        # Save with compression
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=quality)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
        
    def extract_text_from_image(self, image, prompt=None):
        """
        Extract text from a single image
        
        Args:
            image (PIL.Image): PIL Image object
            prompt (str, optional): Custom prompt for the vision model
            
        Returns:
            str: Extracted text from the image
        """
        # Encode image
        base64_image = self.encode_image(image)
        
        # Use default or custom prompt
        text_prompt = prompt or (
            "You are an OCR expert. Extract ALL text from this image accurately, "
            "preserving the original formatting as much as possible. Include all visible text."
        )
        
        try:
            # Prepare message with image and prompt
            msg = HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": text_prompt
                    }
                ]
            )
            
            # Invoke OCR
            logging.info("Sending image to vision model for text extraction")
            response = self.chat.invoke([msg])
            return response.content
        except Exception as e:
            logging.error(f"Text Extraction Error: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_path, dpi=300, prompt=None):
        """
        Extract text from a PDF file by converting pages to images
        and performing OCR on each page
        
        Args:
            pdf_path (str): Path to the PDF file
            dpi (int): DPI for rendering PDF pages as images
            prompt (str, optional): Custom prompt for the vision model
            
        Returns:
            dict: Dictionary with page numbers as keys and extracted text as values
        """
        results = {}
        
        try:
            # Open the PDF
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            logging.info(f"Processing PDF with {total_pages} pages at {dpi} DPI")
            
            # Process each page
            for page_num, page in enumerate(pdf_document):
                page_number = page_num + 1
                logging.info(f"Processing page {page_number} of {total_pages}")
                
                # Convert page to an image
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Extract text from the image
                page_prompt = prompt or f"Extract ALL text from page {page_number} of this document. Preserve formatting."
                extracted_text = self.extract_text_from_image(img, prompt=page_prompt)
                
                # Store the result
                results[page_number] = extracted_text
                
            return results
            
        except Exception as e:
            logging.error(f"PDF Processing Error: {e}")
            return None
            
    def extract_text_from_pdf_to_string(self, pdf_path, dpi=300, prompt=None, 
                                        separator="\n\n--- Page {page_num} ---\n\n"):
        """
        Extract text from a PDF file and return as a single string
        
        Args:
            pdf_path (str): Path to the PDF file
            dpi (int): DPI for rendering PDF pages as images
            prompt (str, optional): Custom prompt for the vision model
            separator (str): Text to insert between pages
            
        Returns:
            str: Extracted text from all pages
        """
        results = self.extract_text_from_pdf(pdf_path, dpi, prompt)
        
        if not results:
            return None
            
        # Combine all pages into a single string
        combined_text = ""
        for page_num, text in sorted(results.items()):
            page_separator = separator.format(page_num=page_num)
            combined_text += page_separator + text
            
        return combined_text
    
    def extract_text(self, file_path, dpi=300, prompt=None):
        """
        Extract text from either an image or PDF file
        
        Args:
            file_path (str): Path to the file (image or PDF)
            dpi (int): DPI for rendering PDF pages (only used for PDFs)
            prompt (str, optional): Custom prompt for the vision model
            
        Returns:
            str or dict: Extracted text. For images: string, for PDFs: dictionary by page
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logging.error(f"File not found: {file_path}")
            return None
            
        # Determine file type
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type and mime_type.startswith('image/'):
            # Handle image file
            logging.info(f"Processing image file: {file_path}")
            image = Image.open(file_path)
            return self.extract_text_from_image(image, prompt)
            
        elif mime_type == 'application/pdf':
            # Handle PDF file
            logging.info(f"Processing PDF file: {file_path}")
            return self.extract_text_from_pdf(file_path, dpi, prompt)
            
        else:
            logging.error(f"Unsupported file type: {mime_type}")
            return None
            
    def extract_text_to_string(self, file_path, dpi=300, prompt=None, 
                              separator="\n\n--- Page {page_num} ---\n\n"):
        """
        Extract text from either an image or PDF file and return as a string
        
        Args:
            file_path (str): Path to the file (image or PDF)
            dpi (int): DPI for rendering PDF pages (only used for PDFs)
            prompt (str, optional): Custom prompt for the vision model
            separator (str): Text to insert between pages (only used for PDFs)
            
        Returns:
            str: Extracted text
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logging.error(f"File not found: {file_path}")
            return None
            
        # Determine file type
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type and mime_type.startswith('image/'):
            # Handle image file
            logging.info(f"Processing image file: {file_path}")
            image = Image.open(file_path)
            return self.extract_text_from_image(image, prompt)
            
        elif mime_type == 'application/pdf':
            # Handle PDF file
            logging.info(f"Processing PDF file: {file_path}")
            return self.extract_text_from_pdf_to_string(file_path, dpi, prompt, separator)
            
        else:
            logging.error(f"Unsupported file type: {mime_type}")
            return None
        