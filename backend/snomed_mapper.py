"""
SNOMED CT + ICD-11 Mapping Service
───────────────────────────────────
Türkçe hasta şikayetlerini SNOMED CT + ICD-11 kodlarına map eder.

Strateji:
  1. Local dictionary (80+ Türkçe terim → SNOMED + ICD-11 kodu) — anında, offline
  2. WHO ICD-11 API — online doğrulama ve zenginleştirme, Türkçe destekli

WHO ICD-11 API: https://icd.who.int/icdapi
Token endpoint: https://icdaccessmanagement.who.int/connect/token
"""

import httpx
import asyncio
import os
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───────────────────────────────────────────

ICD_TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
ICD_API_BASE = "https://id.who.int"
ICD_CLIENT_ID = os.getenv("ICD_CLIENT_ID", "")
ICD_CLIENT_SECRET = os.getenv("ICD_CLIENT_SECRET", "")


# ─── Local Dictionary: Turkish → English → SNOMED + ICD-11 ──

TR_EN_SYMPTOM_MAP: dict[str, dict] = {
    # ── Genel Semptomlar ──
    "ateş":                   {"en": "fever", "snomed": "386661006", "icd11": "MG26"},
    "yüksek ateş":            {"en": "high fever", "snomed": "386661006", "icd11": "MG26"},
    "titreme":                {"en": "chills", "snomed": "43724002", "icd11": "MG26.1"},
    "halsizlik":              {"en": "malaise", "snomed": "367391008", "icd11": "MG22"},
    "yorgunluk":              {"en": "fatigue", "snomed": "84229001", "icd11": "MG22"},
    "kilo kaybı":             {"en": "weight loss", "snomed": "89362005", "icd11": "MG43.0"},
    "iştahsızlık":            {"en": "loss of appetite", "snomed": "79890006", "icd11": "MG43.1"},
    "terleme":                {"en": "sweating", "snomed": "415690000", "icd11": "MG26.4"},
    "gece terlemesi":         {"en": "night sweats", "snomed": "42984000", "icd11": "MG26.4"},

    # ── Solunum Sistemi ──
    "öksürük":                {"en": "cough", "snomed": "49727002", "icd11": "MD12"},
    "kuru öksürük":           {"en": "dry cough", "snomed": "11833005", "icd11": "MD12.0"},
    "balgamlı öksürük":       {"en": "productive cough", "snomed": "28743005", "icd11": "MD12.1"},
    "prodüktif öksürük":      {"en": "productive cough", "snomed": "28743005", "icd11": "MD12.1"},
    "nefes darlığı":          {"en": "dyspnea", "snomed": "267036007", "icd11": "MD11"},
    "nefes alma güçlüğü":     {"en": "dyspnea", "snomed": "267036007", "icd11": "MD11"},
    "nefes almada zorluk":    {"en": "difficulty breathing", "snomed": "267036007", "icd11": "MD11"},
    "göğüs ağrısı":           {"en": "chest pain", "snomed": "29857009", "icd11": "MD30"},
    "hırıltı":                {"en": "wheezing", "snomed": "56018004", "icd11": "MD11.3"},
    "hemoptizi":              {"en": "hemoptysis", "snomed": "66857006", "icd11": "MD13"},
    "kan tükürme":            {"en": "hemoptysis", "snomed": "66857006", "icd11": "MD13"},
    "boğaz ağrısı":           {"en": "sore throat", "snomed": "162397003", "icd11": "MD10"},
    "burun tıkanıklığı":      {"en": "nasal congestion", "snomed": "68235000", "icd11": "MA01"},
    "burun akıntısı":         {"en": "rhinorrhea", "snomed": "64531003", "icd11": "MA02"},

    # ── Kardiyovasküler ──
    "çarpıntı":               {"en": "palpitations", "snomed": "80313002", "icd11": "MC80"},
    "göğüste baskı hissi":    {"en": "chest pressure", "snomed": "23924001", "icd11": "MD30"},
    "bacak şişliği":          {"en": "leg swelling", "snomed": "297142003", "icd11": "ME03"},
    "ödem":                   {"en": "edema", "snomed": "267038008", "icd11": "ME03"},

    # ── Gastrointestinal ──
    "karın ağrısı":           {"en": "abdominal pain", "snomed": "21522001", "icd11": "ME04"},
    "bulantı":                {"en": "nausea", "snomed": "422587007", "icd11": "ME05.0"},
    "kusma":                  {"en": "vomiting", "snomed": "422400008", "icd11": "ME05.1"},
    "ishal":                  {"en": "diarrhea", "snomed": "62315008", "icd11": "ME06.0"},
    "kabızlık":               {"en": "constipation", "snomed": "14760008", "icd11": "ME06.1"},
    "şişkinlik":              {"en": "bloating", "snomed": "248490000", "icd11": "ME08"},
    "mide yanması":           {"en": "heartburn", "snomed": "16331000", "icd11": "MD90"},
    "kanlı dışkı":            {"en": "blood in stool", "snomed": "405729008", "icd11": "ME14"},

    # ── Nörolojik ──
    "baş ağrısı":             {"en": "headache", "snomed": "25064002", "icd11": "MB40"},
    "baş dönmesi":            {"en": "dizziness", "snomed": "404640003", "icd11": "MB48"},
    "bayılma":                {"en": "syncope", "snomed": "271594007", "icd11": "MF30"},
    "uyuşma":                 {"en": "numbness", "snomed": "44077006", "icd11": "MB40.3"},
    "karıncalanma":           {"en": "tingling", "snomed": "62507009", "icd11": "MB40.3"},
    "konuşma bozukluğu":      {"en": "speech difficulty", "snomed": "29164008", "icd11": "MB47"},
    "bulanık görme":          {"en": "blurred vision", "snomed": "246636008", "icd11": "MC20"},
    "nöbet":                  {"en": "seizure", "snomed": "91175000", "icd11": "MB41"},
    "bilinç kaybı":           {"en": "loss of consciousness", "snomed": "419045004", "icd11": "MF30"},

    # ── Kas-İskelet ──
    "sırt ağrısı":            {"en": "back pain", "snomed": "161891005", "icd11": "ME84"},
    "bel ağrısı":             {"en": "low back pain", "snomed": "279039007", "icd11": "ME84.2"},
    "eklem ağrısı":           {"en": "joint pain", "snomed": "57676002", "icd11": "ME82"},
    "kas ağrısı":             {"en": "muscle pain", "snomed": "68962001", "icd11": "ME81"},
    "boyun ağrısı":           {"en": "neck pain", "snomed": "81680005", "icd11": "ME84.0"},

    # ── Ürogenital ──
    "idrarda yanma":          {"en": "dysuria", "snomed": "49650001", "icd11": "MF50"},
    "sık idrara çıkma":       {"en": "urinary frequency", "snomed": "162116003", "icd11": "MF52"},
    "kanlı idrar":            {"en": "hematuria", "snomed": "34436003", "icd11": "MF56"},
    "böğür ağrısı":           {"en": "flank pain", "snomed": "247355005", "icd11": "MF90"},

    # ── Deri ──
    "döküntü":                {"en": "rash", "snomed": "271807003", "icd11": "ME60"},
    "kaşıntı":                {"en": "itching", "snomed": "418290006", "icd11": "ME61"},
    "yara":                   {"en": "wound", "snomed": "13924000", "icd11": "NF0Y"},
    "şişlik":                 {"en": "swelling", "snomed": "442672001", "icd11": "ME03"},

    # ── Psikiyatrik ──
    "uykusuzluk":             {"en": "insomnia", "snomed": "193462001", "icd11": "7A00"},
    "anksiyete":              {"en": "anxiety", "snomed": "48694002", "icd11": "6B00"},
    "depresyon":              {"en": "depression", "snomed": "35489007", "icd11": "6A70"},

    # ── Kronik Hastalıklar ──
    "hipertansiyon":          {"en": "hypertension", "snomed": "38341003", "icd11": "BA00"},
    "tansiyon hastası":       {"en": "hypertension", "snomed": "38341003", "icd11": "BA00"},
    "tansiyon hastalığı":     {"en": "hypertension", "snomed": "38341003", "icd11": "BA00"},
    "şeker hastalığı":        {"en": "diabetes mellitus", "snomed": "73211009", "icd11": "5A10"},
    "diyabet":                {"en": "diabetes mellitus", "snomed": "73211009", "icd11": "5A10"},
    "astım":                  {"en": "asthma", "snomed": "195967001", "icd11": "CA23"},
    "koah":                   {"en": "COPD", "snomed": "13645005", "icd11": "CA22"},

    # ── Alerjenler ──
    "penisilin":              {"en": "penicillin allergy", "snomed": "91936005", "icd11": "4A84"},
    "penisiline alerjim var": {"en": "penicillin allergy", "snomed": "91936005", "icd11": "4A84"},
    "aspirin":                {"en": "aspirin allergy", "snomed": "293586001", "icd11": "4A85"},

    # ── Cerrahi Prosedürler ──
    "apandisit ameliyatı":    {"en": "appendectomy", "snomed": "80146002", "icd11": "JA01"},
    "apendektomi":            {"en": "appendectomy", "snomed": "80146002", "icd11": "JA01"},
    "sezaryen":               {"en": "cesarean section", "snomed": "11466000", "icd11": "JB40"},
    "kolesistektomi":         {"en": "cholecystectomy", "snomed": "38102005", "icd11": "JA63"},
    "safra kesesi ameliyatı": {"en": "cholecystectomy", "snomed": "38102005", "icd11": "JA63"},
}


