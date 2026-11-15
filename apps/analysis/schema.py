"""
Canonical Schema Definition and Strict Validation Engine for LAB_FINDER.
Enforces schema invariance across all workflows, LLMs, and extraction engines.
"""

from typing import Dict, Any, Optional
from django.utils import timezone
from apps.extractor.deterministic import format_social_links_dict

CANONICAL_SCHEMA_KEYS = {
    "website",
    "summary",
    "company_logo",
    "about_us",
    "contact_us",
    "products_services",
    "accreditations",
}

STATE_FULLNAME_MAP = {
    "up": "Uttar Pradesh",
    "u.p.": "Uttar Pradesh",
    "uttar pradesh": "Uttar Pradesh",
    "mp": "Madhya Pradesh",
    "m.p.": "Madhya Pradesh",
    "madhya pradesh": "Madhya Pradesh",
    "hp": "Himachal Pradesh",
    "h.p.": "Himachal Pradesh",
    "himachal pradesh": "Himachal Pradesh",
    "ap": "Andhra Pradesh",
    "a.p.": "Andhra Pradesh",
    "andhra pradesh": "Andhra Pradesh",
    "tn": "Tamil Nadu",
    "t.n.": "Tamil Nadu",
    "tamil nadu": "Tamil Nadu",
    "wb": "West Bengal",
    "w.b.": "West Bengal",
    "west bengal": "West Bengal",
    "mh": "Maharashtra",
    "maharashtra": "Maharashtra",
    "ka": "Karnataka",
    "karnataka": "Karnataka",
    "hr": "Haryana",
    "haryana": "Haryana",
    "pb": "Punjab",
    "punjab": "Punjab",
    "rj": "Rajasthan",
    "rajasthan": "Rajasthan",
    "gj": "Gujarat",
    "gujarat": "Gujarat",
    "ts": "Telangana",
    "tg": "Telangana",
    "telangana": "Telangana",
    "kl": "Kerala",
    "kerala": "Kerala",
    "br": "Bihar",
    "bihar": "Bihar",
    "or": "Odisha",
    "od": "Odisha",
    "odisha": "Odisha",
    "uk": "Uttarakhand",
    "ua": "Uttarakhand",
    "uttarakhand": "Uttarakhand",
    "cg": "Chhattisgarh",
    "chhattisgarh": "Chhattisgarh",
    "jh": "Jharkhand",
    "jharkhand": "Jharkhand",
    "dl": "Delhi",
    "delhi": "Delhi",
    "ga": "Goa",
    "goa": "Goa",
}

