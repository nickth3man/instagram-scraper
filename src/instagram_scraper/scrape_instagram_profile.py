import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import instaloader
from instaloader import Profile
from instaloader.exceptions import InstaloaderException


def comment_to_dict(comment, parent_id=None):
    owner = getattr(comment, "owner", None)
    owner_username = getattr(owner, "username", None)
    owner_id = getattr(owner, "userid", None)
    created_at = getattr(comment, "created_at_utc", None)
    if created_at is not None:
        created_at = created_at.isoformat()

    return {
        "id": str(getattr(comment, "id", "")),
        "parent_id": str(parent_id) if parent_id is not None else None,
        "created_at_utc": created_at,
        "text": getattr(comment, "text", None),
        "likes_count": getattr(comment, "likes_count", None),
        "owner_username": owner_username,
        "owner_id": str(owner_id) if owner_id is not None else None,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--username", required=True, help="Instagram username to scrape"
    )
    args = parser.parse_args()

    target_username = args.username
    started_at = datetime.now(timezone.utc)

    output_dir = Path("data") / target_username
    output_dir.mkdir(parents=True, exist_ok=True)

    loader = instaloader.Instaloader(
        dirname_pattern="{target}",
        filename_pattern="{shortcode}",
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
        compress_json=False,
        quiet=True,
    )

    profile = Profile.from_username(loader.context, target_username)

    all_posts = []
    flat_comments = []
    extraction_errors = []

    for post in profile.get_posts():
        post_data = {
            "shortcode": post.shortcode,
            "post_url": f"https://www.instagram.com/p/{post.shortcode}/",
            "date_utc": post.date_utc.isoformat(),
            "caption": post.caption,
            "likes": post.likes,
            "comments_count_reported": post.comments,
            "is_video": post.is_video,
            "typename": post.typename,
            "owner_username": target_username,
            "comments": [],
        }

        comment_extraction_success = False
        try:
            for comment in post.get_comments():
                base_comment = comment_to_dict(comment)
                base_comment["post_shortcode"] = post.shortcode
                post_data["comments"].append(base_comment)
                flat_comments.append(base_comment)

                answers = list(getattr(comment, "answers", []))
                for answer in answers:
                    reply = comment_to_dict(answer, parent_id=comment.id)
                    reply["post_shortcode"] = post.shortcode
                    post_data["comments"].append(reply)
                    flat_comments.append(reply)
            comment_extraction_success = True
        except InstaloaderException as exc:
            extraction_errors.append(
                {
                    "post_shortcode": post.shortcode,
                    "error": str(exc),
                }
            )

        # Only add post if comment extraction succeeded or post has no comments
        if comment_extraction_success or post.comments == 0:
            all_posts.append(post_data)

    finished_at = datetime.now(timezone.utc)
    dataset = {
        "target_profile": target_username,
        "source_url": f"https://www.instagram.com/{target_username}/?hl=en",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "posts_total": len(all_posts),
        "comments_total": len(flat_comments),
        "errors_count": len(extraction_errors),
        "posts": all_posts,
    }

    (output_dir / "instagram_dataset.json").write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    posts_csv_path = output_dir / "posts.csv"
    with posts_csv_path.open("w", newline="", encoding="utf-8") as posts_file:
        writer = csv.DictWriter(
            posts_file,
            fieldnames=[
                "shortcode",
                "post_url",
                "date_utc",
                "caption",
                "likes",
                "comments_count_reported",
                "is_video",
                "typename",
                "owner_username",
            ],
        )
        writer.writeheader()
        for post in all_posts:
            row = {
                key: post[key]
                for key in [
                    "shortcode",
                    "post_url",
                    "date_utc",
                    "caption",
                    "likes",
                    "comments_count_reported",
                    "is_video",
                    "typename",
                    "owner_username",
                ]
            }
            writer.writerow(row)

    comments_csv_path = output_dir / "comments.csv"
    with comments_csv_path.open("w", newline="", encoding="utf-8") as comments_file:
        writer = csv.DictWriter(
            comments_file,
            fieldnames=[
                "post_shortcode",
                "id",
                "parent_id",
                "created_at_utc",
                "text",
                "likes_count",
                "owner_username",
                "owner_id",
            ],
        )
        writer.writeheader()
        for comment in flat_comments:
            writer.writerow(comment)

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "profile": target_username,
                "posts_extracted": len(all_posts),
                "comments_extracted": len(flat_comments),
                "errors_count": len(extraction_errors),
                "generated_at_utc": finished_at.isoformat(),
                "files": {
                    "dataset_json": str(output_dir / "instagram_dataset.json"),
                    "posts_csv": str(posts_csv_path),
                    "comments_csv": str(comments_csv_path),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "posts": len(all_posts),
                "comments": len(flat_comments),
                "errors": len(extraction_errors),
            }
        )
    )


if __name__ == "__main__":
    main()
