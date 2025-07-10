from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from db.database import get_db
from db.models import (
    User as DBUser, 
    Organization as DBOrganization, 
    UserAPIUsage as DBUserAPIUsage,
    Lead as DBLead,
    ChatMessage as DBChatMessage
)
from models.user import (
    UserCreate, User, UserUpdate, LoginRequest, LoginResponse, 
    OrganizationCreate, Organization, UsageStats, UserWithoutOrg
)
from services.auth_service import (
    auth_service, get_current_user, get_current_active_user, 
    get_admin_user, require_role, security
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/register", response_model=User)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user already exists
    existing_user = db.query(DBUser).filter(DBUser.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if organization exists
    organization = db.query(DBOrganization).filter(
        DBOrganization.id == user_data.organization_id
    ).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found"
        )
    
    # Check organization user limit
    user_count = db.query(DBUser).filter(
        DBUser.organization_id == user_data.organization_id,
        DBUser.is_active == True
    ).count()
    
    if user_count >= organization.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization user limit reached"
        )
    
    # Create new user
    hashed_password = auth_service.get_password_hash(user_data.password)
    db_user = DBUser(
        id=str(uuid.uuid4()),
        email=user_data.email,
        hashed_password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
        organization_id=user_data.organization_id,
        api_rate_limit=user_data.api_rate_limit,
        ai_token_limit=user_data.ai_token_limit,
        is_active=True,
        is_verified=False
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Load organization for response
    db_user.organization = organization
    
    return User.from_orm(db_user)

@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login user and return access token"""
    return auth_service.login_user(login_data.email, login_data.password, db)

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Logout user and invalidate session"""
    token = credentials.credentials
    token_data = auth_service.verify_token(token)
    
    # Here you could invalidate the token in a blacklist if needed
    # For now, we'll just return success since JWT tokens are stateless
    
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    # Load organization
    organization = db.query(DBOrganization).filter(
        DBOrganization.id == current_user.organization_id
    ).first()
    current_user.organization = organization
    
    return User.from_orm(current_user)

@router.put("/me", response_model=User)
async def update_current_user(
    user_update: UserUpdate,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user information"""
    update_data = user_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    # Load organization
    organization = db.query(DBOrganization).filter(
        DBOrganization.id == current_user.organization_id
    ).first()
    current_user.organization = organization
    
    return User.from_orm(current_user)

@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's API usage statistics"""
    today = datetime.utcnow().date()
    
    # Get today's usage
    daily_usage = db.query(DBUserAPIUsage).filter(
        DBUserAPIUsage.user_id == current_user.id,
        DBUserAPIUsage.date == today
    ).first()
    
    # Get monthly usage (last 30 days)
    from datetime import timedelta
    month_ago = today - timedelta(days=30)
    
    monthly_usage = db.query(DBUserAPIUsage).filter(
        DBUserAPIUsage.user_id == current_user.id,
        DBUserAPIUsage.date >= month_ago
    ).all()
    
    daily_api_calls = daily_usage.api_calls if daily_usage else 0
    daily_ai_tokens = daily_usage.ai_tokens_used if daily_usage else 0
    
    monthly_api_calls = sum(usage.api_calls for usage in monthly_usage)
    monthly_ai_tokens = sum(usage.ai_tokens_used for usage in monthly_usage)
    
    return UsageStats(
        daily_api_calls=daily_api_calls,
        daily_ai_tokens=daily_ai_tokens,
        monthly_api_calls=monthly_api_calls,
        monthly_ai_tokens=monthly_ai_tokens,
        api_limit=current_user.api_rate_limit,
        token_limit=current_user.ai_token_limit,
        api_usage_percentage=(daily_api_calls / current_user.api_rate_limit) * 100,
        token_usage_percentage=(monthly_ai_tokens / current_user.ai_token_limit) * 100
    )

# Organization routes
@router.post("/organizations", response_model=Organization)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: DBUser = Depends(require_role("admin"))
):
    """Create a new organization (admin only)"""
    db = next(get_db())
    try:
        # Check if organization domain already exists
        existing_org = db.query(DBOrganization).filter(
            DBOrganization.domain == org_data.domain
        ).first()
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization domain already exists"
            )
        
        # Create new organization
        db_org = DBOrganization(
            id=str(uuid.uuid4()),
            name=org_data.name,
            domain=org_data.domain,
            org_type=org_data.org_type,
            max_users=org_data.max_users,
            max_leads=org_data.max_leads,
            ai_token_limit_monthly=org_data.ai_token_limit_monthly,
            is_active=True
        )
        
        db.add(db_org)
        db.commit()
        db.refresh(db_org)
        
        return Organization.from_orm(db_org)
    finally:
        db.close()

@router.get("/organizations", response_model=List[Organization])
async def list_organizations(
    current_user: DBUser = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """List all organizations (admin only)"""
    organizations = db.query(DBOrganization).all()
    return [Organization.from_orm(org) for org in organizations]

@router.get("/organizations/{org_id}/users", response_model=List[UserWithoutOrg])
async def list_organization_users(
    org_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List users in an organization"""
    # Check if user is admin or belongs to the organization
    if current_user.role.value != "admin" and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this organization's users"
        )
    
    users = db.query(DBUser).filter(DBUser.organization_id == org_id).all()
    return [UserWithoutOrg.from_orm(user) for user in users]

# Admin routes for user management
@router.get("/admin/users", response_model=List[User])
async def list_all_users(
    current_user: DBUser = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List all users (admin only)"""
    users = db.query(DBUser).all()
    result = []
    
    for user in users:
        # Load organization
        organization = db.query(DBOrganization).filter(
            DBOrganization.id == user.organization_id
        ).first()
        user.organization = organization
        result.append(User.from_orm(user))
    
    return result

@router.put("/admin/users/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: DBUser = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update any user (admin only)"""
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    # Load organization
    organization = db.query(DBOrganization).filter(
        DBOrganization.id == user.organization_id
    ).first()
    user.organization = organization
    
    return User.from_orm(user)

@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: DBUser = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Don't allow deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete by deactivating
    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "User deactivated successfully"}

@router.get("/admin/stats")
async def get_admin_stats(
    current_user: DBUser = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get system statistics (admin only)"""
    total_users = db.query(DBUser).count()
    active_users = db.query(DBUser).filter(DBUser.is_active == True).count()
    total_orgs = db.query(DBOrganization).count()
    total_leads = db.query(DBLead).count()
    total_messages = db.query(DBChatMessage).count()
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users
        },
        "organizations": {
            "total": total_orgs
        },
        "leads": {
            "total": total_leads
        },
        "messages": {
            "total": total_messages
        }
    } 