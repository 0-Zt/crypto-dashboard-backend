from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class PortfolioAsset(BaseModel):
    symbol: str
    amount: float
    purchase_price: float
    purchase_date: datetime
    notes: Optional[str] = None

class BinanceKeys(BaseModel):
    api_key: str
    api_secret: str

class UserPortfolio(BaseModel):
    user_id: str
    manual_assets: List[PortfolioAsset] = []
    binance_keys: Optional[BinanceKeys] = None
    last_updated: datetime

class User(BaseModel):
    id: str
    email: str
    hashed_password: str
    name: Optional[str] = None
    portfolio: Optional[UserPortfolio] = None
