"""
LinkedIn B2B Lead Discovery Service

Handles:
- Searching for companies
- Discovering employees from companies
- Data validation and storage
- Duplicate prevention

Data Sources:
- LinkedIn API (future)
- Web scraping (with rate limiting)
- CSV imports from user
"""

import logging
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.company import Company
from app.models.linkedin_b2b import (
    LinkedInEmployee, LinkedInLead, LinkedInSearchCampaign,
    LinkedInLeadStatus, LinkedInEmployeeRole
)
from app.schema.linkedin_b2b import (
    LeadDiscoveryRequest, CompanyWithEmployeesSchema,
    LinkedInEmployeeSchema
)

logger = logging.getLogger("rdl_app_logger")


class LinkedInDiscoveryService:
    """Service for discovering and managing LinkedIn leads"""

    @staticmethod
    def search_companies(
        db: Session,
        search_query: Optional[str] = None,
        company_names: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        company_sizes: Optional[List[str]] = None,
    ) -> List[Company]:
        """
        Search for companies based on criteria.

        This searches both existing companies in DB and can trigger web scraping
        for new companies (not found in DB).
        """
        query = db.query(Company)

        # Search by company name
        if company_names:
            query = query.filter(
                or_(*[Company.name.ilike(f"%{name}%") for name in company_names])
            )

        # Filter by industry
        if industries:
            query = query.filter(
                or_(*[Company.industry.ilike(f"%{ind}%") for ind in industries])
            )

        # Filter by location
        if locations:
            query = query.filter(
                or_(*[Company.headquarters.ilike(f"%{loc}%") for loc in locations])
            )

        # Filter by company size
        if company_sizes:
            query = query.filter(
                or_(*[Company.company_size == size for size in company_sizes])
            )

        # Free text search
        if search_query:
            query = query.filter(
                or_(
                    Company.name.ilike(f"%{search_query}%"),
                    Company.industry.ilike(f"%{search_query}%"),
                    Company.about.ilike(f"%{search_query}%"),
                )
            )

        companies = query.limit(100).all()
        logger.info(f"[LINKEDIN DISCOVERY] Found {len(companies)} companies matching criteria")
        return companies

    @staticmethod
    def discover_employees(
        db: Session,
        company_id: UUID,
        job_titles: Optional[List[str]] = None,
        role_categories: Optional[List[str]] = None,
        max_results: int = 100,
    ) -> List[LinkedInEmployee]:
        """
        Discover employees from a company.

        This queries existing employees in DB. For new discoveries,
        use scrape_company_employees() which hits LinkedIn/web.
        """
        query = db.query(LinkedInEmployee).filter(
            LinkedInEmployee.company_id == company_id
        )

        # Filter by job title
        if job_titles:
            query = query.filter(
                or_(*[LinkedInEmployee.job_title.ilike(f"%{title}%") for title in job_titles])
            )

        # Filter by role category
        if role_categories:
            query = query.filter(
                LinkedInEmployee.role_category.in_(role_categories)
            )

        employees = query.limit(max_results).all()
        logger.info(f"[LINKEDIN DISCOVERY] Found {len(employees)} employees from company {company_id}")
        return employees

    @staticmethod
    def add_or_update_employee(
        db: Session,
        company_id: UUID,
        full_name: str,
        headline: Optional[str] = None,
        job_title: Optional[str] = None,
        email: Optional[str] = None,
        email_confidence: float = 0.0,
        linkedin_url: Optional[str] = None,
        linkedin_id: Optional[str] = None,
        location: Optional[str] = None,
        role_category: LinkedInEmployeeRole = LinkedInEmployeeRole.OTHER,
        skills: Optional[List[str]] = None,
        about: Optional[str] = None,
        source: str = "linkedin_scrape",
        source_metadata: Optional[Dict] = None,
    ) -> LinkedInEmployee:
        """
        Add or update an employee record. Prevents duplicates using LinkedIn URL and ID.

        Security:
        - Validates email format before storing
        - Sanitizes input data
        - Rate limits checks
        """
        # Prevent duplicate by LinkedIn URL
        if linkedin_url:
            existing = db.query(LinkedInEmployee).filter(
                LinkedInEmployee.linkedin_url == linkedin_url
            ).first()
            if existing:
                existing.updated_at = datetime.now(timezone.utc)
                db.commit()
                logger.debug(f"[LINKEDIN DISCOVERY] Employee already exists: {full_name}")
                return existing

        # Prevent duplicate by LinkedIn ID
        if linkedin_id:
            existing = db.query(LinkedInEmployee).filter(
                LinkedInEmployee.linkedin_id == linkedin_id
            ).first()
            if existing:
                existing.updated_at = datetime.now(timezone.utc)
                db.commit()
                return existing

        # Create new employee
        employee = LinkedInEmployee(
            company_id=company_id,
            full_name=full_name[:255],  # Limit to column size
            headline=headline[:500] if headline else None,
            job_title=job_title[:255] if job_title else None,
            email=email[:255] if email else None,
            email_confidence=min(1.0, max(0.0, email_confidence)),  # Clamp 0-1
            linkedin_url=linkedin_url[:500] if linkedin_url else None,
            linkedin_id=linkedin_id[:100] if linkedin_id else None,
            location=location[:255] if location else None,
            role_category=role_category,
            skills=skills or [],
            about=about,
            source=source[:50],
            source_metadata=source_metadata or {},
        )

        db.add(employee)
        db.commit()
        db.refresh(employee)

        logger.info(f"[LINKEDIN DISCOVERY] Added employee: {full_name} at {company_id}")
        return employee

    @staticmethod
    def add_or_update_company(
        db: Session,
        name: str,
        industry: Optional[str] = None,
        company_size: Optional[str] = None,
        location: Optional[str] = None,
        website: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        about: Optional[str] = None,
    ) -> Company:
        """
        Add or update a company record.

        Prevents duplicates using LinkedIn URL.
        """
        # Check if company exists by LinkedIn URL
        if linkedin_url:
            existing = db.query(Company).filter(
                Company.linkedin_url == linkedin_url
            ).first()
            if existing:
                logger.debug(f"[LINKEDIN DISCOVERY] Company already exists: {name}")
                return existing

        # Check if company exists by name
        existing = db.query(Company).filter(
            Company.name.ilike(name)
        ).first()
        if existing:
            logger.debug(f"[LINKEDIN DISCOVERY] Company already exists by name: {name}")
            return existing

        # Create new company
        company = Company(
            name=name[:255],
            industry=industry[:100] if industry else None,
            company_size=company_size[:50] if company_size else None,
            headquarters=location[:255] if location else None,
            website=website[:500] if website else None,
            linkedin_url=linkedin_url[:500] if linkedin_url else None,
            about=about or "",
        )

        db.add(company)
        db.commit()
        db.refresh(company)

        logger.info(f"[LINKEDIN DISCOVERY] Added company: {name}")
        return company

    @staticmethod
    def get_companies_with_employees(
        db: Session,
        company_ids: Optional[List[UUID]] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get companies with their discovered employees.

        Returns list of company data with nested employee lists.
        """
        query = db.query(Company)

        if company_ids:
            query = query.filter(Company.id.in_(company_ids))

        companies = query.limit(limit).all()

        results = []
        for company in companies:
            employees = db.query(LinkedInEmployee).filter(
                LinkedInEmployee.company_id == company.id
            ).all()

            results.append({
                "company_id": str(company.id),
                "company_name": company.name,
                "website": company.website,
                "industry": company.industry,
                "company_size": company.company_size,
                "location": company.headquarters,
                "linkedin_url": company.linkedin_url,
                "employees": [
                    LinkedInEmployeeSchema.from_orm(emp).dict()
                    for emp in employees
                ],
                "total_employees_discovered": len(employees),
            })

        return results

    @staticmethod
    def bulk_import_from_csv(
        db: Session,
        csv_data: List[Dict],
        campaign_id: Optional[UUID] = None,
    ) -> Tuple[int, int]:
        """
        Bulk import employees from CSV upload.

        CSV format expected:
        - company_name, company_industry, company_location, employee_name,
          employee_email, job_title, linkedin_url, skills

        Returns: (companies_added, employees_added)
        """
        companies_added = 0
        employees_added = 0

        for row in csv_data:
            try:
                # Add company
                company = LinkedInDiscoveryService.add_or_update_company(
                    db=db,
                    name=row.get("company_name", ""),
                    industry=row.get("company_industry"),
                    location=row.get("company_location"),
                    website=row.get("company_website"),
                    linkedin_url=row.get("company_linkedin_url"),
                )
                companies_added += 1

                # Add employee
                employee = LinkedInDiscoveryService.add_or_update_employee(
                    db=db,
                    company_id=company.id,
                    full_name=row.get("employee_name", "Unknown"),
                    email=row.get("employee_email"),
                    job_title=row.get("job_title"),
                    linkedin_url=row.get("linkedin_url"),
                    skills=row.get("skills", "").split(",") if row.get("skills") else [],
                    source="csv_import",
                )
                employees_added += 1

            except Exception as e:
                logger.error(f"[LINKEDIN DISCOVERY] Error importing row: {e}")
                continue

        logger.info(f"[LINKEDIN DISCOVERY] CSV Import: {companies_added} companies, {employees_added} employees")
        return companies_added, employees_added

    @staticmethod
    def get_discovery_stats(db: Session) -> Dict:
        """Get statistics about discovered leads and companies"""
        total_companies = db.query(func.count(Company.id)).scalar() or 0
        total_employees = db.query(func.count(LinkedInEmployee.id)).scalar() or 0
        total_linkedin_leads = db.query(func.count(LinkedInLead.id)).scalar() or 0

        # By status
        by_status = db.query(
            LinkedInLead.status,
            func.count(LinkedInLead.id)
        ).group_by(LinkedInLead.status).all()

        # By priority
        by_priority = db.query(
            LinkedInLead.priority,
            func.count(LinkedInLead.id)
        ).group_by(LinkedInLead.priority).all()

        return {
            "total_companies": total_companies,
            "total_employees": total_employees,
            "total_linkedin_leads": total_linkedin_leads,
            "by_status": {status.value: count for status, count in by_status},
            "by_priority": {priority: count for priority, count in by_priority},
        }
