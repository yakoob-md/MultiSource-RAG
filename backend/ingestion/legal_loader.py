import pdfplumber
from pathlib import Path

def load_legal_document(file_path: Path) -> tuple[str, list[str]]:
    """
    Safely reads physical PDF formats specifically for legal text pipelines. 
    Strictly handles text extraction cleanly without side effects.
    
    Returns:
        tuple containing:
        - full_text (str): Complete document text joined together.
        - pages (list[str]): Each explicit page cleanly extracted in an array index.
    """
    
    pages = []
    
    try:
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
    except Exception as e:
        raise ValueError(f"Failed to read PDF file {file_path.name}: {e}")

    full_text = "\n".join(pages)
    
    if not full_text:
        raise ValueError(f"No text could be extracted from {file_path.name}. It might be a scanned image-only PDF without OCR.")
        
    return full_text, pages
