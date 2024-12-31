from pydantic import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Firebase Config
    FIREBASE_PROJECT_ID: str = "crypto-dashboard-227f6"
    
    # CORS
    FRONTEND_URL: str = "http://localhost:5173"  # URL del frontend en desarrollo
    
    # Binance
    BINANCE_API_URL: str = "https://api.binance.com"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
