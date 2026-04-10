import asyncio
import argparse
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)
#  source venv/bin/activate
#  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_test"
# ./venv/bin/python artists_bio.py \
#   --artists /Users/tghnx1/Desktop/42/scenegraph/Parsers/data/json/artists.json \
#   --out /Users/tghnx1/Desktop/42/scenegraph/Parsers/data/json/artist_biographies.json \
#   --cdp-url http://localhost:9222 \
#   --limit 5
RA_BASE = "https://ra.co"
SCRIPT_DIR = Path(__file__).resolve().parent
PARSERS_DIR = SCRIPT_DIR.parent
DATA_DIR = PARSERS_DIR / "data"
JSON_DIR = DATA_DIR / "json"
LOG_DIR = DATA_DIR / "logs"
DEBUG_DIR = DATA_DIR / "debug" / "biographies"
LOGGER = logging.getLogger("artists_bio")
TERMINAL_SKIP_STATUSES = {"ok", "not_found", "empty"}
DEFAULT_CHECKPOINT_EVERY = 10


def setup_logging(log_path: Path) -> Path:
    resolved_path = log_path.expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()

    handler = logging.FileHandler(resolved_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    LOGGER.addHandler(handler)
    LOGGER.propagate = False
    return resolved_path


def announce(message: str, level: int = logging.INFO) -> None:
    print(message)
    if LOGGER.handlers:
        LOGGER.log(level, message)


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    return normalize_space(str(value))


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"

    total_seconds = int(round(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def normalize_space(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.replace("\xa0", " ").split()).strip()


def build_biography_url(url: str) -> str:
    """
    Accepts:
      - https://ra.co/dj/name
      - https://ra.co/dj/name/
      - https://ra.co/dj/name/biography

    Returns:
      - https://ra.co/dj/name/biography
    """
    url = normalize_space(url).rstrip("/")
    if not url:
        return ""
    if url.endswith("/biography"):
        return url
    return f"{url}/biography"


def load_artists(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("artists.json must contain a JSON array")

    out: List[Dict[str, Any]] = []
    seen = set()

    for item in data:
        if not isinstance(item, dict):
            continue

        artist_id = normalize_value(item.get("id")) or None
        raw_url = normalize_value(item.get("url"))
        if not raw_url:
            continue

        bio_url = build_biography_url(raw_url)
        key = (artist_id, bio_url.casefold())

        if key in seen:
            continue
        seen.add(key)

        out.append({
            "id": artist_id,
            "source_url": raw_url,
            "biography_url": bio_url,
        })

    return out


def make_artist_key(item: Dict[str, Any]) -> Tuple[str, str]:
    artist_id = normalize_value(item.get("id"))
    candidate_url = (
        normalize_value(item.get("biography_url"))
        or normalize_value(item.get("source_url"))
        or normalize_value(item.get("url"))
    )
    biography_url = build_biography_url(candidate_url) if candidate_url else ""
    return (artist_id, biography_url.casefold())


def load_existing_results(
    out_path: Path,
) -> Tuple[List[Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]], List[Tuple[str, str]]]:
    if not out_path.exists():
        return [], {}, []

    try:
        with out_path.open("r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception as e:
        announce(f"[!] Failed to read existing output {out_path}: {e}", logging.ERROR)
        return [], {}, []

    if not content:
        return [], {}, []

    try:
        data = json.loads(content)
    except Exception as e:
        announce(f"[!] Failed to parse existing output {out_path}: {e}", logging.ERROR)
        return [], {}, []

    if not isinstance(data, list):
        announce(f"[!] Existing output {out_path} is not a JSON array. Starting fresh.", logging.WARNING)
        return [], {}, []

    existing_results: List[Dict[str, Any]] = []
    results_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    existing_order: List[Tuple[str, str]] = []

    for item in data:
        if not isinstance(item, dict):
            continue

        key = make_artist_key(item)
        if key in results_by_key:
            continue

        existing_results.append(item)
        results_by_key[key] = item
        existing_order.append(key)

    return existing_results, results_by_key, existing_order


def should_skip_existing(item: Optional[Dict[str, Any]]) -> bool:
    if not item:
        return False

    if normalize_value(item.get("biography")):
        return True

    return normalize_value(item.get("status")) in TERMINAL_SKIP_STATUSES


def build_results_list(
    results_by_key: Dict[Tuple[str, str], Dict[str, Any]],
    current_keys: List[Tuple[str, str]],
    existing_order: List[Tuple[str, str]],
) -> List[Dict[str, Any]]:
    ordered_results: List[Dict[str, Any]] = []
    seen = set()

    for key in current_keys + existing_order:
        if key in seen or key not in results_by_key:
            continue
        seen.add(key)
        ordered_results.append(results_by_key[key])

    return ordered_results


def save_results(out_path: Path, results: List[Dict[str, Any]]) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


async def human_pause(min_ms: int = 1500, max_ms: int = 3500) -> None:
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def human_scroll(page: Page) -> None:
    try:
        steps = random.randint(1, 3)
        for _ in range(steps):
            delta = random.randint(250, 800)
            await page.mouse.wheel(0, delta)
            await human_pause(400, 1200)
    except Exception:
        pass


async def save_debug(page: Page, prefix: str = "debug") -> None:
    prefix_path = Path(prefix)
    prefix_path.parent.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", prefix_path.name)
    output_base = prefix_path.with_name(safe_name)
    screenshot_path = output_base.with_suffix(".png")
    html_path = output_base.with_suffix(".html")

    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception as e:
        announce(f"[!] Screenshot save failed: {e}", logging.ERROR)

    try:
        html = await page.content()
        with html_path.open("w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        announce(f"[!] HTML save failed: {e}", logging.ERROR)

    announce(f"[i] Saved debug files: {screenshot_path}, {html_path}")


async def is_blocked_page(page: Page) -> bool:
    try:
        content = (await page.content()).lower()
        title = (await page.title()).lower()
        url = (page.url or "").lower()
    except Exception as e:
        announce(f"[!] is_blocked_page exception: {e}", logging.ERROR)
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
        "sorry, you have been blocked",
    ]

    combined = f"{title}\n{url}\n{content}"
    return any(marker in combined for marker in blocked_markers)


async def page_looks_like_404(page: Page) -> bool:
    try:
        title = (await page.title()).lower()
        url = (page.url or "").lower()
        visible_text = normalize_space(await page.locator("body").inner_text()).lower()
    except Exception:
        return False

    # Avoid matching hidden script/JSON markup on client-rendered pages.
    # We only treat a page as 404 when the final URL clearly points to the
    # 404 route or the visible page text/title strongly indicates it.
    if url.rstrip("/").endswith("/404"):
        return True

    strong_markers = [
        "page not found",
        "this page could not be found",
        "sorry, the page you requested could not be found",
    ]

    combined = f"{title}\n{visible_text}"
    if any(marker in combined for marker in strong_markers):
        return True

    return "404" in title and "not found" in visible_text


async def extract_artist_name(page: Page) -> Optional[str]:
    selectors = [
        "h1",
        '[data-testid="artist-name"]',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count():
                text = normalize_space(await locator.text_content())
                if text:
                    return text
        except Exception:
            continue
    return None


async def extract_biography_text(page: Page) -> str:
    """
    Extracts the visible biography text and ignores embedded iframes/audio/etc.

    We prefer a DOM-based extraction:
    - find a likely container that includes many text spans/divs
    - get innerText
    - clean it
    """

    biography_section_js = """
    () => {
      const clean = (s) =>
        (s || '')
          .replace(/\\u00a0/g, ' ')
          .replace(/\\s+/g, ' ')
          .trim();

      const isAdLike = (el) => {
        if (!el) return false;
        const testId = (el.getAttribute('data-testid') || '').toLowerCase();
        const className = typeof el.className === 'string' ? el.className.toLowerCase() : '';
        return (
          testId.includes('ad') ||
          className.includes('adslot') ||
          className.includes('admarkup')
        );
      };

      const pushUnique = (items, text) => {
        if (!text) return;
        if (items.some(existing => existing === text || existing.includes(text))) {
          return;
        }
        for (let i = items.length - 1; i >= 0; i -= 1) {
          if (text.includes(items[i])) {
            items.splice(i, 1);
          }
        }
        items.push(text);
      };

      const headings = Array.from(
        document.querySelectorAll('h1, h2, h3, h4, span, div')
      ).filter(el => clean(el.innerText).toLowerCase() === 'biography');

      for (const heading of headings) {
        const section = heading.closest('section');
        if (!section) continue;

        const candidates = Array.from(section.querySelectorAll('li, article, div, section'))
          .filter(el => !isAdLike(el) && clean(el.innerText).length >= 50)
          .sort((a, b) => clean(b.innerText).length - clean(a.innerText).length);

        for (const candidate of candidates) {
          const blocks = [];

          candidate.querySelectorAll('p, span[color="primary"], div').forEach(node => {
            if (isAdLike(node)) return;
            const text = clean(node.innerText);
            if (!text || text.toLowerCase() === 'biography' || text.length < 20) return;
            pushUnique(blocks, text);
          });

          if (blocks.length) {
            const joined = clean(blocks.join(' '));
            if (joined.length >= 50) {
              return joined;
            }
          }

          const fallback = clean(candidate.innerText).replace(/^biography\\s*/i, '');
          if (fallback.length >= 50) {
            return fallback;
          }
        }
      }

      return '';
    }
    """

    text = normalize_space(await page.evaluate(biography_section_js))
    if text:
        return text

    # First, try specific biography section selectors for ra.co
    biography_selectors = [
        'section[class*="Biography"]',
        'section[class*="biography"]',
        'div[class*="Biography"]',
        'div[class*="biography"]',
        '[data-testid*="biography"]',
        'span[color="primary"]',
    ]

    for selector in biography_selectors:
        try:
            locator = page.locator(selector)
            count = await locator.count()

            for i in range(count):
                element = locator.nth(i)
                text = normalize_space(await element.inner_text())
                # Lower threshold for biography-specific selectors
                if text and len(text) >= 50:
                    return text
        except Exception:
            continue

    # JavaScript-based extraction with improved logic
    js = """
    () => {
      const clean = (s) =>
        (s || '')
          .replace(/\\u00a0/g, ' ')
          .replace(/\\s+/g, ' ')
          .trim();

      const badTags = new Set(['IFRAME', 'SCRIPT', 'STYLE', 'NOSCRIPT', 'NAV', 'HEADER', 'FOOTER']);

      // Look for elements that might contain biography
      const allElements = Array.from(document.querySelectorAll('div, section, article, span[color]'));

      const candidates = allElements.filter(el => {
        if (!el || !el.innerText) return false;
        const text = clean(el.innerText);
        if (!text || text.length < 50) return false;

        // Check for biography-related classes or attributes
        const className = (el.className || '').toLowerCase();
        const hasbiographyClass = className.includes('biography') || className.includes('bio');

        const spanCount = el.querySelectorAll('span').length;
        const divCount = el.querySelectorAll('div').length;
        const pCount = el.querySelectorAll('p').length;

        return hasbiographyClass || spanCount >= 1 || divCount >= 1 || pCount >= 1;
      });

      function score(el) {
        const text = clean(el.innerText || '');
        if (!text) return -1;
        let score = 0;

        // Prioritize text length
        score += Math.min(text.length, 4000);

        // Boost for biography-related classes
        const className = (el.className || '').toLowerCase();
        if (className.includes('biography') || className.includes('bio')) {
          score += 1000;
        }

        // Boost for section tags
        if (el.tagName === 'SECTION') score += 300;

        // Moderate boost for nested elements
        score += el.querySelectorAll('span').length * 20;
        score += el.querySelectorAll('p').length * 30;

        return score;
      }

      candidates.sort((a, b) => score(b) - score(a));

      for (const root of candidates) {
        const clone = root.cloneNode(true);

        // Remove unwanted elements
        clone.querySelectorAll('*').forEach(el => {
          if (badTags.has(el.tagName)) {
            el.remove();
          }
        });

        const text = clean(clone.innerText || '');
        if (text && text.length >= 50) {
          return text;
        }
      }

      return '';
    }
    """

    text = normalize_space(await page.evaluate(js))
    if text:
        return text

    # Expanded fallback selectors
    fallback_selectors = [
        "section",
        "article",
        "main",
        '[role="main"]',
        "body",
    ]

    for selector in fallback_selectors:
        try:
            txt = normalize_space(await page.locator(selector).first.inner_text())
            if len(txt) >= 80:
                return txt
        except Exception:
            continue

    return ""


async def get_or_create_page(browser: Browser) -> Page:
    for context in browser.contexts:
        for page in context.pages:
            try:
                if "ra.co" in (page.url or ""):
                    return page
            except Exception:
                continue

    if browser.contexts:
        return await browser.contexts[0].new_page()

    context = await browser.new_context()
    return await context.new_page()


async def parse_biography_page(page: Page, artist: Dict[str, Any], debug_dir: Path) -> Dict[str, Any]:
    url = artist["biography_url"]
    artist_id = artist.get("id")

    result: Dict[str, Any] = {
        "id": artist_id,
        "source_url": artist.get("source_url"),
        "biography_url": url,
        "artist_name": None,
        "biography": None,
        "status": None,
        "http_status": None,
        "final_url": None,
        "error": None,
    }

    announce(f"[i] Opening: {url}")

    try:
        await human_pause(1800, 3200)

        response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await human_pause(2500, 4500)
        await human_scroll(page)
        await human_pause(1200, 2200)

        status = response.status if response else None
        result["http_status"] = status
        result["final_url"] = page.url

        if await is_blocked_page(page):
            result["status"] = "blocked"
            prefix = debug_dir / f"blocked_{artist_id or 'unknown'}"
            await save_debug(page, str(prefix))
            return result

        if status == 404 or await page_looks_like_404(page):
            result["status"] = "not_found"
            if status != 404 and not (page.url or "").lower().rstrip("/").endswith("/404"):
                prefix = debug_dir / f"not_found_{artist_id or 'unknown'}"
                await save_debug(page, str(prefix))
            return result

        artist_name = await extract_artist_name(page)
        biography = await extract_biography_text(page)

        result["artist_name"] = artist_name

        if biography:
            result["biography"] = biography
            result["status"] = "ok"
            return result

        # Sometimes page exists but biography section is empty/missing.
        # Save debug info to help diagnose why extraction failed
        result["status"] = "empty"
        prefix = debug_dir / f"empty_{artist_id or 'unknown'}"
        await save_debug(page, str(prefix))
        return result

    except PlaywrightTimeoutError as e:
        result["status"] = "timeout"
        result["error"] = str(e)
        announce(f"[!] Timeout while opening {url}: {e}", logging.ERROR)
        prefix = debug_dir / f"timeout_{artist_id or 'unknown'}"
        await save_debug(page, str(prefix))
        return result

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        announce(f"[!] Unexpected error while parsing {url}: {e}", logging.ERROR)
        prefix = debug_dir / f"error_{artist_id or 'unknown'}"
        await save_debug(page, str(prefix))
        return result


async def run(
    artists_path: Path,
    out_path: Path,
    cdp_url: str,
    limit: Optional[int],
    debug_dir: Path,
    log_path: Optional[Path],
    checkpoint_every: int,
) -> None:
    checkpoint_every = max(1, checkpoint_every)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_log_path = setup_logging(
        log_path if log_path is not None else LOG_DIR / f"{out_path.stem}.log"
    )
    run_started_at = time.perf_counter()

    announce(f"[i] Logging to {resolved_log_path}")

    artists = load_artists(artists_path)

    if limit is not None:
        artists = artists[:limit]

    announce(f"[i] Loaded {len(artists)} artists from {artists_path}")

    debug_dir.mkdir(parents=True, exist_ok=True)

    existing_results, results_by_key, existing_order = load_existing_results(out_path)
    if existing_results:
        announce(f"[i] Loaded {len(existing_results)} existing biography records from {out_path}")

    current_keys = [make_artist_key(artist) for artist in artists]
    skipped_existing = sum(
        1 for key in current_keys if should_skip_existing(results_by_key.get(key))
    )
    if skipped_existing:
        announce(f"[i] Will skip {skipped_existing} artists already parsed with terminal status")

    if skipped_existing == len(artists):
        final_results = build_results_list(results_by_key, current_keys, existing_order)
        save_results(out_path, final_results)
        total_elapsed = time.perf_counter() - run_started_at

        announce(f"[i] Nothing new to parse. Saved {len(final_results)} records to {out_path}")
        announce(
            "[i] Run summary: "
            f"total_artists={len(artists)}, "
            "parsed_this_run=0, "
            f"skipped_existing={skipped_existing}, "
            f"total_time={format_elapsed(total_elapsed)}, "
            "average_parse_time=0.00s"
        )
        return

    async with async_playwright() as p:
        announce(f"[i] Connecting to existing Chrome via CDP: {cdp_url}")
        browser = await p.chromium.connect_over_cdp(cdp_url)

        if not browser.contexts:
            raise RuntimeError(
                "No Chrome contexts found. Start Chrome with --remote-debugging-port=9222"
            )

        page = await get_or_create_page(browser)
        announce(f"[i] Using page: {page.url or 'about:blank'}")

        parsed_this_run = 0
        skipped_this_run = 0
        parse_durations: List[float] = []

        for idx, artist in enumerate(artists, start=1):
            key = current_keys[idx - 1]
            existing_item = results_by_key.get(key)
            artist_label = artist.get("id") or artist.get("biography_url")

            if should_skip_existing(existing_item):
                skipped_this_run += 1
                announce(
                    f"[{idx}/{len(artists)}] Skipping {artist_label} "
                    f"(already parsed, status={existing_item.get('status')})"
                )
                continue

            artist_started_at = time.perf_counter()
            announce(f"[{idx}/{len(artists)}] Parsing {artist_label}")
            item = await parse_biography_page(page, artist, debug_dir)
            elapsed = time.perf_counter() - artist_started_at

            results_by_key[key] = item
            parsed_this_run += 1
            parse_durations.append(elapsed)

            announce(
                f"[{idx}/{len(artists)}] Finished {artist_label} "
                f"status={item['status']} in {format_elapsed(elapsed)}"
            )

            if parsed_this_run % checkpoint_every == 0:
                checkpoint_results = build_results_list(results_by_key, current_keys, existing_order)
                save_results(out_path, checkpoint_results)
                announce(
                    f"[i] Checkpoint saved {len(checkpoint_results)} records to {out_path}"
                )

            # stronger cooldown after block to reduce repeated bans
            if item["status"] == "blocked":
                announce("[!] Block detected. Cooling down longer...", logging.WARNING)
                await human_pause(12000, 20000)
            else:
                await human_pause(3000, 7000)

        final_results = build_results_list(results_by_key, current_keys, existing_order)
        save_results(out_path, final_results)

        total_elapsed = time.perf_counter() - run_started_at
        average_elapsed = (
            sum(parse_durations) / len(parse_durations) if parse_durations else 0.0
        )

        announce(f"[i] Saved {len(final_results)} records to {out_path}")
        announce(
            "[i] Run summary: "
            f"total_artists={len(artists)}, "
            f"parsed_this_run={parsed_this_run}, "
            f"skipped_existing={skipped_this_run}, "
            f"total_time={format_elapsed(total_elapsed)}, "
            f"average_parse_time={format_elapsed(average_elapsed) if parse_durations else '0.00s'}"
        )
        await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artists",
        type=Path,
        default=JSON_DIR / "artists.json",
        help="Path to artists.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=JSON_DIR / "artist_biographies.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--cdp-url",
        type=str,
        default="http://localhost:9222",
        help="Chrome remote debugging URL",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Parse only first N artists",
    )
    parser.add_argument(
        "--debug-dir",
        type=Path,
        default=DEBUG_DIR,
        help="Directory for screenshots/html dumps",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional log file path. Defaults to <out>.log",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=DEFAULT_CHECKPOINT_EVERY,
        help="Save output after every N newly parsed artists",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    await run(
        artists_path=args.artists,
        out_path=args.out,
        cdp_url=args.cdp_url,
        limit=args.limit,
        debug_dir=args.debug_dir,
        log_path=args.log_file,
        checkpoint_every=args.checkpoint_every,
    )


if __name__ == "__main__":
    asyncio.run(main())
