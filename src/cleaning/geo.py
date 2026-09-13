"""Canonical geography mapping — the single source of truth for region/city.

Every source spells cities/regions differently (Arabic, English, neighbourhoods,
underscores). This module maps any raw value to:
  - one of the 13 canonical **regions** (English), and
  - a canonical **city** (English) where the source is city-level.

It is the join key that lets places, hotels, events, entertainment and statistics
be cross-referenced (see docs/data_dictionary.md §1.4, §10).

Design decisions:
  - Arabic is normalized (diacritics/tatweel removed, alef/ta-marbuta/alef-maqsura
    folded) so spelling variants collapse before lookup.
  - Unmapped values are NOT dropped: `map_city` returns (title-cased raw, None) and the
    caller logs it. Only entertainment drops rows that are confirmed non-Saudi elsewhere.
"""
from __future__ import annotations

import re
import unicodedata

# The 13 official administrative regions (canonical English spelling).
REGIONS = {
    "Riyadh", "Makkah", "Madinah", "Eastern Province", "Asir", "Tabuk", "Hail",
    "Northern Borders", "Jazan", "Najran", "Al Bahah", "Al Jawf", "Qassim",
}

# Diacritics/tatweel only — must not touch the Arabic letter block (U+0621-U+064A).
_AR_DIACRITICS = re.compile("[\u0640\u064B-\u065F\u0670\u06D6-\u06ED]")


def normalize_ar(text: str) -> str:
    """Normalize Arabic text for matching (not for display)."""
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", str(text))
    t = _AR_DIACRITICS.sub("", t)
    t = (t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
           .replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي"))
    return re.sub(r"\s+", " ", t).strip()


# canonical city -> region
CITY_REGION = {
    "Riyadh": "Riyadh", "Diriyah": "Riyadh", "Al Kharj": "Riyadh",
    "Shaqra": "Riyadh", "Al Muzahimiyah": "Riyadh",
    "Jeddah": "Makkah", "Makkah": "Makkah", "Taif": "Makkah", "Rabigh": "Makkah",
    "Madinah": "Madinah", "Yanbu": "Madinah", "Al Ula": "Madinah",
    "Dammam": "Eastern Province", "Al Khobar": "Eastern Province",
    "Dhahran": "Eastern Province", "Al Ahsa": "Eastern Province",
    "Jubail": "Eastern Province", "Qatif": "Eastern Province",
    "Hafar Al Batin": "Eastern Province",
    "Abha": "Asir", "Khamis Mushait": "Asir",
    "Tabuk": "Tabuk", "Hail": "Hail", "Arar": "Northern Borders",
    "Jazan": "Jazan", "Najran": "Najran", "Al Bahah": "Al Bahah",
    "Al Jawf": "Al Jawf", "Sakaka": "Al Jawf",
    "Buraydah": "Qassim", "Unayzah": "Qassim",
}

# English / romanized aliases (lower-cased key) -> canonical city
_EN_ALIASES = {
    "riyadh": "Riyadh", "diriyah": "Diriyah", "ad diriyah": "Diriyah",
    "al kharj": "Al Kharj", "shaqra": "Shaqra", "shaqraa": "Shaqra",
    "al-muzahmiya": "Al Muzahimiyah", "al muzahimiyah": "Al Muzahimiyah",
    "jeddah": "Jeddah", "jedah": "Jeddah", "makkah": "Makkah", "mecca": "Makkah",
    "taif": "Taif", "al taif": "Taif", "rabigh": "Rabigh",
    "madinah": "Madinah", "al madinah": "Madinah", "medina": "Madinah",
    "al madinah al munawwarah": "Madinah", "al-madinah al munawwarah": "Madinah",
    "yanbu": "Yanbu", "al ula": "Al Ula", "alula": "Al Ula",
    "dammam": "Dammam", "al khobar": "Al Khobar", "khobar": "Al Khobar",
    "dhahran": "Dhahran", "al ahsa": "Al Ahsa", "hofuf": "Al Ahsa", "al hofuf": "Al Ahsa",
    "jubail": "Jubail", "al jubail": "Jubail", "qatif": "Qatif", "al qatif": "Qatif",
    "hafar al batin": "Hafar Al Batin",
    "abha": "Abha", "khamis mushait": "Khamis Mushait", "khamis mushayt": "Khamis Mushait",
    "tabuk": "Tabuk", "tabouk": "Tabuk", "hail": "Hail",
    "arar": "Arar", "jazan": "Jazan", "jizan": "Jazan", "najran": "Najran",
    "al baha": "Al Bahah", "al bahah": "Al Bahah",
    "al jawf": "Al Jawf", "sakaka": "Sakaka",
    "buraydah": "Buraydah", "buraidah": "Buraydah", "unayzah": "Unayzah", "onaizah": "Unayzah",
    "qassim": "Buraydah", "al qaseem": "Buraydah",
}

# Arabic aliases (normalize_ar key) -> canonical city
_AR_ALIASES = {
    "الرياض": "Riyadh", "الدرعيه": "Diriyah", "الخرج": "Al Kharj",
    "شقرا": "Shaqra", "المزاحميه": "Al Muzahimiyah",
    "جده": "Jeddah", "مكه": "Makkah", "مكه المكرمه": "Makkah",
    "الطايف": "Taif", "رابغ": "Rabigh",
    "المدينه المنوره": "Madinah", "المدينه": "Madinah", "ينبع": "Yanbu", "العلا": "Al Ula",
    "الدمام": "Dammam", "الخبر": "Al Khobar", "الظهران": "Dhahran",
    "الاحسا": "Al Ahsa", "الجبيل": "Jubail", "القطيف": "Qatif", "حفر الباطن": "Hafar Al Batin",
    "ابها": "Abha", "خميس مشيط": "Khamis Mushait",
    "تبوك": "Tabuk", "حايل": "Hail", "عرعر": "Arar",
    "جازان": "Jazan", "جيزان": "Jazan", "نجران": "Najran",
    "الباحه": "Al Bahah", "الجوف": "Al Jawf", "سكاكا": "Sakaka",
    "القصيم": "Buraydah", "بريده": "Buraydah", "عنيزه": "Unayzah",
}

# Region-level aliases (province names from statistics sources) -> canonical region
_REGION_ALIASES = {
    # tourism_data.csv (underscore)
    "albaha": "Al Bahah", "alqassim": "Qassim", "aseer": "Asir",
    "eastern_region": "Eastern Province", "hail": "Hail", "jazan": "Jazan",
    "jouf": "Al Jawf", "madinah": "Madinah", "makkah": "Makkah", "najran": "Najran",
    "northern_borders": "Northern Borders", "riyadh": "Riyadh", "tabuk": "Tabuk",
    # DataSaudi
    "al-baha": "Al Bahah", "al-jouf": "Al Jawf",
    "al-madinah al-monawarah": "Madinah", "al-qaseem": "Qassim", "al-riyadh": "Riyadh",
    "eastern region": "Eastern Province", "makkah al-mokarramah": "Makkah",
    "northern borders": "Northern Borders", "tabouk": "Tabuk", "asir": "Asir",
}


# Notable towns (ascii, lower-case, Latin-diacritics folded) -> region.
# Covers the higher-frequency long tail; obscure villages stay region=None (best-effort).
_TOWN_REGION = {
    "sharurah": "Najran", "al khafji": "Eastern Province", "al jubayl": "Eastern Province",
    "al nairyah": "Eastern Province", "hafr al baten": "Eastern Province",
    "ras tannurah": "Eastern Province", "turayf": "Northern Borders",
    "al majmaah": "Riyadh", "ad dawadimi": "Riyadh", "afif": "Riyadh",
    "al quwayiyah": "Riyadh", "hotat bani tamim": "Riyadh",
    "al rass": "Qassim", "ar rass": "Qassim", "al bukayriyah": "Qassim",
    "al qunfudhah": "Makkah", "king abdullah economic city": "Makkah",
    "al hada": "Makkah", "al shafa": "Makkah",
    "ahad rafidah": "Asir", "muhayil": "Asir", "tanomah": "Asir",
    "tathleeth": "Asir", "bishah": "Asir", "qalat bishah": "Asir",
    "baljurashi": "Al Bahah", "umm lajj": "Tabuk", "al bad": "Tabuk", "rayyis": "Madinah",
}


def _fold_latin(text: str) -> str:
    """Lower-case and strip Latin diacritics (Ţurayf -> turayf, ‘Afīf -> afif)."""
    t = unicodedata.normalize("NFKD", str(text))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-zA-Z ]", " ", t)          # drop stray punctuation/marks
    return re.sub(r"\s+", " ", t).strip().lower()


