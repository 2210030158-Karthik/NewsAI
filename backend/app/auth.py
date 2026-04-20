from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from . import models, schemas, db # Import db and schemas
from .config import settings

# --- Password Hashing ---
# Use argon2 as our default hashing algorithm
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# --- JWT Token Configuration ---
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# This tells FastAPI what URL to check for the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# --- Auth Utility Functions ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if a plain password matches a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generates a hash from a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    """Generates a new JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Database / User Functions ---

def get_user_by_email(db_session: Session, email: str) -> Optional[models.User]:
    """Finds a user in the DB by their email."""
    return db_session.query(models.User).filter(models.User.email == email).first()

def authenticate_user(db_session: Session, email: str, password: str) -> Optional[models.User]:
    """
Analyses the user's login attempt."""
    user = get_user_by_email(db_session, email)
    if not user:
        return None # User doesn't exist
    if not verify_password(password, user.hashed_password):
        return None # Password incorrect
    return user # Authentication successful

# --- FastAPI Dependency Functions ---
# THESE WERE THE MISSING FUNCTIONS

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db_session: Session = Depends(db.get_db)
) -> models.User:
    """
    Dependency to get the current user from a token.
    This is called by `get_current_active_user`.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_email(db_session, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    This is the *actual* dependency our API endpoints will use.
    It verifies the user is valid and (in the future) could
    check if they are active.
    """
    # if not current_user.is_active: # We could add this later
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

