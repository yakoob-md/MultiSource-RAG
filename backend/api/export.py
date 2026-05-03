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
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'InteleX Research Memorandum', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

@router.post("/pdf")
async def export_pdf(req: ExportRequest):
    try:
        pdf = PDFGenerator()
        pdf.add_page()
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.multi_cell(0, 10, req.title)
        pdf.ln(10)
        
        # Content
        pdf.set_font("Arial", '', 11)
        # Simple markdown to plain text conversion for fpdf
        clean_content = req.content.replace('# ', '').replace('## ', '').replace('### ', '')
        pdf.multi_cell(0, 7, clean_content)
        
        # Citations
        if req.citations:
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, 'Sources & Citations', 0, 1)
            pdf.set_font("Arial", '', 9)
            for i, cite in enumerate(req.citations):
                text = f"[{i+1}] {cite.get('sourceTitle', 'Source')} - {cite.get('reference', '')}"
                pdf.multi_cell(0, 5, text)
        
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
        raise HTTPException(status_code=500, detail=str(e))
