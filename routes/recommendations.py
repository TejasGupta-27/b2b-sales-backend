from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from db.database import get_db
from models.recommendation import RecommendationSet, ProductRecommendation
from ai_services.factory import AIServiceFactory
from ai_services.enhanced_b2b_sales_agent import EnhancedB2BSalesAgent
from db.models import Lead, RecommendationSet as DBRecommendationSet, ProductRecommendation as DBProductRecommendation

router = APIRouter()

@router.post("/generate")
async def generate_recommendations(
    request: Dict[str, Any],
    db: Session = Depends(get_db)
) -> RecommendationSet:
    """Generate product recommendations based on customer requirements"""
    try:
        # Validate lead exists
        lead = db.query(Lead).filter(Lead.id == request.get("lead_id")).first()
        if not lead:
            raise HTTPException(
                status_code=404,
                detail=f"Lead with ID {request.get('lead_id')} not found"
            )

        # Initialize AI services
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = EnhancedB2BSalesAgent(base_provider)
        
        # Generate recommendations using the sales agent
        recommendations = await sales_agent.generate_recommendations(request)
        
        if not recommendations:
            raise HTTPException(
                status_code=400,
                detail="No recommendations could be generated based on the provided requirements"
            )

        # Create recommendation set in database
        db_recommendation_set = DBRecommendationSet(
            id=str(uuid.uuid4()),
            lead_id=request.get("lead_id"),
            recommendations=recommendations,
            created_at=datetime.utcnow(),
            reasoning=request.get("reasoning", ""),
            next_steps=request.get("next_steps", [])
        )
        
        # Add individual product recommendations
        for rec in recommendations:
            db_product_rec = DBProductRecommendation(
                id=str(uuid.uuid4()),
                recommendation_set_id=db_recommendation_set.id,
                product_id=rec["product_id"],
                name=rec["name"],
                description=rec["description"],
                price=rec["price"],
                features=rec["features"],
                benefits=rec["benefits"],
                suitability_score=rec["suitability_score"],
                customization_options=rec.get("customization_options")
            )
            db.add(db_product_rec)
        
        db.add(db_recommendation_set)
        db.commit()
        db.refresh(db_recommendation_set)
        
        # Convert to Pydantic model for response
        recommendation_set = RecommendationSet(
            id=db_recommendation_set.id,
            lead_id=db_recommendation_set.lead_id,
            recommendations=recommendations,
            created_at=db_recommendation_set.created_at,
            reasoning=db_recommendation_set.reasoning,
            next_steps=db_recommendation_set.next_steps
        )
        
        return recommendation_set
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/select/{recommendation_set_id}")
async def select_recommendation(
    recommendation_set_id: str,
    selection: Dict[str, str],
    db: Session = Depends(get_db)
) -> RecommendationSet:
    """Select a recommendation from the set"""
    try:
        # Get recommendation set
        db_recommendation_set = db.query(DBRecommendationSet).filter(
            DBRecommendationSet.id == recommendation_set_id
        ).first()
        
        if not db_recommendation_set:
            raise HTTPException(
                status_code=404,
                detail=f"Recommendation set with ID {recommendation_set_id} not found"
            )
        
        # Validate product exists in recommendations
        product_id = selection.get("product_id")
        if not product_id:
            raise HTTPException(
                status_code=400,
                detail="product_id is required in selection"
            )
            
        # Check if product exists in recommendations
        product_exists = any(
            rec["product_id"] == product_id 
            for rec in db_recommendation_set.recommendations
        )
        
        if not product_exists:
            raise HTTPException(
                status_code=400,
                detail=f"Product with ID {product_id} not found in recommendations"
            )
        
        # Update recommendation set with selection
        db_recommendation_set.selected_recommendation = product_id
        db_recommendation_set.selection_timestamp = datetime.utcnow()
        
        db.commit()
        db.refresh(db_recommendation_set)
        
        # Convert to Pydantic model for response
        recommendation_set = RecommendationSet(
            id=db_recommendation_set.id,
            lead_id=db_recommendation_set.lead_id,
            recommendations=db_recommendation_set.recommendations,
            created_at=db_recommendation_set.created_at,
            selected_recommendation=db_recommendation_set.selected_recommendation,
            selection_timestamp=db_recommendation_set.selection_timestamp,
            reasoning=db_recommendation_set.reasoning,
            next_steps=db_recommendation_set.next_steps
        )
        
        return recommendation_set
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{recommendation_set_id}")
async def get_recommendation_set(
    recommendation_set_id: str,
    db: Session = Depends(get_db)
) -> RecommendationSet:
    """Get a specific recommendation set"""
    try:
        # Query the database for the recommendation set
        db_recommendation_set = db.query(DBRecommendationSet).filter(
            DBRecommendationSet.id == recommendation_set_id
        ).first()
        
        if not db_recommendation_set:
            raise HTTPException(
                status_code=404,
                detail=f"Recommendation set with ID {recommendation_set_id} not found"
            )
        
        # Convert database model to Pydantic model
        recommendation_set = RecommendationSet(
            id=db_recommendation_set.id,
            lead_id=db_recommendation_set.lead_id,
            recommendations=db_recommendation_set.recommendations,
            created_at=db_recommendation_set.created_at,
            selected_recommendation=db_recommendation_set.selected_recommendation,
            selection_timestamp=db_recommendation_set.selection_timestamp,
            reasoning=db_recommendation_set.reasoning,
            next_steps=db_recommendation_set.next_steps
        )
        
        return recommendation_set
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 