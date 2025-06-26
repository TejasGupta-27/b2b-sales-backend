from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any
from sqlalchemy.orm import Session
import os
from pathlib import Path
import uuid

from db.database import get_db
from ai_services.enhanced_b2b_sales_agent import EnhancedB2BSalesAgent
from services.pdf_generator import PDFGenerator
from services.pitch_deck_service import PitchDeckService
from services.email_sender import send_quote_email  # You must have this implemented
from ai_services.azure_openai import AzureOpenAIProvider as AIServiceFactory  # Fixed relative import

router = APIRouter()

@router.post("/generate-quote")
async def generate_quote(quote_request: Dict[str, Any]):
    """Generate a detailed quotation and pitch deck"""
    try:
        language = quote_request.get("language", "en")
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = EnhancedB2BSalesAgent(base_provider)
        
        # Generate the quote
        quote = await sales_agent.generate_quote(quote_request)
        
        # Generate unique IDs
        quote_id = str(uuid.uuid4())
        deck_id = str(uuid.uuid4())
        
        # Save the quote to a file
        quote_path = f"Data/quotes/quote_{quote_id}.pdf"
        os.makedirs(os.path.dirname(quote_path), exist_ok=True)
        
        # Generate PDF for the quote
        pdf_generator = PDFGenerator()
        pdf_buffer = pdf_generator.generate_quote_pdf(quote)
        with open(quote_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        # Generate pitch deck
        pitch_deck_service = PitchDeckService()
        deck_structure = await pitch_deck_service.extract_ppt_structure(str(quote), language=language)

        # Generate the pitch deck
        deck_path = f"Data/pitch_decks/pitch_deck_{deck_id}.pptx"
        os.makedirs(os.path.dirname(deck_path), exist_ok=True)
        
        # Generate the PowerPoint file
        await pitch_deck_service.generate_ppt(deck_structure, deck_path)
        
        return {
            "quote": quote,
            "quote_id": quote_id,
            "quote_link": f"/api/quotes/download-pdf/{quote_id}",
            "pitch_deck_id": deck_id,
            "pitch_deck_link": f"/api/quotes/download-pitch-deck/{deck_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-quote-with-pdf")
async def generate_quote_with_pdf(quote_request: Dict[str, Any]):
    """Generate a quotation with PDF file and pitch deck"""
    try:
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = EnhancedB2BSalesAgent(base_provider)
        
        # Generate the quote
        quote = await sales_agent.generate_quote_with_pdf(quote_request)
        
        # Generate unique IDs
        quote_id = str(uuid.uuid4())
        deck_id = str(uuid.uuid4())
        
        # Save the quote to a file
        quote_path = f"Data/quotes/quote_{quote_id}.pdf"
        os.makedirs(os.path.dirname(quote_path), exist_ok=True)
        
        # Generate PDF for the quote
        pdf_generator = PDFGenerator()
        pdf_buffer = pdf_generator.generate_quote_pdf(quote)
        with open(quote_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        # Generate pitch deck
        pitch_deck_service = PitchDeckService()
        deck_structure = await pitch_deck_service.extract_ppt_structure(str(quote))
        
        # Generate the pitch deck
        deck_path = f"Data/pitch_decks/pitch_deck_{deck_id}.pptx"
        os.makedirs(os.path.dirname(deck_path), exist_ok=True)
        
        # Generate the PowerPoint file
        await pitch_deck_service.generate_ppt(deck_structure, deck_path)
        
        def iter_file():
            with open(quote_path, 'rb') as file:
                yield from file
        
        return StreamingResponse(
            iter_file(),
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename=quote_{quote_id}.pdf",
                "X-Quote-ID": quote_id,
                "X-Quote-Link": f"/api/quotes/download-pdf/{quote_id}",
                "X-Pitch-Deck-ID": deck_id,
                "X-Pitch-Deck-Link": f"/api/quotes/download-pitch-deck/{deck_id}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download-pdf/{quote_id}")
async def download_quote_pdf(quote_id: str):
    """Download PDF file for a quote"""
    try:
        file_path = Path(f"Data/quotes/quote_{quote_id}.pdf")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")

        def iter_file():
            with open(file_path, 'rb') as file:
                yield from file

        # Add a custom header with the send email link
        return StreamingResponse(
            iter_file(),
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename=quote_{quote_id}.pdf",
                "X-Send-Email-Link": f"/api/quotes/send-email/{quote_id}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# PPT
@router.get("/download/{quote_id}")
async def download_quote_ppt(quote_id: str):
    """Download PowerPoint file for a quote"""
    try:
        file_path = Path(f"Data/presentations/quote_{quote_id}_deck.pptx")
        print("Presentation being saved")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="PPT file not found")
        
        def iter_file():
            with open(file_path, 'rb') as file:
                yield from file
        
        return StreamingResponse(
            iter_file(),
            media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            headers={
                "Content-Disposition": f"attachment; filename=quote_{quote_id}_deck.pptx",
                "X-Send-Email-Link": f"/api/quotes/send-email/{quote_id}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-pdf-from-data")
async def generate_pdf_from_quote_data(quote_data: Dict[str, Any]):
    """Generate PDF from existing quote data"""
    try:
        pdf_generator = PDFGenerator()
        pdf_buffer = pdf_generator.generate_quote_pdf(quote_data)
        
        return StreamingResponse(
            iter([pdf_buffer.getvalue()]),
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename=quote_{quote_data.get('id', 'quote')}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview-pdf/{quote_id}")
async def preview_quote_pdf(quote_id: str):
    """Preview PDF file in browser"""
    try:
        file_path = Path(f"Data/quotes/quote_{quote_id}.pdf")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        def iter_file():
            with open(file_path, 'rb') as file:
                yield from file
        
        return StreamingResponse(
            iter_file(),
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"inline; filename=quote_{quote_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-pitch-deck")
async def generate_pitch_deck(quote_request: Dict[str, Any]):
    """Generate a sales pitch deck from a quotation"""
    try:
        # Generate the quote first
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = EnhancedB2BSalesAgent(base_provider)
        
        quote = await sales_agent.generate_quote(quote_request)
        
        # Initialize pitch deck service
        pitch_deck_service = PitchDeckService()
        
        # Generate the pitch deck structure
        deck_structure = await pitch_deck_service.extract_ppt_structure(str(quote))
        
        # Generate unique IDs for both quote and pitch deck
        quote_id = str(uuid.uuid4())
        deck_id = str(uuid.uuid4())
        
        # Save the quote to a file
        quote_path = f"Data/quotes/quote_{quote_id}.pdf"
        os.makedirs(os.path.dirname(quote_path), exist_ok=True)
        
        # Generate PDF for the quote
        pdf_generator = PDFGenerator()
        pdf_buffer = pdf_generator.generate_quote_pdf(quote)
        with open(quote_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        # Generate the pitch deck
        deck_path = f"Data/pitch_decks/pitch_deck_{deck_id}.pptx"
        os.makedirs(os.path.dirname(deck_path), exist_ok=True)
        
        # Generate the PowerPoint file
        file_path = await pitch_deck_service.generate_ppt(deck_structure, deck_path)
        
        def iter_file():
            with open(file_path, 'rb') as file:
                yield from file
        
        # Return both the pitch deck and the quotation links
        return StreamingResponse(
            iter_file(),
            media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            headers={
                "Content-Disposition": f"attachment; filename=pitch_deck_{deck_id}.pptx",
                "X-Quote-ID": quote_id,
                "X-Quote-Link": f"/api/quotes/download-pdf/{quote_id}",
                "X-Deck-ID": deck_id,
                "X-Deck-Link": f"/api/quotes/download-pitch-deck/{deck_id}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download-pitch-deck/{deck_id}")
async def download_pitch_deck(deck_id: str):
    """Download a generated pitch deck"""
    try:
        file_path = Path(f"Data/pitch_decks/pitch_deck_{deck_id}.pptx")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Pitch deck file not found")
        
        def iter_file():
            with open(file_path, 'rb') as file:
                yield from file
        
        return StreamingResponse(
            iter_file(),
            media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            headers={
                "Content-Disposition": f"attachment; filename=pitch_deck_{deck_id}.pptx"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send-email/{quote_id}")
async def send_quote_email_endpoint(quote_id: str):
    """Send the quote and pitch deck to the customer via email."""
    try:
        # Load quote data (adjust path/logic as needed)
        quote_path = Path(f"Data/quotes/quote_{quote_id}.pdf")
        ppt_path = Path(f"Data/presentations/quote_{quote_id}_deck.pptx")
        if not quote_path.exists():
            raise HTTPException(status_code=404, detail="Quote PDF not found")
        if not ppt_path.exists():
            raise HTTPException(status_code=404, detail="Pitch deck not found")
        # Load quote metadata (implement as needed)
        # For example, load from DB or a JSON file
        # quote = load_quote_metadata(quote_id)
        quote = {}  # Replace with actual loading logic

        # Send the email (implement send_quote_email accordingly)
        send_quote_email(quote, str(ppt_path), str(quote_path))
        return {"status": "success", "message": "Email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))