import json
import requests
from fastapi import HTTPException, status
from jose import jwt
from config import get_settings

settings = get_settings()

def get_firebase_public_keys():
    """Obtiene las claves públicas de Firebase."""
    response = requests.get('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com')
    return response.json()

def verify_firebase_token(token: str):
    """Verifica un token de Firebase ID."""
    try:
        # Obtener las claves públicas de Firebase
        public_keys = get_firebase_public_keys()
        
        # Decodificar el header del token para obtener el kid
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        
        if not kid or kid not in public_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature"
            )
        
        # Verificar y decodificar el token
        decoded_token = jwt.decode(
            token,
            public_keys[kid],
            algorithms=['RS256'],
            audience=settings.FIREBASE_PROJECT_ID
        )
        
        # Verificar que el token fue emitido para tu proyecto
        if decoded_token.get('aud') != settings.FIREBASE_PROJECT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience"
            )
        
        return decoded_token
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error validating token: {str(e)}"
        )