def parse_address_dict(addr_input: Any) -> Dict[str, str]:
    """Parses or normalizes address into canonical address sub-object with state/country inference."""
    if isinstance(addr_input, dict):
        full_addr = str(addr_input.get("full_address") or "").strip()
        country = str(addr_input.get("country") or "").strip()
        state = str(addr_input.get("state") or "").strip()
        city = str(addr_input.get("city") or "").strip()
        pin_code = str(addr_input.get("pin_code") or "").strip()
    elif isinstance(addr_input, str):
        full_addr = addr_input.strip()
        country = ""
        state = ""
        city = ""
        pin_code = ""
    else:
        full_addr = ""
        country = ""
        state = ""
        city = ""
        pin_code = ""

    if full_addr:
        import re
        full_low = full_addr.lower()

        # 1. Direct Country Extraction
        if not country:
            if "india" in full_low:
                country = "India"
            elif "usa" in full_low or "united states" in full_low:
                country = "USA"
            elif "uk" in full_low or "united kingdom" in full_low:
                country = "UK"

        # 2. Pin Code Extraction
        if not pin_code:
            pin_match = re.search(r'\b(\d{6}|\b\d{5}(?:-\d{4})?)\b', full_addr)
            if pin_match:
                pin_code = pin_match.group(1)

        # 3. Direct State Extraction
        if not state:
            if "uttar pradesh" in full_low or re.search(r'\b(up|u\.p\.)\b', full_low):
                state = "Uttar Pradesh"
            elif "madhya pradesh" in full_low or re.search(r'\b(mp|m\.p\.)\b', full_low):
                state = "Madhya Pradesh"
            elif "himachal pradesh" in full_low or re.search(r'\b(hp|h\.p\.)\b', full_low):
                state = "Himachal Pradesh"
            elif "andhra pradesh" in full_low or re.search(r'\b(ap|a\.p\.)\b', full_low):
                state = "Andhra Pradesh"
            elif "tamil nadu" in full_low or re.search(r'\b(tn|t\.n\.)\b', full_low):
                state = "Tamil Nadu"
            elif "west bengal" in full_low or re.search(r'\b(wb|w\.b\.)\b', full_low):
                state = "West Bengal"
            elif "delhi" in full_low:
                state = "Delhi"
            elif "maharashtra" in full_low:
                state = "Maharashtra"
            elif "karnataka" in full_low:
                state = "Karnataka"
            elif "haryana" in full_low:
                state = "Haryana"
            elif "telangana" in full_low:
                state = "Telangana"
            elif "gujarat" in full_low:
                state = "Gujarat"
            elif "punjab" in full_low:
                state = "Punjab"
            elif "rajasthan" in full_low:
                state = "Rajasthan"

        # 4. Direct City Extraction
        if not city:
            if "ghaziabad" in full_low:
                city = "Ghaziabad"
            elif "greater noida" in full_low:
                city = "Greater Noida"
            elif "noida" in full_low:
                city = "Noida"
            elif "delhi" in full_low or "new delhi" in full_low:
                city = "Delhi"
            elif "mumbai" in full_low:
                city = "Mumbai"
            elif "bengaluru" in full_low or "bangalore" in full_low:
                city = "Bengaluru"
            elif "gurugram" in full_low or "gurgaon" in full_low:
                city = "Gurugram"
            elif "pune" in full_low:
                city = "Pune"
            elif "hyderabad" in full_low:
                city = "Hyderabad"
            elif "chennai" in full_low:
                city = "Chennai"
            elif "kolkata" in full_low:
                city = "Kolkata"
            elif "ahmedabad" in full_low:
                city = "Ahmedabad"
            elif "jaipur" in full_low:
                city = "Jaipur"
            elif "chandigarh" in full_low:
                city = "Chandigarh"
            elif "lucknow" in full_low:
                city = "Lucknow"
            elif "kanpur" in full_low:
                city = "Kanpur"
            elif "bhopal" in full_low:
                city = "Bhopal"
            elif "indore" in full_low:
                city = "Indore"
            elif "gwalior" in full_low:
                city = "Gwalior"
            elif "jabalpur" in full_low:
                city = "Jabalpur"

        # 5. Intelligent City-to-State Inference (if state is missing)
        if not state and city:
            city_low = city.lower()
            if city_low in ('noida', 'ghaziabad', 'greater noida', 'lucknow', 'kanpur', 'agra', 'varanasi'):
                state = "Uttar Pradesh"
            elif city_low in ('bhopal', 'indore', 'gwalior', 'jabalpur'):
                state = "Madhya Pradesh"
            elif city_low in ('delhi', 'new delhi'):
                state = "Delhi"
            elif city_low in ('mumbai', 'pune', 'nagpur', 'thane', 'nashik'):
                state = "Maharashtra"
            elif city_low in ('bengaluru', 'bangalore', 'mysuru'):
                state = "Karnataka"
            elif city_low in ('gurugram', 'gurgaon', 'faridabad', 'panipat'):
                state = "Haryana"
            elif city_low in ('hyderabad',):
                state = "Telangana"
            elif city_low in ('chennai', 'coimbatore'):
                state = "Tamil Nadu"
            elif city_low in ('kolkata',):
                state = "West Bengal"
            elif city_low in ('ahmedabad', 'surat', 'vadodara'):
                state = "Gujarat"

        # 6. Intelligent State/City/Pincode-to-Country Inference (if country is missing)
        if not country:
            indian_states = (
                'uttar pradesh', 'up', 'madhya pradesh', 'mp', 'delhi', 'maharashtra', 'karnataka', 'tamil nadu',
                'haryana', 'telangana', 'gujarat', 'punjab', 'rajasthan', 'west bengal',
                'kerala', 'bihar', 'odisha', 'assam', 'jharkhand', 'goa'
            )
            if state and state.lower() in indian_states:
                country = "India"
            elif city and city.lower() in ('noida', 'ghaziabad', 'greater noida', 'delhi', 'mumbai', 'bengaluru', 'gurugram', 'hyderabad', 'chennai', 'pune', 'kolkata', 'ahmedabad'):
                country = "India"
            elif pin_code and re.match(r'^\d{6}$', pin_code):
                country = "India"

    # Always expand state abbreviation to Full Form if present in dictionary
    if state:
        st_clean = state.lower().strip()
        if st_clean in STATE_FULLNAME_MAP:
            state = STATE_FULLNAME_MAP[st_clean]

    return {
        "full_address": full_addr,
        "country": country,
        "state": state,
        "city": city,
        "pin_code": pin_code,
    }

