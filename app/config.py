import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    ops_base_url: str = os.getenv("OPS_BASE_URL", "http://127.0.0.1:8642")
    ops_api_key: str = os.getenv("OPS_API_KEY", "aerlink-ops-local-key")
    llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"
    llm_cache: bool = os.getenv("LLM_CACHE", "true").lower() == "true"
    cache_dir: str = os.getenv("CACHE_DIR", ".cache")

settings = Settings()

# Ensure cache directory exists if needed
if settings.llm_cache:
    os.makedirs(settings.cache_dir, exist_ok=True)
