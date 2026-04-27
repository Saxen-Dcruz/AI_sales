import re
from typing import List

# Full catalog intent — route directly to DB, no LLM needed.
# Kept narrow — "what products do you have for X" must NOT trigger this.
CATALOG_KEYWORDS = [
    "all products",
    "all the products",
    "list all products",
    "list of products",
    "show all products",
    "full catalog",
    "product catalog",
    "every product you",
    "complete list of products",
    "what do you sell",
    "what do you offer",
]

# Queries needing long responses: comparisons, multi-variant listings, full detail.
# Token budget: 1024. Checked before factual — expanded takes precedence.
EXPANDED_KEYWORDS = [
    # Direct comparisons
    "compare", "comparison", "versus", "vs ", "vs.", "vs,",
    "difference between", "differences between",
    "compared to", "compare to",
    "similarities", "similar to",
    "pros and cons", "advantages and disadvantages",
    "which is better", "which one is better", "which one should i",
    "better than", "worse than",
    "choose between", "choosing between",
    # Multi-variant / full range listing
    "all variants", "all models", "all versions", "all types",
    "every variant", "every model", "every version",
    "list all modules", "show all modules",
    "full range", "entire range",
    # Full product detail
    "tell me everything", "full details", "complete details",
    "complete specifications", "full specifications",
    "all features", "all the features", "all specifications",
    "detailed overview", "in-depth", "full overview",
    "everything about",
    # Package / bundle contents
    "what's included", "what is included", "what comes with",
    "package contents", "package includes", "kit contents", "box contents",
    "what does it include", "what does the kit include",
]

# LATENCY-C: tokens that signal a question references prior conversation.
# If none present in a follow-up, query rewriter is skipped → -1–3s.
CONTEXT_REF_MARKERS = frozenset([
    " it ", " it's", " its ", " they ", " them ", " their ",
    " this ", " that ", " these ", " those ", " he ", " she ", " we ",
    "the same", "same one", "the other", "the above",
    "mentioned", "previous", "earlier", "last one",
    "that product", "that model", "that one",
    "what about", "how about", "also ", " too ", "as well",
    "instead", "alternatively", "compared to",
    "which one", "what else",
])

# Queries needing short, precise answers: prices, codes, single facts.
# Token budget: 256. Only triggered when no expanded keyword matches.
FACTUAL_KEYWORDS = [
    # Price / cost
    "price", "cost", "how much", "rate", "pricing",
    "charge", "fee", "tariff", "affordable", "cheapest", "expensive",
    "bulk price", "single price", "unit price", "mrp",
    # Order / SKU / part number
    "order code", "sku", "part number", "model number",
    "product code", "item code", "reference number", "ref no",
    # Availability / stock (keep specific — "do you have" is too broad, matches product searches)
    "in stock", "out of stock", "is it available", "is it in stock",
    "do you stock", "can i order", "when will it be available",
    # Quick reference lookups
    "datasheet", "manual", "documentation", "download link",
    "product link", "website link",
    "weight", "dimensions", "size", "voltage", "wattage",
    "operating temperature", "warranty", "lead time",
    # Contact / support
    "address", "phone", "email", "contact", "reach", "helpline",
]

# ISSUE-008: keywords that, when combined with a factual keyword, bump tier to standard.
# "price AND specifications" must not be truncated at 256 tokens.
SPEC_OVERRIDE_KEYWORDS = [
    "specification", "specifications", "specs", "spec ",
    "features", "how does", "how do", "what are the",
]

# Chunk types to serve for package/contents queries
PACKAGE_CHUNK_TYPES = [
    "package_contains", "package_includes",
    "scope_of_learning_experiments", "description", "product_description",
]

# Chunk types to serve for factual queries (price, order code)
# Features excluded — RAGAS rates it as noise for price/stock queries
FACTUAL_CHUNK_TYPES = [
    "description", "product_description", "descriptions",
    "specification", "specifications",
]

# Intent keywords that signal a package/contents question
PACKAGE_INTENTS = frozenset([
    "what is included", "what's included", "what comes with",
    "included in", "package includes", "package contains",
    "kit contains", "box contents", "what does it include",
    "what does the kit include", "includes what",
])


def normalize(text: str) -> str:
    """Lowercase, collapse hyphens/slashes to space, normalize all whitespace."""
    text = re.sub(r'[-/]+', ' ', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


def is_catalog_query(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in CATALOG_KEYWORDS)


def classify_budget(question: str) -> str:
    """Return budget tier based on question keywords: 'expanded', 'factual', or 'standard'."""
    q = question.lower()
    if any(kw in q for kw in EXPANDED_KEYWORDS):
        return "expanded"
    if any(kw in q for kw in FACTUAL_KEYWORDS):
        # ISSUE-008: if question also asks for detail (specs, features), bump to standard
        if any(kw in q for kw in SPEC_OVERRIDE_KEYWORDS):
            return "standard"
        return "factual"
    return "standard"


def get_chunk_type_filter(question: str) -> dict:
    """
    Return the PGVector chunk_type filter based on query intent.
    Package queries → only package/description chunks.
    Factual queries → only description/spec chunks.
    Default         → exclude frequently_bought_together and noise chunk types.
    """
    q = question.lower()
    if any(kw in q for kw in PACKAGE_INTENTS):
        return {"chunk_type": {"$in": PACKAGE_CHUNK_TYPES}}
    if classify_budget(question) == "factual":
        return {"chunk_type": {"$in": FACTUAL_CHUNK_TYPES}}
    return {"chunk_type": {"$nin": ["frequently_bought_together", "benefits", "package_contains", "package_includes"]}}


def detect_product_ids(question: str, catalog: List[dict]) -> List[str]:
    """
    Match products mentioned in the query by name or order code.
    - Name match: normalized substring >= 8 chars (strips hyphens/slashes).
    - Order code match: exact case-insensitive match (e.g. "RDL740").
    Returns string UUIDs — pgvector serialises metadata to JSON so UUIDs are strings.
    """
    q_norm = normalize(question)
    q_lower = question.lower()
    matched = set()
    for p in catalog:
        name_norm = normalize(p["name"])
        if len(name_norm) >= 8 and name_norm in q_norm:
            matched.add(str(p["id"]))
            continue
        order_code = p.get("order_code", "")
        if order_code and order_code.lower() in q_lower:
            matched.add(str(p["id"]))
    return list(matched)
