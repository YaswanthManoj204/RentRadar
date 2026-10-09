
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://findmyhostel.in/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

LOCATION_ALIASES = {
    "kochi": [
        "kochi", "cochin", "ernakulam", "kakkanad", "edappally",
        "edapally", "ponekkara", "kaloor", "kacheripady",
        "kacheripadi", "thevara", "thammanam", "vyttila",
        "kadavanthra", "ravipuram", "thrikkakara", "palarivattom",
        "fort kochi", "marine drive", "mg road", "aluva",
    ]
}


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def normalize(value):
    return clean_text(value).lower().replace("’", "'")


def fetch_homepage():
    response = requests.get(BASE_URL, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.text


def parse_rent(text):
    patterns = [
        r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)",
        r"([\d,]+(?:\.\d{1,2})?)\s*(?:₹|rs\.?|inr)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass

    return None


def extract_category(text):
    text = normalize(text)

    ladies_keywords = [
        "ladies hostel", "lady hostel", "women hostel",
        "womens hostel", "women's hostel", "girls hostel",
        "girl's hostel", "girls pg", "ladies pg", "women pg",
        "womens pg", "girls accommodation", "female hostel",
    ]

    mens_keywords = [
        "mens hostel", "men's hostel", "men hostel",
        "gents hostel", "gent's hostel", "boys hostel",
        "boy's hostel", "boys pg", "gents pg", "mens pg",
        "men's pg", "male hostel",
    ]

    coliving_keywords = [
        "co-living", "coliving", "co living",
    ]

    if any(word in text for word in ladies_keywords):
        return "Ladies' Hostel"

    if any(word in text for word in mens_keywords):
        return "Men's Hostel"

    if any(word in text for word in coliving_keywords):
        return "Co-living"

    if (
        "paying guest" in text
        or "pg accommodation" in text
        or re.search(r"\bpg\b", text)
    ):
        return "PG"

    return "Other"


def extract_location(text, url):
    known_places = [
        "Kakkanad", "Edappally", "Edapally", "Ponekkara",
        "Kaloor", "Kacheripady", "Kacheripadi", "Thevara",
        "Thammanam", "Vyttila", "Kadavanthra", "Ravipuram",
        "Thrikkakara", "Palarivattom", "Fort Kochi",
        "Marine Drive", "Aluva", "Ernakulam", "Kochi", "Cochin",
    ]

    normalized_text = normalize(text)

    for place in known_places:
        if normalize(place) in normalized_text:
            return place

    parts = urlparse(url).path.strip("/").split("/")

    for part in reversed(parts):
        value = part.replace("-", " ").replace("_", " ").strip()

        if value and value.lower() not in {
            "hostel", "details", "ernakulam", "kerala", "india"
        }:
            return value.title()

    return "Kochi"


def find_card(anchor):
    anchor_text = clean_text(anchor.get_text(" ", strip=True))

    if anchor_text and parse_rent(anchor_text) is not None:
        return anchor

    for parent in anchor.parents:
        if getattr(parent, "name", None) in {"body", "html"}:
            break

        parent_text = clean_text(parent.get_text(" ", strip=True))

        if (
            parent_text
            and parse_rent(parent_text) is not None
            and parent.find(["h2", "h3", "h4"])
        ):
            return parent

    return anchor


def extract_title(card, anchor):
    heading = card.find(["h1", "h2", "h3", "h4"])

    if heading:
        title = clean_text(heading.get_text(" ", strip=True))
        if title:
            return title

    for element in (anchor, card):
        for attribute in ("aria-label", "title"):
            value = clean_text(element.get(attribute, ""))
            if value:
                return value

    return "Hostel listing"


def extract_image(card, anchor):
    image = card.find("img") or anchor.find("img")

    if not image:
        return ""

    image_url = (
        image.get("src")
        or image.get("data-src")
        or image.get("data-lazy-src")
        or ""
    )

    if not image_url:
        srcset = image.get("srcset", "")
        if srcset:
            image_url = srcset.split(",")[0].strip().split(" ")[0]

    if not image_url or image_url.startswith("data:"):
        return ""

    return urljoin(BASE_URL, image_url)


def listing_matches_location(location, title, card_text, url):
    if not location:
        return True

    requested = normalize(location)
    searchable = normalize(f"{title} {card_text} {url}")
    aliases = LOCATION_ALIASES.get(requested, [requested])

    return any(normalize(alias) in searchable for alias in aliases)


def discover_listings(html):
    soup = BeautifulSoup(html, "html.parser")
    properties = []
    seen_urls = set()

    # Discover listing links from the homepage.
    for anchor in soup.select('a[href*="/hostel/"]'):
        href = anchor.get("href", "").strip()

        if not href:
            continue

        url = urljoin(BASE_URL, href)
        parsed = urlparse(url)

        if parsed.netloc != urlparse(BASE_URL).netloc:
            continue

        canonical_url = parsed._replace(
            query="", fragment=""
        ).geturl().rstrip("/")

        if canonical_url in seen_urls:
            continue

        card = find_card(anchor)
        card_text = clean_text(card.get_text(" ", strip=True))
        rent = parse_rent(card_text)

        if rent is None or not card_text:
            continue

        title = extract_title(card, anchor)
        category = extract_category(f"{title} {card_text}")

        properties.append({
            "title": title,
            "location": extract_location(card_text, url),
            "rent": rent,
            "category": category,
            "source": "FindMyHostel",
            "amenities": "",
            "image": extract_image(card, anchor),
            "url": canonical_url,
            "_card_text": card_text,
        })

        seen_urls.add(canonical_url)

    print(f"Unique listing cards extracted: {len(properties)}")
    return properties


def scrape_properties(
    location="Kochi",
    min_rent=1000,
    max_rent=15000,
    accommodation_type="all",
    sort_by="rent_asc",
):
    html = fetch_homepage()
    properties = discover_listings(html)
    filtered = []

    selected_type = normalize(accommodation_type or "all")

    for prop in properties:
        rent = prop["rent"]

        if min_rent is not None and rent < min_rent:
            continue

        if max_rent is not None and rent > max_rent:
            continue

        if not listing_matches_location(
            location,
            prop["title"],
            prop["_card_text"],
            prop["url"],
        ):
            continue

        category = prop["category"]

        if selected_type == "mens" and category != "Men's Hostel":
            continue

        if selected_type == "ladies" and category != "Ladies' Hostel":
            continue

        if selected_type == "coliving" and category != "Co-living":
            continue

        if selected_type == "pg" and category != "PG":
            continue

        if selected_type == "other" and category != "Other":
            continue

        if selected_type not in {
            "all", "mens", "ladies", "coliving", "pg", "other", ""
        }:
            continue

        filtered.append(prop)

    if sort_by in {"rent_desc", "highest", "highest_rent"}:
        filtered.sort(key=lambda item: item["rent"], reverse=True)
    else:
        filtered.sort(key=lambda item: item["rent"])

    for prop in filtered:
        prop.pop("_card_text", None)

    print(f"Listings after filters: {len(filtered)}")

    for prop in filtered:
        print(
            f"- {prop['title']} | ₹{prop['rent']:,.0f} | "
            f"{prop['category']} | {prop['url']}"
        )

    return filtered
