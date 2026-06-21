import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def scan_receipt(image_path):
    try:
        image = Image.open(image_path)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        Analyze this receipt or bill image. Extract the total amount, an appropriate single-word category (e.g., Food, Travel, Shopping, Medical, Utilities), a short one-line description, and the transaction date (in YYYY-MM-DD format, use today's date if not found).
        
        You MUST return the output strictly as a valid JSON object with the following keys:
        {
            "amount": float,
            "category": "string",
            "description": "string",
            "date": "string"
        }
        Do not wrap the response in markdown code blocks or add any other text.
        """
        
        response = model.generate_content([prompt, image])
        data = json.loads(response.text.strip())
        return data
        
    except Exception as e:
        print(f"Error scanning receipt: {e}")
        return None