"""Output categories for the OpenClaw-style digest layout."""

BRIEFING_CULTURE_CENTRAL = "briefing_culture_central"
BRIEFING_CHWA = "briefing_chwa"
TIME_SENSITIVE = "time_sensitive"  # display only; items use deadline_at, not this category
FUNDING_OPPORTUNITIES = "funding_opportunities"
BIRMINGHAM_BLACK_COUNTRY = "birmingham_black_country"
AUDIO_WALKING_ARTS = "audio_walking_arts"
POETRY_PLACE = "poetry_place"
ARTS_HEALTH = "arts_health"
NETWORK_OTHER = "network_other"
WORTH_CHECKING = "worth_checking"

WHY_FOR_CATEGORY: dict[str, str] = {
    BRIEFING_CULTURE_CENTRAL: "Regional arts infrastructure news relevant to partnerships and funding context.",
    BRIEFING_CHWA: "Creative health policy and practice links to OVERHEAR’s NHS and wellbeing work.",
    TIME_SENSITIVE: "Parsed upcoming deadline — confirm on the page and act before the date shown.",
    FUNDING_OPPORTUNITIES: "Potential grant, commission, open call, or contract aligned with place-based and participatory work.",
    BIRMINGHAM_BLACK_COUNTRY: "Local scene, partners, and commissioning landscape in your core geography.",
    AUDIO_WALKING_ARTS: "Audio, walking, geolocated, and oral-history practice adjacent to OVERHEAR’s offer.",
    POETRY_PLACE: "Literature, poetry, and place-based commissioning.",
    ARTS_HEALTH: "Arts and health crossovers and creative wellbeing programmes.",
    NETWORK_OTHER: "Broader sector signal worth a quick scan.",
    WORTH_CHECKING: "Mentioned deadlines or dates but could not verify — open the link before relying on timing.",
}