def map_region(raw: str) -> str | None:
    """Map a province/region string to a canonical region, or None if unknown."""
    if raw is None:
        return None
    key = str(raw).strip()
    if key in REGIONS:
        return key
    low = key.lower()
    if low in _REGION_ALIASES:
        return _REGION_ALIASES[low]
    return None


def map_city(raw: str) -> tuple[str | None, str | None]:
    """Map a raw city/location string to (canonical_city, region).

    Handles English, Arabic, and 'Neighbourhood, City' forms. Unknown values are
    returned title-cased with region None (caller should log, not drop).
    """
    if raw is None or str(raw).strip() == "":
        return None, None
    s = str(raw).strip()
    # 'Ajyad, Makkah' / 'Al Olayya, Al Khobar' -> take the part after the last comma
    if "," in s:
        s = s.split(",")[-1].strip()

    low = s.lower()
    if low in _EN_ALIASES:
        city = _EN_ALIASES[low]
        return city, CITY_REGION.get(city)

    ar = normalize_ar(s)
    if ar in _AR_ALIASES:
        city = _AR_ALIASES[ar]
        return city, CITY_REGION.get(city)

    # Some sources put a region name in the city field.
    reg = map_region(s)
    if reg:
        return s.title(), reg

    # 'كل مناطق المملكة' = all regions.
    if ar in ("كل مناطق المملكه", "جميع مناطق المملكه"):
        return "All Regions", None

    # Notable town -> region (Latin-diacritics folded); keep the town as the city.
    folded = _fold_latin(s)
    if folded in _TOWN_REGION:
        return s.title(), _TOWN_REGION[folded]

    return s.title(), None
