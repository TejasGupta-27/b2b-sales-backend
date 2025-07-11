from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime
import uuid
import json
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.lead import Lead, LeadCreate, LeadUpdate, LeadStatus
from db.database import get_db
from db.models import Lead as DBLead, User as DBUser
from ai_services.factory import AIServiceFactory
from services.auth_service import get_current_active_user, get_lead_access_filter, check_lead_access


router = APIRouter(prefix="/api/leads", tags=["leads"])

@router.get("/", response_model=List[Lead])
async def get_leads(
    status: Optional[LeadStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get leads with role-based filtering - sales agents see only their assigned leads, managers see all organization leads"""
    # Get role-based filters
    lead_filters = get_lead_access_filter(current_user)
    
    query = db.query(DBLead).filter(*lead_filters)
    
    if status:
        query = query.filter(DBLead.status == status.value)
    
    # Use database pagination instead of loading all and slicing
    leads = query.offset(skip).limit(limit).all()
    
    return [Lead.from_orm(lead) for lead in leads]

@router.post("/", response_model=Lead)
async def create_lead(
    lead_data: LeadCreate, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new lead - associated with current user and organization"""
    # Check if lead already exists using database query
    existing_lead = db.query(DBLead).filter(DBLead.email == lead_data.email).first()
    if existing_lead:
        raise HTTPException(status_code=400, detail="Lead with this email already exists")
    
    # Create new lead associated with current user and organization
    lead_dict = lead_data.dict()
    lead_dict.update({
        "assigned_user_id": current_user.id,
        "organization_id": current_user.organization_id
    })
    
    db_lead = DBLead(
        id=str(uuid.uuid4()),
        **lead_dict
    )
    
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    
    return Lead.from_orm(db_lead)

@router.get("/{lead_id}", response_model=Lead)
async def get_lead(
    lead_id: str, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific lead with role-based access control"""
    # Verify user has access to this lead
    lead = check_lead_access(lead_id, current_user, db)
    
    return Lead.from_orm(lead)

@router.put("/{lead_id}", response_model=Lead)
async def update_lead(
    lead_id: str, 
    lead_update: LeadUpdate, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a lead with role-based access control"""
    # Verify user has access to this lead
    lead = check_lead_access(lead_id, current_user, db)
    
    # Update lead
    update_data = lead_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(lead, field, value)
    
    lead.updated_at = datetime.now()
    
    db.commit()
    db.refresh(lead)
    
    return Lead.from_orm(lead)

@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str, 
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a lead with role-based access control"""
    # Verify user has access to this lead
    lead = check_lead_access(lead_id, current_user, db)
    
    db.delete(lead)
    db.commit()
    
    return {"message": "Lead deleted successfully"}

@router.post("/{lead_id}/conversations")
async def add_conversation(lead_id: str, message: str, stage: str = "discovery"):
    """Add a conversation entry to a lead"""
    leads = await load_leads()
    lead_index = next((i for i, l in enumerate(leads) if l.id == lead_id), None)
    
    if lead_index is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead = leads[lead_index]
    
    # Add conversation entry
    conversation_entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "stage": stage,
        "type": "note"
    }
    
    lead.conversation_history.append(conversation_entry)
    lead.last_contact = datetime.now()
    lead.updated_at = datetime.now()
    
    await save_leads(leads)
    
    return {"message": "Conversation added successfully"}

@router.get("/{lead_id}/score")
async def calculate_lead_score(lead_id: str):
    """Calculate and return lead score"""
    leads = await load_leads()
    lead = next((l for l in leads if l.id == lead_id), None)
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Simple lead scoring algorithm
    score = 0
    
    # Company size scoring
    size_scores = {
        "startup": 20,
        "small": 40,
        "medium": 60,
        "large": 80,
        "enterprise": 100
    }
    
    if lead.company_size:
        score += size_scores.get(lead.company_size.value, 0)
    
    # Budget range scoring
    if lead.budget_range:
        if "100k+" in lead.budget_range.lower():
            score += 50
        elif "50k+" in lead.budget_range.lower():
            score += 30
        elif "10k+" in lead.budget_range.lower():
            score += 20
    
    # Decision timeline scoring
    if lead.decision_timeline:
        if "immediate" in lead.decision_timeline.lower() or "asap" in lead.decision_timeline.lower():
            score += 30
        elif "month" in lead.decision_timeline.lower():
            score += 20
        elif "quarter" in lead.decision_timeline.lower():
            score += 10
    
    # Pain points scoring
    score += len(lead.pain_points) * 5
    
    # Recent activity scoring
    if lead.last_contact:
        days_since_contact = (datetime.now() - lead.last_contact).days
        if days_since_contact <= 7:
            score += 20
        elif days_since_contact <= 30:
            score += 10
    
    # Update lead score
    lead.lead_score = min(score, 100)  # Cap at 100
    
    leads_list = await load_leads()
    lead_index = next((i for i, l in enumerate(leads_list) if l.id == lead_id), None)
    if lead_index is not None:
        leads_list[lead_index] = lead
        await save_leads(leads_list)
    
    return {"lead_score": lead.lead_score, "factors": {
        "company_size": lead.company_size.value if lead.company_size else None,
        "budget_range": lead.budget_range,
        "decision_timeline": lead.decision_timeline,
        "pain_points_count": len(lead.pain_points),
        "days_since_contact": (datetime.now() - lead.last_contact).days if lead.last_contact else None
    }} 