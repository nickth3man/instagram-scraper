import argparse
import csv
import json
import os
import random
import re
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import requests


DEFAULT_DATA_DIR_FALLBACK = "data"
DEFAULT_USERNAME_FALLBACK = "target_profile"
DEFAULT_USER_AGENT = os.getenv(
    "INSTAGRAM_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
)


def default_data_dir() -> Path:
    return Path(os.getenv("INSTAGRAM_DATA_DIR", DEFAULT_DATA_DIR_FALLBACK))


def default_username() -> str:
    return os.getenv("INSTAGRAM_USERNAME", DEFAULT_USERNAME_FALLBACK)


def default_output_dir() -> Path:
    return default_data_dir() / default_username()

COOKIE_HEADER = os.getenv("IG_COOKIE_HEADER", "")


@dataclass
class Config:
    output_dir: Path
    posts_csv: Path
    comments_csv: Path
    resume: bool
    reset_output: bool
    min_delay: float
    max_delay: float
    max_retries: int
    timeout: int
    checkpoint_every: int
    limit: int | None
    cookie_header: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    defaults_output_dir = default_output_dir()
    parser.add_argument("--output-dir", default=str(defaults_output_dir))
    parser.add_argument("--posts-csv", default=str(defaults_output_dir / "posts.csv"))
    parser.add_argument(
        "--comments-csv", default=str(defaults_output_dir / "comments.csv")
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    parser.add_argument("--min-delay", type=float, default=0.05)
    parser.add_argument("--max-delay", type=float, default=0.2)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cookie-header", default=COOKIE_HEADER)
    args = parser.parse_args()
    return Config(
        output_dir=Path(args.output_dir),
        posts_csv=Path(args.posts_csv),
        comments_csv=Path(args.comments_csv),
        resume=args.resume,
        reset_output=args.reset_output,
        min_delay=max(0.0, args.min_delay),
        max_delay=max(args.min_delay, args.max_delay),
        max_retries=max(1, args.max_retries),
        timeout=max(5, args.timeout),
        checkpoint_every=max(1, args.checkpoint_every),
        limit=args.limit,
        cookie_header=args.cookie_header,
    )


def cookie_value(cookie_header: str, key: str) -> str | None:
    match = re.search(r"(?:^|; )" + re.escape(key) + r"=([^;]+)", cookie_header)
    if not match:
        return None
    return match.group(1)


def build_session() -> requests.Session:
    return build_session_with_cookie(COOKIE_HEADER)


def build_session_with_cookie(cookie_header: str) -> requests.Session:
    session = requests.Session()
    csrftoken = cookie_value(cookie_header, "csrftoken")
    app_id = os.getenv("INSTAGRAM_APP_ID")
    asbd_id = os.getenv("INSTAGRAM_ASBD_ID")

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.instagram.com/",
        "Cookie": cookie_header,
    }

    if app_id:
        headers["X-IG-App-ID"] = app_id
    if asbd_id:
        headers["X-ASBD-ID"] = asbd_id

    session.headers.update(headers)
    if csrftoken:
        session.headers["X-CSRFToken"] = csrftoken
    return session


def randomized_delay(cfg: Config, scale: float = 1.0) -> None:
    time.sleep(random.uniform(cfg.min_delay * scale, cfg.max_delay * scale))


def request_with_retry(
    session: requests.Session,
    url: str,
    cfg: Config,
    stream: bool = False,
) -> tuple[requests.Response | None, str | None]:
    last_error = None
    for attempt in range(1, cfg.max_retries + 1):
        try:
            response = session.get(url, timeout=cfg.timeout, stream=stream)
        except requests.RequestException as exc:
            last_error = f"request_exception:{exc.__class__.__name__}"
            randomized_delay(cfg, scale=2 ** (attempt - 1))
            continue

        if response.status_code == 200:
            return response, None

        if response.status_code in {429, 500, 502, 503, 504}:
            last_error = f"http_{response.status_code}"
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait_seconds = float(retry_after)
            else:
                wait_seconds = float(2 ** (attempt - 1))
            randomized_delay(cfg, scale=max(1.0, wait_seconds))
            continue

        return None, f"http_{response.status_code}"

    return None, last_error or "request_failed"


def fetch_media_info(
    session: requests.Session, media_id: str, cfg: Config
) -> tuple[dict | None, str | None]:
    url = f"https://www.instagram.com/api/v1/media/{media_id}/info/"
    response, error = request_with_retry(session, url, cfg)
    if response is None:
        return None, error or "media_info_request_failed"
    try:
        payload = response.json()
    except ValueError:
        content_type = (response.headers.get("content-type") or "").lower()
        preview = (response.text or "")[:120].replace("\n", " ")
        if "json" not in content_type:
            return None, f"media_info_non_json:{content_type}:{preview}"
        return None, "media_info_json_decode_failed"
    items = payload.get("items") or []
    if not items:
        return None, "media_info_empty"
    return items[0], None


