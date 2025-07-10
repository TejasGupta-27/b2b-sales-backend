from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    SALES_AGENT = "sales_agent"
    SALES_MANAGER = "sales_manager"
    VIEWER = "viewer"

class OrganizationType(str, Enum):
    ENTERPRISE = "enterprise"
    SMB = "smb"
    STARTUP = "startup"

# Organization Models
class OrganizationBase(BaseModel):
    name: str
    domain: str
    org_type: OrganizationType = OrganizationType.SMB
    max_users: int = 5
    max_leads: int = 1000
    ai_token_limit_monthly: int = 100000

class OrganizationCreate(OrganizationBase):
    pass

class Organization(OrganizationBase):
    id: str
    is_active: bool
    settings: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# User Models
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole = UserRole.SALES_AGENT
    api_rate_limit: int = 1000
    ai_token_limit: int = 50000

class UserCreate(UserBase):
    password: str
    organization_id: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    api_rate_limit: Optional[int] = None
    ai_token_limit: Optional[int] = None
    preferences: Optional[Dict[str, Any]] = None

class User(UserBase):
    id: str
    is_active: bool
    is_verified: bool
    organization_id: str
    organization: Optional[Organization] = None
    preferences: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserWithoutOrg(UserBase):
    id: str
    is_active: bool
    is_verified: bool
    organization_id: str
    preferences: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Authentication Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserWithoutOrg

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

# API Usage Models
class UserAPIUsage(BaseModel):
    user_id: str
    date: datetime
    api_calls: int = 0
    ai_tokens_used: int = 0
    
    class Config:
        from_attributes = True

class UsageStats(BaseModel):
    daily_api_calls: int
    daily_ai_tokens: int
    monthly_api_calls: int
    monthly_ai_tokens: int
    api_limit: int
    token_limit: int
    api_usage_percentage: float
    token_usage_percentage: float

# Session Models
class UserSession(BaseModel):
    id: str
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True 