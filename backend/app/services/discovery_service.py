"""
Company & Contact Discovery via SerpAPI + Gemini extraction.
"""
import json
import logging
import re
from typing import Optional

import httpx
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lead_gen import ProspectCompany, ProspectContact
from app.schema.lead_gen import DiscoverySearchRequest, DiscoverySearchResponse

logger = logging.getLogger("rdl_app_logger")

_SERP_URL = "https://serpapi.com/search"


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        max_output_tokens=2048,
        google_api_key=settings.GOOGLE_API_KEY,
    )


def _serp_search(query: str, num: int = 10) -> list[dict]:
    """Call SerpAPI and return organic results."""
    if not settings.SERP_API_KEY:
        logger.warning("[DISCOVERY] SERP_API_KEY not set — returning empty results")
        return []
    try:
        resp = httpx.get(
            _SERP_URL,
            params={"api_key": settings.SERP_API_KEY, "q": query, "num": num, "engine": "google"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("organic_results", [])
    except Exception as e:
        logger.error(f"[DISCOVERY] SerpAPI error: {e}")
        return []


def _extract_companies_with_ai(raw_results: list[dict], industry: str, location: str) -> list[dict]:
    """Use Gemini to extract structured company data from search snippets."""
    if not raw_results:
        return []
    snippets = "\n".join(
        f"- Title: {r.get('title','')} | URL: {r.get('link','')} | Snippet: {r.get('snippet','')}"
        for r in raw_results[:15]
    )
    prompt = f"""Extract company information from these Google search results about {industry} companies in {location}.
For each distinct company found, return a JSON array of objects with these fields:
- name (string, required)
- website (string, the URL)
- industry (string)
- description (string, 1-2 sentences about what they do)
- location (string)
- company_size (one of: "1-10", "11-50", "51-200", "201-500", "500+", or null)
- technologies (list of strings, tech stack if mentioned)

Search results:
{snippets}

Return ONLY a valid JSON array. No markdown, no explanation."""
    try:
        llm = _build_llm()
        response = llm.invoke(prompt)
        text = response.content.strip()
        # strip markdown fences if present
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except Exception as e:
        logger.error(f"[DISCOVERY] Company extraction failed: {e}")
        return []


def _extract_contacts_with_ai(raw_results: list[dict], company_name: str, target_role: str) -> list[dict]:
    """Use Gemini to extract contact info from search snippets."""
    if not raw_results:
        return []
    snippets = "\n".join(
        f"- Title: {r.get('title','')} | URL: {r.get('link','')} | Snippet: {r.get('snippet','')}"
        for r in raw_results[:10]
    )
    prompt = f"""Extract contact information for people at "{company_name}" with roles related to "{target_role}" from these search results.
Return a JSON array of objects with:
- name (string)
- job_title (string)
- email (string or null — only if explicitly found in the snippets)
- linkedin_url (string or null — only if a linkedin.com URL is present)

Search results:
{snippets}

Return ONLY a valid JSON array. If no contacts found, return []. No markdown, no explanation."""
    try:
        llm = _build_llm()
        response = llm.invoke(prompt)
        text = response.content.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except Exception as e:
        logger.error(f"[DISCOVERY] Contact extraction failed: {e}")
        return []


def _upsert_company(db: Session, data: dict) -> Optional[ProspectCompany]:
    name = (data.get("name") or "").strip()
    if not name:
        return None
    existing = db.query(ProspectCompany).filter(ProspectCompany.name.ilike(name)).first()
    if existing:
        return existing
    company = ProspectCompany(
        name=name,
        industry=data.get("industry"),
        website=data.get("website"),
        location=data.get("location"),
        company_size=data.get("company_size"),
        description=data.get("description"),
        technologies=data.get("technologies") or [],
        source="serpapi",
    )
    db.add(company)
    db.flush()
    return company


def _upsert_contact(db: Session, company: ProspectCompany, data: dict) -> Optional[ProspectContact]:
    name = (data.get("name") or "").strip()
    if not name:
        return None
    email = data.get("email")
    existing = None
    if email:
        existing = db.query(ProspectContact).filter(
            ProspectContact.company_id == company.id,
            ProspectContact.email == email,
        ).first()
    if not existing:
        existing = db.query(ProspectContact).filter(
            ProspectContact.company_id == company.id,
            ProspectContact.name.ilike(name),
        ).first()
    if existing:
        return existing
    contact = ProspectContact(
        company_id=company.id,
        name=name,
        email=email,
        job_title=data.get("job_title"),
        linkedin_url=data.get("linkedin_url"),
    )
    db.add(contact)
    db.flush()
    return contact


def run_discovery(db: Session, request: DiscoverySearchRequest) -> DiscoverySearchResponse:
    """Main entry point: search, extract, upsert, return results."""
    industry = request.industry or request.keywords or "business"
    location = request.location or ""
    size_hint = f"{request.company_size} company" if request.company_size else ""

    # Build company search query
    query_parts = [industry, "companies"]
    if location:
        query_parts.append(location)
    if size_hint:
        query_parts.append(size_hint)
    company_query = " ".join(query_parts)
    logger.info(f"[DISCOVERY] Searching: {company_query}")

    raw = _serp_search(company_query, num=min(request.max_results, 20))
    company_dicts = _extract_companies_with_ai(raw, industry, location)

    new_companies: list[ProspectCompany] = []
    new_contacts: list[ProspectContact] = []

    for cd in company_dicts:
        company = _upsert_company(db, cd)
        if company:
            new_companies.append(company)

            # Search for contacts at this company for each target role
            for role in (request.target_roles or []):
                contact_query = f'"{company.name}" {role} site:linkedin.com OR email'
                contact_raw = _serp_search(contact_query, num=5)
                contact_dicts = _extract_contacts_with_ai(contact_raw, company.name, role)
                for ct in contact_dicts:
                    contact = _upsert_contact(db, company, ct)
                    if contact:
                        new_contacts.append(contact)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[DISCOVERY] DB commit failed: {e}")
        raise

    # Refresh to load relationships
    for c in new_companies:
        db.refresh(c)
    for ct in new_contacts:
        db.refresh(ct)

    from app.schema.lead_gen import ProspectCompanyOut, ProspectContactOut
    return DiscoverySearchResponse(
        companies_found=len(new_companies),
        contacts_found=len(new_contacts),
        search_query=company_query,
        companies=[ProspectCompanyOut.model_validate(c) for c in new_companies],
        contacts=[ProspectContactOut.model_validate(ct) for ct in new_contacts],
    )
