**New Instagram Scraper**


### Final Requirements

- Input: Instagram username + limit (e.g. `--limit 10`)
- Scrapes the **10 most recent posts** (photos + reels mixed, newest first)
- For **each post/reel**, creates its own folder with:
  - The media file (`media.jpg` or `media.mp4`)
  - `comments.csv` (username, comment text, timestamp)
  - `likes.csv` (usernames of likers)
- Very simple CLI: `instagram-scraper <username> --limit 10`

---

### Project Structure

```bash
instagram-scraper/
├── pyproject.toml
├── src/
│   └── instagram_scraper/
│       ├── __init__.py
│       ├── main.py
│       └── scraper.py
└── data/                     # ← output goes here
```

---

### 1. `pyproject.toml`

```toml
[project]
name = "instagram-scraper"
version = "0.1.0"
description = "Instagram profile scraper - posts, reels, comments, likes + media download"
requires-python = ">=3.10"
dependencies = [
    "instaloader>=4.10",
    "typer>=0.9",
    "pandas>=2.0",
]

[project.scripts]
instagram-scraper = "instagram_scraper.main:app"
```

---

### 2. `src/instagram_scraper/scraper.py`

```python
from pathlib import Path
import pandas as pd
import instaloader
from datetime import datetime
from typing import Optional


def sanitize_folder_name(name: str) -> str:
    """Clean folder name."""
    invalid = '<>:"/\\|?*'
    for char in invalid:
        name = name.replace(char, '_')
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
        download_comments=False,   # We'll handle comments ourselves
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
        
        print(f"  [{count+1}/{limit}] Downloading {post_type} {shortcode}...")
        
        # Download media directly into the post folder
        L.download_post(post, target=folder_name)
        
        # Rename media file to simple name
        media_files = list(post_dir.glob("*.mp4")) + list(post_dir.glob("*.jpg")) + list(post_dir.glob("*.jpeg"))
        if media_files:
            media_file = media_files[0]
            new_name = "media.mp4" if media_file.suffix == ".mp4" else "media.jpg"
            media_file.rename(post_dir / new_name)
        
        # === Comments ===
        comments_data = []
        try:
            for comment in post.get_comments():
                comments_data.append({
                    "username": comment.owner.username,
                    "comment_text": comment.text,
                    "timestamp": comment.created_utc.strftime("%Y-%m-%d %H:%M:%S"),
                    "likes": comment.likes_count,
                })
        except Exception as e:
            print(f"    Warning: Could not fetch all comments: {e}")
        
        if comments_data:
            pd.DataFrame(comments_data).to_csv(post_dir / "comments.csv", index=False)
        else:
            pd.DataFrame(columns=["username", "comment_text", "timestamp", "likes"]).to_csv(
                post_dir / "comments.csv", index=False
            )
        
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
            pd.DataFrame(columns=["username"]).to_csv(post_dir / "likes.csv", index=False)
        
        count += 1
    
    print(f"\n✅ Done! Scraped {count} posts/reels.")
    print(f"Output folder: {output_dir.resolve()}")
```

---

### 3. `src/instagram_scraper/main.py`

```python
import typer
from pathlib import Path
from .scraper import scrape_profile

app = typer.Typer(help="Instagram Profile Scraper")


@app.command()
def scrape(
    username: str = typer.Argument(..., help="Instagram username (without @)"),
    limit: int = typer.Option(10, help="Number of most recent posts/reels to scrape"),
    output: Path = typer.Option(None, help="Custom output directory"),
):
    """Scrape recent posts/reels with media, comments, and likes."""
    scrape_profile(username, limit, output)


if __name__ == "__main__":
    app()
```

---

### How to Install & Use

```bash
# 1. Create project and install
cd instagram-scraper
pip install -e .

# 2. Run it
instagram-scraper natgeo --limit 5
```

**Output structure:**

```
data/
└── natgeo/
    ├── post_ABC1234567/
    │   ├── media.jpg
    │   ├── comments.csv
    │   └── likes.csv
    ├── reel_DEF9876543/
    │   ├── media.mp4
    │   ├── comments.csv
    │   └── likes.csv
    └── ...
```

---

### Important Reality Check

- **Likes**: Instagram only allows a limited number of likers to be fetched (often < 50 per post, even on big accounts). This is not a library limitation — it's Instagram's restriction.
- **Comments**: Usually works well.
- **Reels**: Treated the same as video posts.

____

possible next steps:

1. Optional login support (for private accounts or more likes)
2. A progress bar
3. Option to skip likes entirely
4. A simple GUI version

