# redmond_historical_society.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict

URL = "https://www.redmondhistoricalsociety.org/volunteer"

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; RedmondHistoricalScraper/1.0)"
}


def fetch_redmond_historical_opportunities() -> List[Dict]:
    """Scrape Redmond Historical Society volunteer page into a normalized list.

    Each item has: title, org, location, tags, time, url, description.
    """

    resp = requests.get(URL, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Basic description: join paragraphs near the "Volunteer" content.
    description_parts = []

    # Try to anchor at the main "Volunteer" heading.
    heading = None
    for tag in soup.find_all(["h1", "h2"]):
        text = tag.get_text(strip=True)
        if text.lower().startswith("volunteer"):
            heading = tag
            break

    if heading is not None:
        # Collect following <p> tags until we hit another main heading.
        for sib in heading.find_next_siblings():
            if sib.name in ("h1", "h2"):
                break
            if sib.name == "p":
                description_parts.append(sib.get_text(" ", strip=True))
    else:
        # Fallback: just grab the first few <p> tags on the page
        for p in soup.find_all("p")[:5]:
            description_parts.append(p.get_text(" ", strip=True))

    description = " ".join(description_parts).strip()

    # Find the "current volunteer opportunities" external link (VolunteerMatch).
    volunteer_link_tag = soup.find(
        "a",
        string=lambda s: s and "current volunteer opportunities" in s.lower()
    )

    if volunteer_link_tag and volunteer_link_tag.get("href"):
        url = urljoin(URL, volunteer_link_tag["href"])
    else:
        # Fallback to the main volunteer page
        url = URL

    opportunities: List[Dict] = [
        {
            "title": "Volunteer with Redmond Historical Society",
            "org": "Redmond Historical Society",
            "location": "Redmond, WA",
            "tags": ["history", "archives", "education", "events"],
            # RHS roles are ongoing and varied
            "time": "ongoing",
            "url": url,
            "description": description,
        }
    ]

    return opportunities


if __name__ == "__main__":
    for opp in fetch_redmond_historical_opportunities():
        print("TITLE:", opp["title"])
        print("URL:", opp["url"])
        print("DESCRIPTION:", opp["description"][:200], "...")
        print("TAGS:", opp["tags"])
        print("-" * 80)