def pick_best_video_url(video_versions: list[dict]) -> str | None:
    if not video_versions:
        return None
    best = None
    best_area = -1
    for version in video_versions:
        width = version.get("width") or 0
        height = version.get("height") or 0
        area = width * height
        if area > best_area and version.get("url"):
            best_area = area
            best = version
    if not best:
        return None
    return best.get("url")


def extract_video_entries(media_info: dict) -> list[dict]:
    entries = []
    media_type = media_info.get("media_type")

    if media_type == 2:
        url = pick_best_video_url(media_info.get("video_versions") or [])
        if url:
            entries.append({"position": 1, "media_type": 2, "video_url": url})

    if media_type == 8:
        for idx, child in enumerate(media_info.get("carousel_media") or [], start=1):
            if child.get("media_type") == 2:
                url = pick_best_video_url(child.get("video_versions") or [])
                if url:
                    entries.append({"position": idx, "media_type": 2, "video_url": url})

    return entries


@contextmanager
def locked_path(path: Path):
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write("\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: Path, content: str) -> None:
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    with locked_path(path):
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)


def ensure_csv(path: Path, header: list[str], reset_output: bool) -> None:
    with locked_path(path):
        if reset_output and path.exists():
            path.unlink()
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=header)
                writer.writeheader()
                file.flush()
                os.fsync(file.fileno())


def append_csv(path: Path, header: list[str], row: dict) -> None:
    with locked_path(path):
        with path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writerow(row)
            file.flush()
            os.fsync(file.fileno())


def load_comments_by_shortcode(comments_csv_path: Path) -> dict[str, list[dict]]:
    by_shortcode = defaultdict(list)
    if not comments_csv_path.exists():
        return by_shortcode
    with comments_csv_path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            shortcode = row.get("shortcode")
            if shortcode:
                by_shortcode[shortcode].append(row)
    return by_shortcode


def checkpoint_file(output_dir: Path) -> Path:
    return output_dir / "videos_checkpoint.json"


def load_checkpoint(output_dir: Path) -> dict:
    path = checkpoint_file(output_dir)
    if not path.exists():
        return {
            "completed_shortcodes": [],
            "processed": 0,
            "downloaded_files": 0,
            "errors": 0,
            "skipped_no_video": 0,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(output_dir: Path, state: dict) -> None:
    atomic_write_text(checkpoint_file(output_dir), json.dumps(state, indent=2))


def download_video_file(
    session: requests.Session,
    video_url: str,
    destination: Path,
    cfg: Config,
) -> tuple[bool, str | None]:
    if destination.exists() and destination.stat().st_size > 0:
        return True, None
    if destination.exists() and destination.stat().st_size == 0:
        destination.unlink()

    response, error = request_with_retry(session, video_url, cfg, stream=True)
    if response is None:
        return False, error or "video_download_request_failed"

    temp_path = destination.with_name(
        f"{destination.name}.{os.getpid()}.{time.time_ns()}.part"
    )
    try:
        with temp_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)
            file.flush()
            os.fsync(file.fileno())
    except (OSError, requests.RequestException) as exc:
        temp_path.unlink(missing_ok=True)
        return False, f"file_write_error:{exc.__class__.__name__}"
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    if not temp_path.exists() or temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        return False, "video_file_empty"

    try:
        temp_path.replace(destination)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        return False, f"file_write_error:{exc.__class__.__name__}"

    return True, None


