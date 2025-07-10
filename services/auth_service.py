from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets
import uuid
import logging

from db.database import get_db
from db.models import User as DBUser, Organization as DBOrganization, UserSession as DBUserSession, UserAPIUsage as DBUserAPIUsage
from models.user import User, TokenData, LoginResponse, UserWithoutOrg
from config import settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = getattr(settings, 'secret_key', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# HTTP Bearer for token extraction
security = HTTPBearer()

class AuthService:
    def __init__(self):
        self.pwd_context = pwd_context
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create refresh token"""
        data = {"sub": user_id, "type": "refresh"}
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {"exp": expire, **data}
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    def verify_token(self, token: str) -> TokenData:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            role: str = payload.get("role")
            organization_id: str = payload.get("organization_id")
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return TokenData(
                user_id=user_id,
                email=email,
                role=role,
                organization_id=organization_id
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def authenticate_user(self, email: str, password: str, db: Session) -> Optional[DBUser]:
        """Authenticate user with email and password"""
        user = db.query(DBUser).filter(DBUser.email == email).first()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def create_user_session(self, user_id: str, db: Session) -> str:
        """Create a new user session"""
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Deactivate old sessions
        db.query(DBUserSession).filter(
            DBUserSession.user_id == user_id,
            DBUserSession.is_active == True
        ).update({"is_active": False})
        
        # Create new session
        session = DBUserSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            is_active=True
        )
        db.add(session)
        db.commit()
        
        return session_token
    
    def get_user_by_session(self, session_token: str, db: Session) -> Optional[DBUser]:
        """Get user by session token"""
        session = db.query(DBUserSession).filter(
            DBUserSession.session_token == session_token,
            DBUserSession.is_active == True,
            DBUserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            return None
        
        return db.query(DBUser).filter(DBUser.id == session.user_id).first()
    
    def invalidate_session(self, session_token: str, db: Session) -> bool:
        """Invalidate a user session"""
        result = db.query(DBUserSession).filter(
            DBUserSession.session_token == session_token
        ).update({"is_active": False})
        db.commit()
        return result > 0
    
    def login_user(self, email: str, password: str, db: Session) -> LoginResponse:
        """Login user and return tokens"""
        user = self.authenticate_user(email, password, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user account"
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={
                "sub": user.id,
                "email": user.email,
                "role": user.role.value,
                "organization_id": user.organization_id
            },
            expires_delta=access_token_expires
        )
        
        # Create session
        session_token = self.create_user_session(user.id, db)
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserWithoutOrg.from_orm(user)
        )
    
    def record_api_usage(self, user_id: str, ai_tokens: int = 0, db: Session = None):
        """Record API usage for rate limiting"""
        if not db:
            return
        
        try:
            today = datetime.utcnow().date()
            usage = db.query(DBUserAPIUsage).filter(
                DBUserAPIUsage.user_id == user_id,
                DBUserAPIUsage.date == today
            ).first()
            
            if usage:
                usage.api_calls += 1
                usage.ai_tokens_used += ai_tokens
            else:
                usage = DBUserAPIUsage(
                    user_id=user_id,
                    date=today,
                    api_calls=1,
                    ai_tokens_used=ai_tokens
                )
                db.add(usage)
            
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record API usage: {e}")

# Create global instance
auth_service = AuthService()

# Dependency to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> DBUser:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    token_data = auth_service.verify_token(token)
    
    user = db.query(DBUser).filter(DBUser.id == token_data.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Record API usage
    auth_service.record_api_usage(user.id, db=db)
    
    return user

# Dependency to get current active user with rate limiting
async def get_current_active_user(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DBUser:
    """Dependency to get current active user with rate limiting check"""
    # Check daily API rate limit
    today = datetime.utcnow().date()
    usage = db.query(DBUserAPIUsage).filter(
        DBUserAPIUsage.user_id == current_user.id,
        DBUserAPIUsage.date == today
    ).first()
    
    if usage and usage.api_calls >= current_user.api_rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily API rate limit exceeded"
        )
    
    return current_user

# Role-based access control dependencies
def require_role(*allowed_roles: str):
    """Decorator to require specific roles"""
    def role_checker(current_user: DBUser = Depends(get_current_active_user)) -> DBUser:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker

# Admin access dependency
def get_admin_user(current_user: DBUser = Depends(get_current_active_user)) -> DBUser:
    """Dependency to ensure admin access"""
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

# Organization isolation dependency
def get_user_with_org_check(current_user: DBUser = Depends(get_current_active_user)) -> DBUser:
    """Dependency to get user with organization context"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with an organization"
        )
    return current_user 