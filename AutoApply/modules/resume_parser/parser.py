import asyncio
import json
import fitz  # pymupdf
from loguru import logger
from core.config import get_config
from core.database import save_profile, get_profile
from core.utils.ai_client import AIClient

RESUME_PARSE_PROMPT = """You are a resume parser. Extract structured data from this resume text.
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
Use this exact structure:
{
  "name": "", "email": "", "phone": "", "linkedin_url": "", "github_url": "",
  "location": "", "summary": "", "total_years_experience": 0,
  "skills": [],
  "experience": [
    { "title": "", "company": "", "duration": "", "years": 0, "description": "", "technologies": [] }
  ],
  "education": [{ "degree": "", "institution": "", "year": "" }],
  "certifications": [],
  "target_roles": []
}
RESUME TEXT:
"""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file using pymupdf."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


async def _parse_with_ai(resume_text: str) -> dict | None:
    """Send resume text to AI for structured extraction."""
    config = get_config()
    ai = AIClient(config)
    prompt = RESUME_PARSE_PROMPT + resume_text
    result = await ai.ask_json(prompt)
    return result


def parse_resume(pdf_path: str) -> dict | None:
    """Parse a resume PDF and save structured profile to DB.
    
    Returns the parsed profile dict, or None on failure.
    """
    logger.info(f"Extracting text from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        logger.error("No text extracted from PDF")
        return None

    logger.info(f"Extracted {len(text)} chars, sending to AI for parsing...")
    profile = asyncio.run(_parse_with_ai(text))
    
    if not profile:
        logger.error("AI failed to parse resume")
        return None

    save_profile(profile)
    logger.success(f"Profile saved: {profile.get('name', 'Unknown')} — {len(profile.get('skills', []))} skills, {len(profile.get('experience', []))} positions")
    return profile
