"""
LinkedIn company and people discovery engine.

Root cause of the old DDGS shallow-results problem:
  - 11 cities × 10 industries = 110 queries
  - max_results=20 per query → ceiling of ~2,200 URLs
  - Single query format → duplicate top-10 results across queries
  - No fallback when DDGS rate-limits or returns 0

Fixes applied:
  1. 200+ cities × 80+ industries = 16,000+ query combinations
  2. 4 query variants per pair (manufacturer / supplier / company / pvt ltd)
  3. max_results=100 on DDGS (was 20)
  4. Google Search fallback via googlesearch-python when DDGS fails
  5. Exponential backoff retry on both backends
  6. URL deduplication + DB deduplication before returning
  7. Progressive saving so progress survives crashes
"""
import time
import random
import logging
from typing import Optional

logger = logging.getLogger("rdl_app_logger")

# ── Target cities ──────────────────────────────────────────────────────────────
# 200+ cities: India tier 1/2/3 industrial hubs + international

CITIES_INDIA = [
    # Tier 1 metros
    "Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata", "Hyderabad",
    "Pune", "Ahmedabad", "Surat", "Jaipur",
    # Tier 2 industrial
    "Nagpur", "Lucknow", "Kanpur", "Indore", "Bhopal", "Coimbatore",
    "Visakhapatnam", "Vadodara", "Rajkot", "Ludhiana", "Amritsar",
    "Faridabad", "Ghaziabad", "Meerut", "Agra", "Varanasi",
    "Patna", "Bhubaneswar", "Kochi", "Thiruvananthapuram", "Mangaluru",
    "Mysuru", "Hubli", "Belgaum", "Nashik", "Aurangabad",
    "Solapur", "Kolhapur", "Sangli", "Navi Mumbai", "Thane",
    "Pimpri-Chinchwad", "Dombivli", "Vasai", "Panvel",
    # Tier 3 + industrial zones
    "Ambala", "Yamunanagar", "Karnal", "Panipat", "Rohtak",
    "Hisar", "Bhiwani", "Moradabad", "Bareilly", "Aligarh",
    "Mathura", "Hapur", "Saharanpur", "Muzaffarnagar",
    "Peenya", "Whitefield", "Electronic City", "Bommasandra",
    "Chakan", "Bhosari", "Waluj", "Butibori",
    "Vapi", "Ankleshwar", "Bharuch", "Gandhinagar", "Mehsana",
    "Morbi", "Bhavnagar", "Junagadh", "Jamnagar", "Porbandar",
    "Tirupur", "Erode", "Salem", "Madurai", "Tiruchirappalli",
    "Vellore", "Thoothukudi", "Tirunelveli", "Karur",
    "Hosur", "Ambattur", "Guindy", "Perungudi", "Sriperumbudur",
    "Noida", "Greater Noida", "Manesar", "Kundli", "Bahadurgarh",
    "Sonipat", "Rewari", "Palwal", "Bhiwadi", "Neemrana",
    "Rudrapur", "Haridwar", "Kashipur", "Dehradun", "Roorkee",
    "Raipur", "Bhilai", "Korba", "Bilaspur",
    "Jamshedpur", "Dhanbad", "Ranchi", "Bokaro",
    "Cuttack", "Rourkela", "Sambalpur",
    "Gurgaon", "Ballabgarh", "Bawal", "IMT Manesar",
    "Baddi", "Nalagarh", "Parwanoo", "Himachal Pradesh industrial",
    "Siliguri", "Haldia", "Durgapur", "Asansol",
    "Vijaywada", "Rajahmundry", "Kakinada", "Nellore", "Guntur",
    "Warangal", "Nizamabad", "Karimnagar", "Khammam",
    "Aurangabad Maharashtra", "Latur", "Osmanabad", "Akola", "Amravati",
    "Goa Vasco", "Margao", "Panaji",
    "Imphal", "Guwahati", "Dibrugarh", "Jorhat", "Silchar",
    "Agartala", "Shillong", "Aizawl",
    "Srinagar", "Jammu", "Udhampur",
    "Bikaner", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Alwar",
    "Jabalpur", "Gwalior", "Ujjain", "Ratlam", "Dewas",
]

