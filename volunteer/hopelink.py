import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict

URL = "https://www.hopelink.org/ways-to-help/volunteer/"

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; HopelinkScraper/1.0)"
}


def fetch_hopelink_opportunities() -> List[Dict]:
    """Scrape Hopelink ongoing volunteer opportunities into a normalized list.

    Each item has: title, org, location, tags, time, url, description.
    Some fields are best-effort / generic because the site is unstructured.
    """

    resp = requests.get(URL, headers=headers)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    opportunities: List[Dict] = []

    # 1. Find the "Ongoing Volunteer Opportunities" heading
    section_heading = None
    for tag in soup.find_all(["h2", "h3"]):
        if "ongoing volunteer opportunities" in tag.get_text(strip=True).lower():
            section_heading = tag
            break

    if not section_heading:
        return opportunities

    # 2. From that heading forward, grab each sub-heading as an opportunity
    for heading in section_heading.find_all_next(["h4", "h5"]):
        title_text = heading.get_text(strip=True)

        # Stop when we reach the FAQ or another big section
        if "volunteer faq" in title_text.lower():
            break

        # 3. Collect description: following <p> siblings until next heading of same/higher level
        description_parts = []
        for sib in heading.find_next_siblings():
            if sib.name and sib.name.startswith("h") and int(sib.name[1]) <= int(heading.name[1]):
                # Next heading at same or higher level → stop
                break
            if sib.name == "p":
                description_parts.append(sib.get_text(" ", strip=True))

        description = " ".join(description_parts).strip()

        # 4. If the heading itself contains a link, use it; otherwise fallback to main URL
        link_tag = heading.find("a")
        if link_tag and link_tag.get("href"):
            link = urljoin(URL, link_tag["href"])
        else:
            link = URL

        opportunities.append(
            {
                "title": title_text,
                "org": "Hopelink",
                "location": "King County, WA",
                "tags": [],  # can be enriched later
                "time": "See Hopelink site",
                "url": link,
                "description": description,
            }
        )

    return opportunities


if __name__ == "__main__":
    # Simple manual test
    for opp in fetch_hopelink_opportunities():
        print("TITLE:", opp["title"])
        print("URL:", opp["url"])
        print("DESCRIPTION:", opp["description"][:200], "...")
        print("-" * 80)
