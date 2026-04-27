







"""
Role × industry LinkedIn message templates.

Template keys: "{role_category}__{industry_bucket}"
Falls back to "{role_category}__generic" if no industry match.

All templates follow LinkedIn's ~300-char connection note limit.
The full message (sent after connection is accepted) has no hard limit.
"""

# ── Role classifier ────────────────────────────────────────────────────────────

def classify_role(headline: str) -> str:
    """Return a role_category based on the person's LinkedIn headline."""
    import re
    h = (headline or "").lower()

    def _word(term: str) -> bool:
        # Word-boundary match to avoid "cto" matching "director", "ceo" matching "ocean", etc.
        return bool(re.search(r'\b' + re.escape(term) + r'\b', h))

    if any(_word(t) for t in ["ceo", "chief executive officer", "managing director",
                               "founder", "owner", "president", "proprietor"]) \
            or "chief executive" in h:
        return "c_suite"
    if any(_word(t) for t in ["cto", "r&d"]) \
            or any(t in h for t in ["chief technology", "technical director", "head of r&d", "research", "innovation"]):
        return "cto"
    if any(_word(t) for t in ["cfo"]) \
            or any(t in h for t in ["chief financial", "finance director", "vp finance", "treasurer"]):
        return "cfo"
    if any(t in h for t in ["procurement", "purchase", "supply chain", "sourcing", "vendor", "buying"]):
        return "procurement"
    if any(t in h for t in ["plant manager", "operations", "production", "manufacturing director", "factory"]):
        return "operations"
    if any(t in h for t in ["chief engineer", "head engineer", "senior engineer", "associate engineer",
                             "electrical engineer", "mechanical engineer", "project engineer", "vp engineering"]):
        return "engineering"
    return "generic"


def classify_industry(industry_tag: str) -> str:
    """Map raw industry tag to a message bucket."""
    t = (industry_tag or "").lower()
    if any(k in t for k in ["pharma", "biotech", "medical", "drug", "api", "vaccine", "nutraceutical"]):
        return "pharma"
    if any(k in t for k in ["petroleum", "oil", "gas", "refinery", "petrochemical", "lpg"]):
        return "petroleum"
    if any(k in t for k in ["textile", "saree", "fabric", "yarn", "garment", "apparel", "dyeing"]):
        return "textile"
    if any(k in t for k in ["food", "beverage", "dairy", "grain", "sugar", "confectionery", "spice", "agro"]):
        return "food"
    if any(k in t for k in ["chemical", "specialty", "agrochemical", "fertilizer", "pesticide", "paint", "polymer"]):
        return "chemical"
    if any(k in t for k in ["auto", "vehicle", "tractor", "truck", "ev", "electric vehicle", "two wheeler"]):
        return "automotive"
    if any(k in t for k in ["electronic", "semiconductor", "pcb", "electrical", "switchgear", "transformer", "cable", "motor", "pump"]):
        return "electronics"
    if any(k in t for k in ["steel", "metal", "aluminium", "copper", "forging", "casting", "foundry", "pipe", "valve"]):
        return "metals"
    if any(k in t for k in ["cement", "glass", "ceramic", "tile", "construction", "sanitary"]):
        return "construction"
    if any(k in t for k in ["packaging", "plastic pack", "paper", "cardboard", "flexible"]):
        return "packaging"
    if any(k in t for k in ["solar", "wind", "battery", "renewable", "power plant"]):
        return "energy"
    if any(k in t for k in ["automation", "scada", "plc", "instrumentation", "sensor", "process control"]):
        return "automation"
    if any(k in t for k in ["mining", "quarry", "mineral"]):
        return "mining"
    if any(k in t for k in ["defence", "defense", "aerospace", "ship", "railway"]):
        return "defense"
    return "generic"


# ── Connection request notes (≤300 chars) ────────────────────────────────────
# Short, personal, not salesy — purpose is just to get the connection accepted.

