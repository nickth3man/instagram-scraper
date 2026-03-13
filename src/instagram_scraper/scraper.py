from pathlib import Path
import pandas as pd
import instaloader
from datetime import datetime
from typing import Optional


def sanitize_folder_name(name: str) -> str:
    """Clean folder name."""
    invalid = '<>:"/\\|?*'
    for char in invalid:
        name = name.replace(char, "_")
    return name.strip()[:50]


def scrape_profile(username: str, limit: int = 10, output_dir: Optional[Path] = None):
    if output_dir is None:
        output_dir = Path("data") / username
    output_dir.mkdir(parents=True, exist_ok=True)

    L = instaloader.Instaloader(
        dirname_pattern=str(output_dir / "{target}"),
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,  # We'll handle comments ourselves
        save_metadata=False,
        compress_json=False,
    )

    print(f"Fetching profile @{username}...")
    profile = instaloader.Profile.from_username(L.context, username)

    print(f"Scraping up to {limit} most recent posts/reels...")
    count = 0

    for post in profile.get_posts():
        if count >= limit:
            break

        shortcode = post.shortcode
        is_reel = post.is_video and post.video_url and "reel" in str(post.url).lower()
        post_type = "reel" if is_reel else "post"

        folder_name = f"{post_type}_{shortcode}"
        post_dir = output_dir / folder_name
        post_dir.mkdir(exist_ok=True)

        print(f"  [{count + 1}/{limit}] Downloading {post_type} {shortcode}...")

        # Download media directly into the post folder
        L.download_post(post, target=folder_name)

        # Rename media file to simple name
        media_files = (
            list(post_dir.glob("*.mp4"))
            + list(post_dir.glob("*.jpg"))
            + list(post_dir.glob("*.jpeg"))
        )
        if media_files:
            media_file = media_files[0]
            new_name = "media.mp4" if media_file.suffix == ".mp4" else "media.jpg"
            media_file.rename(post_dir / new_name)

        # === Comments ===
        comments_data = []
        try:
            for comment in post.get_comments():
                comments_data.append(
                    {
                        "username": comment.owner.username,
                        "comment_text": comment.text,
                        "timestamp": comment.created_utc.strftime("%Y-%m-%d %H:%M:%S"),
                        "likes": comment.likes_count,
                    }
                )
        except Exception as e:
            print(f"    Warning: Could not fetch all comments: {e}")

        if comments_data:
            pd.DataFrame(comments_data).to_csv(post_dir / "comments.csv", index=False)
        else:
            pd.DataFrame(
                columns=["username", "comment_text", "timestamp", "likes"]
            ).to_csv(post_dir / "comments.csv", index=False)

        # === Likes ===
        likes_data = []
        try:
            likes = list(post.get_likes())  # Note: Instagram heavily limits this
            for liker in likes[:100]:  # Safety limit
                likes_data.append({"username": liker.username})
        except Exception as e:
            print(f"    Warning: Could not fetch likes (common limitation): {e}")

        if likes_data:
            pd.DataFrame(likes_data).to_csv(post_dir / "likes.csv", index=False)
        else:
            pd.DataFrame(columns=["username"]).to_csv(
                post_dir / "likes.csv", index=False
            )

        count += 1

    print(f"\n✅ Done! Scraped {count} posts/reels.")
    print(f"Output folder: {output_dir.resolve()}")
