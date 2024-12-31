from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from config import get_settings
from firebase_auth import verify_firebase_token

settings = get_settings()
security = HTTPBearer()

async def get_current_user(credentials = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return verify_firebase_token(credentials.credentials)
