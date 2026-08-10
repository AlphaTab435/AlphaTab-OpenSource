# ─── Shared location blocking (used by all platforms) ───────────────────────

# Countries where user CANNOT work onsite (no visa/auth).
# Jobs in these locations are rejected UNLESS "remote" appears in location.
BLOCKED_COUNTRIES = {
    "india", "china", "japan", "south korea", "brazil", "mexico",
    "argentina", "colombia", "chile", "peru", "nigeria", "kenya",
    "south africa", "egypt", "thailand", "vietnam", "indonesia",
    "philippines", "malaysia", "singapore", "taiwan", "hong kong",
    "bangladesh", "sri lanka", "nepal", "myanmar",
}

# Common cities/states in blocked countries (very frequent on job boards)
BLOCKED_LOCATIONS = {
    # India
    "bangalore", "bengaluru", "mumbai", "pune", "hyderabad", "chennai",
    "delhi", "new delhi", "noida", "gurgaon", "gurugram", "kolkata",
    "ahmedabad", "jaipur", "lucknow", "kochi", "thiruvananthapuram",
    "maharashtra", "karnataka", "telangana", "tamil nadu", "kerala",
    "uttar pradesh", "west bengal", "gujarat", "rajasthan",
    # Other blocked-country cities
    "são paulo", "sao paulo", "rio de janeiro", "mexico city",
    "bogota", "bogotá", "buenos aires", "manila", "jakarta",
    "bangkok", "ho chi minh", "hanoi", "kuala lumpur",
    "shanghai", "beijing", "shenzhen", "tokyo", "seoul",
}

# Countries/regions where user can work WITHOUT visa (local)
LOCAL_REGIONS = {
    # Pakistan (home)
    "pakistan", "karachi", "lahore", "islamabad", "faisalabad", "gojra",
    "rawalpindi", "peshawar", "multan",
    # Saudi Arabia
    "saudi arabia", "saudi", "riyadh", "jeddah", "dammam", "khobar", "mecca",
    # UAE
    "uae", "united arab emirates", "emirates", "abu dhabi", "dubai", "sharjah", "ajman",
    # Qatar
    "qatar", "doha",
    # Bahrain
    "bahrain", "manama",
    # Oman
    "oman", "muscat",
    # Kuwait
    "kuwait",
    # Turkey (growing tech hub, hires Pakistanis, easy work visa)
    "turkey", "türkiye", "istanbul", "ankara", "izmir",
}

# Keywords that indicate visa sponsorship / relocation support
SPONSORSHIP_KEYWORDS = {
    "visa sponsor", "visa sponsorship", "sponsorship available",
    "relocation package", "relocation assistance", "relocation support",
    "will sponsor", "we sponsor", "sponsoring visa", "work permit",
    "relocation provided", "relocation offered",
}

# Keywords that indicate remote-friendly
REMOTE_KEYWORDS = {"remote", "work from home", "wfh", "fully remote",
                   "remote-first", "anywhere", "distributed"}

# Knockout keywords (hard requirements user cannot meet)
KNOCKOUT_KEYWORDS = {
    "us citizen", "u.s. citizen", "us person", "u.s. person", "green card",
    "ts/sci", "security clearance", "secret clearance", "active clearance",
    "australian citizen", "eu citizen", "uk citizen", "british citizen",
    "must reside in the us", "must reside in the uk",
    "no sponsorship", "will not sponsor"
}


def is_location_blocked(location: str) -> bool:
    """Return True if the job location is in a blocked country/city."""
    if not location:
        return False
    loc = location.lower()
    if "remote" in loc:
        return False
    for city in BLOCKED_LOCATIONS:
        if city in loc:
            return True
    for country in BLOCKED_COUNTRIES:
        if country in loc:
            return True
    return False


def is_job_suitable(location: str, title: str, description: str) -> bool:
    """Smart filter: ALL JOBS NOW PASS DIRECTLY TO AI.
    The AI will determine if the job is remote and if visa sponsorship is required.
    We no longer drop jobs based on naive string matching.
    """
    return True

