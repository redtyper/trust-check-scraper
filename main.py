#!/usr/bin/env python3
"""
TrustCheck Scraper Bot
Automatycznie wykrywa oszustwa z grup Facebook i dodaje do bazy
"""

import time
import requests
from datetime import datetime
from config import Config
from modules.facebook_scraper import FacebookScraper
from modules.vision_processor import VisionProcessor
from modules.trustcheck_api import TrustCheckAPI


def map_scam_type_to_reason(scam_desc: str) -> str:
    """Mapuje opis oszustwa na kategorię w TrustCheck"""
    desc_lower = (scam_desc or "").lower()

    if any(word in desc_lower for word in ["wyłudzenie", "oszustwo", "scam", "przekręt"]):
        return "SCAM"
    elif any(word in desc_lower for word in ["spam", "reklama", "telemarketing"]):
        return "SPAM"
    elif any(word in desc_lower for word in ["towar", "nie wysłał", "nie otrzymał"]):
        return "TOWAR"
    else:
        return "SCAM"


def calculate_rating(confidence: str) -> int:
    """Oblicza rating na podstawie confidence"""
    mapping = {
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return mapping.get((confidence or "medium").lower(), 2)


def download_and_upload_screenshot(image_url: str, post_id: str, idx: int, api: TrustCheckAPI) -> str:
    """
    Pobiera screenshot z FB i uploaduje na backend.
    Zwraca ścieżkę do pliku na backendzie lub None.
    """
    try:
        # 1. Pobierz obrazek z FB
        print(f"   ⬇️  Pobieranie screenshot...")
        r = requests.get(image_url, timeout=20)
        r.raise_for_status()

        # 2. Sprawdź Content-Type
        ct = (r.headers.get("Content-Type") or "").lower()
        if not ct.startswith("image/"):
            print(f"   ⚠️  Nie jest obrazkiem (Content-Type={ct})")
            return None

        # 3. Uploaduj na backend
        print(f"   📤 Wysyłam na backend...")
        backend_path = api.upload_screenshot(r.content, image_url)

        if backend_path:
            print(f"   ✅ Zapisano: {backend_path}")
            return backend_path
        else:
            print(f"   ⚠️  Backend odrzucił plik")
            return None

    except Exception as e:
        print(f"   ❌ Błąd: {str(e)}")
        return None


def process_post(post: dict, vision: VisionProcessor, api: TrustCheckAPI) -> bool:
    """
    Przetwarza pojedynczy post i dodaje zgłoszenia.
    """
    print(f"\n{'='*60}")
    print(f"📄 Post: {post.get('post_url')}")
    print(f"👤 Autor: {post.get('author')}")

    # Analiza tekstu posta (szybka prefiltracja)
    text_analysis = vision.analyze_post_text(post.get("text", ""))
    if not text_analysis.get("is_scam_report", True):
        print("⏭️  Pomijam - nie wygląda na zgłoszenie oszustwa")
        return False

    images = post.get("images") or []
    for idx, img_url in enumerate(images[:3]):
        print(f"🖼️  Analizuję: {img_url[:80]}...")

        # Ekstrakcja danych z obrazka
        extracted = vision.analyze_screenshot(img_url)
        if not extracted:
            print("⚠️  Nie udało się wyodrębnić danych")
            continue

        print("📊 Wyodrębnione dane:")
        print(f"   Imię: {extracted.get('scammer_name')}")
        print(f"   Telefon: {extracted.get('phone_number')}")
        print(f"   Konto: {extracted.get('bank_account')}")
        print(f"   Email: {extracted.get('email')}")
        print(f"   Confidence: {extracted.get('confidence')}")

        # ===== LOGIKA WYBORU TYPU ZGŁOSZENIA =====
        phone = extracted.get("phone_number")
        name = extracted.get("scammer_name")
        email = extracted.get("email")
        bank_account = extracted.get("bank_account")

        target_type = None
        target_value = None

        # Priorytet: telefon > email > nazwa > IBAN
        if phone:
            target_type = "PHONE"
            target_value = phone
        elif email:
            # Jeśli jest email, ale nie ma telefonu, wysyłamy jako PERSON
            target_type = "PERSON"
            target_value = email
        elif name:
            target_type = "PERSON"
            target_value = name
        elif bank_account:
            target_type = "BANK_ACCOUNT"
            target_value = bank_account
        
        if not target_type or not target_value:
            print("⏭️  Pomijam - brak identyfikujących danych")
            continue

        # Sprawdź duplikaty
        if api.check_if_exists(target_value):
            print(f"⏭️  Pomijam - {target_value} już jest w bazie")
            continue

        # ===== UPLOAD SCREENSHOTU =====
        screenshot_path = None
        if img_url:
            screenshot_path = download_and_upload_screenshot(
                img_url, post.get("post_id"), idx, api
            )

        # ===== PRZYGOTUJ DANE ZGŁOSZENIA =====
        report_data = {
            "targetType": target_type,
            "targetValue": target_value,
            "rating": calculate_rating(extracted.get("confidence", "medium")),
            "reason": map_scam_type_to_reason(extracted.get("scam_description", "")),
            "comment": extracted.get("scam_description", "Oszustwo zgłoszone przez społeczność"),
            
            # Dane OSINT
            "reportedEmail": email,
            "facebookLink": extracted.get("facebook_link"),
            "screenshotUrl": img_url,  # Oryginał z FB (dla referencji)
            "screenshotPath": screenshot_path,  # Ścieżka po uploadzie
            
            # Dane oszusta
            "scammerName": name,
            "bankAccount": bank_account,
            
            # Metadane
            "isAutoGenerated": True,
            "sourceUrl": post.get("post_url"),
        }

        # Wyślij do TrustCheck
        success = api.submit_report(report_data)

        if success:
            print(f"✅ DODANO ZGŁOSZENIE!")
            return True

    return False


def main():
    """Główna pętla scrapera"""
    print(
        """
╔══════════════════════════════════════════════════════╗
║      TrustCheck Auto-Scraper v2.0                    ║
║      Automatyczne wykrywanie oszustw + Upload        ║
╚══════════════════════════════════════════════════════╝
"""
    )

    # Walidacja konfiguracji
    if not Config.APIFY_API_KEY:
        raise RuntimeError("❌ Brak APIFY_API_KEY w .env")
    if not Config.OPENAI_API_KEY:
        raise RuntimeError("❌ Brak OPENAI_API_KEY w .env")
    if not Config.TRUSTCHECK_BOT_TOKEN:
        raise RuntimeError("❌ Brak TRUSTCHECK_BOT_TOKEN w .env")

    # Inicjalizacja modułów
    print("🔧 Inicjalizacja...")
    fb_scraper = FacebookScraper(Config.APIFY_API_KEY)
    vision = VisionProcessor(Config.OPENAI_API_KEY, model=Config.OPENAI_MODEL)
    api = TrustCheckAPI(Config.TRUSTCHECK_API_URL, Config.TRUSTCHECK_BOT_TOKEN)

    print("✅ Gotowe!\n")

    # Główna pętla
    while True:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🕐 [{timestamp}] Rozpoczynam skanowanie...")

            # 1. Scrapuj posty z Facebooka
            posts = fb_scraper.scrape_group_posts(
                Config.FACEBOOK_GROUP_URL,
                max_posts=Config.MAX_POSTS_PER_RUN,
                days_back=Config.ONLY_POSTS_DAYS_BACK,
            )

            # 2. Filtruj posty ze screenshotami
            posts_with_images = fb_scraper.filter_posts_with_screenshots(posts)

            # 3. Przetwarzaj każdy post
            processed = 0
            added = 0

            for post in posts_with_images:
                success = process_post(post, vision, api)
                processed += 1
                if success:
                    added += 1

                # Pauza między requestami (aby nie przekroczyć limitów API)
                time.sleep(3)

            print(f"\n{'='*60}")
            print("📊 PODSUMOWANIE:")
            print(f"   Przetworzono: {processed} postów")
            print(f"   Dodano zgłoszeń: {added}")
            print(f"   Następne skanowanie za {Config.CHECK_INTERVAL_HOURS}h")
            print(f"{'='*60}\n")

            # Czekaj do następnego cyklu
            time.sleep(Config.CHECK_INTERVAL_HOURS * 3600)

        except KeyboardInterrupt:
            print("\n\n👋 Zatrzymano scraper. Do zobaczenia!")
            break
        except Exception as e:
            print(f"\n❌ Błąd krytyczny: {str(e)}")
            import traceback
            traceback.print_exc()
            print("⏸️  Czekam 5 minut przed ponowną próbą...")
            time.sleep(300)


if __name__ == "__main__":
    main()