CITIES_INTERNATIONAL = [
    # Southeast Asia
    "Singapore", "Kuala Lumpur", "Bangkok", "Jakarta", "Manila",
    "Ho Chi Minh City", "Hanoi", "Yangon", "Phnom Penh",
    # Middle East
    "Dubai", "Abu Dhabi", "Sharjah", "Riyadh", "Jeddah",
    "Dammam", "Kuwait City", "Doha", "Muscat", "Bahrain",
    # East Asia
    "Shanghai", "Beijing", "Guangzhou", "Shenzhen", "Chengdu",
    "Wuhan", "Tianjin", "Nanjing", "Hangzhou", "Suzhou",
    "Hong Kong", "Taipei", "Seoul", "Busan", "Incheon",
    "Tokyo", "Osaka", "Nagoya", "Yokohama",
    # South Asia
    "Karachi", "Lahore", "Dhaka", "Chittagong", "Colombo",
    "Kathmandu", "Islamabad",
    # Europe
    "London", "Birmingham", "Manchester", "Rotterdam", "Amsterdam",
    "Frankfurt", "Hamburg", "Munich", "Düsseldorf", "Stuttgart",
    "Paris", "Lyon", "Marseille", "Milan", "Turin", "Rome",
    "Warsaw", "Krakow", "Prague", "Budapest", "Bucharest",
    "Barcelona", "Madrid", "Lisbon", "Brussels", "Antwerp",
    "Stockholm", "Gothenburg", "Copenhagen", "Helsinki", "Oslo",
    "Vienna", "Zurich", "Geneva",
    # USA & Canada
    "New York", "Los Angeles", "Chicago", "Houston", "Detroit",
    "Dallas", "Atlanta", "Boston", "Philadelphia", "Phoenix",
    "San Jose", "Seattle", "Portland", "Denver", "Minneapolis",
    "Toronto", "Vancouver", "Montreal", "Calgary",
    # Australia
    "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
    # Africa
    "Lagos", "Johannesburg", "Cape Town", "Nairobi", "Cairo",
    "Casablanca", "Accra", "Dar es Salaam",
    # Latin America
    "São Paulo", "Rio de Janeiro", "Mexico City", "Bogotá",
    "Lima", "Santiago", "Buenos Aires",
]

ALL_CITIES = CITIES_INDIA + CITIES_INTERNATIONAL

# ── Target industries ──────────────────────────────────────────────────────────
# 80+ industrial manufacturing categories

INDUSTRIES = [
    # Life sciences
    "pharmaceutical manufacturing",
    "pharma company",
    "biotech manufacturing",
    "medical device manufacturing",
    "hospital equipment manufacturing",
    "surgical instrument manufacturing",
    "diagnostic equipment manufacturing",
    "nutraceutical manufacturing",
    "API active pharmaceutical ingredient",
    "bulk drug manufacturing",
    "vaccine manufacturing",
    "laboratory equipment manufacturing",
    # Energy
    "petroleum refinery",
    "oil and gas manufacturing",
    "refinery equipment manufacturing",
    "petrochemical manufacturing",
    "natural gas processing",
    "LPG manufacturing",
    "renewable energy manufacturing",
    "solar panel manufacturing",
    "wind turbine manufacturing",
    "battery manufacturing",
    "power plant equipment",
    # Textiles & garments
    "textile manufacturing",
    "saree manufacturing",
    "fabric manufacturing",
    "yarn spinning mill",
    "garment manufacturing",
    "apparel manufacturing",
    "dyeing and printing",
    "technical textiles",
    "nonwoven fabric manufacturing",
    # Automotive
    "automotive manufacturing",
    "auto parts manufacturing",
    "automotive component supplier",
    "two wheeler manufacturing",
    "truck manufacturing",
    "tractor manufacturing",
    "EV electric vehicle manufacturing",
    # Electronics & electrical
    "electronics manufacturing",
    "semiconductor manufacturing",
    "PCB manufacturing",
    "electrical equipment manufacturing",
    "switchgear manufacturing",
    "transformer manufacturing",
    "cable and wire manufacturing",
    "motor manufacturing",
    "pump manufacturing",
    "compressor manufacturing",
    # Chemical
    "chemical manufacturing",
    "specialty chemical",
    "agrochemical manufacturing",
    "fertilizer manufacturing",
    "pesticide manufacturing",
    "paint manufacturing",
    "adhesive manufacturing",
    "polymer manufacturing",
    "plastic manufacturing",
    "rubber manufacturing",
    # Food & beverage
    "food processing",
    "food manufacturing",
    "beverage manufacturing",
    "dairy processing",
    "grain milling",
    "sugar manufacturing",
    "confectionery manufacturing",
    "packaged food manufacturing",
    # Heavy industry & metals
    "steel manufacturing",
    "metal fabrication",
    "foundry manufacturing",
    "aluminium manufacturing",
    "copper manufacturing",
    "forging and casting",
    "pipe and tube manufacturing",
    "valve manufacturing",
    "fastener manufacturing",
    "tool and die manufacturing",
    "CNC machining",
    "sheet metal fabrication",
    # Construction & infrastructure
    "cement manufacturing",
    "construction material",
    "glass manufacturing",
    "ceramic manufacturing",
    "tile manufacturing",
    "sanitary ware manufacturing",
    "plumbing equipment",
    # Packaging
    "packaging manufacturing",
    "plastic packaging",
    "paper and board manufacturing",
    "cardboard box manufacturing",
    "flexible packaging",
    # Industrial equipment
    "machine tool manufacturing",
    "hydraulic equipment",
    "pneumatic equipment",
    "conveyor system manufacturer",
    "industrial automation",
    "SCADA PLC manufacturer",
    "instrumentation manufacturing",
    "industrial sensor manufacturer",
    "process control equipment",
    # Mining & quarrying
    "mining equipment manufacturing",
    "quarry mining operations",
    "mineral processing",
    # Other
    "defense manufacturing",
    "aerospace manufacturing",
    "shipbuilding",
    "railway equipment",
    "printing and publishing equipment",
    "water treatment equipment",
    "waste management equipment",
    "cold storage manufacturing",
    "agro processing",
    "spice manufacturing",
    "paper manufacturing",
]