# ─── Data Classes ────────────────────────────────────────────

@dataclass
class MappedSymptom:
    original_text_tr: str
    name_en: str
    snomed_code: str
    snomed_term: str
    icd11_code: str
    icd11_title: str
    semantic_tag: str
    confidence: float
    body_site: Optional[str] = None
    body_site_name: Optional[str] = None
    icd11_uri: Optional[str] = None


@dataclass
class MappingResult:
    mapped: list[MappedSymptom] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ─── WHO ICD-11 API Client ──────────────────────────────────

class ICD11Client:
    """
    WHO ICD-11 API Client (v2)
    - OAuth2 authentication
    - Search (coding tool + linearization search)
    - Türkçe dil desteği
    """

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = client_id or ICD_CLIENT_ID
        self.client_secret = client_secret or ICD_CLIENT_SECRET
        self.token: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=10.0)

    async def _get_token(self) -> str:
        """OAuth2 token al"""
        if self.token:
            return self.token

        if not self.client_id or not self.client_secret:
            raise ValueError("ICD_CLIENT_ID ve ICD_CLIENT_SECRET .env dosyasında tanımlı olmalı")

        resp = await self.client.post(ICD_TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "icdapi_access",
            "grant_type": "client_credentials",
        })
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        return self.token

    def _headers(self, token: str, lang: str = "en") -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Accept-Language": lang,
            "API-Version": "v2",
        }

    async def search(self, query: str, lang: str = "en", max_results: int = 5) -> list[dict]:
        """
        ICD-11 Coding Tool search — en güçlü arama endpoint'i.
        Fuzzy search, Türkçe destekli.
        """
        try:
            token = await self._get_token()
            url = f"{ICD_API_BASE}/icd/release/11/2024-01/mms/search"
            params = {
                "q": query,
                "subtreeFilterUsesFoundationDescendants": False,
                "includeKeywordResult": True,
                "flatResults": True,
                "highlightingEnabled": False,
            }
            resp = await self.client.get(url, headers=self._headers(token, lang), params=params)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("destinationEntities", [])[:max_results]:
                results.append({
                    "icd11_code": item.get("theCode", ""),
                    "title": item.get("title", ""),
                    "uri": item.get("id", ""),
                    "score": item.get("score", 0),
                    "chapter": item.get("chapter", ""),
                })
            return results

        except Exception as e:
            print(f"ICD-11 API error: {e}")
            return []

    async def search_turkish(self, query: str, max_results: int = 5) -> list[dict]:
        """Türkçe arama"""
        return await self.search(query, lang="tr", max_results=max_results)

    async def get_entity(self, uri: str, lang: str = "en") -> Optional[dict]:
        """Tek bir ICD-11 entity detay"""
        try:
            token = await self._get_token()
            # URI'yi https'e çevir
            url = uri.replace("http://", "https://")
            resp = await self.client.get(url, headers=self._headers(token, lang))
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"ICD-11 entity fetch error: {e}")
            return None

    async def lookup_code(self, code: str, lang: str = "en") -> Optional[dict]:
        """ICD-11 kodu ile entity bul"""
        try:
            token = await self._get_token()
            url = f"{ICD_API_BASE}/icd/release/11/2024-01/mms/codeinfo/{code}"
            resp = await self.client.get(url, headers=self._headers(token, lang))
            resp.raise_for_status()
            data = resp.json()
            stem = data.get("stemId", "")
            if stem:
                entity = await self.get_entity(stem, lang)
                if entity:
                    return {
                        "code": code,
                        "title": entity.get("title", {}).get("@value", ""),
                        "definition": entity.get("definition", {}).get("@value", ""),
                        "uri": stem,
                    }
            return None
        except Exception as e:
            print(f"ICD-11 lookup error: {e}")
            return None

    async def close(self):
        await self.client.aclose()


