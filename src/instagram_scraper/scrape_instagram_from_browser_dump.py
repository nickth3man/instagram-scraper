import argparse
import csv
import json
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests


DEFAULT_TOOL_DUMP_PATH = Path("data") / "tool_dump.json"
DEFAULT_USERNAME = os.getenv("INSTAGRAM_USERNAME", "believerofbuckets")
DEFAULT_OUTPUT_DIR = Path("data") / DEFAULT_USERNAME

COOKIE_HEADER = os.getenv("IG_COOKIE_HEADER", "")


@dataclass
class Config:
    tool_dump_path: Path
    output_dir: Path
    resume: bool
    reset_output: bool
    start_index: int
    limit: int | None
    checkpoint_every: int
    max_comment_pages: int
    min_delay: float
    max_delay: float
    request_timeout: int
    max_retries: int
    base_retry_seconds: float
    cookie_header: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-dump-path", default=str(DEFAULT_TOOL_DUMP_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--max-comment-pages", type=int, default=100)
    parser.add_argument("--min-delay", type=float, default=0.05)
    parser.add_argument("--max-delay", type=float, default=0.2)
    parser.add_argument("--request-timeout", type=int, default=30)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--base-retry-seconds", type=float, default=2.0)
    parser.add_argument("--cookie-header", default=COOKIE_HEADER)

    args = parser.parse_args()
    return Config(
        tool_dump_path=Path(args.tool_dump_path),
        output_dir=Path(args.output_dir),
        resume=args.resume,
        reset_output=args.reset_output,
        start_index=max(0, args.start_index),
        limit=args.limit,
        checkpoint_every=max(1, args.checkpoint_every),
        max_comment_pages=max(1, args.max_comment_pages),
        min_delay=max(0.0, args.min_delay),
        max_delay=max(args.min_delay, args.max_delay),
        request_timeout=max(1, args.request_timeout),
        max_retries=max(1, args.max_retries),
        base_retry_seconds=max(0.1, args.base_retry_seconds),
        cookie_header=args.cookie_header,
    )


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_urls_from_tool_dump(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")

    start = text.find('{"count"')
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        payload = json.loads(text[start : end + 1])
        urls = payload.get("urls")
        if isinstance(urls, list):
            return urls

    start = text.find("```json")
    end = text.rfind("```")
    if start != -1 and end != -1 and end > start:
        payload = json.loads(text[start + len("```json") : end].strip())
        urls = payload.get("urls")
        if isinstance(urls, list):
            return urls

    raise ValueError("Could not parse URL payload from tool dump")


def cookie_value(cookie_header: str, key: str) -> str | None:
    match = re.search(r"(?:^|; )" + re.escape(key) + r"=([^;]+)", cookie_header)
    if not match:
        return None
    return match.group(1)


def build_session(cookie_header: str) -> requests.Session:
    session = requests.Session()
    csrftoken = cookie_value(cookie_header, "csrftoken")
    app_id = os.getenv("INSTAGRAM_APP_ID")
    asbd_id = os.getenv("INSTAGRAM_ASBD_ID")

    headers = {
        "User-Agent": "Mozilla/5.0",
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


def randomized_delay(cfg: Config, extra_scale: float = 1.0) -> None:
    low = cfg.min_delay * extra_scale
    high = cfg.max_delay * extra_scale
    time.sleep(random.uniform(low, high))


def request_with_retry(
    session: requests.Session,
    url: str,
    cfg: Config,
    params: dict | None = None,
) -> tuple[requests.Response | None, str | None]:
    last_error = None
    for attempt in range(1, cfg.max_retries + 1):
        try:
            response = session.get(url, params=params, timeout=cfg.request_timeout)
        except requests.RequestException as exc:
            last_error = f"request_exception:{exc.__class__.__name__}"
            wait_seconds = cfg.base_retry_seconds * (2 ** (attempt - 1))
            randomized_delay(cfg, extra_scale=wait_seconds)
            continue

        if response.status_code == 200:
            return response, None

        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait_seconds = float(retry_after)
            else:
                wait_seconds = cfg.base_retry_seconds * (2 ** (attempt - 1))
            last_error = f"http_{response.status_code}"
            randomized_delay(cfg, extra_scale=wait_seconds)
            continue

        return None, f"http_{response.status_code}"

    return None, last_error or "request_failed"


def extract_shortcode(url: str) -> str | None:
    match = re.search(r"/(?:p|reel)/([^/]+)/", url)
    if not match:
        return None
    return match.group(1)


def fetch_media_id(
    session: requests.Session, post_url: str, shortcode: str, cfg: Config
) -> tuple[str | None, str | None]:
    response, error = request_with_retry(session, post_url, cfg)
    if response is None:
        return None, error or "media_page_request_failed"

    text = response.text
    primary = re.search(r'"media_id":"(\d+)"', text)
    if primary:
        return primary.group(1), None

    escaped_shortcode = re.escape(shortcode)
    secondary = re.search(
        rf'"shortcode":"{escaped_shortcode}".*?"id":"(\d+)"',
        text,
        re.DOTALL,
    )
    if secondary:
        return secondary.group(1), None

    return None, "media_id_not_found"


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


def fetch_comments(
    session: requests.Session, media_id: str, cfg: Config
) -> tuple[list[dict], str | None]:
    comments = []
    max_id = None
    pages = 0

    while pages < cfg.max_comment_pages:
        pages += 1
        url = f"https://www.instagram.com/api/v1/media/{media_id}/comments/"
        params = {
            "can_support_threading": "true",
            "permalink_enabled": "false",
        }
        if max_id:
            params["max_id"] = max_id

        response, error = request_with_retry(session, url, cfg, params=params)
        if response is None:
            return comments, error or "comments_request_failed"

        try:
            payload = response.json()
        except ValueError:
            content_type = (response.headers.get("content-type") or "").lower()
            preview = (response.text or "")[:120].replace("\n", " ")
            if "json" not in content_type:
                return comments, f"comments_non_json:{content_type}:{preview}"
            return comments, "comments_json_decode_failed"

        page_comments = payload.get("comments") or []
        for comment in page_comments:
            user = comment.get("user") or {}
            comments.append(
                {
                    "id": str(comment.get("pk") or ""),
                    "created_at_utc": comment.get("created_at_utc"),
                    "text": comment.get("text"),
                    "comment_like_count": comment.get("comment_like_count"),
                    "owner_username": user.get("username"),
                    "owner_id": str(user.get("pk") or ""),
                }
            )

        has_more = bool(payload.get("has_more_comments"))
        max_id = payload.get("next_max_id") or payload.get("next_min_id")
        if not has_more or not max_id:
            return comments, None

        randomized_delay(cfg, extra_scale=1.5)

    return comments, "comments_page_guard_exhausted"


def write_json_line(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def ensure_csv_with_header(path: Path, header: list[str], reset: bool) -> None:
    if reset and path.exists():
        path.unlink()
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writeheader()


def append_csv_row(path: Path, header: list[str], row: dict) -> None:
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=header)
        writer.writerow(row)


def checkpoint_path(output_dir: Path) -> Path:
    return output_dir / "checkpoint.json"


def load_checkpoint(output_dir: Path) -> dict | None:
    path = checkpoint_path(output_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(output_dir: Path, state: dict) -> None:
    checkpoint_path(output_dir).write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def reset_output(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "posts.ndjson",
        "comments.ndjson",
        "errors.ndjson",
        "posts.csv",
        "comments.csv",
        "errors.csv",
        "summary.json",
        "checkpoint.json",
    ]:
        path = output_dir / name
        if path.exists():
            path.unlink()


def run(cfg: Config) -> dict:
    urls = load_urls_from_tool_dump(cfg.tool_dump_path)
    output_dir = cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if cfg.reset_output:
        reset_output(output_dir)

    posts_ndjson = output_dir / "posts.ndjson"
    comments_ndjson = output_dir / "comments.ndjson"
    errors_ndjson = output_dir / "errors.ndjson"

    posts_csv = output_dir / "posts.csv"
    comments_csv = output_dir / "comments.csv"
    errors_csv = output_dir / "errors.csv"

    post_header = [
        "media_id",
        "shortcode",
        "post_url",
        "type",
        "taken_at_utc",
        "caption",
        "like_count",
        "comment_count",
    ]
    comment_header = [
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
    error_header = ["index", "post_url", "shortcode", "media_id", "stage", "error"]

    ensure_csv_with_header(posts_csv, post_header, cfg.reset_output)
    ensure_csv_with_header(comments_csv, comment_header, cfg.reset_output)
    ensure_csv_with_header(errors_csv, error_header, cfg.reset_output)

    checkpoint = load_checkpoint(output_dir) if cfg.resume else None
    start_index = cfg.start_index
    if checkpoint is not None:
        start_index = max(start_index, int(checkpoint.get("next_index", start_index)))

    end_index = len(urls)
    if cfg.limit is not None:
        end_index = min(end_index, start_index + cfg.limit)

    session = build_session(cfg.cookie_header)
    started_at = checkpoint.get("started_at_utc") if checkpoint else iso_utc_now()

    processed = int(checkpoint.get("processed", 0)) if checkpoint else 0
    posts_count = int(checkpoint.get("posts", 0)) if checkpoint else 1
    comments_count = int(checkpoint.get("comments", 0)) if checkpoint else 1
    errors_count = int(checkpoint.get("errors", 0)) if checkpoint else 1

    try:
        for index in range(start_index, end_index):
            post_url = urls[index]
            shortcode = extract_shortcode(post_url)
            if not shortcode:
                err = {
                    "index": index,
                    "post_url": post_url,
                    "shortcode": None,
                    "media_id": None,
                    "stage": "extract_shortcode",
                    "error": "missing_shortcode",
                }
                write_json_line(errors_ndjson, err)
                append_csv_row(errors_csv, error_header, err)
                errors_count += 1
                processed += 1
                continue

            media_id, media_id_error = fetch_media_id(session, post_url, shortcode, cfg)
            if not media_id:
                err = {
                    "index": index,
                    "post_url": post_url,
                    "shortcode": shortcode,
                    "media_id": None,
                    "stage": "fetch_media_id",
                    "error": media_id_error or "media_id_not_found",
                }
                write_json_line(errors_ndjson, err)
                append_csv_row(errors_csv, error_header, err)
                errors_count += 1
                processed += 1
                randomized_delay(cfg)
                continue

            media_info, media_info_error = fetch_media_info(session, media_id, cfg)
            if not media_info:
                err = {
                    "index": index,
                    "post_url": post_url,
                    "shortcode": shortcode,
                    "media_id": media_id,
                    "stage": "fetch_media_info",
                    "error": media_info_error or "media_info_failed",
                }
                write_json_line(errors_ndjson, err)
                append_csv_row(errors_csv, error_header, err)
                errors_count += 1
                processed += 1
                randomized_delay(cfg)
                continue

            caption_obj = media_info.get("caption") or {}
            post_row = {
                "media_id": media_id,
                "shortcode": shortcode,
                "post_url": post_url,
                "type": media_info.get("media_type"),
                "taken_at_utc": media_info.get("taken_at_utc"),
                "caption": caption_obj.get("text"),
                "like_count": media_info.get("like_count"),
                "comment_count": media_info.get("comment_count"),
            }
            write_json_line(posts_ndjson, post_row)
            append_csv_row(posts_csv, post_header, post_row)
            posts_count += 1

            post_comments = []
            comments_error = None
            declared_comment_count = post_row.get("comment_count")
            if isinstance(declared_comment_count, int) and declared_comment_count > 0:
                post_comments, comments_error = fetch_comments(session, media_id, cfg)

            for comment in post_comments:
                row = {
                    "media_id": media_id,
                    "shortcode": shortcode,
                    "post_url": post_url,
                    **comment,
                }
                write_json_line(comments_ndjson, row)
                append_csv_row(comments_csv, comment_header, row)
                comments_count += 1

            if comments_error:
                err = {
                    "index": index,
                    "post_url": post_url,
                    "shortcode": shortcode,
                    "media_id": media_id,
                    "stage": "fetch_comments",
                    "error": comments_error,
                }
                write_json_line(errors_ndjson, err)
                append_csv_row(errors_csv, error_header, err)
                errors_count += 1
            processed += 1
            if processed % cfg.checkpoint_every == 0:
                save_checkpoint(
                    output_dir,
                    {
                        "started_at_utc": started_at,
                        "updated_at_utc": iso_utc_now(),
                        "next_index": index + 1,
                        "processed": processed,
                        "posts": posts_count,
                        "comments": comments_count,
                        "errors": errors_count,
                        "total_urls": len(urls),
                    },
                )
            randomized_delay(cfg)
    finally:
        session.close()

    finished_at = iso_utc_now()

    # Extract username from output directory name
    username = output_dir.name if output_dir.name != "data" else "unknown"

    summary = {
        "target_profile": username,
        "source_url": f"https://www.instagram.com/{username}/?hl=en"
        if username != "unknown"
        else None,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "range": {"start_index": start_index, "end_index_exclusive": end_index},
        "processed": processed,
        "posts": posts_count,
        "comments": comments_count,
        "errors": errors_count,
        "files": {
            "posts_csv": str(posts_csv),
            "comments_csv": str(comments_csv),
            "errors_csv": str(errors_csv),
            "posts_ndjson": str(posts_ndjson),
            "comments_ndjson": str(comments_ndjson),
            "errors_ndjson": str(errors_ndjson),
            "checkpoint": str(checkpoint_path(output_dir)),
        },
    }

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    save_checkpoint(
        output_dir,
        {
            "started_at_utc": started_at,
            "updated_at_utc": finished_at,
            "next_index": end_index,
            "processed": processed,
            "posts": posts_count,
            "comments": comments_count,
            "errors": errors_count,
            "total_urls": len(urls),
            "completed": end_index >= len(urls),
        },
    )
    return summary


def main() -> None:
    config = parse_args()
    summary = run(config)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
