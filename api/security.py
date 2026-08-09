from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User

password_hash=PasswordHash.recommended()
bearer=HTTPBearer()

def hash_password(password:str)->str: return password_hash.hash(password)
def verify_password(password:str, hashed:str)->bool: return password_hash.verify(password,hashed)
def create_token(user:User)->str:
    return jwt.encode({"sub":user.id,"role":user.role,"exp":datetime.now(timezone.utc)+timedelta(minutes=settings.token_expire_minutes)},settings.jwt_secret,algorithm=settings.jwt_algorithm)
def current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db))->User:
    try: payload=jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=[settings.jwt_algorithm]); user=db.get(User,payload["sub"])
    except Exception: raise HTTPException(status_code=401,detail="认证失败")
    if not user or not user.is_active: raise HTTPException(status_code=401,detail="账户不可用")
    return user
def require_roles(*roles):
    def guard(user:User=Depends(current_user)):
        if user.role not in roles: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="无权执行该操作")
        return user
    return guard

