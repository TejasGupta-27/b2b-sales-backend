from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import logging
import json

from db.database import get_db
from models.recommendation import RecommendationSet, ProductRecommendation
from ai_services.factory import AIServiceFactory
from ai_services.simple_conversational_agent import SimpleConversationalAgent
from db.models import Lead, RecommendationSet as DBRecommendationSet, ProductRecommendation as DBProductRecommendation
from ai_services.conversation_flow_manager import ConversationFlowAgent
from ai_services.base import AIResponse  # Needed to build dummy response for quote agent
from services.metrics_service import get_metrics_service
from services.elasticsearch_service import get_elasticsearch_service
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate")
async def generate_recommendations(
    request: Dict[str, Any],
    db: Session = Depends(get_db)
) -> RecommendationSet:
    """Generate product recommendations based on customer requirements"""
    try:
        logger.info(f"📊 Generating recommendations for lead_id: {request.get('lead_id')}")
        
        # Validate lead exists
        lead = db.query(Lead).filter(Lead.id == request.get("lead_id")).first()
        if not lead:
            raise HTTPException(
                status_code=404,
                detail=f"Lead with ID {request.get('lead_id')} not found"
            )

        # Initialize AI services
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = SimpleConversationalAgent(base_provider)
        flow_agent = ConversationFlowAgent(base_provider)
        
        # Get conversation messages from request
        messages = request.get("messages", [])
        customer_context = request.get("customer_context", {})
        
        # Analyze conversation state
        flow_analysis = await flow_agent.analyze_conversation_state(messages, customer_context)
        
        # Generate recommendations using the sales agent
        recommendations = await sales_agent.generate_recommendations(request)
        
        if not recommendations:
            logger.warning("❌ No recommendations generated from sales agent")
            raise HTTPException(
                status_code=400,
                detail="No recommendations could be generated based on the provided requirements"
            )

        logger.info(f"✅ Generated {len(recommendations)} recommendations")

        # Create recommendation set in database with better error handling
        try:
            # Create a unique ID for the recommendation set
            recommendation_set_id = str(uuid.uuid4())
            
            # Create the recommendation set
            db_recommendation_set = DBRecommendationSet(
                id=recommendation_set_id,
                lead_id=request.get("lead_id"),
                recommendations=recommendations,
                created_at=datetime.utcnow(),
                reasoning=request.get("reasoning", ""),
                next_steps=request.get("next_steps", []),
                conversation_state={
                    "recommendations": recommendations,
                    "current_stage": "solution_presentation",
                    "customer_context": customer_context,
                    "flow_analysis": flow_analysis,
                    "recommendation_context": {
                        "conversation_messages": messages,
                        "available_products": recommendations,
                        "available_solutions": recommendations,
                        "extracted_requirements": flow_analysis.get("extracted_requirements", {}),
                        "customer_context": customer_context,
                        "conversation_stage": "solution_presentation",
                    },
                },
                current_stage="solution_presentation"
            )
            
            # Add individual product recommendations with validation
            for i, rec in enumerate(recommendations):
                try:
                    # Validate required fields
                    if not rec.get("product_id"):
                        logger.error(f"❌ Missing product_id in recommendation {i}")
                        continue
                        
                    db_product_rec = DBProductRecommendation(
                        id=str(uuid.uuid4()),
                        recommendation_set_id=recommendation_set_id,
                        product_id=rec["product_id"],
                        name=rec.get("name", "Unknown Product"),
                        description=rec.get("description", ""),
                        price=float(rec.get("price", 0)),
                        features=rec.get("features", []),
                        benefits=rec.get("benefits", []),
                        suitability_score=float(rec.get("suitability_score", 0)),
                        customization_options=rec.get("customization_options")
                    )
                    db.add(db_product_rec)
                    logger.debug(f"✅ Added product recommendation: {rec.get('name')}")
                except Exception as rec_error:
                    logger.error(f"❌ Error adding recommendation {i}: {rec_error}")
                    continue
            
            db.add(db_recommendation_set)
            db.commit()
            db.refresh(db_recommendation_set)
            logger.info(f"✅ Successfully saved recommendation set: {db_recommendation_set.id}")
            
        except Exception as db_error:
            logger.error(f"❌ Database error while saving recommendations: {db_error}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save recommendations: {str(db_error)}")
        
        # Convert to Pydantic model for response
        recommendation_set = RecommendationSet(
            id=db_recommendation_set.id,
            lead_id=db_recommendation_set.lead_id,
            recommendations=recommendations,
            created_at=db_recommendation_set.created_at,
            reasoning=db_recommendation_set.reasoning,
            next_steps=db_recommendation_set.next_steps,
            conversation_state=db_recommendation_set.conversation_state,
            current_stage=db_recommendation_set.current_stage
        )
        
        return recommendation_set
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in generate_recommendations: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/select/{recommendation_set_id}")
async def select_recommendation(
    recommendation_set_id: str,
    selection: Dict[str, str],
    db: Session = Depends(get_db)
) -> RecommendationSet:
    """Select a recommendation from the set and track selection for quote generation"""
    try:
        logger.info(f"🎯 Selecting recommendation from set: {recommendation_set_id}")
        
        # Get recommendation set
        db_recommendation_set = db.query(DBRecommendationSet).filter(
            DBRecommendationSet.id == recommendation_set_id
        ).first()
        
        if not db_recommendation_set:
            logger.error(f"❌ Recommendation set not found: {recommendation_set_id}")
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
            logger.error(f"❌ Product {product_id} not found in recommendations")
            raise HTTPException(
                status_code=400,
                detail=f"Product with ID {product_id} not found in recommendations"
            )
        
        # Find the selected recommendation from the recommendations list
        selected_recommendation = None
        for rec in db_recommendation_set.recommendations:
            if rec["product_id"] == product_id:
                selected_recommendation = rec
                break
        
        if not selected_recommendation:
            logger.error(f"❌ Could not find recommendation data for product: {product_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Could not find recommendation data for product {product_id}"
            )
        
        logger.info(f"✅ Found selected recommendation: {selected_recommendation.get('name', 'Unknown')}")
        
        # Get conversation state and ensure it's properly structured
        conversation_state = db_recommendation_set.conversation_state or {}
        
        # Initialize or get selected recommendations list
        selected_recommendations = db_recommendation_set.selected_recommendations or []
        selection_timestamps = db_recommendation_set.selection_timestamps or {}
        
        # Add new selection if not already selected
        if product_id not in selected_recommendations:
            selected_recommendations.append(product_id)
            selection_timestamps[product_id] = datetime.utcnow().isoformat()
            
            # Update conversation state with new selection
            if "selected_recommendations" not in conversation_state:
                conversation_state["selected_recommendations"] = []
            conversation_state["selected_recommendations"].append(selected_recommendation)
            
            logger.info(f"✅ Added new selection: {selected_recommendation.get('name', 'Unknown')}")
        else:
            logger.info(f"ℹ️ Product {product_id} was already selected")
        
        # Update conversation state flags
        conversation_state["recommendation_selected"] = True
        conversation_state["selected_product_id"] = product_id
        conversation_state["selected_recommendation"] = selected_recommendation

        # ----------------------------------------------------------------------------------
        # Keep recommendation_context up-to-date so the QuoteGenerationAgent receives the
        # full picture of what products were shown and which ones the customer accepted.
        # ----------------------------------------------------------------------------------
        recommendation_context = conversation_state.get("recommendation_context", {
            "conversation_stage": "solution_presentation",
            "available_products": db_recommendation_set.recommendations,
            "conversation_messages": [],
            "extracted_requirements": {},
            "customer_context": conversation_state.get("customer_context", {}),
        })

        # Track selections inside the recommendation_context
        recommendation_context["selected_recommendations"] = selected_recommendations
        recommendation_context["selected_recommendation"] = selected_recommendation

        conversation_state["recommendation_context"] = recommendation_context
        
        # Keep legacy customer_context updated as well before persisting
        conversation_state.setdefault("customer_context", {})
        conversation_state["customer_context"]["selected_recommendation"] = selected_recommendation
        
        # Mark as ready for quote generation if we have selections
        if selected_recommendations:
            conversation_state["quote_ready"] = True
            conversation_state["should_generate_quote"] = True
        
        logger.info(f"🎯 Total selections: {len(selected_recommendations)}")
        
        # Update recommendation set with selection and new state
        try:
            db_recommendation_set.selected_recommendations = selected_recommendations
            db_recommendation_set.selection_timestamps = selection_timestamps
            db_recommendation_set.conversation_state = conversation_state
            db_recommendation_set.current_stage = "quote_ready" if selected_recommendations else "solution_presentation"
            
            db.commit()
            db.refresh(db_recommendation_set)
            logger.info(f"✅ Recommendation selection saved successfully")
            
        except Exception as save_error:
            logger.error(f"❌ Failed to save recommendation selection: {save_error}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save selection: {str(save_error)}")
        
        # Convert to Pydantic model for response
        recommendation_set = RecommendationSet(
            id=db_recommendation_set.id,
            lead_id=db_recommendation_set.lead_id,
            recommendations=db_recommendation_set.recommendations,
            created_at=db_recommendation_set.created_at,
            reasoning=db_recommendation_set.reasoning,
            next_steps=db_recommendation_set.next_steps,
            conversation_state=conversation_state,
            current_stage=conversation_state.get("current_stage", "quote_ready"),
            selected_recommendations=selected_recommendations,
            selection_timestamps=selection_timestamps
        )
        
        return recommendation_set
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in select_recommendation: {e}")
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
            next_steps=db_recommendation_set.next_steps,
            conversation_state=db_recommendation_set.conversation_state,
            current_stage=db_recommendation_set.current_stage
        )
        
        return recommendation_set
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-quote/{recommendation_set_id}")
async def generate_quote(
    recommendation_set_id: str,
    db: Session = Depends(get_db)
) -> RecommendationSet:
    """Generate a quote based on the selected recommendations"""
    try:
        logger.info(f"💰 Generating quote for recommendation set: {recommendation_set_id}")
        
        # Get recommendation set
        db_recommendation_set = db.query(DBRecommendationSet).filter(
            DBRecommendationSet.id == recommendation_set_id
        ).first()
        
        if not db_recommendation_set:
            logger.error(f"❌ Recommendation set not found: {recommendation_set_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Recommendation set with ID {recommendation_set_id} not found"
            )
        
        # Check if any recommendations have been selected
        selected_recommendations = db_recommendation_set.selected_recommendations or []
        if not selected_recommendations:
            logger.error("❌ No recommendations have been selected for quote generation")
            raise HTTPException(
                status_code=400,
                detail="No recommendations have been selected. Please select at least one recommendation first."
            )
        
        # Get conversation state and selected recommendations
        conversation_state = db_recommendation_set.conversation_state or {}
        selected_recommendations_data = conversation_state.get("selected_recommendations", [])
        
        if not selected_recommendations_data:
            # Find selected recommendations in the recommendations list
            selected_recommendations_data = []
            for rec in db_recommendation_set.recommendations:
                if isinstance(rec, dict) and rec.get('product_id') in selected_recommendations:
                    selected_recommendations_data.append(rec)
            
            if not selected_recommendations_data:
                logger.error("❌ Selected recommendations not found in conversation state")
                raise HTTPException(
                    status_code=400,
                    detail="Selected recommendations data not found. Please select recommendations again."
                )
        
        # Initialize AI services for quote generation
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = SimpleConversationalAgent(base_provider)
        
        # Generate quote using sales agent
        try:
            # Update conversation state with all selected recommendations
            conversation_state["selected_recommendations"] = selected_recommendations_data
            conversation_state["quote_ready"] = True
            
            # Prepare a minimal empty response object (the quote agent will populate metadata)
            dummy_response = AIResponse(content="", model="quote_generation", provider="sales_agent", usage={}, metadata={})

            # Generate quote with full recommendation context
            quote_response = await sales_agent._collaborate_with_quote_agent(
                response=dummy_response,
                recommendation_context=conversation_state.get("recommendation_context", {}),
                flow_analysis=conversation_state,
            )

            # Extract generated quote data from the returned AIResponse metadata
            quote = quote_response.metadata if quote_response and quote_response.metadata else {}
            quote_data = quote.get("quote") if quote else None
            
            if quote_data:
                # Add quote data to conversation state and update database fields
                conversation_state["quote"] = quote_data
                conversation_state["quote_generated"] = True

                # Update recommendation set with quote data
                db_recommendation_set.quote_data = quote_data
                db_recommendation_set.quote_generated_at = datetime.utcnow()
                db_recommendation_set.conversation_state = conversation_state
                
                db.commit()
                db.refresh(db_recommendation_set)
                logger.info(f"✅ Quote generated and saved successfully for {len(selected_recommendations_data)} products")
            else:
                logger.warning("⚠️ Quote generation returned no result")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate quote. Please try again."
                )
                
        except Exception as quote_error:
            logger.error(f"❌ Quote generation failed: {quote_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate quote: {str(quote_error)}"
            )
        
        return db_recommendation_set
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating quote: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while generating the quote: {str(e)}"
        )