# ── Query templates ────────────────────────────────────────────────────────────
# 4 variants per (industry × city) to break out of top-10 duplicates

QUERY_VARIANTS = [
    'site:linkedin.com/company/ "{industry}" "{city}"',
    'site:linkedin.com/company/ "{industry} manufacturer" "{city}"',
    'site:linkedin.com/company/ "{industry} company" "{city}" India',
    'site:linkedin.com/company/ "{industry}" "{city}" "pvt ltd" OR "limited"',
]

# Target roles for people search
TARGET_ROLES = [
    "CEO",
    "Chief Executive Officer",
    "Managing Director",
    "Founder",
    "CTO",
    "Chief Technology Officer",
    "Technical Director",
    "R&D Head",
    "CFO",
    "Chief Financial Officer",
    "VP Operations",
    "Director Operations",
    "Plant Manager",
    "General Manager",
    "Head of Engineering",
    "Chief Engineer",
    "Senior Engineer",
    "Associate Vice President",
    "Purchase Manager",
    "Procurement Head",
    "Supply Chain Director",
]


# ── Search backends ────────────────────────────────────────────────────────────

def _ddgs_search(query: str, max_results: int = 100) -> list[str]:
    """DuckDuckGo search via the `ddgs` package (renamed from duckduckgo_search)."""
    urls = []
    try:
        from ddgs import DDGS
        with DDGS() as ddgs_client:
            results = ddgs_client.text(query, max_results=max_results)
            if results:
                for r in results:
                    url = r.get("href", "").split("?")[0].rstrip("/")
                    if "linkedin.com/company/" in url and "/dir/" not in url:
                        urls.append(url)
    except Exception as e:
        logger.warning(f"[DDGS] Error on query '{query[:60]}': {e}")
    return urls


def _bing_search(query: str, max_results: int = 50) -> list[str]:
    """
    Bing scrape fallback — uses requests with a browser User-Agent.
    Less aggressive rate-limiting than Google on server IPs.
    """
    import re
    import requests

    urls = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        fetched = 0
        offset = 0
        while fetched < max_results:
            params = {"q": query, "count": 10, "first": offset}
            resp = requests.get("https://www.bing.com/search", params=params,
                                headers=headers, timeout=10)
            if resp.status_code != 200:
                break
            found = re.findall(r'href="(https://[^"]*linkedin\.com/company/[^"?/][^"]*)"', resp.text)
            new = [u.split("?")[0].rstrip("/") for u in found
                   if "/dir/" not in u and u not in urls]
            urls.extend(new)
            fetched += len(new)
            if not new:
                break
            offset += 10
            time.sleep(random.uniform(2, 4))
    except Exception as e:
        logger.warning(f"[BING] Error on query '{query[:60]}': {e}")
    return list(set(urls))


def _google_search(query: str, max_results: int = 100) -> list[str]:
    """Google Search via googlesearch-python. Works best from residential IPs."""
    urls = []
    try:
        from googlesearch import search
        for url in search(query, num_results=max_results, sleep_interval=3):
            clean = url.split("?")[0].rstrip("/")
            if "linkedin.com/company/" in clean and "/dir/" not in clean:
                urls.append(clean)
    except Exception as e:
        logger.warning(f"[GOOGLE] Error on query '{query[:60]}': {e}")
    return urls


