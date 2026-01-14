from apify_client import ApifyClient
from typing import List, Dict
import time

class FacebookScraper:
    def __init__(self, api_key: str):
        self.client = ApifyClient(api_key)
    
    def extract_image_urls(item: dict) -> list[str]:
        urls: list[str] = []

        for att in item.get("attachments", []) or []:
            if not isinstance(att, dict):
                continue

            # Najpewniejsze: direct CDN image
            photo_img = att.get("photo_image")
            if isinstance(photo_img, dict) and isinstance(photo_img.get("uri"), str):
                urls.append(photo_img["uri"])

            # Czasem tylko thumbnail
            if isinstance(att.get("thumbnail"), str):
                urls.append(att["thumbnail"])

            # Uwaga: att.get("url") to często STRONA FB -> pomijamy
            # if isinstance(att.get("url"), str): ...

        # dedupe
        return list(dict.fromkeys(urls))    
    def scrape_group_posts(self, group_url: str, max_posts: int = 50) -> List[Dict]:
   
        print(f"🔍 Scrapuję grupę: {group_url}")
        
        # Oblicz datę sprzed 2 dni w formacie ISO
        from datetime import datetime, timedelta
        import json
        
        two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        
        run_input = {
            "startUrls": [{"url": group_url}],
            "resultsLimit": max_posts,
            "onlyPostsNewerThan": two_days_ago,
            "proxyConfiguration": {"useApifyProxy": True},  # Dodane proxy
        }
        
        try:
            # Uruchom scraper Apify
            run = self.client.actor("apify/facebook-groups-scraper").call(run_input=run_input)
            
            # Pobierz wyniki - ZBIERAMY NAJPIERW DO LISTY
            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
            
            # ===== DEBUG: POKAŻ STRUKTURĘ PIERWSZEGO POSTA =====
            if items:
                print("\n" + "="*60)
                print("🔍 DEBUG: Klucze w pierwszym poście:")
                print(list(items[0].keys()))
                print("\n🔍 DEBUG: Pierwszy post (pierwsze 3000 znaków):")
                print(json.dumps(items[0], indent=2, ensure_ascii=False)[:3000])
                print("="*60 + "\n")
            else:
                print("⚠️  Brak postów w datasecie!")
            # ===== KONIEC DEBUG =====
            
            # Teraz mapujemy do naszego formatu
            posts = []
            for item in items:
                # Wyciąganie obrazków - sprawdzamy różne warianty
                images = []
                
                # Wariant 1: pole "images" (lista stringów)
                if item.get('images'):
                    images.extend(item['images'])
                
                # Wariant 2: pole "attachments" lub "media"
                attachments = item.get('attachments', []) or item.get('media', [])
                for att in attachments:
                    if isinstance(att, dict):
                        # Szukamy URL obrazka w różnych miejscach
                        if att.get('image', {}).get('uri'):
                            images.append(att['image']['uri'])
                        elif att.get('url'):
                            images.append(att['url'])
                
                # Wariant 3: pojedyncze pole "image"
                if item.get('image'):
                    if isinstance(item['image'], str):
                        images.append(item['image'])
                    elif isinstance(item['image'], dict) and item['image'].get('uri'):
                        images.append(item['image']['uri'])
                
                posts.append({
                    "post_id": item.get("legacyId") or item.get("id"),
                    "post_url": item.get("url"),
                    "text": item.get("text", ""),
                    "images": extract_image_urls(item),
                    "author": (item.get("user") or {}).get("name"),
                    "timestamp": item.get("time"),
                    "comments_count": item.get("commentsCount", 0),
                })
            
            print(f"✅ Znaleziono {len(posts)} postów")
            return posts
            
        except Exception as e:
            print(f"❌ Błąd scrapowania: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    
    def filter_posts_with_screenshots(self, posts: List[Dict]) -> List[Dict]:
        """
        Filtruje posty które zawierają screenshoty (obrazki)
        """
        filtered = [post for post in posts if post.get('images')]
        print(f"📸 Posty ze screenshotami: {len(filtered)}/{len(posts)}")
        return filtered
    