import base64
import json
import re
from typing import Dict, Optional, Any
import requests
from openai import OpenAI


class VisionProcessor:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def _content_to_text(self, content: Any) -> str:
        """
        OpenAI SDK potrafi zwrócić message.content jako:
        - string
        - listę “parts” (dict/str)
        """
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            out = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    out.append(part["text"])
                elif isinstance(part, str):
                    out.append(part)
            return "".join(out)

        return str(content)

    def _extract_json_from_text(self, text: str) -> dict:
   
        original_text = text
        
        # Usuń markdown backticks
        if "```json" in text:
            try:
                # Wyciągnij między ```json a ```
                text = text.split("```json").split("```").strip()[1]
            except (IndexError, AttributeError):
                pass
        
        elif "```" in text:
            try:
                # Wyciągnij między ``` a ```
                parts = text.split("```")
                if len(parts) >= 3:
                    text = parts.strip()
            except (IndexError, AttributeError):
                pass
        
        # Jeśli nadal nie wygląda na JSON, szukaj od { do }
        if not text.lstrip().startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]
        
        # Parse
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"⚠️  Nie udało się sparsować JSON: {str(e)[:100]}")
            print(f"   Tekst: {text[:200]}")
            raise

    def analyze_screenshot(self, image_url: str) -> Optional[Dict]:
        try:
            # Pobierz obraz
            r = requests.get(image_url, timeout=20)
            r.raise_for_status()

            ct = (r.headers.get("Content-Type") or "").lower()
            if not ct.startswith("image/"):
                print(f"⚠️  URL nie zwrócił obrazu (Content-Type={ct})")
                return None

            # Ustal mime (np. image/jpeg, image/png, image/webp)
            mime = ct.split(";", 1)[0].strip()
            if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                # i tak spróbujemy jako jpeg (czasem serwery źle ustawiają nagłówki)
                mime = "image/jpeg"

            base64_image = base64.b64encode(r.content).decode("utf-8")

            prompt = (
                "Przeanalizuj ten screenshot rozmowy i wyodrębnij informacje o oszuście.\n"
                "Zwróć TYLKO JSON o polach:\n"
                "{\n"
                '  "scammer_name": "string lub null",\n'
                '  "phone_number": "string lub null",\n'
                '  "bank_account": "string lub null",\n'
                '  "email": "string lub null",\n'
                '  "facebook_link": "string lub null",\n'
                '  "scam_description": "string",\n'
                '  "confidence": "high/medium/low",\n'
                '  "screenshot_type": "messenger/whatsapp/olx/sms/other"\n'
                "}\n"
                "Zasady:\n"
                "- Jeśli dane niewidoczne -> null.\n"
                "- Telefon normalizuj do +48XXXXXXXXX jeśli to możliwe.\n"
                "- IBAN Polski: PL + 26 cyfr (bez spacji).\n"
            )

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=900,
                temperature=0.1,
            )

            raw_content = completion.choices[0].message.content
            text = self._content_to_text(raw_content)
            print(f"[DEBUG] Raw text z GPT:\n{text[:500]}\n")

            data = self._extract_json_from_text(text)

            return self._validate_extracted_data(data)

        except Exception as e:
            print(f"❌ Błąd analizy obrazu: {str(e)}")
            import traceback

            traceback.print_exc()
            return None

    def analyze_post_text(self, post_text: str) -> Dict:
        prompt = (
            "Oceń czy ten post z grupy o oszustwach wygląda jak zgłoszenie oszustwa.\n"
            "Zwróć JSON:\n"
            '{ "is_scam_report": true/false, "has_contact_info": true/false, "priority": "high/medium/low" }\n\n'
            f"POST:\n{post_text}"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0,
            )

            raw_content = response.choices[0].message.content
            text = self._content_to_text(raw_content)
            data = self._extract_json_from_text(text)
            return data

        except Exception:
            # Fail-open: nie blokuj procesu
            return {"is_scam_report": True, "has_contact_info": False, "priority": "low"}

    def _validate_extracted_data(self, data: Dict) -> Optional[Dict]:
        if not isinstance(data, dict):
            return None

        # Normalizacja telefonu
        if data.get("phone_number"):
            data["phone_number"] = self._normalize_phone(str(data["phone_number"]))
        else:
            data["phone_number"] = None

        # Normalizacja IBAN
        if data.get("bank_account"):
            data["bank_account"] = self._validate_iban(str(data["bank_account"]))
        else:
            data["bank_account"] = None

        # Email
        if data.get("email"):
            if not self._validate_email(str(data["email"])):
                data["email"] = None
        else:
            data["email"] = None

        # scammer_name/facebook_link
        if data.get("scammer_name") is not None:
            data["scammer_name"] = str(data["scammer_name"]).strip() or None
        if data.get("facebook_link") is not None:
            data["facebook_link"] = str(data["facebook_link"]).strip() or None

        # Opis
        if not data.get("scam_description"):
            data["scam_description"] = "Zgłoszenie z Facebook (auto)."

        # Minimalny warunek użyteczności (telefon lub IBAN lub nazwa)
        has_any = any([data.get("phone_number"), data.get("bank_account"), data.get("scammer_name"), data.get("email")])
        if not has_any:
            return None

        return data

    def _normalize_phone(self, phone: str) -> Optional[str]:
        clean = re.sub(r"[^\d+]", "", phone)

        if not clean:
            return None

        if not clean.startswith("+"):
            if clean.startswith("48"):
                clean = "+" + clean
            elif len(clean) == 9:
                clean = "+48" + clean
            else:
                return None

        # +48 + 9 cyfr
        if re.match(r"^\+48\d{9}$", clean):
            return clean
        return None

    def _validate_iban(self, iban: str) -> Optional[str]:
        clean = iban.replace(" ", "").upper()
        if re.match(r"^PL\d{26}$", clean):
            return clean
        return None

    def _validate_email(self, email: str) -> bool:
        return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))