@router.get("/debug/recommendation-state/{recommendation_set_id}")
async def debug_recommendation_state(
    recommendation_set_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Debug endpoint to show current recommendation and quote state"""
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
        
        # Get conversation state
        conversation_state = db_recommendation_set.conversation_state or {}
        
        # Build debug response
        debug_info = {
            "recommendation_set_id": recommendation_set_id,
            "created_at": db_recommendation_set.created_at,
            "updated_at": db_recommendation_set.updated_at,
            "quote_generated": db_recommendation_set.quote_generated,
            "quote_generated_at": db_recommendation_set.quote_generated_at,
            "conversation_state": {
                "quote_ready": conversation_state.get("quote_ready", False),
                "should_generate_quote": conversation_state.get("should_generate_quote", False),
                "recommendation_selected": conversation_state.get("recommendation_selected", False),
                "current_stage": conversation_state.get("current_stage", "unknown"),
                "selected_recommendations": conversation_state.get("selected_recommendations", []),
                "product_recommendations": conversation_state.get("product_recommendations", []),
                "extracted_requirements": conversation_state.get("extracted_requirements", {}),
                "business_context_score": conversation_state.get("business_context_score", 0),
                "technical_requirements_score": conversation_state.get("technical_requirements_score", 0),
                "completion_scores": conversation_state.get("completion_scores", {})
            },
            "quote_data": db_recommendation_set.quote_data
        }
        
        return debug_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting debug info: {str(e)}"
        )

@router.post("/generate-quote-with-selection/{recommendation_set_id}")
async def generate_quote_with_selection(
    recommendation_set_id: str,
    selection: Dict[str, str],
    db: Session = Depends(get_db)
) -> RecommendationSet:
    """Select recommendations and generate quote in one step"""
    try:
        logger.info(f"🎯 Selecting recommendations and generating quote for set: {recommendation_set_id}")
        
        # First select the recommendations
        selected_set = await select_recommendation(recommendation_set_id, selection, db)
        
        # Then generate the quote
        quoted_set = await generate_quote(recommendation_set_id, db)
        
        return quoted_set
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in generate_quote_with_selection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while generating the quote: {str(e)}"
        ) 