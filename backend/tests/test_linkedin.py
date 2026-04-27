"""
Tests for Phase 4 LinkedIn module:
  - sourcing: city/industry lists, query variants, URL extraction, deduplication
  - linkedin_templates: role classifier, industry classifier, template generation
  - linkedin_outreach_service: budget tracking, record management, queue logic
  - router endpoints: stats, budget, CRUD, queue-connection, queue-message, reply, template preview
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database.core import SessionLocal

BASE = "/api/v1/linkedin"


@contextmanager
def _no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        yield
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def _insert_outreach(**kwargs):
    from app.models.linkedin import LinkedInOutreach
    defaults = {
        "linkedin_url":   f"https://linkedin.com/in/test-{uuid.uuid4().hex[:8]}",
        "full_name":      "Test Person",
        "headline":       "CEO at Test Company",
        "company_name":   "Test Manufacturing Ltd",
        "role_category":  "c_suite",
        "industry_tag":   "pharmaceutical manufacturing",
        "city_tag":       "Mumbai",
        "connection_status": "not_sent",
        "message_status":    "not_sent",
    }
    defaults.update(kwargs)
    with SessionLocal() as db:
        rec = LinkedInOutreach(**defaults)
        db.add(rec); db.commit(); db.refresh(rec)
        return rec.id


# ── Sourcing module — list coverage ──────────────────────────────────────────

def test_sourcing_cities_count():
    """ALL_CITIES must contain at least 200 unique entries."""
    from app.scripts.linkedin.sourcing import ALL_CITIES
    assert len(ALL_CITIES) >= 200, f"Expected ≥200 cities, got {len(ALL_CITIES)}"
    assert len(set(ALL_CITIES)) == len(ALL_CITIES), "Duplicate cities in list"


def test_sourcing_industries_count():
    """INDUSTRIES must contain at least 60 unique entries."""
    from app.scripts.linkedin.sourcing import INDUSTRIES
    assert len(INDUSTRIES) >= 60, f"Expected ≥60 industries, got {len(INDUSTRIES)}"
    assert len(set(INDUSTRIES)) == len(INDUSTRIES), "Duplicate industries in list"


def test_sourcing_query_variants_count():
    """Must have at least 4 query variants per pair to break DDGS top-10 trap."""
    from app.scripts.linkedin.sourcing import QUERY_VARIANTS
    assert len(QUERY_VARIANTS) >= 4


def test_sourcing_query_variants_all_have_placeholders():
    """Every variant must contain {industry} and {city} placeholders."""
    from app.scripts.linkedin.sourcing import QUERY_VARIANTS
    for v in QUERY_VARIANTS:
        assert "{industry}" in v, f"Missing {{industry}} in: {v}"
        assert "{city}" in v, f"Missing {{city}} in: {v}"


def test_sourcing_query_variant_renders():
    """Rendered query must not contain raw placeholder text."""
    from app.scripts.linkedin.sourcing import QUERY_VARIANTS
    for v in QUERY_VARIANTS:
        rendered = v.format(industry="pharma", city="Mumbai")
        assert "{industry}" not in rendered
        assert "{city}" not in rendered
        assert "pharma" in rendered
        assert "Mumbai" in rendered


def test_sourcing_cities_includes_key_india_hubs():
    from app.scripts.linkedin.sourcing import CITIES_INDIA
    required = ["Mumbai", "Pune", "Chennai", "Ahmedabad", "Bengaluru",
                "Coimbatore", "Ludhiana", "Pimpri-Chinchwad"]
    for city in required:
        assert city in CITIES_INDIA, f"Key Indian hub '{city}' missing from city list"


def test_sourcing_cities_includes_international():
    from app.scripts.linkedin.sourcing import CITIES_INTERNATIONAL
    required = ["Dubai", "Singapore", "London", "Frankfurt", "Shanghai"]
    for city in required:
        assert city in CITIES_INTERNATIONAL, f"International city '{city}' missing"


def test_sourcing_industries_covers_key_sectors():
    from app.scripts.linkedin.sourcing import INDUSTRIES
    keywords = ["pharma", "petroleum", "textile", "automotive", "chemical",
                "food", "steel", "electronics", "cement", "packaging"]
    for kw in keywords:
        assert any(kw in ind for ind in INDUSTRIES), f"Industry keyword '{kw}' not found in any industry"


# ── Sourcing — DDGS/Google extraction ─────────────────────────────────────────

def test_ddgs_search_extracts_linkedin_urls():
    """_ddgs_search must return only linkedin.com/company/ URLs, stripping /dir/ noise."""
    from app.scripts.linkedin.sourcing import _ddgs_search
    fake_results = [
        {"href": "https://www.linkedin.com/company/rdltech/"},
        {"href": "https://www.linkedin.com/company/abc-pharma/?trk=123"},
        {"href": "https://www.linkedin.com/dir/some/path"},
        {"href": "https://example.com/some/page"},
    ]
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
    mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
    mock_ddgs_instance.text.return_value = fake_results
    # Patch at the duckduckgo_search module level since it's a local import inside the function
    with patch("ddgs.DDGS", return_value=mock_ddgs_instance):
        urls = _ddgs_search("test query", max_results=10)
    assert "https://www.linkedin.com/company/rdltech" in urls
    assert "https://www.linkedin.com/company/abc-pharma" in urls
    assert all("/dir/" not in u for u in urls)
    assert all("linkedin.com/company/" in u for u in urls)


def test_google_search_extracts_linkedin_urls():
    """_google_search must return only linkedin.com/company/ URLs."""
    from app.scripts.linkedin.sourcing import _google_search
    fake_urls = [
        "https://www.linkedin.com/company/test-pharma/about",
        "https://example.com/irrelevant",
        "https://www.linkedin.com/company/rdltech/",
        "https://www.linkedin.com/dir/nope",
    ]
    # googlesearch.search is imported inside the function — patch at origin module
    with patch("googlesearch.search", return_value=iter(fake_urls)):
        urls = _google_search("test", 10)
    assert len(urls) == 2
    assert all("linkedin.com/company/" in u for u in urls)
    assert all("/dir/" not in u for u in urls)


def test_bing_search_extracts_linkedin_urls():
    """_bing_search must extract linkedin.com/company/ URLs from Bing HTML."""
    from app.scripts.linkedin.sourcing import _bing_search
    import requests as req_mod
    fake_html = '''
    <html><body>
    <a href="https://www.linkedin.com/company/rdltech/">RDL</a>
    <a href="https://www.linkedin.com/company/pharma-co/?trk=abc">Pharma</a>
    <a href="https://www.linkedin.com/dir/noise">Noise</a>
    <a href="https://example.com/other">Other</a>
    </body></html>
    '''
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html
    with patch("requests.get", return_value=mock_resp):
        urls = _bing_search("test query", max_results=5)
    assert any("linkedin.com/company/" in u for u in urls)
    assert all("/dir/" not in u for u in urls)


def test_search_with_fallback_uses_ddgs_first():
    """Primary path: DDGS returns results → Bing and Google NOT called."""
    from app.scripts.linkedin.sourcing import _search_with_fallback
    with (
        patch("app.scripts.linkedin.sourcing._ddgs_search",
              return_value=[f"https://linkedin.com/company/co{i}" for i in range(10)]) as mock_ddgs,
        patch("app.scripts.linkedin.sourcing._bing_search") as mock_bing,
        patch("app.scripts.linkedin.sourcing._google_search") as mock_google,
    ):
        urls = _search_with_fallback("test query")
    mock_ddgs.assert_called_once()
    mock_bing.assert_not_called()
    mock_google.assert_not_called()
    assert len(urls) == 10


def test_search_with_fallback_tries_bing_before_google():
    """DDGS < 5 results → Bing tried next, Google only if Bing also < 5."""
    from app.scripts.linkedin.sourcing import _search_with_fallback
    with (
        patch("app.scripts.linkedin.sourcing._ddgs_search", return_value=["https://linkedin.com/company/ddgs-1"]),
        patch("app.scripts.linkedin.sourcing._bing_search",
              return_value=[f"https://linkedin.com/company/bing-{i}" for i in range(8)]) as mock_bing,
        patch("app.scripts.linkedin.sourcing._google_search") as mock_google,
    ):
        urls = _search_with_fallback("test query")
    mock_bing.assert_called_once()
    mock_google.assert_not_called()      # Bing returned enough — Google skipped
    assert len(urls) >= 8


def test_search_with_fallback_triggers_google_when_ddgs_and_bing_return_few():
    """If DDGS and Bing both return < 5, Google fallback must be invoked."""
    from app.scripts.linkedin.sourcing import _search_with_fallback
    with (
        patch("app.scripts.linkedin.sourcing._ddgs_search", return_value=["https://linkedin.com/company/only-one"]),
        patch("app.scripts.linkedin.sourcing._bing_search", return_value=["https://linkedin.com/company/bing-one"]),
        patch("app.scripts.linkedin.sourcing._google_search",
              return_value=["https://linkedin.com/company/google-result"]) as mock_google,
    ):
        urls = _search_with_fallback("test query")
    mock_google.assert_called_once()
    assert "https://linkedin.com/company/google-result" in urls


def test_find_companies_deduplicates_urls():
    """find_companies_at_scale must not return duplicate URLs."""
    from app.scripts.linkedin.sourcing import find_companies_at_scale
    duplicate_url = "https://linkedin.com/company/rdltech"
    with patch("app.scripts.linkedin.sourcing._search_with_fallback", return_value=[duplicate_url]):
        urls = find_companies_at_scale(
            city_batch=["Mumbai"],
            industry_batch=["pharma"],
            delay_min=0, delay_max=0,
        )
    assert urls.count(duplicate_url) <= 1, "Duplicate URLs returned"


def test_find_companies_respects_existing_urls():
    """URLs already in existing_urls must not be returned again."""
    from app.scripts.linkedin.sourcing import find_companies_at_scale
    existing = {"https://linkedin.com/company/already-scraped"}
    with patch("app.scripts.linkedin.sourcing._search_with_fallback",
               return_value=["https://linkedin.com/company/already-scraped",
                             "https://linkedin.com/company/new-one"]):
        urls = find_companies_at_scale(
            city_batch=["Mumbai"],
            industry_batch=["pharma"],
            delay_min=0, delay_max=0,
            existing_urls=existing,
        )
    assert "https://linkedin.com/company/already-scraped" not in urls
    assert "https://linkedin.com/company/new-one" in urls


def test_find_decision_makers_returns_linkedin_in_urls():
    """find_decision_makers must return only /in/ profile URLs."""
    from app.scripts.linkedin.sourcing import find_decision_makers
    fake = [
        {"href": "https://linkedin.com/in/john-doe"},
        {"href": "https://linkedin.com/in/jane-ceo"},
        {"href": "https://linkedin.com/company/abc"},
        {"href": "https://example.com/profile"},
    ]
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
    mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
    mock_ddgs_instance.text.return_value = fake
    with patch("ddgs.DDGS", return_value=mock_ddgs_instance):
        urls = find_decision_makers("ACME Corp", max_results=10, delay_min=0, delay_max=0,
                                    roles=["CEO"])
    assert all("linkedin.com/in/" in u for u in urls)
    assert all("/company/" not in u for u in urls)


# ── Templates — role classifier ────────────────────────────────────────────────

def test_classify_role_ceo():
    from app.services.linkedin_templates import classify_role
    assert classify_role("CEO at ABC Manufacturing") == "c_suite"
    assert classify_role("Managing Director, ACME Ltd") == "c_suite"
    assert classify_role("Founder & President") == "c_suite"


def test_classify_role_cto():
    from app.services.linkedin_templates import classify_role
    assert classify_role("CTO at TechCorp") == "cto"
    assert classify_role("Chief Technology Officer") == "cto"
    assert classify_role("Head of R&D, Pharma Inc") == "cto"


def test_classify_role_cfo():
    from app.services.linkedin_templates import classify_role
    assert classify_role("CFO at National Industries") == "cfo"
    assert classify_role("Chief Financial Officer") == "cfo"


def test_classify_role_procurement():
    from app.services.linkedin_templates import classify_role
    assert classify_role("Procurement Head at ABC") == "procurement"
    assert classify_role("Supply Chain Director") == "procurement"
    assert classify_role("Purchase Manager") == "procurement"


def test_classify_role_operations():
    from app.services.linkedin_templates import classify_role
    assert classify_role("Plant Manager, Steel Works") == "operations"
    assert classify_role("VP Operations") == "operations"
    assert classify_role("Production Manager") == "operations"


def test_classify_role_engineering():
    from app.services.linkedin_templates import classify_role
    assert classify_role("Chief Engineer") == "engineering"
    assert classify_role("Senior Electrical Engineer") == "engineering"
    assert classify_role("Associate Engineer, Manufacturing") == "engineering"


def test_classify_role_unknown_returns_generic():
    from app.services.linkedin_templates import classify_role
    assert classify_role("Sales Representative") == "generic"
    assert classify_role("") == "generic"
    assert classify_role(None) == "generic"


# ── Templates — industry classifier ───────────────────────────────────────────

def test_classify_industry_pharma():
    from app.services.linkedin_templates import classify_industry
    assert classify_industry("pharmaceutical manufacturing") == "pharma"
    assert classify_industry("biotech company") == "pharma"
    assert classify_industry("API bulk drug") == "pharma"


def test_classify_industry_petroleum():
    from app.services.linkedin_templates import classify_industry
    assert classify_industry("petroleum refinery") == "petroleum"
    assert classify_industry("oil and gas") == "petroleum"
    assert classify_industry("petrochemical") == "petroleum"


def test_classify_industry_textile():
    from app.services.linkedin_templates import classify_industry
    assert classify_industry("textile manufacturing") == "textile"
    assert classify_industry("saree manufacturing") == "textile"
    assert classify_industry("garment apparel") == "textile"


def test_classify_industry_automotive():
    from app.services.linkedin_templates import classify_industry
    assert classify_industry("automotive manufacturing") == "automotive"
    assert classify_industry("auto parts") == "automotive"


def test_classify_industry_unknown_returns_generic():
    from app.services.linkedin_templates import classify_industry
    assert classify_industry("") == "generic"
    assert classify_industry(None) == "generic"
    assert classify_industry("random stuff") == "generic"


# ── Templates — message generation ────────────────────────────────────────────

def test_connection_note_under_300_chars():
    from app.services.linkedin_templates import get_connection_note
    for role in ("c_suite", "cto", "cfo", "procurement", "operations", "engineering", "generic"):
        for industry in ("pharma", "petroleum", "textile", "automotive", "generic"):
            note = get_connection_note("Rahul", "ACME Ltd", role, industry)
            assert len(note) <= 300, f"Note too long ({len(note)}) for role={role} industry={industry}"


def test_connection_note_contains_name():
    from app.services.linkedin_templates import get_connection_note
    note = get_connection_note("Priya", "Test Corp", "c_suite", "pharma")
    assert "Priya" in note


def test_connection_note_contains_company():
    from app.services.linkedin_templates import get_connection_note
    note = get_connection_note("Rahul", "Mumbai Pharma Ltd", "c_suite", "pharma")
    assert "Mumbai Pharma Ltd" in note


def test_full_message_contains_rdl():
    from app.services.linkedin_templates import get_full_message
    msg = get_full_message("Rahul", "ACME Ltd", "c_suite", "generic")
    assert "RDL" in msg or "rdl" in msg.lower()


def test_full_message_not_empty_for_all_combinations():
    from app.services.linkedin_templates import get_full_message
    roles      = ("c_suite", "cto", "cfo", "procurement", "operations", "engineering", "generic")
    industries = ("pharma", "petroleum", "textile", "food", "chemical",
                  "automotive", "electronics", "metals", "generic")
    for role in roles:
        for ind in industries:
            msg = get_full_message("Test", "Company", role, ind)
            assert msg, f"Empty message for role={role} industry={ind}"


def test_get_template_key_falls_back_gracefully():
    from app.services.linkedin_templates import get_template_key
    key = get_template_key("nonexistent_role", "nonexistent_industry")
    assert key  # must always return something non-empty
    assert "__" in key


# ── Router endpoints ───────────────────────────────────────────────────────────

def test_stats_shape(client, auth_headers):
    resp = client.get(f"{BASE}/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for k in ("total_discovered", "connection_not_sent", "connection_accepted",
              "connection_rate_pct", "messages_sent", "reply_rate_pct", "daily_budget"):
        assert k in body, f"Missing key: {k}"


def test_stats_no_auth(client):
    with _no_auth(client):
        resp = client.get(f"{BASE}/stats")
    assert resp.status_code == 401


def test_budget_shape(client, auth_headers):
    resp = client.get(f"{BASE}/budget", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for k in ("connections_used", "connections_remaining", "connections_limit",
              "messages_used_today", "messages_remaining_today"):
        assert k in body


def test_budget_no_auth(client):
    with _no_auth(client):
        resp = client.get(f"{BASE}/budget")
    assert resp.status_code == 401


def test_add_outreach_record(client, auth_headers):
    resp = client.post(f"{BASE}/", json={
        "linkedin_url": f"https://linkedin.com/in/test-{uuid.uuid4().hex[:8]}",
        "full_name": "Jane Pharma CEO",
        "headline": "CEO at Pharma Solutions",
        "company_name": "Pharma Solutions Ltd",
        "industry_tag": "pharmaceutical manufacturing",
        "city_tag": "Mumbai",
    }, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["role_category"] == "c_suite"
    assert body["connection_status"] == "not_sent"
    assert body["message_status"] == "not_sent"


def test_add_duplicate_linkedin_url_returns_existing(client, auth_headers):
    """Posting the same linkedin_url twice must not fail — returns existing record."""
    url = f"https://linkedin.com/in/dedup-{uuid.uuid4().hex[:8]}"
    r1 = client.post(f"{BASE}/", json={"linkedin_url": url, "full_name": "A"}, headers=auth_headers)
    r2 = client.post(f"{BASE}/", json={"linkedin_url": url, "full_name": "B"}, headers=auth_headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_add_outreach_missing_url(client, auth_headers):
    resp = client.post(f"{BASE}/", json={"full_name": "No URL"}, headers=auth_headers)
    assert resp.status_code == 422


def test_list_outreach_shape(client, auth_headers):
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for k in ("items", "total", "page", "limit"):
        assert k in body


def test_list_outreach_filter_by_connection_status(client, auth_headers):
    _insert_outreach(connection_status="connected")
    resp = client.get(f"{BASE}/?connection_status=connected", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["connection_status"] == "connected"


def test_list_outreach_filter_by_role(client, auth_headers):
    _insert_outreach(role_category="cto", headline="CTO at Tech")
    resp = client.get(f"{BASE}/?role_category=cto", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["role_category"] == "cto"


def test_list_outreach_no_auth(client):
    with _no_auth(client):
        resp = client.get(f"{BASE}/")
    assert resp.status_code == 401


def test_get_outreach_found(client, auth_headers):
    oid = _insert_outreach()
    resp = client.get(f"{BASE}/{oid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(oid)


def test_get_outreach_not_found(client, auth_headers):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Queue connection ───────────────────────────────────────────────────────────

def test_queue_connection_succeeds_when_budget_available(client, auth_headers):
    oid = _insert_outreach(connection_status="not_sent")
    with patch("app.services.linkedin_outreach_service._check_and_increment", return_value=True):
        resp = client.post(f"{BASE}/{oid}/queue-connection", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "note" in body
    assert len(body["note"]) <= 300


def test_queue_connection_rejected_when_budget_exhausted(client, auth_headers):
    oid = _insert_outreach(connection_status="not_sent")
    with patch("app.services.linkedin_outreach_service._check_and_increment", return_value=False):
        resp = client.post(f"{BASE}/{oid}/queue-connection", headers=auth_headers)
    assert resp.status_code == 429


def test_queue_connection_not_found(client, auth_headers):
    with patch("app.services.linkedin_outreach_service._check_and_increment", return_value=True):
        resp = client.post(f"{BASE}/{uuid.uuid4()}/queue-connection", headers=auth_headers)
    assert resp.status_code == 404


def test_queue_connection_no_auth(client):
    oid = _insert_outreach()
    with _no_auth(client):
        resp = client.post(f"{BASE}/{oid}/queue-connection")
    assert resp.status_code == 401


# ── Queue message ──────────────────────────────────────────────────────────────

def test_queue_message_fails_if_not_connected(client, auth_headers):
    oid = _insert_outreach(connection_status="pending")
    with patch("app.services.linkedin_outreach_service._check_and_increment", return_value=True):
        resp = client.post(f"{BASE}/{oid}/queue-message", headers=auth_headers)
    assert resp.status_code == 429
    assert "Not connected" in resp.json()["detail"]


def test_queue_message_succeeds_when_connected(client, auth_headers):
    oid = _insert_outreach(connection_status="connected", message_status="not_sent")
    with patch("app.services.linkedin_outreach_service._check_and_increment", return_value=True):
        resp = client.post(f"{BASE}/{oid}/queue-message", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "RDL" in body["message"] or "rdl" in body["message"].lower()


def test_queue_message_budget_exhausted(client, auth_headers):
    oid = _insert_outreach(connection_status="connected", message_status="not_sent")
    with patch("app.services.linkedin_outreach_service._check_and_increment", return_value=False):
        resp = client.post(f"{BASE}/{oid}/queue-message", headers=auth_headers)
    assert resp.status_code == 429


# ── Status update endpoints ────────────────────────────────────────────────────

def test_mark_connected(client, auth_headers):
    oid = _insert_outreach(connection_status="pending")
    resp = client.patch(f"{BASE}/{oid}/connected", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["connection_status"] == "connected"


def test_mark_message_sent(client, auth_headers):
    oid = _insert_outreach(connection_status="connected", message_status="queued")
    resp = client.patch(f"{BASE}/{oid}/message-sent", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["message_status"] == "sent"


def test_mark_reply(client, auth_headers):
    oid = _insert_outreach(connection_status="connected", message_status="sent")
    resp = client.patch(
        f"{BASE}/{oid}/reply",
        json={"reply_preview": "Thanks for reaching out! Interested to know more."},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message_status"] == "replied"
    assert "Thanks" in body["reply_preview"]


def test_mark_connected_not_found(client, auth_headers):
    resp = client.patch(f"{BASE}/{uuid.uuid4()}/connected", headers=auth_headers)
    assert resp.status_code == 404


# ── Template preview ───────────────────────────────────────────────────────────

def test_template_preview_shape(client, auth_headers):
    resp = client.get(
        f"{BASE}/templates/preview?role_category=c_suite&industry_tag=pharma&name=Rahul&company=ABC",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    for k in ("role_category", "industry_bucket", "template_key", "connection_note", "full_message"):
        assert k in body


def test_template_preview_connection_note_under_300(client, auth_headers):
    resp = client.get(
        f"{BASE}/templates/preview?role_category=cto&industry_tag=petroleum",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    note = resp.json()["connection_note"]
    assert len(note) <= 300


def test_template_preview_no_auth(client):
    with _no_auth(client):
        resp = client.get(f"{BASE}/templates/preview?role_category=c_suite&industry_tag=pharma")
    assert resp.status_code == 401


# ── Discover companies endpoint ────────────────────────────────────────────────

def test_discover_companies_accepts_payload(client, auth_headers):
    """POST /discover-companies returns 202 and starts background job."""
    # find_companies_at_scale is imported inside the background _run() closure —
    # patch at the source module, not at the router module
    with patch("app.scripts.linkedin.sourcing.find_companies_at_scale", return_value=[]):
        resp = client.post(f"{BASE}/discover-companies", json={
            "city_batch": ["Mumbai", "Pune"],
            "industry_batch": ["pharma"],
            "max_results_per_query": 50,
        }, headers=auth_headers)
    assert resp.status_code == 202
    body = resp.json()
    assert "discovery" in body["message"].lower() or "started" in body["message"].lower()


def test_discover_companies_no_auth(client):
    with _no_auth(client):
        resp = client.post(f"{BASE}/discover-companies", json={"city_batch": ["Mumbai"]})
    assert resp.status_code == 401