# ─── Text Preprocessor ──────────────────────────────────────

class TurkishSymptomPreprocessor:
    """Türkçe şikayet metnini normalize eder ve token'lara ayırır."""

    @staticmethod
    def normalize(text: str) -> str:
        import re
        text = text.lower().strip()
        text = text.replace("İ", "i").replace("I", "ı")
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def extract_symptom_tokens(text: str) -> list[str]:
        import re
        text = TurkishSymptomPreprocessor.normalize(text)
        tokens = re.split(r'[,;.\n]|\bve\b', text)
        return [t.strip() for t in tokens if len(t.strip()) >= 2]

    @staticmethod
    def extract_severity(text: str) -> Optional[int]:
        import re
        for pattern in [r'(\d+)\s*(?:üzerinden|/)\s*10', r'şiddet(?:i|inde)?\s*(\d+)', r'(\d+)\s*(?:puan|derece)']:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 10:
                    return val
        return None

    @staticmethod
    def extract_onset_days(text: str) -> Optional[float]:
        import re
        for pattern, mult in [(r'(\d+)\s*gün', 1.0), (r'(\d+)\s*hafta', 7.0),
                               (r'(\d+)\s*ay', 30.0), (r'(\d+)\s*saat', 1/24), (r'(\d+)\s*yıl', 365.0)]:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1)) * mult
        return None


