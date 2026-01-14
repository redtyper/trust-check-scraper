import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = 'gpt-4o'  # Najnowszy model z vision
    
    # Apify
    APIFY_API_KEY = os.getenv('APIFY_API_KEY')
    
    # TrustCheck
    TRUSTCHECK_API_URL = os.getenv('TRUSTCHECK_API_URL')
    TRUSTCHECK_BOT_TOKEN = os.getenv('TRUSTCHECK_BOT_TOKEN')
    
    # Facebook
    FACEBOOK_GROUP_URL = os.getenv('FACEBOOK_GROUP_URL')
    
    # Scraping
    MAX_POSTS_PER_RUN = 50
    CHECK_INTERVAL_HOURS = 2
