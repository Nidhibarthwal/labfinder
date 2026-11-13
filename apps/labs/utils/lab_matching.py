import re
from rapidfuzz.fuzz import ratio

from apps.labs.models import Branch


LEGAL_NAME_REPLACEMENTS = {
    "private limited": "pvt ltd",
    "private ltd": "pvt ltd",
    "pvt. ltd.": "pvt ltd",
    "pvt ltd.": "pvt ltd",
    "pvt. limited": "pvt ltd",
    "limited": "ltd",
}


def normalize_text(value):
    """
    Generic text normalization.
    """
    if not value:
        return ""

    value = str(value).strip().lower()

    # Remove text inside brackets
    # Ghaziabad (UP) -> Ghaziabad
    value = re.sub(r"\([^)]*\)", " ", value)

    # Replace & with and
    value = value.replace("&", " and ")

    # Remove punctuation
    value = re.sub(r"[^a-z0-9\s]", " ", value)

    # Normalize spaces
    value = re.sub(r"\s+", " ", value).strip()

    return value


def normalize_lab_name(name):
    """
    Normalize laboratory name for duplicate matching.
    """

    name = normalize_text(name)

    for old, new in LEGAL_NAME_REPLACEMENTS.items():
        name = name.replace(old, new)

    name = re.sub(r"\s+", " ", name).strip()

    return name


def normalize_city(city):
    """
    Normalize city.

    Ghaziabad
    ghaziabad
    GHAZIABAD
    Ghaziabad (UP)

    -> ghaziabad
    """

    if not city:
        return ""

    city = str(city).strip().lower()

    # Remove bracket content
    city = re.sub(r"\([^)]*\)", " ", city)

    # Remove punctuation
    city = re.sub(r"[^a-z0-9\s]", " ", city)

    city = re.sub(r"\s+", " ", city).strip()

    return city


def normalize_state(state):
    """
    Normalize state name.
    """

    if not state:
        return ""

    return normalize_text(state)


def lab_name_similarity(name1, name2):
    """
    Return similarity percentage between two lab names.
    """

    name1 = normalize_lab_name(name1)
    name2 = normalize_lab_name(name2)

    if not name1 or not name2:
        return 0

    return ratio(name1, name2)


def find_existing_lab(
    name,
    city,
    state,
    threshold=90,
):
    """
    Find an existing Branch which represents the same laboratory.

    Matching rules:

    1. Same normalized state
    2. Same normalized city
    3. Laboratory name similarity >= threshold
    """


    normalized_name = normalize_lab_name(name)
    normalized_city = normalize_city(city)
    normalized_state = normalize_state(state)

    if not normalized_name:
        return None

    if not normalized_city:
        return None

    if not normalized_state:
        return None

    best_match = None
    best_score = 0

    # Get candidates.

    # We intentionally don't use exact city/state filtering here
    # because database values may have:
    #
    # Ghaziabad
    # ghaziabad
    # Ghaziabad (UP)
    #
    # which need our Python normalization.

    candidates = Branch.objects.all().only(
        "id",
        "lab_name",
        "lab_city",
        "lab_state",
    )

    for branch in candidates:

        branch_state = normalize_state(branch.lab_state)
        branch_city = normalize_city(branch.lab_city)

        # State MUST match
        if branch_state != normalized_state:
            continue

        # City MUST match
        if branch_city != normalized_city:
            continue

        score = lab_name_similarity(
            normalized_name,
            branch.lab_name,
        )

        if score >= threshold and score > best_score:
            best_score = score
            best_match = branch

    return best_match