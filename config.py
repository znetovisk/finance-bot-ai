import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # WPP Connect
    WPP_BASE_URL = os.getenv("WPP_BASE_URL")
    SESSION = os.getenv("WPP_SESSION")
    TOKEN = os.getenv("WPP_TOKEN")
    
    # URL completa
    WPP_API_URL = f"{WPP_BASE_URL}/{SESSION}"
    
    HEADERS = {
        'Authorization': f'Bearer {TOKEN}', 
        'Content-Type': 'application/json'
    }

    # AI
    OLLAMA_URL = os.getenv("OLLAMA_URL")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

    # Business Logic
    ADMIN_PHONE = os.getenv("ADMIN_PHONE")
    # Garante formato JID (apenas números + @c.us)
    ADMIN_JID = f"{ADMIN_PHONE}@c.us" if "@" not in ADMIN_PHONE else ADMIN_PHONE
    
    PIX_KEY = os.getenv("PIX_KEY")
    BENEFICIARY_NAME = os.getenv("BENEFICIARY_NAME")