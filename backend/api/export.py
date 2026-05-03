from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fpdf import FPDF
import os
import tempfile
import uuid

router = APIRouter()

class ExportRequest(BaseModel):
    title: str
    content: str
    citations: list[dict] = []

class PDFGenerator(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 12)
        self.cell(0, 10, 'InteleX Research Memorandum', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

import re

def _clean_text(text: str) -> str:
    """Strip emojis and non-latin characters that crash FPDF."""
    # Remove markdown headers and emojis
    text = text.replace('#', '')
    # Keep only common latin characters and punctuation
    return re.sub(r'[^\x00-\x7F]+', '', text)

@router.post("/pdf")
async def export_pdf(req: ExportRequest):
    try:
        pdf = PDFGenerator()
        pdf.add_page()
        
        # Title
        pdf.set_font("helvetica", 'B', 16)
        pdf.multi_cell(0, 10, _clean_text(req.title))
        pdf.ln(10)
        
        # Content
        pdf.set_font("helvetica", '', 11)
        pdf.multi_cell(0, 7, _clean_text(req.content))
        
        # Citations
        if req.citations:
            pdf.ln(10)
            pdf.set_font("helvetica", 'B', 12)
            pdf.cell(0, 10, 'Sources & Citations', 0, 1)
            pdf.set_font("helvetica", '', 9)
            for i, cite in enumerate(req.citations):
                # Use .get() carefully for field names coming from frontend
                source_title = cite.get('source_title') or cite.get('sourceTitle') or "Source"
                ref = cite.get('reference') or ""
                text = f"[{i+1}] {source_title} - {ref}"
                pdf.multi_cell(0, 5, _clean_text(text))
        
        # Save to temp file
        tmp_dir = tempfile.gettempdir()
        filename = f"research_{uuid.uuid4().hex[:8]}.pdf"
        filepath = os.path.join(tmp_dir, filename)
        pdf.output(filepath)
        
        return FileResponse(
            path=filepath, 
            filename=filename,
            media_type='application/pdf'
        )
    except Exception as e:
        print(f"[Export] PDF Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