def run(cfg: Config) -> dict:
    if not cfg.posts_csv.exists():
        raise FileNotFoundError(f"posts CSV not found: {cfg.posts_csv}")

    videos_root = cfg.output_dir / "videos"
    videos_root.mkdir(parents=True, exist_ok=True)

    if cfg.reset_output:
        for path in [
            cfg.output_dir / "videos_index.csv",
            cfg.output_dir / "videos_errors.csv",
            checkpoint_file(cfg.output_dir),
            cfg.output_dir / "videos_summary.json",
        ]:
            if path.exists():
                path.unlink()

    index_header = [
        "shortcode",
        "media_id",
        "post_url",
        "position",
        "video_url",
        "file_path",
        "file_size_bytes",
    ]
    error_header = ["shortcode", "media_id", "post_url", "stage", "error"]

    index_csv = cfg.output_dir / "videos_index.csv"
    errors_csv = cfg.output_dir / "videos_errors.csv"
    ensure_csv(index_csv, index_header, cfg.reset_output)
    ensure_csv(errors_csv, error_header, cfg.reset_output)

    comments_by_shortcode = load_comments_by_shortcode(cfg.comments_csv)

    with cfg.posts_csv.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    target_rows = [row for row in rows if row.get("type") in {"2", "8"}]
    target_rows = sorted(
        target_rows,
        key=lambda row: (
            0 if row.get("type") == "2" else 1,
            row.get("shortcode") or "",
        ),
    )
    if cfg.limit is not None:
        target_rows = target_rows[: cfg.limit]

    checkpoint = (
        load_checkpoint(cfg.output_dir)
        if cfg.resume
        else {
            "completed_shortcodes": [],
            "processed": 0,
            "downloaded_files": 0,
            "errors": 0,
            "skipped_no_video": 0,
        }
    )
    completed = set(checkpoint.get("completed_shortcodes", []))

    session = build_session_with_cookie(cfg.cookie_header)
    processed = int(checkpoint.get("processed", 0))
    downloaded_files = int(checkpoint.get("downloaded_files", 0))
    errors = int(checkpoint.get("errors", 0))
    skipped_no_video = int(checkpoint.get("skipped_no_video", 0))

    try:
        for row in target_rows:
            shortcode = row.get("shortcode") or ""
            media_id = row.get("media_id") or ""
            post_url = row.get("post_url") or ""

            if cfg.resume and shortcode in completed:
                continue

            if not shortcode or not media_id:
                append_csv(
                    errors_csv,
                    error_header,
                    {
                        "shortcode": shortcode,
                        "media_id": media_id,
                        "post_url": post_url,
                        "stage": "input_validation",
                        "error": "missing_shortcode_or_media_id",
                    },
                )
                errors += 1
                processed += 1
                continue

            media_info, media_info_error = fetch_media_info(session, media_id, cfg)
            if not media_info:
                append_csv(
                    errors_csv,
                    error_header,
                    {
                        "shortcode": shortcode,
                        "media_id": media_id,
                        "post_url": post_url,
                        "stage": "fetch_media_info",
                        "error": media_info_error or "media_info_failed",
                    },
                )
                errors += 1
                processed += 1
                completed.add(shortcode)
                continue

            video_entries = extract_video_entries(media_info)
            if not video_entries:
                skipped_no_video += 1
                processed += 1
                completed.add(shortcode)
                continue

            post_dir = videos_root / shortcode
            post_dir.mkdir(parents=True, exist_ok=True)

            caption_text = row.get("caption") or ""
            (post_dir / "caption.txt").write_text(caption_text, encoding="utf-8")

            post_comments = comments_by_shortcode.get(shortcode, [])
            comments_header = [
                "media_id",
                "shortcode",
                "post_url",
                "id",
                "created_at_utc",
                "text",
                "comment_like_count",
                "owner_username",
                "owner_id",
            ]
            ensure_csv(post_dir / "comments.csv", comments_header, reset_output=False)
            if post_comments:
                with (post_dir / "comments.csv").open(
                    "w", newline="", encoding="utf-8"
                ) as file:
                    writer = csv.DictWriter(file, fieldnames=comments_header)
                    writer.writeheader()
                    for comment_row in post_comments:
                        writer.writerow(comment_row)

            downloaded_for_post = []
            for entry in video_entries:
                position = int(entry.get("position") or 1)
                video_url = entry.get("video_url") or ""
                filename = f"{shortcode}_{position:02d}.mp4"
                destination = post_dir / filename

                ok, download_error = download_video_file(
                    session, video_url, destination, cfg
                )
                if not ok:
                    append_csv(
                        errors_csv,
                        error_header,
                        {
                            "shortcode": shortcode,
                            "media_id": media_id,
                            "post_url": post_url,
                            "stage": "download_video_file",
                            "error": download_error or "video_download_failed",
                        },
                    )
                    errors += 1
                    continue

                file_size = destination.stat().st_size
                index_row = {
                    "shortcode": shortcode,
                    "media_id": media_id,
                    "post_url": post_url,
                    "position": position,
                    "video_url": video_url,
                    "file_path": str(destination),
                    "file_size_bytes": file_size,
                }
                append_csv(index_csv, index_header, index_row)
                downloaded_for_post.append(index_row)
                downloaded_files += 1

            metadata = {
                "shortcode": shortcode,
                "media_id": media_id,
                "post_url": post_url,
                "caption": caption_text,
                "comment_count_reported": row.get("comment_count"),
                "comments_saved": len(post_comments),
                "video_files": downloaded_for_post,
            }
            (post_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            processed += 1
            completed.add(shortcode)

            if processed % cfg.checkpoint_every == 0:
                save_checkpoint(
                    cfg.output_dir,
                    {
                        "completed_shortcodes": sorted(completed),
                        "processed": processed,
                        "downloaded_files": downloaded_files,
                        "errors": errors,
                        "skipped_no_video": skipped_no_video,
                    },
                )

            randomized_delay(cfg)
    finally:
        session.close()

    summary = {
        "target_posts_considered": len(target_rows),
        "processed": processed,
        "downloaded_files": downloaded_files,
        "errors": errors,
        "skipped_no_video": skipped_no_video,
        "videos_root": str(videos_root),
        "index_csv": str(index_csv),
        "errors_csv": str(errors_csv),
        "checkpoint": str(checkpoint_file(cfg.output_dir)),
    }
    atomic_write_text(cfg.output_dir / "videos_summary.json", json.dumps(summary, indent=2))
    save_checkpoint(
        cfg.output_dir,
        {
            "completed_shortcodes": sorted(completed),
            "processed": processed,
            "downloaded_files": downloaded_files,
            "errors": errors,
            "skipped_no_video": skipped_no_video,
        },
    )
    return summary


def main() -> None:
    config = parse_args()
    summary = run(config)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