def validate_and_normalize_structured_data(
    data: Optional[Dict[str, Any]],
    root_url: str = "",
    objective: str = "lab_intelligence",
    pages_analyzed: int = 1
) -> Dict[str, Any]:
    """
    Validates and normalizes structured_data against the immutable canonical schema contract.
    Strips unknown top-level keys and fills missing fields with schema-compatible defaults.
    """
    if not isinstance(data, dict):
        data = {}

    # 1. Website
    website_val = data.get("website") or root_url or ""
    if isinstance(website_val, dict):
        website_val = website_val.get("url") or root_url or ""

    # 2. Overall Summary
    summary_val = data.get("summary")
    if not summary_val or not str(summary_val).strip():
        # Fallback to about_us summary if available
        about_obj = data.get("about_us")
        if isinstance(about_obj, dict) and about_obj.get("summary"):
            summary_val = about_obj.get("summary")
        else:
            summary_val = ""
    summary_str = str(summary_val).strip()

    # 3. Company Logo
    logo = data.get("company_logo")
    if not isinstance(logo, dict):
        logo = {}
    normalized_logo = {
        "url": logo.get("url") if logo.get("url") else None,
        "base64": logo.get("base64") if logo.get("base64") else None,
        "alt": logo.get("alt") if logo.get("alt") else None,
        "source_page": logo.get("source_page") if logo.get("source_page") else None,
    }

    # 4. About Us
    about = data.get("about_us")
    if not isinstance(about, dict):
        about = {}
    normalized_about = {
        "summary": str(about.get("summary")).strip() if about.get("summary") else "",
        "source_url": str(about.get("source_url")).strip() if about.get("source_url") else "",
    }

    # 5. Contact Us
    contact = data.get("contact_us")
    if not isinstance(contact, dict):
        contact = {}

    def _to_str_list(val):
        if val is None:
            return []
        if isinstance(val, list):
            return [str(item).strip() for item in val if item and str(item).strip()]
        if isinstance(val, (str, int, float)):
            s = str(val).strip()
            return [s] if s else []
        return []

    # Extract Headquarter
    hq = contact.get("headquarter")
    if not isinstance(hq, dict):
        hq = {}
    
    hq_phones = _to_str_list(hq.get("phone") or contact.get("phone"))
    hq_emails = _to_str_list(hq.get("email") or contact.get("email"))
    hq_email_single = hq_emails[0] if hq_emails else ""
    
    hq_addr_raw = hq.get("address") or (contact.get("address")[0] if contact.get("address") else "")
    hq_address_obj = parse_address_dict(hq_addr_raw)
    hq_source_url = str(hq.get("source_url") or contact.get("source_url") or "").strip()

    normalized_headquarter = {
        "phone": hq_phones,
        "email": hq_email_single,
        "address": hq_address_obj,
        "source_url": hq_source_url,
    }

    # Extract Branches
    branches_raw = contact.get("branches")
    normalized_branches = {}
    if isinstance(branches_raw, dict):
        for b_name, b_val in branches_raw.items():
            if isinstance(b_val, dict):
                b_phones = _to_str_list(b_val.get("phone"))
                b_emails = _to_str_list(b_val.get("email"))
                b_email_single = b_emails[0] if b_emails else ""
                b_addr_obj = parse_address_dict(b_val.get("address"))
                b_source_url = str(b_val.get("source_url") or "").strip()
                normalized_branches[str(b_name)] = {
                    "phone": b_phones,
                    "email": b_email_single,
                    "address": b_addr_obj,
                    "source_url": b_source_url,
                }

    # Social Links inside contact_us
    raw_socials = contact.get("social_links") or data.get("social_links")
    normalized_socials = format_social_links_dict(raw_socials)

    normalized_contact = {
        "headquarter": normalized_headquarter,
        "branches": normalized_branches,
        "social_links": normalized_socials,
    }

    # 6. Products / Services
    ps_raw = data.get("products_services")
    normalized_ps = []
    seen_names = set()
    import re
    from apps.extractor.sections import ProductServiceExtractor
    extractor = ProductServiceExtractor()
    if isinstance(ps_raw, list):
        for item in ps_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            if extractor._is_boilerplate(name):
                continue

            # Filter out statistics / non-service headings (e.g. "7500", "6000", "20 +", "450 +", "Openings", "Happy Clients")
            name_low = name.lower()
            if re.match(r'^[\d\s\+\,\-\%]+$', name) or any(bad in name_low for bad in ["openings", "clients", "staff", "years of experience", "samples tested"]):
                continue

            name_key = name_low
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            summary = str(item.get("summary", "")).strip()
            intro_phrases = [
                'welcome to', 'is a leading', 'leading third-party',
                'providing a wide range of testing services', 'quality control testing laboratory',
                'established in', 'since 2002', 'about our company', 'who we are'
            ]
            summary_low = summary.lower()
            if summary == "None" or summary.startswith("Comprehensive testing and analysis solution for") or any(p in summary_low for p in intro_phrases):
                summary = ""
            src_url = str(item.get("source_url", "")).strip() or str(website_val)

            normalized_ps.append({
                "name": name,
                "summary": summary,
                "source_url": src_url,
            })

    # 7. Accreditations
    acc_raw = data.get("accreditations")
    normalized_acc = []
    if isinstance(acc_raw, list):
        for acc in acc_raw:
            if isinstance(acc, dict) and acc.get("name"):
                normalized_acc.append({
                    "name": str(acc.get("name")).strip(),
                    "full_name": str(acc.get("full_name")).strip() if acc.get("full_name") else None,
                    "accreditation_type": str(acc.get("accreditation_type")).strip() if acc.get("accreditation_type") else None,
                    "grade": str(acc.get("grade")).strip() if acc.get("grade") else None,
                    "score": acc.get("score") if isinstance(acc.get("score"), (int, float)) else None,
                    "status": str(acc.get("status", "Active")).strip() if acc.get("status") else "Active",
                    "valid_from": str(acc.get("valid_from")).strip() if acc.get("valid_from") else None,
                    "valid_until": str(acc.get("valid_until")).strip() if acc.get("valid_until") else None,
                    "certificate_url": str(acc.get("certificate_url")).strip() if acc.get("certificate_url") else None,
                })

    # Assemble Canonical Schema Dict (Strips any unknown extra keys)
    final_output = {
        "website": str(website_val),
        "summary": summary_str,
        "company_logo": normalized_logo,
        "about_us": normalized_about,
        "contact_us": normalized_contact,
        "products_services": normalized_ps,
        "accreditations": normalized_acc,
    }

    return final_output

