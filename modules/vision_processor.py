import base64
import re
from typing import Dict, Optional, List
from openai import OpenAI
from PIL import Image
import io
import requests

class VisionProcessor:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        
    def analyze_screenshot(self, image_url: str) -> Optional[Dict]:
        """
        Analizuje screenshot z Messengera/WhatsApp/OLX używając GPT-4 Vision
        i wyodrębnia dane oszusta
        """
        try:
            # Pobierz obraz
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Konwertuj do base64
            base64_image = base64.b64encode(response.content).decode('utf-8')
            
            # Przygotuj prompt dla GPT-4 Vision
            prompt = """
Przeanalizuj ten screenshot rozmowy i wyodrębnij następujące informacje o oszuście:

1. **Imię i nazwisko oszusta** (jeśli widoczne w nagłówku lub treści)
2. **Numer telefonu** (w formacie +48... lub 48... lub lokalnym)
3. **Numer konta bankowego** (IBAN, zazwyczaj zaczyna się od PL, 26 cyfr)
4. **Email** (jeśli jest widoczny)
5. **Link do profilu Facebook** (jeśli widoczny)
6. **Opis oszustwa** (krótkie podsumowanie o co chodziło)

WAŻNE:
- Jeśli jakieś dane NIE SĄ widoczne, zwróć null dla tego pola
- Numery telefonów zapisz w formacie międzynarodowym (+48...)
- IBAN musi mieć dokładnie 26 cyfr po PL

Zwróć TYLKO JSON w formacie:
{
  "scammer_name": "string lub null",
  "phone_number": "string lub null",
  "bank_account": "string lub null",
  "email": "string lub null",
  "facebook_link": "string lub null",
  "scam_description": "string opisujący oszustwo",
  "confidence": "high/medium/low",
  "screenshot_type": "messenger/whatsapp/olx/sms/other"
}
"""
            
            # Wywołaj GPT-4 Vision API
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"  # Wysoka jakość analizy
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1  # Niska temperatura dla precyzji
            )
            
            # Wyciągnij JSON z odpowiedzi
            content = response.choices[0].message.content
            
            # Parsuj JSON (GPT-4 czasami otacza go markdown)
            import json
            if "```json" in content:
                content = content.split("```json").split("```").strip()[1]
            elif "```" in content:
                content = content.split("```")[19].split("```")[0].strip()
            
            data = json.loads(content)
            
            # Walidacja i czyszczenie danych
            validated_data = self._validate_extracted_data(data)
            
            return validated_data
            
        except Exception as e:
            print(f"❌ Błąd analizy obrazu: {str(e)}")
            return None
    
    def _validate_extracted_data(self, data: Dict) -> Optional[Dict]:
        """Waliduje i normalizuje wyodrębnione dane"""
        
        # Walidacja numeru telefonu
        if data.get('phone_number'):
            phone = self._normalize_phone(data['phone_number'])
            if not phone:
                data['phone_number'] = None
            else:
                data['phone_number'] = phone
        
        # Walidacja IBAN
        if data.get('bank_account'):
            iban = self._validate_iban(data['bank_account'])
            if not iban:
                data['bank_account'] = None
            else:
                data['bank_account'] = iban
        
        # Walidacja email
        if data.get('email'):
            if not self._validate_email(data['email']):
                data['email'] = None
        
        # Sprawdź czy są jakiekolwiek użyteczne dane
        has_useful_data = any([
            data.get('scammer_name'),
            data.get('phone_number'),
            data.get('bank_account'),
            data.get('email')
        ])
        
        if not has_useful_data:
            return None
        
        return data
    
    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Normalizuje numer telefonu do formatu +48..."""
        # Usuń wszystko oprócz cyfr i plusa
        clean = re.sub(r'[^\d+]', '', phone)
        
        # Dodaj +48 jeśli brak
        if not clean.startswith('+'):
            if clean.startswith('48'):
                clean = '+' + clean
            elif len(clean) == 9:  # Polski numer lokalny
                clean = '+48' + clean
            else:
                return None
        
        # Walidacja: +48 + 9 cyfr
        if re.match(r'^\+48\d{9}$', clean):
            return clean
        
        return None
    
    def _validate_iban(self, iban: str) -> Optional[str]:
        """Waliduje i normalizuje IBAN"""
        # Usuń spacje
        clean = iban.replace(' ', '').upper()
        
        # Polski IBAN: PL + 26 cyfr
        if re.match(r'^PL\d{26}$', clean):
            return clean
        
        return None
    
    def _validate_email(self, email: str) -> bool:
        """Waliduje email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def analyze_post_text(self, post_text: str) -> Dict:
        """
        Analizuje tekst posta bez obrazka, aby ocenić czy warto go procesować
        """
        prompt = f"""
Przeanalizuj ten post z grupy o oszustwach i oceń czy zawiera użyteczne informacje:

{post_text}

Zwróć JSON:
{{
  "is_scam_report": true/false,
  "has_contact_info": true/false,
  "priority": "high/medium/low"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Tańszy model dla prostej analizy tekstu
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0
            )
            
            content = response.choices[0].message.content
            import json
            if "```json" in content:
                content = content.split("```json").split("```").strip()[1]
            
            return json.loads(content)
        except:
            return {"is_scam_report": True, "has_contact_info": False, "priority": "low"}
