import requests
from typing import Dict, Optional
from urllib.parse import quote
import io


class TrustCheckAPI:
    def __init__(self, api_url: str, bot_token: str):
        self.api_url = api_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {bot_token}",
        }
        self.headers_json = {**self.headers, "Content-Type": "application/json"}

    def submit_report(self, report_data: Dict) -> bool:
        endpoint = f"{self.api_url}/reports"
        try:
            response = requests.post(
                endpoint,
                json=report_data,
                headers=self.headers_json,
                timeout=20
            )

            if response.status_code in (200, 201):
                print(f"✅ Zgłoszenie dodane: {report_data.get('targetValue')}")
                return True

            print(f"❌ Błąd API ({response.status_code}): {response.text}")
            return False
        except Exception as e:
            print(f"❌ Błąd połączenia z API: {str(e)}")
            return False

    def upload_screenshot(self, file_content: bytes, original_url: str) -> Optional[str]:
        """
        Uploaduje screenshot na backend i zwraca ścieżkę.
        """
        endpoint = f"{self.api_url}/reports/upload-screenshot"

        try:
            # Przygotuj multipart form
            files = {
                "file": ("screenshot.jpg", io.BytesIO(file_content), "image/jpeg")
            }

            # Uploaduj (bez Authorization header w headers_json, bo to multipart)
            response = requests.post(
                endpoint,
                files=files,
                headers={"Authorization": f"Bearer {self.headers['Authorization'].split(' ')[1]}"},
                timeout=30
            )

            if response.status_code in (200, 201):
                data = response.json()
                return data.get("path")  # Backend zwraca {"path": "uploads/..."}
            else:
                print(f"⚠️  Backend odrzucił upload ({response.status_code})")
                return None

        except Exception as e:
            print(f"⚠️  Błąd uploadowania: {str(e)}")
            return None

    def check_if_exists(self, target_value: str) -> bool:
        """
        Sprawdza czy dane już istnieją w bazie.
        """
        safe = quote(target_value, safe="")
        endpoint = f"{self.api_url}/verification/search/{safe}"

        try:
            response = requests.get(
                endpoint,
                headers=self.headers_json,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("community", {}).get("totalReports", 0) > 0
            return False
        except Exception:
            return False