def _search_with_fallback(query: str, max_results: int = 100) -> list[str]:
    """
    Priority: DDGS → Bing → Google.
    Falls through to the next backend only when the previous returns < 5 results.
    Bing is preferred over Google as second choice since it rate-limits less
    aggressively on server/Docker IPs.
    """
    urls = _ddgs_search(query, max_results)
    if len(urls) < 5:
        logger.info(f"[SEARCH] DDGS {len(urls)} results — trying Bing")
        bing_urls = _bing_search(query, min(max_results, 50))
        urls = list(set(urls + bing_urls))
    if len(urls) < 5:
        logger.info(f"[SEARCH] Bing {len(urls)} results — trying Google")
        google_urls = _google_search(query, max_results)
        urls = list(set(urls + google_urls))
    return urls


# ── Main discovery functions ───────────────────────────────────────────────────

def find_companies_at_scale(
    city_batch: Optional[list[str]] = None,
    industry_batch: Optional[list[str]] = None,
    max_results_per_query: int = 100,
    delay_min: float = 3.0,
    delay_max: float = 7.0,
    existing_urls: Optional[set] = None,
) -> list[str]:
    """
    Systematically search for LinkedIn company URLs across all city × industry combinations.

    city_batch / industry_batch — pass subsets to run in chunks (for API-driven batching).
    Omit both to run the full matrix (200+ cities × 80+ industries × 4 variants).

    Returns deduplicated list of linkedin.com/company/ URLs not already in existing_urls.
    """
    cities    = city_batch    or ALL_CITIES
    industries = industry_batch or INDUSTRIES
    seen      = set(existing_urls or [])
    new_urls: list[str] = []

    total = len(cities) * len(industries) * len(QUERY_VARIANTS)
    done  = 0

    logger.info(f"[DISCOVERY] Starting: {len(cities)} cities × {len(industries)} industries × {len(QUERY_VARIANTS)} variants = {total} queries")

    for city in cities:
        for industry in industries:
            for variant in QUERY_VARIANTS:
                query = variant.format(industry=industry, city=city)
                done += 1

                try:
                    results = _search_with_fallback(query, max_results_per_query)
                    added = 0
                    for url in results:
                        # Normalise: strip /about suffix, trailing slash
                        clean = url.replace("/about", "").rstrip("/")
                        if clean not in seen:
                            seen.add(clean)
                            new_urls.append(clean)
                            added += 1

                    if added:
                        logger.info(f"[DISCOVERY] {done}/{total} | +{added} | {industry} @ {city}")

                except Exception as e:
                    logger.error(f"[DISCOVERY] Query failed: {query[:80]} | {e}")

                # Rate-limit: random jitter between queries
                sleep = random.uniform(delay_min, delay_max)
                time.sleep(sleep)

    logger.info(f"[DISCOVERY] Done. {len(new_urls)} new unique company URLs found.")
    return new_urls


def find_decision_makers(
    company_name: str,
    max_results: int = 50,
    roles: Optional[list[str]] = None,
    delay_min: float = 4.0,
    delay_max: float = 8.0,
) -> list[str]:
    """
    Search LinkedIn for decision-makers at a given company.
    Rotates across target roles. Returns deduplicated /in/ profile URLs.
    """
    target_roles = roles or TARGET_ROLES
    all_urls: list[str] = []
    seen: set[str] = set()

    for role in target_roles:
        # Primary query — exact company + exact role
        query = f'site:linkedin.com/in/ "{company_name}" "{role}"'

        try:
            # Try DDGS first
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=max_results)
                if results:
                    for r in results:
                        url = r.get("href", "").split("?")[0].rstrip("/")
                        if "linkedin.com/in/" in url and "/dir/" not in url and url not in seen:
                            seen.add(url)
                            all_urls.append(url)
                elif len(all_urls) < 3:
                    # Fallback to Google for this role
                    for url in _google_search(query, max_results):
                        clean = url.split("?")[0].rstrip("/")
                        if "linkedin.com/in/" in clean and clean not in seen:
                            seen.add(clean)
                            all_urls.append(clean)

        except Exception as e:
            logger.warning(f"[PEOPLE] Error finding {role} at {company_name}: {e}")

        time.sleep(random.uniform(delay_min, delay_max))

    logger.info(f"[PEOPLE] Found {len(all_urls)} decision-makers at {company_name}")
    return all_urls
