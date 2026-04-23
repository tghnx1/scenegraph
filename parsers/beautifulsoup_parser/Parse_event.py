import requests
from bs4 import BeautifulSoup
import warnings

try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except Exception:
    pass

STOP_HEADERS = {
    "Location",
    "Links",
    "Followers",
    "Upcoming events",
    "Stats",
    "About",
    "Related Artists",
    "RA News",
    "RA Editorial",
    "Play all",
    "Share",
    "Booking information",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://ra.co/",
}


def clean_lines(text: str) -> list[str]:
    return [x.strip() for x in text.splitlines() if x.strip()]


def collect_section(lines: list[str], header: str) -> list[str]:
    try:
        start = lines.index(header) + 1
    except ValueError:
        return []

    out = []
    for line in lines[start:]:
        if line in STOP_HEADERS:
            break
        out.append(line)
    return out


def normalize_list(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        value = item.strip()
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def parse_artist_page(url: str) -> dict:
    data = {
        "url": url,
        "status_code": None,
        "ok": False,
        "error": None,
        "locations": {
            "born": None,
            "based": None,
        },
        "links": [],
        "followers": None,
        "stats": {
            "first_event_on_ra": None,
            "regions_most_played": [],
            "clubs_most_played": [],
        },
        "about": None,
        "body_preview": None,
    }

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(url, timeout=20)
        data["status_code"] = response.status_code

        if response.status_code != 200:
            data["error"] = f"HTTP {response.status_code}"
            data["body_preview"] = response.text[:500]
            return data

        soup = BeautifulSoup(response.text, "html.parser")
        lines = clean_lines(soup.get_text("\n", strip=True))

        # locations
        location_section = collect_section(lines, "Location")
        for item in location_section:
            if item.endswith("(Born)"):
                data["locations"]["born"] = item.replace("(Born)", "").strip()
            elif item.endswith("(Based)"):
                data["locations"]["based"] = item.replace("(Based)", "").strip()

        # followers
        try:
            idx = lines.index("Followers")
            if idx + 1 < len(lines):
                data["followers"] = lines[idx + 1]
        except ValueError:
            pass

        # about
        about_section = collect_section(lines, "About")
        if about_section:
            data["about"] = about_section[0]

        # stats
        for i, line in enumerate(lines):
            if line == "First event on RA" and i + 1 < len(lines):
                data["stats"]["first_event_on_ra"] = lines[i + 1]

            elif line == "Regions most played":
                values = []
                j = i + 1
                while j < len(lines):
                    if lines[j] in STOP_HEADERS or lines[j] in {"First event on RA", "Clubs most played"}:
                        break
                    values.append(lines[j])
                    j += 1
                data["stats"]["regions_most_played"] = normalize_list(values)

            elif line == "Clubs most played":
                values = []
                j = i + 1
                while j < len(lines):
                    if lines[j] in STOP_HEADERS:
                        break
                    values.append(lines[j])
                    j += 1
                data["stats"]["clubs_most_played"] = normalize_list(values)

        # external links only
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            label = a.get_text(" ", strip=True)

            if not href.startswith("http"):
                continue
            if "ra.co" in href:
                continue

            key = (label, href)
            if key in seen:
                continue
            seen.add(key)

            data["links"].append({
                "label": label if label else None,
                "url": href,
            })

        data["ok"] = True
        return data

    except requests.RequestException as e:
        data["error"] = str(e)
        return data


if __name__ == "__main__":
    url = "https://ra.co/dj/samaabdulhadi"
    result = parse_artist_page(url)
    print(result)