_CONNECTION_NOTES: dict[str, str] = {
    "c_suite__pharma":     "Hi {name}, I came across {company} and was impressed by your work in pharmaceutical manufacturing. I'm with RDL Technologies — we help pharma plants improve automation and monitoring. Would love to connect.",
    "c_suite__petroleum":  "Hi {name}, RDL Technologies works with petroleum and refinery units on process automation and IoT monitoring. I'd love to connect and share how we've helped similar facilities.",
    "c_suite__textile":    "Hi {name}, I noticed {company}'s work in textile manufacturing. RDL Technologies offers automation solutions that help textile units reduce downtime and improve output quality. Happy to connect.",
    "c_suite__food":       "Hi {name}, RDL Technologies partners with food processing companies to implement monitoring and automation systems. Would love to explore synergies with {company}.",
    "c_suite__automotive": "Hi {name}, RDL Technologies supports automotive component manufacturers with PLC-based automation and quality monitoring. Would be great to connect and explore a conversation.",
    "c_suite__electronics":"Hi {name}, I'd love to connect. RDL Technologies provides automation and SCADA solutions to electronics manufacturers — we've helped facilities like {company} improve OEE.",
    "c_suite__chemical":   "Hi {name}, RDL Technologies specialises in process automation for chemical plants. Would love to connect and share how we're helping manufacturers like {company} improve safety and efficiency.",
    "c_suite__metals":     "Hi {name}, RDL Technologies works with steel and metal fabrication units on automation, monitoring and SCADA. Would be great to connect and explore what we could do for {company}.",
    "c_suite__generic":    "Hi {name}, I'm with RDL Technologies — we provide industrial automation and IoT solutions to manufacturing companies. I'd love to connect and share how we might add value to {company}.",

    "cto__pharma":         "Hi {name}, RDL Technologies builds automation and monitoring platforms purpose-built for pharma manufacturing — from batch tracking to SCADA. Would love to connect and exchange ideas.",
    "cto__petroleum":      "Hi {name}, we at RDL Technologies work on industrial IoT and SCADA for petroleum facilities. Would love to connect and explore the technical side of what you're building at {company}.",
    "cto__automotive":     "Hi {name}, RDL Technologies offers PLC/SCADA automation for automotive manufacturing. I'd love to connect and see if there's a technical fit with what {company} is working on.",
    "cto__electronics":    "Hi {name}, I'd love to connect. RDL Technologies provides embedded automation solutions to electronics manufacturers — happy to share technical details of what we've built.",
    "cto__chemical":       "Hi {name}, RDL Technologies provides SIL-rated process control and automation for chemical plants. Would love to connect and exchange ideas with you at {company}.",
    "cto__generic":        "Hi {name}, I'm with RDL Technologies — we develop industrial automation and IoT products for manufacturing. I'd love to connect and explore technical synergies with {company}.",

    "cfo__generic":        "Hi {name}, RDL Technologies helps manufacturing companies reduce operational costs through targeted automation. I'd love to connect and share some ROI data from similar deployments.",

    "procurement__pharma": "Hi {name}, RDL Technologies is a trusted automation supplier to pharma manufacturing units. We offer competitive pricing and after-sales support. Would love to connect.",
    "procurement__generic":"Hi {name}, RDL Technologies manufactures industrial automation equipment including PLCs, sensors and SCADA systems. I'd love to connect and share our product catalogue.",

    "operations__pharma":  "Hi {name}, RDL Technologies helps pharma plant operations teams reduce manual intervention through targeted automation. Would love to connect and share what's worked for similar facilities.",
    "operations__petroleum":"Hi {name}, RDL Technologies supports petroleum plant operations with remote monitoring and predictive maintenance tools. Happy to connect and share more.",
    "operations__generic": "Hi {name}, RDL Technologies works with plant operations teams to cut downtime and improve throughput through automation. Would love to connect.",

    "engineering__pharma": "Hi {name}, as someone in pharma plant engineering, you might find RDL Technologies' batch monitoring and PLC automation relevant. Happy to connect and share technical details.",
    "engineering__petroleum":"Hi {name}, RDL Technologies builds industrial sensors and automation modules for petroleum facilities. Would love to connect and discuss the technical side with you.",
    "engineering__generic":"Hi {name}, I'm with RDL Technologies — we develop PLCs, sensors, and automation systems for industrial manufacturing. Would love to connect with someone in your engineering role.",
}

# ── Full messages (sent after connection is accepted) ─────────────────────────

