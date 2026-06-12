"""
LinkedIn B2B Lead Qualification Service

Uses Gemini AI to:
- Score leads based on company + employee data
- Calculate interest probability
- Identify decision makers
- Determine product relevance
- Assess budget authority and timing

Scoring Factors:
- Company industry fit
- Employee role/seniority
- Company size alignment
- Technology stack usage
- Recent company activities
"""

import logging
import json
import re
from typing import Dict, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.linkedin_b2b import (
    LinkedInLead, LinkedInEmployee, LinkedInLeadStatus, LinkedInLeadAnalytics
)
from app.models.company import Company
from app.core.config import settings

logger = logging.getLogger("rdl_app_logger")

# Import Gemini via LangChain (same as discovery_service)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("[LINKEDIN QUALIFICATION] langchain_google_genai not available")


def _build_llm() -> "ChatGoogleGenerativeAI":
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        max_output_tokens=1024,
        google_api_key=settings.GOOGLE_API_KEY,
    )


QUALIFICATION_PROMPT = """
You are a B2B lead qualification expert. Score a LinkedIn lead based on the provided data.

Company Data:
- Name: {company_name}
- Industry: {company_industry}
- Size: {company_size}
- Location: {company_location}
- Website: {company_website}
- About: {company_about}

Employee Data:
- Name: {employee_name}
- Job Title: {employee_title}
- Current Role: {employee_role}
- Seniority: {employee_seniority}
- Location: {employee_location}
- Skills: {employee_skills}
- About: {employee_about}

Our Products/Services:
{our_products}

Please provide:
1. Overall Qualification Score (0-100): How likely is this lead to be interested in our products?
2. Interest Probability (0-1): Probability they would consider our solution
3. Product Relevance (0-1): How relevant are our products to their business?
4. Budget Authority (0-1): Likelihood they have budget and authority to decide
5. Timing (0-1): How soon are they likely to make a purchase?

Respond in JSON format:
{{
    "overall_score": <0-100>,
    "interest_probability": <0-1>,
    "product_relevance": <0-1>,
    "budget_authority": <0-1>,
    "timing": <0-1>,
    "reasoning": "<human-readable explanation>",
    "key_factors": ["factor1", "factor2", "factor3"],
    "recommended_messaging": "<brief suggestion for outreach message>",
    "risk_factors": ["risk1", "risk2"]
}}

Return ONLY valid JSON. No markdown, no explanation.
"""