# ─── Main Mapper ─────────────────────────────────────────────

class SnomedMapper:
    """
    Offline-first mapper + ICD-11 API zenginleştirme.
    1. Local dictionary → anında SNOMED + ICD-11 kodu
    2. ICD-11 API → online doğrulama, Türkçe başlık, ek detay
    """

    def __init__(self, use_icd11_api: bool = True):
        self.use_icd11_api = use_icd11_api and bool(ICD_CLIENT_ID)
        self.icd11 = ICD11Client() if self.use_icd11_api else None
        self.preprocessor = TurkishSymptomPreprocessor()

    async def map_symptom(self, symptom_text_tr: str) -> Optional[MappedSymptom]:
        """Tek bir Türkçe semptomu SNOMED + ICD-11'e map et."""
        normalized = self.preprocessor.normalize(symptom_text_tr)

        # Step 1: Local dictionary
        local = TR_EN_SYMPTOM_MAP.get(normalized)

        if local:
            result = MappedSymptom(
                original_text_tr=symptom_text_tr,
                name_en=local["en"],
                snomed_code=local.get("snomed", "unknown"),
                snomed_term=local["en"],
                icd11_code=local.get("icd11", ""),
                icd11_title=local["en"],
                semantic_tag="finding",
                confidence=0.85,
            )

            # Step 2: ICD-11 API ile zenginleştir (opsiyonel)
            if self.use_icd11_api and self.icd11 and local.get("icd11"):
                enriched = await self.icd11.lookup_code(local["icd11"])
                if enriched:
                    result.icd11_title = enriched.get("title", result.icd11_title)
                    result.icd11_uri = enriched.get("uri")
                    result.confidence = 0.95

            return result

        # Step 3: Local'de yok — ICD-11 API'de Türkçe ara
        if self.use_icd11_api and self.icd11:
            # Önce Türkçe ara
            results = await self.icd11.search_turkish(normalized, max_results=3)
            if not results:
                # Türkçe bulamadıysa İngilizce dene
                results = await self.icd11.search(normalized, lang="en", max_results=3)

            if results:
                best = results[0]
                return MappedSymptom(
                    original_text_tr=symptom_text_tr,
                    name_en=best.get("title", normalized),
                    snomed_code="unknown",
                    snomed_term=best.get("title", ""),
                    icd11_code=best.get("icd11_code", ""),
                    icd11_title=best.get("title", ""),
                    semantic_tag="finding",
                    confidence=0.70,
                    icd11_uri=best.get("uri"),
                )

        return None

    async def map_complaint_form(self, form_data: dict) -> MappingResult:
        """Tam bir hasta şikayet formunu map et."""
        result = MappingResult()
        existing_codes = set()

        async def map_field(field_key: str):
            text = form_data.get(field_key, "")
            if not text:
                return
            tokens = self.preprocessor.extract_symptom_tokens(text)
            for token in tokens:
                mapped = await self.map_symptom(token)
                if mapped and mapped.snomed_code not in existing_codes:
                    existing_codes.add(mapped.snomed_code)
                    result.mapped.append(mapped)
                elif not mapped and len(token) > 3:
                    result.unmapped.append(token)

        # Sırayla tüm form alanlarını map et
        await map_field("chief_complaints")
        await map_field("pain_presence")
        await map_field("additional_complaints")
        await map_field("allergies")
        await map_field("chronic_conditions")
        await map_field("surgical_history")

        return result

    async def close(self):
        if self.icd11:
            await self.icd11.close()


