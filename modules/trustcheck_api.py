import requests
from typing import Dict, Optional

class TrustCheckAPI:
    def __init__(self, api_url: str, bot_token: str):
        self.api_url = api_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {bot_token}',
            'Content-Type': 'application/json'
        }
    
    def submit_report(self, report_data: Dict) -> bool:
        """
        Wysyła zgłoszenie oszustwa do TrustCheck API
        """
        endpoint = f"{self.api_url}/reports"
        
        try:
            response = requests.post(
                endpoint,
                json=report_data,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 201:
                print(f"✅ Zgłoszenie dodane: {report_data.get('targetValue')}")
                return True
            else:
                print(f"❌ Błąd API ({response.status_code}): {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Błąd połączenia z API: {str(e)}")
            return False
    
    def check_if_exists(self, target_value: str, target_type: str) -> bool:
        """
        Sprawdza czy dane już istnieją w bazie (aby uniknąć duplikatów)
        """
        endpoint = f"{self.api_url}/verification/search/{target_value}"
        
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Jeśli już są zgłoszenia, nie dodawaj ponownie
                return data.get('community', {}).get('totalReports', 0) > 0
            return False
        except:
            return False
