
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlencode
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree
import time

BASE = "https://www.graduateinstitute.ch"

NEWS_URL = BASE + "/news?" + urlencode({
    "field_thematics": "All",
    "field_geographical_area": "All",
    "field_academic_departments": "All",
    "field_research_centres": "21",
    "field_type": "All",
    "s": "",
    "viewsreference[compressed]": "eJxdkNEKwyAMRf_F5z5sFNzWn5GsRhtQW2w6GKX_voissj0I3px7E5JdWWBQw64g-y1iYjWkLYROBYp0ignBYv6q2bkVT7aAb4iJA1ZxdAoTPANaI26m5NffOe175jhveJSWWcpGHvHb8HsRVIrgMyyT-jeQFXzt749GHGGwJkEsySpGWTTM3mR0KJ4Rmzvji1aaU-2kda9vvRZcg8QYjcVQ7nQ5Pkg0bFI"
})

EVENTS_URL = BASE + "/events?" + urlencode({
    "field_thematics": "All",
    "field_event_format": "All",
    "field_academic_departments": "All",
    "field_research_centres": "21",
    "viewsreference[compressed]": "eJxdkNEKgzAMRf-lzz5Mkcn8mZLZtAvEKjUORPz3pThX2EOhJ_fehGQ3DgRMvxshYTR9XJkrM0PAdMHk_YJyEdNIP4AU1hHjl4_KYIQno7MaEIphyZ2LqXyra56kFY88MGnZ6iPZrGyzSrkIIcH8Mv8GcirXbdMVxROysxHGnDxh0NV4CjahR_UMWNwJ37TQFM9O96bt7o9a5TNIgqN1yPkyt-MDlPxnew",
    "iheid_event_end_date_rounder": "",
    "search_api_fulltext": ""
})

session = requests.Session()
session.headers.update({
    "User-Agent": "DemocracyCentreRSS/1.0 (public research news feed)"
})


def fetch(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def text_from(element, selector):
    found = element.select_one(selector)
    return found.get_text(" ", strip=True) if found else ""


def find_link(card):
    link = card.find_parent("a", href=True)

    if not link:
        link = card.select_one("a[href]")

    if not link:
        return None

    url = urljoin(BASE, link["href"])

    if not url.startswith(BASE + "/"):
        return None

    return url


def get_news():
    print("Collecting news...")
    soup = fetch(NEWS_URL)
    items = []

    # Institute news listing cards
    cards = soup.select(
        ".iheid--entity--node--type-news"
    )

    for card in cards:
        title = text_from(card, ".iheid--field--name-title")
        url = find_link(card)

        if not title or not url:
            continue

        try:
            article = fetch(url)

            # Intro field beneath the article title
            intro = text_from(
                article,
                ".iheid--field--name-body"
            )

            items.append({
                "title": title,
                "url": url,
                "description": intro,
                "category": "News",
                "event_date": None
            })

            time.sleep(0.3)

        except requests.RequestException as error:
            print(f"Could not read {url}: {error}")

    return items


def get_events():
    print("Collecting events...")
    soup = fetch(EVENTS_URL)
    items = []

    cards = soup.select(
        ".iheid--entity--node--type-event"
        ".iheid--entity--node--view-mode-small-card"
    )

    for card in cards:
        title = text_from(card, ".iheid--field--name-title")
        url = find_link(card)

        if not title or not url:
            continue

        event_type = text_from(
            card, ".iheid--field--name-field-top-header"
        )
        speakers = text_from(
            card, ".iheid--field--name-field-speakers"
        )
        date = text_from(
            card, ".iheid--field--name-visual-date"
        )
        event_time = card.select_one(
            ".iheid--field--name-field-start-end-date time"
        )
        time_label = (
            event_time.get_text(" ", strip=True)
            if event_time else ""
        )
        event_date = (
            event_time.get("datetime")
            if event_time else None
        )
        event_format = text_from(
            card, ".iheid--field--name-field-event-format"
        )

        details = [
            f"Date: {date}" if date else "",
            f"Time: {time_label}" if time_label else "",
            f"Type: {event_type}" if event_type else "",
            f"Speakers: {speakers}" if speakers else "",
            f"Format: {event_format}" if event_format else ""
        ]

        items.append({
            "title": title,
            "url": url,
            "description": " | ".join(
                detail for detail in details if detail
            ),
            "category": "Event",
            "event_date": event_date
        })

    return items


def make_feed(items):
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = (
        "Geneva Graduate Institute - Democracy Centre"
    )
    SubElement(channel, "link").text = BASE
    SubElement(channel, "description").text = (
        "News and events from the Democracy Centre"
    )
    SubElement(channel, "language").text = "en"

    seen = set()

    for entry in items:
        if entry["url"] in seen:
            continue

        seen.add(entry["url"])

        item = SubElement(channel, "item")
        SubElement(item, "title").text = entry["title"]
        SubElement(item, "link").text = entry["url"]
        SubElement(
            item, "guid", isPermaLink="true"
        ).text = entry["url"]
        SubElement(item, "description").text = (
            entry["description"]
        )
        SubElement(item, "category").text = (
            entry["category"]
        )

        if entry["event_date"]:
            try:
                dt = datetime.fromisoformat(
                    entry["event_date"].replace("Z", "+00:00")
                )
                # Event start is stored separately from publication date.
                SubElement(item, "eventStart").text = (
                    dt.isoformat()
                )
            except ValueError:
                pass

    tree = ElementTree(rss)
    tree.write(
        "feed.xml",
        encoding="utf-8",
        xml_declaration=True
    )

    print(f"Created feed.xml with {len(seen)} items")


if __name__ == "__main__":
    news = get_news()
    events = get_events()

    if not news and not events:
        raise RuntimeError(
            "No items found. Check website selectors."
        )

    make_feed(news + events)