class LinkedInLeadQualificationService:
    """Service for AI-powered lead qualification using Gemini"""

    @staticmethod
    def qualify_lead(
        db: Session,
        linkedin_lead_id: UUID,
        company_id: UUID,
        employee_id: UUID,
        force_requalify: bool = False,
    ) -> Dict:
        """
        Qualify a single lead using Gemini AI.
        Scores the lead and updates the database.
        Returns the qualification results.
        """
        if not GEMINI_AVAILABLE:
            logger.error("[LINKEDIN QUALIFICATION] Gemini (langchain_google_genai) not available")
            return {"error": "AI qualification unavailable"}

        # Fetch lead data
        lead = db.query(LinkedInLead).filter(
            LinkedInLead.id == linkedin_lead_id
        ).first()

        if not lead:
            return {"error": "Lead not found"}

        # Skip if already qualified (unless force requalify)
        if lead.qualification_score > 0 and not force_requalify:
            logger.debug(f"[LINKEDIN QUALIFICATION] Lead already qualified: {linkedin_lead_id}")
            return {
                "score": lead.qualification_score,
                "status": "already_qualified"
            }

        # Fetch company and employee data
        company = db.query(Company).filter(Company.id == company_id).first()
        employee = db.query(LinkedInEmployee).filter(
            LinkedInEmployee.id == employee_id
        ).first()

        if not company or not employee:
            return {"error": "Company or employee not found"}

        our_products = LinkedInLeadQualificationService._get_product_description()

        prompt = QUALIFICATION_PROMPT.format(
            company_name=company.name or "Unknown",
            company_industry=company.industry or "Unknown",
            company_size=company.company_size or "Unknown",
            company_location=company.headquarters or "Unknown",
            company_website=company.website or "Not provided",
            company_about=company.about or "No description",
            employee_name=employee.full_name or "Unknown",
            employee_title=employee.headline or "Unknown",
            employee_role=employee.role_category.value or "Unknown",
            employee_seniority=employee.seniority_level or "Unknown",
            employee_location=employee.location or "Unknown",
            employee_skills=", ".join(employee.skills) if employee.skills else "Not specified",
            employee_about=employee.about or "No bio",
            our_products=our_products,
        )

        try:
            llm = _build_llm()
            response = llm.invoke(prompt)
            text = response.content.strip()
            # Strip markdown fences if Gemini wraps the JSON
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            qualification_data = json.loads(text)

            # Validate response structure
            required_fields = ["overall_score", "interest_probability", "product_relevance"]
            if not all(field in qualification_data for field in required_fields):
                logger.error(f"[LINKEDIN QUALIFICATION] Invalid response structure: {text}")
                return {"error": "Invalid AI response"}

            # Update lead in database
            lead.qualification_score    = float(qualification_data.get("overall_score", 0))
            lead.interest_probability   = float(qualification_data.get("interest_probability", 0))
            lead.product_relevance      = float(qualification_data.get("product_relevance", 0))
            lead.budget_authority       = float(qualification_data.get("budget_authority", 0))
            lead.timing                 = float(qualification_data.get("timing", 0))

            lead.qualification_reasoning = qualification_data.get("reasoning", "")
            lead.qualification_factors = {
                "key_factors":            qualification_data.get("key_factors", []),
                "recommended_messaging":  qualification_data.get("recommended_messaging", ""),
                "risk_factors":           qualification_data.get("risk_factors", []),
            }
            lead.qualified_at = datetime.now(timezone.utc)
            lead.qualified_by = "ai"

            # Auto-set priority based on score
            if lead.qualification_score >= 70:
                lead.status   = LinkedInLeadStatus.QUALIFIED
                lead.priority = "high" if lead.qualification_score >= 80 else "medium"
            else:
                lead.priority = "low"

            # Create analytics record if it doesn't exist yet
            if not lead.analytics:
                analytics = LinkedInLeadAnalytics(linkedin_lead_id=linkedin_lead_id)
                db.add(analytics)

            db.commit()
            db.refresh(lead)

            logger.info(f"[LINKEDIN QUALIFICATION] Lead qualified: {employee.full_name} (Score: {lead.qualification_score})")

            return {
                "linkedin_lead_id":   str(linkedin_lead_id),
                "overall_score":      lead.qualification_score,
                "interest_probability": lead.interest_probability,
                "product_relevance":  lead.product_relevance,
                "budget_authority":   lead.budget_authority,
                "timing":             lead.timing,
                "status":             lead.status.value,
                "priority":           lead.priority,
                "reasoning":          lead.qualification_reasoning,
            }

        except json.JSONDecodeError as e:
            logger.error(f"[LINKEDIN QUALIFICATION] JSON parsing error: {e}")
            return {"error": "Failed to parse AI response"}
        except Exception as e:
            logger.error(f"[LINKEDIN QUALIFICATION] Error: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def qualify_batch(
        db: Session,
        linkedin_lead_ids: list,
        force_requalify: bool = False,
    ) -> Dict:
        """Qualify multiple leads in batch. Returns summary of results."""
        results = {
            "total":        len(linkedin_lead_ids),
            "qualified":    0,
            "high_priority": 0,
            "errors":       0,
            "details":      [],
        }

        for lead_id in linkedin_lead_ids:
            try:
                lead = db.query(LinkedInLead).filter(LinkedInLead.id == lead_id).first()
                if not lead:
                    results["errors"] += 1
                    continue

                result = LinkedInLeadQualificationService.qualify_lead(
                    db=db,
                    linkedin_lead_id=lead_id,
                    company_id=lead.company_id,
                    employee_id=lead.employee_id,
                    force_requalify=force_requalify,
                )

                if "error" not in result:
                    results["qualified"] += 1
                    if result.get("overall_score", 0) >= 80:
                        results["high_priority"] += 1
                    results["details"].append(result)
                else:
                    results["errors"] += 1

            except Exception as e:
                logger.error(f"[LINKEDIN QUALIFICATION] Batch error: {e}")
                results["errors"] += 1
                continue

        logger.info(f"[LINKEDIN QUALIFICATION] Batch complete: {results['qualified']} qualified, {results['errors']} errors")
        return results

    @staticmethod
    def _get_product_description() -> str:
        """Get description of our products/services for AI context."""
        if hasattr(settings, 'PRODUCT_DESCRIPTION') and settings.PRODUCT_DESCRIPTION:
            return settings.PRODUCT_DESCRIPTION
        return """
        Our products/services are B2B SaaS solutions focused on:
        - Sales automation and lead generation
        - Email and LinkedIn outreach automation
        - AI-powered lead qualification
        - Conversation automation
        """

    @staticmethod
    def get_qualification_summary(db: Session) -> Dict:
        """Get summary statistics of lead qualifications."""
        from sqlalchemy import func

        total_leads     = db.query(func.count(LinkedInLead.id)).scalar() or 0
        qualified_leads = db.query(func.count(LinkedInLead.id)).filter(
            LinkedInLead.status == LinkedInLeadStatus.QUALIFIED
        ).scalar() or 0
        avg_score       = db.query(func.avg(LinkedInLead.qualification_score)).scalar() or 0
        high_priority   = db.query(func.count(LinkedInLead.id)).filter(
            LinkedInLead.priority == "high"
        ).scalar() or 0

        return {
            "total_leads":        total_leads,
            "qualified_leads":    qualified_leads,
            "qualification_rate": (qualified_leads / total_leads * 100) if total_leads > 0 else 0,
            "average_score":      round(avg_score, 2),
            "high_priority_leads": high_priority,
        }