_FULL_MESSAGES: dict[str, str] = {
    "c_suite__pharma": """\
Hi {name},

Thank you for connecting! I wanted to share a quick overview of how RDL Technologies supports pharmaceutical manufacturers.

We supply:
• Batch monitoring and logging systems compliant with 21 CFR Part 11
• PLC-based automation for filling, packaging, and QC lines
• SCADA systems with OEE dashboards
• Temperature and humidity monitoring for cleanrooms and cold storage
• Customised IoT sensors and data loggers

Our clients include mid-to-large pharma manufacturers across India. We have helped facilities reduce manual logging errors by up to 60% and improve batch traceability significantly.

Would you be open to a 20-minute call to explore whether any of this is relevant to {company}'s current operations?

Best regards,
RDL Technologies Sales Team
www.rdltech.in""",

    "c_suite__petroleum": """\
Hi {name},

Thanks for connecting. I'd like to introduce RDL Technologies and how we work with petroleum and refinery operations.

We provide:
• Remote monitoring systems for tanks, pipelines, and process units
• PLC/SCADA integration for refinery control systems
• Industrial IoT data loggers with 4G/LTE connectivity
• Gas detection and safety monitoring modules
• Predictive maintenance dashboards

We have deployed systems at several petroleum handling and storage facilities and understand the safety-critical nature of the environment.

Would {company} be open to a technical discussion? Happy to share detailed specs and case studies.

Best regards,
RDL Technologies
www.rdltech.in""",

    "cto__generic": """\
Hi {name},

Thanks for connecting! I wanted to share some technical details about RDL Technologies' industrial product line.

Our product portfolio includes:
• Industrial Data Loggers (4G LTE, RS485/Modbus, analog/digital I/O)
• PLCs and HMIs for manufacturing process control
• SCADA platforms with cloud and on-premise deployment options
• Wireless and wired sensor networks (temperature, pressure, vibration, current)
• Energy monitoring and power quality analysis systems

We work directly with engineering teams to customize solutions for specific process requirements. Our products are designed for harsh industrial environments — rated for wide temperature ranges, IP65+.

Would be happy to share our product datasheet or arrange a technical demo. What are the key automation challenges at {company} right now?

Best regards,
RDL Technologies
www.rdltech.in""",

    "procurement__generic": """\
Hi {name},

Thanks for connecting! I'm reaching out from RDL Technologies, an industrial automation manufacturer based in India.

We supply:
• PLCs and HMIs
• Industrial sensors (temperature, pressure, level, flow, vibration)
• Data loggers with wireless/wired connectivity
• SCADA systems
• Energy meters and power quality monitors

We offer:
• Direct manufacturer pricing (no intermediary)
• Technical support and after-sales service
• Custom configurations for specific industry requirements
• Pan-India delivery and installation support

Would be happy to share our product catalogue and pricing. Is {company} currently sourcing automation or instrumentation equipment?

Best regards,
RDL Technologies
www.rdltech.in""",

    "operations__generic": """\
Hi {name},

Thanks for connecting! I wanted to share how RDL Technologies helps plant operations teams at manufacturing facilities.

Common challenges we solve:
• Unplanned downtime — through real-time equipment monitoring and early warning alerts
• Manual data logging errors — replaced with automated data loggers
• Energy wastage — through power quality monitoring and load analytics
• Compliance reporting — automated batch records and audit trails

Our systems integrate with existing PLCs and SCADA, so there's minimal disruption to current operations.

Would you be open to a 20-minute call to discuss what's relevant for {company}? Happy to share case studies from similar facilities.

Best regards,
RDL Technologies
www.rdltech.in""",

    "engineering__generic": """\
Hi {name},

Thanks for connecting! As someone in an engineering role, you might find RDL Technologies' technical product range directly relevant.

Key products:
• Industrial Data Logger 4G LTE — RS485, Modbus RTU/TCP, 16 analog inputs, cloud dashboard
• Cloud PLC 4G — remote programming, Ladder/FBD, 32 I/O, MQTT/REST API
• Biometric Authentication for PLC/SCADA — fingerprint-based access control
• IoT Energy Monitoring Kit — 3-phase power, CT coils, real-time and historical data
• Soil/environmental monitoring sensors

All products are designed for industrial environments and come with full technical documentation, API access, and application support.

Happy to share detailed datasheets or discuss a specific requirement at {company}.

Best regards,
RDL Technologies
www.rdltech.in""",

    # Generic fallback
    "generic__generic": """\
Hi {name},

Thanks for connecting! I wanted to briefly introduce RDL Technologies.

We are an industrial automation and IoT solutions company. Our products include PLCs, HMIs, industrial data loggers, SCADA systems, sensors, and energy monitoring equipment — all designed for manufacturing environments.

We work with companies across pharma, petroleum, textiles, automotive, electronics, chemicals, food processing, and heavy industry.

If any of this is relevant to what {company} is working on, I'd be happy to share more details or arrange a quick demo.

Best regards,
RDL Technologies
www.rdltech.in""",
}


def get_connection_note(name: str, company: str, role_category: str, industry_bucket: str) -> str:
    """Return the ≤300-char connection request note."""
    key = f"{role_category}__{industry_bucket}"
    template = (
        _CONNECTION_NOTES.get(key)
        or _CONNECTION_NOTES.get(f"{role_category}__generic")
        or _CONNECTION_NOTES["c_suite__generic"]
    )
    note = template.format(name=name.split()[0] if name else "there", company=company or "your company")
    return note[:299]  # LinkedIn hard cap


def get_full_message(name: str, company: str, role_category: str, industry_bucket: str) -> str:
    """Return the full follow-up message (sent after connection accepted)."""
    key = f"{role_category}__{industry_bucket}"
    template = (
        _FULL_MESSAGES.get(key)
        or _FULL_MESSAGES.get(f"{role_category}__generic")
        or _FULL_MESSAGES.get(f"generic__generic")
    )
    return template.format(
        name=name.split()[0] if name else "there",
        company=company or "your organisation",
    )


def get_template_key(role_category: str, industry_bucket: str) -> str:
    key = f"{role_category}__{industry_bucket}"
    if key in _CONNECTION_NOTES:
        return key
    fallback = f"{role_category}__generic"
    if fallback in _CONNECTION_NOTES:
        return fallback
    return "c_suite__generic"
