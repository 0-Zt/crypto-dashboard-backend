from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from auth import get_current_user
import requests
from config import get_settings

settings = get_settings()

class PortfolioAsset(BaseModel):
    symbol: str
    quantity: float
    average_price: float
    purchase_date: datetime = datetime.now()
    notes: Optional[str] = None

router = APIRouter()

def get_firestore_url(user_id: str, collection: str = 'portfolios'):
    return f'https://firestore.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/databases/(default)/documents/users/{user_id}/{collection}'

@router.get("/portfolio", response_model=List[PortfolioAsset])
async def get_portfolio(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user.get('user_id') or current_user.get('uid')
        url = get_firestore_url(user_id)
        
        # Para pruebas, retornar una lista vacía
        return []
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/portfolio/asset")
async def add_asset(asset: PortfolioAsset, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user.get('user_id') or current_user.get('uid')
        
        # Para pruebas, solo retornar éxito
        return {"message": "Asset added successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/portfolio/asset/{symbol}")
async def delete_asset(symbol: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user.get('user_id') or current_user.get('uid')
        
        # Para pruebas, solo retornar éxito
        return {"message": "Asset deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
