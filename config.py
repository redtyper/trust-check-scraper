import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Apify
    APIFY_API_KEY = os.getenv("APIFY_API_KEY")

    # TrustCheck
    TRUSTCHECK_API_URL = os.getenv("TRUSTCHECK_API_URL", "http://localhost:3001")
    TRUSTCHECK_BOT_TOKEN = os.getenv("TRUSTCHECK_BOT_TOKEN")

    # Facebook
    FACEBOOK_GROUP_URL = os.getenv("FACEBOOK_GROUP_URL", "https://www.facebook.com/groups/oszustwa")

    # Scraping
    MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "50"))
    CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "2"))
    ONLY_POSTS_DAYS_BACK = int(os.getenv("ONLY_POSTS_DAYS_BACK", "2"))
