from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from typing import Dict, Any
from sqlalchemy.orm import Session
import os
from pathlib import Path
import uuid

from db.database import get_db
from ai_services.simple_conversational_agent import SimpleConversationalAgent
from services.pdf_generator import PDFGenerator
from services.pitch_deck_service import PitchDeckService
from services.email_sender import send_quote_email  # You must have this implemented
from ai_services.azure_openai import AzureOpenAIProvider as AIServiceFactory  # Fixed relative import
from services.metrics_service import get_metrics_service
from ai_services.factory import AIServiceFactory

router = APIRouter()

@router.post("/generate-quote")
async def generate_quote(quote_request: Dict[str, Any]):
    """Generate a detailed quotation and pitch deck"""
    metrics_service = get_metrics_service()
    
    try:
        language = quote_request.get("language", "en")
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = SimpleConversationalAgent(base_provider)
        
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
        
        # Record successful quote generation
        metrics_service.record_quote_generation(status="success")
        
        return {
            "quote": quote,
            "quote_id": quote_id,
            "quote_link": f"/api/quotes/download-pdf/{quote_id}?language={language}",
            "pitch_deck_id": deck_id,
            "pitch_deck_link": f"/api/quotes/download-pitch-deck/{deck_id}"
        }
    except Exception as e:
        # Record failed quote generation
        metrics_service.record_quote_generation(status="failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-quote-with-pdf")
async def generate_quote_with_pdf(quote_request: Dict[str, Any]):
    """Generate a quotation with PDF file and pitch deck"""
    metrics_service = get_metrics_service()
    
    try:
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = SimpleConversationalAgent(base_provider)
        
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
        
        # Record successful quote generation
        metrics_service.record_quote_generation(status="success")
        
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
        # Record failed quote generation
        metrics_service.record_quote_generation(status="failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download-pdf/{quote_id}")
async def download_quote_pdf(quote_id: str, language: str = "en"):
    """Download PDF file for a quote with language support"""
    try:
        quotes_dir = Path("Data/quotes")
        
        # First try to find the language-specific file
        language_file_path = quotes_dir / f"quote_{quote_id}_{language}.pdf"
        
        # If language-specific file doesn't exist, try common language files
        if not language_file_path.exists():
            # Try Japanese first if not already tried
            if language != "ja":
                ja_file_path = quotes_dir / f"quote_{quote_id}_ja.pdf"
                if ja_file_path.exists():
                    language_file_path = ja_file_path
            
            # Try English if still not found
            if not language_file_path.exists() and language != "en":
                en_file_path = quotes_dir / f"quote_{quote_id}_en.pdf"
                if en_file_path.exists():
                    language_file_path = en_file_path
            
            # Fall back to original naming convention
            if not language_file_path.exists():
                language_file_path = quotes_dir / f"quote_{quote_id}.pdf"
        
        if not language_file_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")

        # Use FileResponse for efficient file serving and proper headers
        return FileResponse(
            path=language_file_path,
            media_type="application/pdf",
            filename=f"quote_{quote_id}.pdf",  # This sets Content-Disposition
            headers={
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
    metrics_service = get_metrics_service()
    
    try:
        # Generate the quote first
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = SimpleConversationalAgent(base_provider)
        
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
        
        # Record successful quote generation
        metrics_service.record_quote_generation(status="success")
        
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
        # Record failed quote generation
        metrics_service.record_quote_generation(status="failed")
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