# ─── Cypher Generator ───────────────────────────────────────

class CypherGenerator:
    @staticmethod
    def generate_encounter_graph(patient_id: str, encounter_id: str, mapping_result: MappingResult) -> str:
        lines = [
            f'MERGE (p:Patient {{patient_id: "{patient_id}"}})',
            f'CREATE (e:Encounter {{encounter_id: "{encounter_id}", created_at: datetime(), status: "active"}})',
            'CREATE (p)-[:HAS_ENCOUNTER]->(e)',
            '',
        ]
        for i, sym in enumerate(mapping_result.mapped):
            var = f"s{i}"
            lines.append(
                f'CREATE ({var}:Symptom {{'
                f'symptom_id: randomUUID(), '
                f'name_tr: "{sym.original_text_tr}", '
                f'name_en: "{sym.name_en}", '
                f'snomed_code: "{sym.snomed_code}", '
                f'icd11_code: "{sym.icd11_code}", '
                f'icd11_title: "{sym.icd11_title}", '
                f'confidence: {sym.confidence}'
                f'}})'
            )
            lines.append(f'CREATE (e)-[:PRESENTS_WITH]->({var})')
            lines.append('')
        return '\n'.join(lines)


# ─── CLI Test ────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("SNOMED + ICD-11 MAPPING TEST")
    print("=" * 60)

    mapper = SnomedMapper(use_icd11_api=True)

    # Tek semptom testleri
    test_terms = ["ateş", "göğüs ağrısı", "nefes alma güçlüğü", "prodüktif öksürük", "hipertansiyon"]
    for term in test_terms:
        result = await mapper.map_symptom(term)
        if result:
            print(f"\n  ✅ '{term}'")
            print(f"     EN: {result.name_en}")
            print(f"     SNOMED: {result.snomed_code}")
            print(f"     ICD-11: {result.icd11_code} | {result.icd11_title}")
            print(f"     Confidence: {result.confidence:.0%}")
        else:
            print(f"\n  ❌ '{term}' — map edilemedi")

    # Full form test
    print(f"\n{'=' * 60}")
    print("FULL FORM MAPPING")
    print("=" * 60)

    form = {
        "chief_complaints": "Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü",
        "allergies": "Penisiline alerjim var",
        "chronic_conditions": "Tansiyon Hastası",
        "additional_complaints": "Öksürük var, sarı-yeşil balgam",
    }
    result = await mapper.map_complaint_form(form)
    print(f"\n  Mapped: {len(result.mapped)}, Unmapped: {len(result.unmapped)}")
    for sym in result.mapped:
        print(f"    📌 {sym.original_text_tr} → SNOMED:{sym.snomed_code} | ICD-11:{sym.icd11_code}")

    if result.unmapped:
        print(f"  ⚠️  Unmapped: {result.unmapped}")

    await mapper.close()


if __name__ == "__main__":
    asyncio.run(main())
