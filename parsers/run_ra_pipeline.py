import argparse
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


#export SCENEGRAPH_DATA_DIR="/Volumes/Untitled/42/scenegraph-data"

#caffeinate -dimsu python3 /Users/tghnx1/code/scenegraph/parsers/run_ra_pipeline.py \
  #--cdp-url http://localhost:9222 \
  #--launch-chrome

SCRIPT_DIR = Path(__file__).resolve().parent
GRAPHQL_DIR = SCRIPT_DIR / "graphql_parser"
PLAYWRIGHT_DIR = SCRIPT_DIR / "playwright_parser"


def resolve_data_dir(default_root: Path) -> Path:
    override = os.environ.get("SCENEGRAPH_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return default_root / "data"


DATA_DIR = resolve_data_dir(SCRIPT_DIR)
JSON_DIR = DATA_DIR / "json"
LOG_DIR = DATA_DIR / "logs"
DEBUG_DIR = DATA_DIR / "debug" / "biographies"
RUNTIME_DIR = DATA_DIR / "runtime"

PARSE_PAST_EVENTS_SCRIPT = GRAPHQL_DIR / "parse_past_events.py"
EXTRACT_ARTISTS_SCRIPT = SCRIPT_DIR / "extract_artists.py"
ARTISTS_BIO_SCRIPT = PLAYWRIGHT_DIR / "artists_bio.py"

DEFAULT_EVENTS_JSON = JSON_DIR / "events_by_year"
DEFAULT_ARTISTS_JSON = JSON_DIR / "artists.json"
DEFAULT_BIO_JSON = JSON_DIR / "artist_biographies.json"
DEFAULT_BIO_LOG = LOG_DIR / "artist_biographies.log"
DEFAULT_BIO_PROCESS_LOG = LOG_DIR / "artist_bio_process.log"
DEFAULT_PIPELINE_LOG = LOG_DIR / "ra_pipeline.log"
DEFAULT_CHROME_LOG = LOG_DIR / "chrome_debug.log"
DEFAULT_BIO_PYTHON = PLAYWRIGHT_DIR / "venv" / "bin" / "python"
DEFAULT_CHROME_BINARY = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
DEFAULT_CHROME_USER_DATA_DIR = RUNTIME_DIR / "chrome-profile"
DEFAULT_CHROME_STARTUP_TIMEOUT = 20.0
DEFAULT_CHROME_START_URL = "https://ra.co"
DEFAULT_EVENTS_MIN_DATE = "2021-01-01"
DEFAULT_EVENTS_CHECKPOINT_EVERY = 50
DEFAULT_BIO_CHECKPOINT_EVERY = 10
DEFAULT_EXTRACT_POLL_INTERVAL = 10.0
DEFAULT_EXTRACT_MIN_INTERVAL = 45.0
YEARLY_FILE_PREFIX = "ra_berlin_past_events_"

LOGGER = logging.getLogger("ra_pipeline")


def setup_logging(log_path: Path) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    LOGGER.addHandler(handler)
    LOGGER.propagate = False
    return log_path


def announce(message: str, level: int = logging.INFO) -> None:
    print(message)
    if LOGGER.handlers:
        LOGGER.log(level, message)


def file_signature(path: Path) -> Optional[tuple[int, ...]]:
    if not path.exists():
        return None
    if path.is_dir() or path.suffix.lower() != ".json":
        json_files = sorted(path.glob(f"{YEARLY_FILE_PREFIX}*.json"))
        if not json_files:
            return None
        latest_mtime = 0
        total_size = 0
        for json_file in json_files:
            stat = json_file.stat()
            latest_mtime = max(latest_mtime, stat.st_mtime_ns)
            total_size += stat.st_size
        return (latest_mtime, total_size, len(json_files))
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def cdp_version_url(cdp_url: str) -> str:
    return f"{cdp_url.rstrip('/')}/json/version"


def cdp_is_available(cdp_url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(cdp_version_url(cdp_url), timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False
    except Exception:
        return False


def cdp_is_local(cdp_url: str) -> bool:
    parsed = urlparse(cdp_url)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def cdp_port(cdp_url: str) -> int:
    parsed = urlparse(cdp_url)
    if parsed.port is None:
        raise ValueError(f"CDP URL must include an explicit port: {cdp_url}")
    return parsed.port


def ensure_output_target(path: Path) -> None:
    if path.suffix.lower() == ".json":
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        path.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parse-python",
        type=Path,
        default=Path(sys.executable),
        help="Python executable for parse_past_events.py and extract_artists.py",
    )
    parser.add_argument(
        "--bio-python",
        type=Path,
        default=DEFAULT_BIO_PYTHON if DEFAULT_BIO_PYTHON.exists() else Path(sys.executable),
        help="Python executable for artists_bio.py",
    )
    parser.add_argument(
        "--events-json",
        type=Path,
        default=DEFAULT_EVENTS_JSON,
        help="Output path for past events JSON, or a directory of yearly event shards",
    )
    parser.add_argument(
        "--artists-json",
        type=Path,
        default=DEFAULT_ARTISTS_JSON,
        help="Output path for extracted artists JSON",
    )
    parser.add_argument(
        "--bio-json",
        type=Path,
        default=DEFAULT_BIO_JSON,
        help="Output path for artist biographies JSON",
    )
    parser.add_argument(
        "--bio-log",
        type=Path,
        default=DEFAULT_BIO_LOG,
        help="Log path for the biography scraper",
    )
    parser.add_argument(
        "--bio-process-log",
        type=Path,
        default=DEFAULT_BIO_PROCESS_LOG,
        help="Log file for stdout/stderr from the artists_bio.py process",
    )
    parser.add_argument(
        "--pipeline-log",
        type=Path,
        default=DEFAULT_PIPELINE_LOG,
        help="Log path for the pipeline runner",
    )
    parser.add_argument(
        "--cdp-url",
        type=str,
        default="http://localhost:9222",
        help="Chrome remote debugging URL for artists_bio.py",
    )
    parser.add_argument(
        "--launch-chrome",
        action="store_true",
        help="Auto-launch a local Chrome instance when the CDP endpoint is unavailable",
    )
    parser.add_argument(
        "--chrome-binary",
        type=Path,
        default=DEFAULT_CHROME_BINARY,
        help="Chrome binary used for auto-launch",
    )
    parser.add_argument(
        "--chrome-user-data-dir",
        type=Path,
        default=DEFAULT_CHROME_USER_DATA_DIR,
        help="User data dir for the auto-launched Chrome debug profile",
    )
    parser.add_argument(
        "--chrome-log",
        type=Path,
        default=DEFAULT_CHROME_LOG,
        help="Log file for stdout/stderr from the auto-launched Chrome process",
    )
    parser.add_argument(
        "--chrome-start-url",
        type=str,
        default=DEFAULT_CHROME_START_URL,
        help="Initial URL to open in the auto-launched Chrome window",
    )
    parser.add_argument(
        "--chrome-startup-timeout",
        type=float,
        default=DEFAULT_CHROME_STARTUP_TIMEOUT,
        help="Seconds to wait for the auto-launched Chrome CDP endpoint to become available",
    )
    parser.add_argument(
        "--events-checkpoint-every",
        type=int,
        default=DEFAULT_EVENTS_CHECKPOINT_EVERY,
        help="Checkpoint frequency for parse_past_events.py",
    )
    parser.add_argument(
        "--events-min-date",
        type=str,
        default=DEFAULT_EVENTS_MIN_DATE,
        help="Oldest event date to crawl in parse_past_events.py, format YYYY-MM-DD",
    )
    parser.add_argument(
        "--bio-checkpoint-every",
        type=int,
        default=DEFAULT_BIO_CHECKPOINT_EVERY,
        help="Checkpoint frequency for artists_bio.py",
    )
    parser.add_argument(
        "--extract-poll-interval",
        type=float,
        default=DEFAULT_EXTRACT_POLL_INTERVAL,
        help="Seconds between checks for new event checkpoints",
    )
    parser.add_argument(
        "--extract-min-interval",
        type=float,
        default=DEFAULT_EXTRACT_MIN_INTERVAL,
        help="Minimum seconds between extract_artists.py refreshes while parsing is still running",
    )
    parser.add_argument(
        "--bio-poll-interval",
        type=float,
        default=15.0,
        help="Seconds between artists list refreshes inside artists_bio.py",
    )
    parser.add_argument(
        "--bio-idle-exit-seconds",
        type=float,
        default=120.0,
        help="Idle timeout for the biography worker watch mode",
    )
    parser.add_argument(
        "--blocked-retry-seconds",
        type=float,
        default=900.0,
        help="Delay before retrying a blocked artist page",
    )
    parser.add_argument(
        "--timeout-retry-seconds",
        type=float,
        default=300.0,
        help="Delay before retrying a timed out artist page",
    )
    parser.add_argument(
        "--error-retry-seconds",
        type=float,
        default=300.0,
        help="Delay before retrying an artist page that errored",
    )
    parser.add_argument(
        "--debug-dir",
        type=Path,
        default=DEBUG_DIR,
        help="Debug output directory for artists_bio.py",
    )
    return parser.parse_args()


def run_extract_artists(args: argparse.Namespace) -> bool:
    cmd = [
        str(args.parse_python),
        str(EXTRACT_ARTISTS_SCRIPT),
        "--input",
        str(args.events_json),
        "--output",
        str(args.artists_json),
    ]
    announce(f"[pipeline] Refreshing artists list from {args.events_json}")
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    if result.returncode != 0:
        announce("[pipeline] extract_artists.py failed", logging.ERROR)
        return False

    announce(f"[pipeline] Artists list updated at {args.artists_json}")
    return True


def start_parse_process(args: argparse.Namespace) -> subprocess.Popen:
    cmd = [
        str(args.parse_python),
        str(PARSE_PAST_EVENTS_SCRIPT),
        "--out",
        str(args.events_json),
        "--checkpoint-every",
        str(max(1, args.events_checkpoint_every)),
        "--min-date",
        args.events_min_date,
    ]
    announce("[pipeline] Starting parse_past_events.py")
    return subprocess.Popen(cmd, cwd=str(GRAPHQL_DIR))


def start_bio_process(args: argparse.Namespace, watch: bool) -> subprocess.Popen:
    cmd = [
        str(args.bio_python),
        str(ARTISTS_BIO_SCRIPT),
        "--artists",
        str(args.artists_json),
        "--out",
        str(args.bio_json),
        "--log-file",
        str(args.bio_log),
        "--debug-dir",
        str(args.debug_dir),
        "--cdp-url",
        args.cdp_url,
        "--checkpoint-every",
        str(max(1, args.bio_checkpoint_every)),
        "--poll-interval",
        str(max(1.0, args.bio_poll_interval)),
        "--idle-exit-seconds",
        str(max(0.0, args.bio_idle_exit_seconds)),
        "--blocked-retry-seconds",
        str(max(0.0, args.blocked_retry_seconds)),
        "--timeout-retry-seconds",
        str(max(0.0, args.timeout_retry_seconds)),
        "--error-retry-seconds",
        str(max(0.0, args.error_retry_seconds)),
    ]

    if watch:
        cmd.append("--watch")

    mode_label = "watch" if watch else "final"
    announce(f"[pipeline] Starting artists_bio.py ({mode_label} mode)")
    args.bio_process_log.parent.mkdir(parents=True, exist_ok=True)
    announce(f"[pipeline] artists_bio.py stdout/stderr -> {args.bio_process_log}")
    bio_log_handle = args.bio_process_log.open("a", encoding="utf-8")
    try:
        return subprocess.Popen(
            cmd,
            cwd=str(PLAYWRIGHT_DIR),
            stdout=bio_log_handle,
            stderr=subprocess.STDOUT,
        )
    finally:
        bio_log_handle.close()


def ensure_chrome_cdp(
    args: argparse.Namespace,
    chrome_proc: Optional[subprocess.Popen],
) -> Optional[subprocess.Popen]:
    if cdp_is_available(args.cdp_url):
        return chrome_proc

    if not args.launch_chrome:
        return chrome_proc

    if not cdp_is_local(args.cdp_url):
        announce(
            f"[pipeline] CDP URL {args.cdp_url} is not local, so auto-launch is disabled for safety.",
            logging.WARNING,
        )
        return chrome_proc

    if not args.chrome_binary.exists():
        announce(
            f"[pipeline] Chrome binary not found at {args.chrome_binary}; cannot auto-launch Chrome.",
            logging.ERROR,
        )
        return chrome_proc

    if chrome_proc is not None and chrome_proc.poll() is None:
        return chrome_proc

    args.chrome_user_data_dir.mkdir(parents=True, exist_ok=True)
    args.chrome_log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(args.chrome_binary),
        f"--remote-debugging-port={cdp_port(args.cdp_url)}",
        f"--user-data-dir={args.chrome_user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if args.chrome_start_url.strip():
        cmd.append(args.chrome_start_url.strip())

    announce(
        f"[pipeline] CDP unavailable. Launching Chrome automatically with profile {args.chrome_user_data_dir}"
    )
    announce(f"[pipeline] Chrome stdout/stderr -> {args.chrome_log}")
    chrome_log_handle = args.chrome_log.open("a", encoding="utf-8")
    try:
        chrome_proc = subprocess.Popen(
            cmd,
            cwd=str(SCRIPT_DIR),
            stdout=chrome_log_handle,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        chrome_log_handle.close()
        announce(f"[pipeline] Failed to launch Chrome: {exc}", logging.ERROR)
        return chrome_proc
    finally:
        chrome_log_handle.close()

    deadline = time.time() + max(1.0, args.chrome_startup_timeout)
    while time.time() < deadline:
        if cdp_is_available(args.cdp_url):
            announce("[pipeline] Chrome CDP is available.")
            return chrome_proc
        if chrome_proc.poll() is not None:
            announce(
                f"[pipeline] Chrome exited during startup with code {chrome_proc.returncode}",
                logging.ERROR,
            )
            return chrome_proc
        time.sleep(1.0)

    announce(
        f"[pipeline] Chrome was launched but CDP did not become ready within {args.chrome_startup_timeout:.0f}s",
        logging.WARNING,
    )
    return chrome_proc


def main() -> int:
    args = parse_args()
    ensure_output_target(args.events_json)
    args.artists_json.parent.mkdir(parents=True, exist_ok=True)
    args.bio_json.parent.mkdir(parents=True, exist_ok=True)
    args.debug_dir.mkdir(parents=True, exist_ok=True)

    pipeline_log = setup_logging(args.pipeline_log)
    announce(f"[pipeline] Logging to {pipeline_log}")
    announce(f"[pipeline] Data directory: {DATA_DIR}")

    chrome_proc: Optional[subprocess.Popen] = None
    chrome_proc = ensure_chrome_cdp(args, chrome_proc)
    parse_proc = start_parse_process(args)
    bio_proc = start_bio_process(args, watch=True)
    last_extracted_signature: Optional[tuple[int, int]] = None
    pending_extract_signature: Optional[tuple[int, int]] = None
    last_extract_ran_at: Optional[float] = None
    extract_failures = 0

    try:
        while True:
            chrome_proc = ensure_chrome_cdp(args, chrome_proc)
            parse_returncode = parse_proc.poll()
            events_signature = file_signature(args.events_json)

            if events_signature is not None and events_signature != last_extracted_signature:
                pending_extract_signature = events_signature

            if pending_extract_signature is not None:
                now = time.monotonic()
                min_interval_reached = (
                    last_extract_ran_at is None
                    or now - last_extract_ran_at >= max(0.0, args.extract_min_interval)
                )

                if parse_returncode is not None or min_interval_reached:
                    if run_extract_artists(args):
                        last_extracted_signature = pending_extract_signature
                    else:
                        extract_failures += 1
                    pending_extract_signature = None
                    last_extract_ran_at = now

            if parse_returncode is None:
                bio_returncode = bio_proc.poll()
                if bio_returncode is not None:
                    announce(
                        f"[pipeline] artists_bio.py exited with code {bio_returncode} while parse_past_events.py is still running. Restarting...",
                        logging.WARNING,
                    )
                    chrome_proc = ensure_chrome_cdp(args, chrome_proc)
                    bio_proc = start_bio_process(args, watch=True)

                time.sleep(max(1.0, args.extract_poll_interval))
                continue

            announce(f"[pipeline] parse_past_events.py finished with code {parse_returncode}")

            final_signature = file_signature(args.events_json)
            if final_signature is not None and final_signature != last_extracted_signature:
                pending_extract_signature = final_signature

            if pending_extract_signature is not None:
                if run_extract_artists(args):
                    last_extracted_signature = pending_extract_signature
                else:
                    extract_failures += 1
                pending_extract_signature = None
                last_extract_ran_at = time.monotonic()

            if bio_proc.poll() is None:
                announce("[pipeline] Waiting for artists_bio.py to finish its watch cycle...")
                bio_returncode = bio_proc.wait()
            else:
                bio_returncode = bio_proc.returncode

            if bio_returncode != 0:
                announce(
                    f"[pipeline] artists_bio.py exited with code {bio_returncode}. Running one final one-shot pass...",
                    logging.WARNING,
                )
                chrome_proc = ensure_chrome_cdp(args, chrome_proc)
                bio_proc = start_bio_process(args, watch=False)
                bio_returncode = bio_proc.wait()

            if parse_returncode != 0:
                return parse_returncode
            if bio_returncode != 0:
                return bio_returncode
            if extract_failures:
                return 1

            announce("[pipeline] Pipeline finished successfully.")
            return 0
    finally:
        if parse_proc.poll() is None:
            parse_proc.terminate()
        if bio_proc.poll() is None:
            bio_proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
