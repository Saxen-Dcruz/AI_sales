"""
AI-powered lead scoring using Gemini.
Scores prospect companies/contacts on relevance to RDL Technologies' products.
"""
import json
import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lead_gen import CampaignContact, OutreachCampaign, ProspectCompany, ProspectContact

logger = logging.getLogger("rdl_app_logger")

_SCORING_PROMPT = """You are a B2B sales qualification expert for RDL Technologies, a company that makes industrial IoT products: data loggers, PLCs, sensors, biometric systems, SCADA software, and industrial automation equipment.

Score this prospect on a scale of 0-100 for likelihood of being interested in industrial automation/IoT products.

Company: {company_name}
Industry: {industry}
Description: {description}
Size: {size}
Technologies: {technologies}
Contact Role: {job_title}
Campaign Target: {campaign_context}

Scoring criteria:
- 80-100: Manufacturing, industrial, factory automation, energy, utilities, oil & gas companies with technical decision makers
- 60-79: Engineering firms, construction, logistics with operations/technical staff
- 40-59: Mid-sized businesses with potential automation needs
- 20-39: Service companies, unlikely but possible need
- 0-19: No relevance (pure software, finance, media, etc.)

Return ONLY valid JSON (no markdown):
{{
  "score": <integer 0-100>,
  "interest_level": "<hot|warm|cold>",
  "reasoning": "<one sentence why>",
  "ideal_customer_fit": <true|false>
}}"""


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        max_output_tokens=256,
        google_api_key=settings.GOOGLE_API_KEY,
    )


def score_prospect(
    company: ProspectCompany,
    contact: ProspectContact,
    campaign: OutreachCampaign | None = None,
) -> dict:
    """Score a single prospect. Returns {score, interest_level, reasoning, ideal_customer_fit}."""
    campaign_context = ""
    if campaign:
        campaign_context = f"{campaign.name} — targeting {campaign.target_industry or ''} {', '.join(campaign.target_roles or [])}"

    prompt = _SCORING_PROMPT.format(
        company_name=company.name,
        industry=company.industry or "Unknown",
        description=(company.description or "")[:300],
        size=company.company_size or "Unknown",
        technologies=", ".join(company.technologies or []) or "Unknown",
        job_title=contact.job_title or "Unknown",
        campaign_context=campaign_context or "General industrial automation",
    )
    try:
        llm = _build_llm()
        response = llm.invoke(prompt)
        text = response.content.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        result = json.loads(text)
        return {
            "score": int(result.get("score", 50)),
            "interest_level": result.get("interest_level", "warm"),
            "reasoning": result.get("reasoning", ""),
            "ideal_customer_fit": bool(result.get("ideal_customer_fit", False)),
        }
    except Exception as e:
        logger.error(f"[LEAD SCORER] Scoring failed for {company.name}: {e}")
        return {"score": 50, "interest_level": "warm", "reasoning": "Scoring unavailable", "ideal_customer_fit": False}


def batch_score_companies(db: Session, company_ids: list | None = None) -> int:
    """Score all unscored companies (or a specific list). Returns count updated."""
    q = db.query(ProspectCompany)
    if company_ids:
        q = q.filter(ProspectCompany.id.in_(company_ids))
    else:
        q = q.filter(ProspectCompany.ai_score.is_(None))

    companies = q.all()
    updated = 0
    for company in companies:
        # Use first contact or dummy contact for scoring
        contact = db.query(ProspectContact).filter(ProspectContact.company_id == company.id).first()
        if not contact:
            contact = ProspectContact(name="", job_title="", company_id=company.id)
        result = score_prospect(company, contact)
        company.ai_score = result["score"]
        company.ai_score_reasoning = result["reasoning"]
        company.interest_level = result["interest_level"]
        updated += 1
    db.commit()
    logger.info(f"[LEAD SCORER] Scored {updated} companies")
    return updated
