from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.models import User
from backend.services.auth import get_current_user, hash_password, verify_password, create_access_token
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Check if username is already taken
    existing_user = db.query(User).filter(User.username == form_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already registered."
        )
    
    # Hash password securely and commit new tenant profile
    hashed = hash_password(form_data.password)
    new_user = User(username=form_data.username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"status": "success", "message": "User registered successfully."}

@router.post("/login")
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Lookup the user profile registry line
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate secure JWT access token string containing the user ID
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "username": user.username
    }

# ─── PROTECTED SECURE PASSWORD UPDATE PATH ─────────────────────────────────
@router.post("/change-password")
async def change_password(
    req: PasswordChangeRequest, 
    current_user: User = Depends(get_current_user), # 🔒 Grabs verified active tenant from JWT
    db: Session = Depends(get_db)
):
    # 1. Assert that the old plain-text password matches what is hashed in our SQLite DB
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect current password value."
        )
        
    # 2. Hash the new password using native safe bcrypt wheels
    current_user.hashed_password = hash_password(req.new_password)
    
    # 3. Save the session line changes permanently
    db.commit()
    
    return {"status": "success", "message": "Password updated successfully."}