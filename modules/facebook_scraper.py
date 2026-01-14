from apify_client import ApifyClient
from typing import List, Dict
from datetime import datetime, timedelta
import json


class FacebookScraper:
    def __init__(self, api_key: str):
        self.client = ApifyClient(api_key)

    def _extract_image_urls(self, item: dict) -> list[str]:
        """
        Zwraca TYLKO bezpośrednie URL-e obrazów (CDN, zwykle scontent...).
        Nie zwracamy linków do stron FB typu photo.php.
        """
        urls: list[str] = []

        attachments = item.get("attachments") or []
        if isinstance(attachments, list):
            for att in attachments:
                if not isinstance(att, dict):
                    continue

                # Najczęstsze w tym actorze: photo_image.uri
                photo_img = att.get("photo_image")
                if isinstance(photo_img, dict) and isinstance(photo_img.get("uri"), str):
                    urls.append(photo_img["uri"])

                # Backup: thumbnail
                if isinstance(att.get("thumbnail"), str):
                    urls.append(att["thumbnail"])

                # Czasem może być "image": {"uri": "..."}
                img = att.get("image")
                if isinstance(img, dict) and isinstance(img.get("uri"), str):
                    urls.append(img["uri"])

        # Dedupe
        return list(dict.fromkeys(urls))

    def scrape_group_posts(self, group_url: str, max_posts: int = 50, days_back: int = 2) -> List[Dict]:
        print(f"🔍 Scrapuję grupę: {group_url}")

        only_posts_newer_than = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        run_input = {
            "startUrls": [{"url": group_url}],
            "resultsLimit": max_posts,
            "onlyPostsNewerThan": only_posts_newer_than,
            "proxyConfiguration": {"useApifyProxy": True},
        }

        try:
            run = self.client.actor("apify/facebook-groups-scraper").call(run_input=run_input)

            items: list[dict] = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)

            # DEBUG (opcjonalne)
            if items:
                print("\n" + "=" * 60)
                print("🔍 DEBUG: Klucze w pierwszym poście:")
                print(list(items[0].keys()))
                print("\n🔍 DEBUG: Pierwszy post (pierwsze 2000 znaków):")
                print(json.dumps(items[0], indent=2, ensure_ascii=False)[:2000])
                print("=" * 60 + "\n")

            posts: list[dict] = []
            for item in items:
                posts.append(
                    {
                        "post_id": item.get("legacyId") or item.get("id"),
                        "post_url": item.get("url"),
                        "text": item.get("text", "") or "",
                        "images": self._extract_image_urls(item),
                        "author": (item.get("user") or {}).get("name"),
                        "timestamp": item.get("time"),
                        "comments_count": item.get("commentsCount", 0),
                    }
                )

            print(f"✅ Znaleziono {len(posts)} postów")
            return posts

        except Exception as e:
            print(f"❌ Błąd scrapowania: {str(e)}")
            import traceback

            traceback.print_exc()
            return []

    def filter_posts_with_screenshots(self, posts: List[Dict]) -> List[Dict]:
        filtered = [post for post in posts if isinstance(post.get("images"), list) and len(post["images"]) > 0]
        print(f"📸 Posty ze screenshotami: {len(filtered)}/{len(posts)}")
        return filtered
