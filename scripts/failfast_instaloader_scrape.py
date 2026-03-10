from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from instaloader import Instaloader, Post
from instaloader.exceptions import BadResponseException, TooManyRequestsException
from instaloader.instaloadercontext import RateController


class FailFastRateController(RateController):
    def handle_429(self, query_type: str) -> None:
        raise TooManyRequestsException(f"fail-fast-429:{query_type}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/believerofbuckets/tool_dump.json")
    parser.add_argument("--output-dir", default="data/believerofbuckets")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--download-media", action="store_true")
    parser.add_argument("--reset-output", action="store_true")
    return parser.parse_args()


def load_cookie_header() -> str:
    env_path = Path(".env")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("IG_COOKIE_HEADER="):
            return line.split("=", 1)[1]
    return ""


def cookie_dict(cookie_header: str) -> dict[str, str]:
    return {
        key.strip(): value.strip()
        for part in cookie_header.split(";")
        if "=" in part
        for key, value in [part.split("=", 1)]
    }


def post_rows_path(output_dir: Path) -> Path:
    return output_dir / "posts.csv"


def comment_rows_path(output_dir: Path) -> Path:
    return output_dir / "comments.csv"


def error_rows_path(output_dir: Path) -> Path:
    return output_dir / "errors.csv"


def checkpoint_path(output_dir: Path) -> Path:
    return output_dir / "checkpoint_instaloader.json"


def ensure_headers(path: Path, fieldnames: list[str], reset: bool) -> None:
    if reset and path.exists():
        path.unlink()
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()


def append_row(path: Path, fieldnames: list[str], row: dict[str, object]) -> None:
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writerow(row)


def save_checkpoint(output_dir: Path, next_index: int, processed: int) -> None:
    checkpoint_path(output_dir).write_text(
        json.dumps({"next_index": next_index, "processed": processed}, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    urls = payload.get("urls", [])
    if not isinstance(urls, list):
        raise ValueError("tool dump must contain a urls list")

    post_fields = [
        "shortcode",
        "post_url",
        "media_id",
        "date_utc",
        "caption",
        "likes",
        "comments_count_reported",
        "is_video",
        "typename",
        "owner_username",
    ]
    comment_fields = [
        "post_shortcode",
        "id",
        "parent_id",
        "created_at_utc",
        "text",
        "comment_like_count",
        "owner_username",
        "owner_id",
    ]
    error_fields = ["index", "post_url", "shortcode", "stage", "error"]

    ensure_headers(post_rows_path(output_dir), post_fields, args.reset_output)
    ensure_headers(comment_rows_path(output_dir), comment_fields, args.reset_output)
    ensure_headers(error_rows_path(output_dir), error_fields, args.reset_output)

    cookie_header = load_cookie_header()
    cookies = cookie_dict(cookie_header)
    username = cookies.get("ds_user_id", "session")

    loader = Instaloader(
        dirname_pattern=str(output_dir / "downloads" / "{target}"),
        filename_pattern="{shortcode}",
        download_pictures=args.download_media,
        download_videos=args.download_media,
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        sleep=False,
        max_connection_attempts=1,
        request_timeout=20.0,
        rate_controller=FailFastRateController,
    )
    loader.load_session(username, cookies)

    end_index = min(len(urls), args.start_index + args.limit)
    processed = 0
    for index in range(args.start_index, end_index):
        post_url = urls[index]
        if not isinstance(post_url, str):
            continue
        shortcode = post_url.rstrip("/").split("/")[-1]
        try:
            post = Post.from_shortcode(loader.context, shortcode)
            append_row(
                post_rows_path(output_dir),
                post_fields,
                {
                    "shortcode": post.shortcode,
                    "post_url": post_url,
                    "media_id": post.mediaid,
                    "date_utc": post.date_utc.isoformat(),
                    "caption": post.caption or "",
                    "likes": post.likes,
                    "comments_count_reported": post.comments,
                    "is_video": post.is_video,
                    "typename": post.typename,
                    "owner_username": post.owner_username,
                },
            )
            for comment in post.get_comments():
                append_row(
                    comment_rows_path(output_dir),
                    comment_fields,
                    {
                        "post_shortcode": post.shortcode,
                        "id": str(comment.id),
                        "parent_id": "",
                        "created_at_utc": comment.created_at_utc.isoformat(),
                        "text": comment.text or "",
                        "comment_like_count": comment.likes_count,
                        "owner_username": comment.owner.username,
                        "owner_id": str(comment.owner.userid),
                    },
                )
                for answer in comment.answers:
                    append_row(
                        comment_rows_path(output_dir),
                        comment_fields,
                        {
                            "post_shortcode": post.shortcode,
                            "id": str(answer.id),
                            "parent_id": str(comment.id),
                            "created_at_utc": answer.created_at_utc.isoformat(),
                            "text": answer.text or "",
                            "comment_like_count": answer.likes_count,
                            "owner_username": answer.owner.username,
                            "owner_id": str(answer.owner.userid),
                        },
                    )
            if args.download_media:
                loader.download_post(post, target=post.owner_username)
            processed += 1
        except (BadResponseException, TooManyRequestsException, KeyError, ValueError) as exc:
            append_row(
                error_rows_path(output_dir),
                error_fields,
                {
                    "index": index,
                    "post_url": post_url,
                    "shortcode": shortcode,
                    "stage": "extract_post",
                    "error": type(exc).__name__,
                },
            )
        save_checkpoint(output_dir, index + 1, processed)

    print(
        json.dumps(
            {
                "start_index": args.start_index,
                "end_index_exclusive": end_index,
                "processed": processed,
                "checkpoint": str(checkpoint_path(output_dir)),
                "posts_csv": str(post_rows_path(output_dir)),
                "comments_csv": str(comment_rows_path(output_dir)),
                "errors_csv": str(error_rows_path(output_dir)),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
