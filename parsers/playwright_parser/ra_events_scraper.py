import asyncio
import json
import argparse
import re
import random
from urllib.parse import urljoin

from playwright.async_api import async_playwright


RA_BERLIN_EVENTS_URL = "https://ra.co/events/de/berlin"


async def is_blocked_page(page) -> bool:
    try:
        content = (await page.content()).lower()
        title = (await page.title()).lower()
        url = (page.url or "").lower()
    except Exception as e:
        print(f"[!] is_blocked_page exception: {e}")
        return True

    blocked_markers = [
        "captcha",
        "verify you are human",
        "access is temporarily restricted",
        "access temporarily restricted",
        "temporarily restricted",
        "unusual activity",
        "unusual traffic",
        "challenge",
        "cloudflare",
        "security check",
        "automated (bot) activity",
        "inspection tools",
    ]

    combined = f"{title}\n{url}\n{content}"
    for marker in blocked_markers:
        if marker in combined:
            print(f"[!] BLOCK MARKER DETECTED: {marker}")
            return True

    return False


async def save_debug(page, prefix="debug"):
    try:
        await page.screenshot(path=f"{prefix}.png", full_page=True)
    except Exception as e:
        print(f"[!] Screenshot save failed: {e}")

    try:
        html = await page.content()
        with open(f"{prefix}.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"[!] HTML save failed: {e}")

    print(f"[i] Saved debug files: {prefix}.png, {prefix}.html")


async def human_pause(min_ms=2500, max_ms=5000):
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def human_scroll(page):
    try:
        steps = random.randint(2, 4)
        for _ in range(steps):
            delta = random.randint(300, 900)
            await page.mouse.wheel(0, delta)
            await human_pause(700, 1800)
    except Exception:
        pass


async def get_best_existing_page(browser):
    candidates = []

    for context in browser.contexts:
        for page in context.pages:
            try:
                url = page.url or ""
            except Exception:
                url = ""

            candidates.append(page)

            if "ra.co/events/de/berlin" in url:
                return page

    for page in candidates:
        try:
            url = page.url or ""
        except Exception:
            url = ""

        if "ra.co" in url:
            return page

    raise RuntimeError(
        "Не нашёл открытую вкладку RA в Chrome. "
        "Сначала открой вручную https://ra.co/events/de/berlin и потом запускай скрипт."
    )


async def ensure_events_page(page):
    current_url = page.url or ""
    print(f"[i] Using existing tab: {current_url}")

    if "ra.co/events/de/berlin" not in current_url:
        raise RuntimeError(
            "Скрипт подключился не к той вкладке. "
            "Открой вручную https://ra.co/events/de/berlin, оставь эту вкладку открытой и активной."
        )

    if await is_blocked_page(page):
        await save_debug(page, "blocked_events_page")
        raise RuntimeError("На уже открытой вручную вкладке виден restricted/block page.")


async def collect_event_links(page, max_events: int):
    print("[i] Collecting event links from existing Chrome tab...")
    await ensure_events_page(page)

    seen = set()
    unique_links = []

    # Несколько циклов: ждём, скроллим, снова читаем ссылки
    for step in range(8):
        await human_pause(2000, 3500)

        anchors = await page.locator("a").evaluate_all(
            """
            els => els
              .map(a => a.getAttribute('href'))
              .filter(Boolean)
            """
        )

        print(f"[i] Step {step+1}: found {len(anchors)} raw hrefs")

        for href in anchors:
            if "/events/" not in href:
                continue

            full_url = urljoin("https://ra.co", href)

            if full_url in seen:
                continue

            is_event_url = (
                re.search(r"^https://ra\.co/events/\d+", full_url) is not None
                or re.search(r"^https://ra\.co/events/.+?/(\d+)$", full_url) is not None
                or re.search(r"/events/.*?(\d{4,})", full_url) is not None
            )

            if not is_event_url:
                continue

            if "past" in full_url.lower():
                continue

            seen.add(full_url)
            unique_links.append(full_url)

            if len(unique_links) >= max_events:
                print(f"[i] Reached max_events={max_events}")
                return unique_links

        await human_scroll(page)

    return unique_links


def normalize_space(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.replace("\xa0", " ").split()).strip()

def parse_count_text(text: str):
    if not text:
        return None

    t = text.strip().upper().replace(",", "")
    if t.endswith("K"):
        try:
            return int(float(t[:-1]) * 1000)
        except ValueError:
            return None

    if t.isdigit():
        return int(t)

    return None


def dedupe_artists(artists):
    seen = set()
    out = []
    for item in artists:
        name = normalize_space(item.get("name", ""))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        item["name"] = name
        out.append(item)
    return out


async def extract_json_ld(page):
    scripts = await page.locator('script[type="application/ld+json"]').all_text_contents()
    for raw in scripts:
        try:
            obj = json.loads(raw)
        except Exception:
            continue

        candidates = obj if isinstance(obj, list) else [obj]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "MusicEvent":
                return item
    return None


async def extract_interested(page):
    js = """
    () => {
      const clean = (s) => (s || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();

      const all = Array.from(document.querySelectorAll('*'));

      for (const el of all) {
        const txt = clean(el.textContent);
        if (txt !== 'Interested') continue;

        let parent = el.parentElement;
        if (!parent) continue;

        let next = parent.nextElementSibling;
        let tries = 0;

        while (next && tries < 3) {
          const nums = Array.from(next.querySelectorAll('*'))
            .map(x => clean(x.textContent))
            .filter(t => /^\\d+(?:\\.\\d+)?K$|^\\d{1,3}(?:,\\d{3})*$|^\\d+$/.test(t));

          if (nums.length) {
            return nums[0];
          }

          next = next.nextElementSibling;
          tries++;
        }
      }

      return null;
    }
    """
    try:
        raw_value = await page.evaluate(js)
        return parse_count_text(raw_value)
    except Exception as e:
        print(f"[!] extract_interested failed: {e}")
        return None

async def extract_lineup_from_dom(page):
    js = """
    () => {
      const clean = (s) => (s || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();

      const headings = Array.from(document.querySelectorAll('*')).filter(el => {
        const txt = clean(el.textContent).toUpperCase();
        return txt === 'LINEUP';
      });

      for (const heading of headings) {
        let node = heading.parentElement;
        let attempts = 0;

        while (node && attempts < 6) {
          const text = clean(node.innerText || '');
          if (text.includes('LINEUP')) {
            const candidates = [];

            if (node.nextElementSibling) candidates.push(node.nextElementSibling);

            for (const child of Array.from(node.parentElement?.children || [])) {
              candidates.push(child);
            }

            for (const cand of candidates) {
              if (!cand) continue;
              const candText = clean(cand.innerText || '');
              if (!candText) continue;
              if (candText.toUpperCase() === 'LINEUP') continue;

              const childNodes = Array.from(cand.childNodes || []);
              const artists = [];
              const seen = new Set();

              for (const child of childNodes) {
                if (child.nodeType === Node.TEXT_NODE) {
                  const txt = clean(child.textContent);
                  if (txt && !seen.has(txt.toLowerCase())) {
                    seen.add(txt.toLowerCase());
                    artists.push({
                      name: txt,
                      ra_url: null,
                      has_ra_profile: false
                    });
                  }
                } else if (child.nodeType === Node.ELEMENT_NODE) {
                  if (child.tagName === 'A') {
                    const name = clean(child.textContent);
                    const href = child.href || null;
                    if (name && !seen.has(name.toLowerCase())) {
                      seen.add(name.toLowerCase());
                      artists.push({
                        name,
                        ra_url: href,
                        has_ra_profile: !!href
                      });
                    }
                  } else {
                    const anchor = child.querySelector('a[href]');
                    if (anchor) {
                      const name = clean(anchor.textContent);
                      const href = anchor.href || null;
                      if (name && !seen.has(name.toLowerCase())) {
                        seen.add(name.toLowerCase());
                        artists.push({
                          name,
                          ra_url: href,
                          has_ra_profile: !!href
                        });
                      }
                    } else {
                      const txt = clean(child.textContent);
                      if (txt && txt.length < 80 && !seen.has(txt.toLowerCase())) {
                        seen.add(txt.toLowerCase());
                        artists.push({
                          name: txt,
                          ra_url: null,
                          has_ra_profile: false
                        });
                      }
                    }
                  }
                }
              }

              if (artists.length) {
                return {
                  lineup_block_text_raw: candText,
                  artists
                };
              }
            }
          }

          node = node.parentElement;
          attempts++;
        }
      }

      return { lineup_block_text_raw: null, artists: [] };
    }
    """
    try:
        result = await page.evaluate(js)
        if not result:
            return {"lineup_block_text_raw": None, "artists": []}
        return result
    except Exception as e:
        print(f"[!] extract_lineup_from_dom failed: {e}")
        return {"lineup_block_text_raw": None, "artists": []}


def merge_artists(lineup_artists, json_ld_artists):
    by_name = {}

    for item in lineup_artists or []:
        name = normalize_space(item.get("name"))
        if not name:
            continue
        by_name[name.casefold()] = {
            "name": name,
            "ra_url": item.get("ra_url"),
            "has_ra_profile": bool(item.get("ra_url")) or bool(item.get("has_ra_profile"))
        }

    for item in json_ld_artists or []:
        name = normalize_space(item.get("name"))
        if not name:
            continue
        key = name.casefold()
        if key in by_name:
            if not by_name[key].get("ra_url") and item.get("ra_url"):
                by_name[key]["ra_url"] = item["ra_url"]
                by_name[key]["has_ra_profile"] = True
        else:
            by_name[key] = {
                "name": name,
                "ra_url": item.get("ra_url"),
                "has_ra_profile": bool(item.get("ra_url"))
            }

    ordered = []
    seen = set()

    for item in lineup_artists or []:
        key = normalize_space(item.get("name")).casefold()
        if key and key in by_name and key not in seen:
            ordered.append(by_name[key])
            seen.add(key)

    for item in json_ld_artists or []:
        key = normalize_space(item.get("name")).casefold()
        if key and key in by_name and key not in seen:
            ordered.append(by_name[key])
            seen.add(key)

    return ordered


async def parse_event(page, event_url: str):
    print(f"[i] Opening event: {event_url}")

    await human_pause(2500, 4500)
    await page.goto(event_url, wait_until="domcontentloaded")
    await human_pause(3500, 6500)

    if await is_blocked_page(page):
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", event_url)[-80:]
        await save_debug(page, f"blocked_event_{safe_name}")
        return {
            "url": event_url,
            "error": "blocked_or_restricted"
        }

    await human_scroll(page)
    await human_pause(1500, 3000)

    data = {
        "url": event_url,
        "title": None,
        "date": {
            "start": None,
            "end": None,
        },
        "venue": None,
        "promoter": [],
        "artists": [],
        "lineup_block_text_raw": None,
        "description": None,
        "interested": None,
    }

    json_ld = await extract_json_ld(page)
    json_ld_artists = []

    if json_ld:
        data["title"] = json_ld.get("name") or data["title"]
        data["description"] = json_ld.get("description") or data["description"]

        if json_ld.get("startDate"):
            data["date"]["start"] = json_ld.get("startDate")
        if json_ld.get("endDate"):
            data["date"]["end"] = json_ld.get("endDate")

        location = json_ld.get("location") or {}
        if isinstance(location, dict):
            data["venue"] = location.get("name") or data["venue"]

        organizers = json_ld.get("organizer") or []
        if isinstance(organizers, dict):
            organizers = [organizers]
        data["promoter"] = [
            normalize_space(x.get("name", ""))
            for x in organizers
            if isinstance(x, dict) and normalize_space(x.get("name", ""))
        ]

        performers = json_ld.get("performer") or []
        if isinstance(performers, dict):
            performers = [performers]
        for p in performers:
            if not isinstance(p, dict):
                continue
            name = normalize_space(p.get("name", ""))
            url = p.get("url")
            if name:
                json_ld_artists.append({
                    "name": name,
                    "ra_url": url,
                    "has_ra_profile": bool(url)
                })

    try:
        next_data_json = await page.locator("#__NEXT_DATA__").text_content()
        if next_data_json:
            next_data = json.loads(next_data_json)
            apollo_state = next_data.get("props", {}).get("pageProps", {}).get("apolloState", {})

            events = [v for k, v in apollo_state.items() if k.startswith("Event:")]
            if events:
                event_obj = events[0]
                data["title"] = data["title"] or event_obj.get("title")
                if not data["date"]["start"] and event_obj.get("date"):
                    data["date"]["start"] = event_obj.get("date")

            if not data["venue"]:
                venues = [v for k, v in apollo_state.items() if k.startswith("Venue:")]
                if venues:
                    data["venue"] = venues[0].get("name")

            if not data["promoter"]:
                promoters = [v for k, v in apollo_state.items() if k.startswith("Promoter:")]
                data["promoter"] = [
                    normalize_space(p.get("name", ""))
                    for p in promoters
                    if p.get("name")
                ]
    except Exception as e:
        print(f"[!] __NEXT_DATA__ extraction failed: {e}")

    lineup_result = await extract_lineup_from_dom(page)
    lineup_artists = dedupe_artists(lineup_result.get("artists", []))
    data["lineup_block_text_raw"] = lineup_result.get("lineup_block_text_raw")
    data["artists"] = merge_artists(lineup_artists, json_ld_artists)

    if not data["title"]:
        try:
            title = await page.locator("h1").first.text_content()
            if title:
                data["title"] = normalize_space(title)
        except Exception:
            pass

    if not data["venue"] or not data["promoter"]:
        try:
            links = await page.locator("a").evaluate_all(
                """
                els => els.map(a => ({
                    text: (a.textContent || '').trim(),
                    href: a.getAttribute('href') || ''
                }))
                """
            )
            promoters = list(data["promoter"])

            for link in links:
                text = normalize_space(link["text"])
                href = link["href"]

                if not text or not href:
                    continue

                if not data["venue"] and href.startswith("/clubs/"):
                    data["venue"] = text

                if href.startswith("/promoters/") and text not in promoters:
                    promoters.append(text)

            data["promoter"] = promoters
        except Exception:
            pass

    data["interested"] = await extract_interested(page)

    return data


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-events", type=int, default=5, help="Maximum number of events to parse")
    parser.add_argument("--out", type=str, default="ra_berlin_events.json", help="Output JSON file")
    parser.add_argument("--cdp-url", type=str, default="http://localhost:9222", help="Chrome remote debugging URL")
    args = parser.parse_args()

    async with async_playwright() as p:
        print(f"[i] Connecting to existing Chrome via CDP: {args.cdp_url}")
        browser = await p.chromium.connect_over_cdp(args.cdp_url)

        if not browser.contexts:
            raise RuntimeError(
                "No Chrome contexts found. "
                "Запусти Chrome с --remote-debugging-port=9222."
            )

        page = await get_best_existing_page(browser)
        print(f"[i] Connected. Found existing RA tab: {page.url}")

        event_links = await collect_event_links(page, args.max_events)
        print(f"[i] Collected {len(event_links)} event links")

        if not event_links:
            await save_debug(page, "no_event_links_found")
            raise RuntimeError("Не удалось найти ссылки на события на странице.")

        results = []

        for idx, link in enumerate(event_links, start=1):
            print(f"[{idx}/{len(event_links)}]")

            try:
                item = await parse_event(page, link)
                results.append(item)
            except Exception as e:
                print(f"[!] Error while parsing {link}: {e}")
                results.append({
                    "url": link,
                    "error": str(e),
                })

            await human_pause(4000, 8000)

        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"[i] Saved {len(results)} records to {args.out}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())