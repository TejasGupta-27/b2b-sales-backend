from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from ai_services.factory import AIServiceFactory
from ai_services.b2b_sales_agent import B2BSalesAgent
from services.pdf_generator import PDFGenerator
import os
from pathlib import Path

router = APIRouter()

@router.post("/generate-quote")
async def generate_quote(quote_request: Dict[str, Any]):
    """Generate a detailed quotation"""
    try:
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = B2BSalesAgent(base_provider)
        
        quote = await sales_agent.generate_quote(quote_request)
        return {"quote": quote}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-quote-with-pdf")
async def generate_quote_with_pdf(quote_request: Dict[str, Any]):
    """Generate a quotation with PDF file"""
    try:
        base_provider = AIServiceFactory.create_provider("azure_openai")
        sales_agent = B2BSalesAgent(base_provider)
        
        quote = await sales_agent.generate_quote_with_pdf(quote_request)
        return {"quote": quote}
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
        
        return StreamingResponse(
            iter_file(),
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename=quote_{quote_id}.pdf"
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