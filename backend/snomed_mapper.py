"""
SNOMED CT Mapping Service
─────────────────────────
Türkçe hasta şikayetlerini Snowstorm API üzerinden SNOMED CT kodlarına map eder.
Neo4j graph'a yazmak için hazır node/relationship yapıları döner.

Snowstorm API: https://snowstorm.ihtsdotools.org/snowstorm/snomed-ct
SNOMED International Browser: https://browser.ihtsdotools.org/
"""

import httpx
import asyncio
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


# ─── Configuration ───────────────────────────────────────────

SNOWSTORM_BASE_URL = "https://snowstorm.ihtsdotools.org/snowstorm/snomed-ct"
SNOMED_EDITION = "MAIN"       # International edition
SNOMED_VERSION = "2024-09-01" # veya en güncel versiyon
ACCEPT_LANGUAGE = "en"        # Snowstorm şu an Türkçe desteklemiyor, EN üzerinden map yapıp TR eşleştireceğiz

# ─── Turkish -> English Symptom Mapping ──────────────────────
# Bu dictionary NLP katmanı eklenene kadar temel çeviri görevi görür.
# Production'da bu katman bir LLM veya medikal çeviri API'si ile değiştirilmeli.

TR_EN_SYMPTOM_MAP: dict[str, dict] = {
    # ── Genel Semptomlar ──
    "ateş":                   {"en": "fever", "snomed_hint": "386661006"},
    "yüksek ateş":            {"en": "high fever", "snomed_hint": "386661006"},
    "titreme":                {"en": "chills", "snomed_hint": "43724002"},
    "halsizlik":              {"en": "malaise", "snomed_hint": "367391008"},
    "yorgunluk":              {"en": "fatigue", "snomed_hint": "84229001"},
    "kilo kaybı":             {"en": "weight loss", "snomed_hint": "89362005"},
    "iştahsızlık":            {"en": "loss of appetite", "snomed_hint": "79890006"},
    "terleme":                {"en": "sweating", "snomed_hint": "415690000"},
    "gece terlemesi":         {"en": "night sweats", "snomed_hint": "42984000"},

    # ── Solunum Sistemi ──
    "öksürük":                {"en": "cough", "snomed_hint": "49727002"},
    "kuru öksürük":           {"en": "dry cough", "snomed_hint": "11833005"},
    "balgamlı öksürük":       {"en": "productive cough", "snomed_hint": "28743005"},
    "prodüktif öksürük":      {"en": "productive cough", "snomed_hint": "28743005"},
    "nefes darlığı":          {"en": "dyspnea", "snomed_hint": "267036007"},
    "nefes alma güçlüğü":     {"en": "dyspnea", "snomed_hint": "267036007"},
    "nefes almada zorluk":    {"en": "difficulty breathing", "snomed_hint": "267036007"},
    "göğüs ağrısı":           {"en": "chest pain", "snomed_hint": "29857009"},
    "hırıltı":                {"en": "wheezing", "snomed_hint": "56018004"},
    "hemoptizi":              {"en": "hemoptysis", "snomed_hint": "66857006"},
    "kan tükürme":            {"en": "hemoptysis", "snomed_hint": "66857006"},
    "boğaz ağrısı":           {"en": "sore throat", "snomed_hint": "162397003"},
    "burun tıkanıklığı":      {"en": "nasal congestion", "snomed_hint": "68235000"},
    "burun akıntısı":         {"en": "rhinorrhea", "snomed_hint": "64531003"},

    # ── Kardiyovasküler ──
    "çarpıntı":               {"en": "palpitations", "snomed_hint": "80313002"},
    "göğüste baskı hissi":    {"en": "chest pressure", "snomed_hint": "23924001"},
    "bacak şişliği":          {"en": "leg swelling", "snomed_hint": "297142003"},
    "ödem":                   {"en": "edema", "snomed_hint": "267038008"},

    # ── Gastrointestinal ──
    "karın ağrısı":           {"en": "abdominal pain", "snomed_hint": "21522001"},
    "bulantı":                {"en": "nausea", "snomed_hint": "422587007"},
    "kusma":                  {"en": "vomiting", "snomed_hint": "422400008"},
    "ishal":                  {"en": "diarrhea", "snomed_hint": "62315008"},
    "kabızlık":               {"en": "constipation", "snomed_hint": "14760008"},
    "şişkinlik":              {"en": "bloating", "snomed_hint": "248490000"},
    "mide yanması":           {"en": "heartburn", "snomed_hint": "16331000"},
    "kanlı dışkı":            {"en": "blood in stool", "snomed_hint": "405729008"},

    # ── Nörolojik ──
    "baş ağrısı":             {"en": "headache", "snomed_hint": "25064002"},
    "baş dönmesi":            {"en": "dizziness", "snomed_hint": "404640003"},
    "bayılma":                {"en": "syncope", "snomed_hint": "271594007"},
    "uyuşma":                 {"en": "numbness", "snomed_hint": "44077006"},
    "karıncalanma":           {"en": "tingling", "snomed_hint": "62507009"},
    "konuşma bozukluğu":      {"en": "speech difficulty", "snomed_hint": "29164008"},
    "bulanık görme":          {"en": "blurred vision", "snomed_hint": "246636008"},
    "nöbet":                  {"en": "seizure", "snomed_hint": "91175000"},
    "bilinç kaybı":           {"en": "loss of consciousness", "snomed_hint": "419045004"},

    # ── Kas-İskelet ──
    "sırt ağrısı":            {"en": "back pain", "snomed_hint": "161891005"},
    "bel ağrısı":             {"en": "low back pain", "snomed_hint": "279039007"},
    "eklem ağrısı":           {"en": "joint pain", "snomed_hint": "57676002"},
    "kas ağrısı":             {"en": "muscle pain", "snomed_hint": "68962001"},
    "boyun ağrısı":           {"en": "neck pain", "snomed_hint": "81680005"},

    # ── Ürogenital ──
    "idrarda yanma":          {"en": "dysuria", "snomed_hint": "49650001"},
    "sık idrara çıkma":       {"en": "urinary frequency", "snomed_hint": "162116003"},
    "kanlı idrar":            {"en": "hematuria", "snomed_hint": "34436003"},
    "böğür ağrısı":           {"en": "flank pain", "snomed_hint": "247355005"},

    # ── Deri ──
    "döküntü":                {"en": "rash", "snomed_hint": "271807003"},
    "kaşıntı":                {"en": "itching", "snomed_hint": "418290006"},
    "yara":                   {"en": "wound", "snomed_hint": "13924000"},
    "şişlik":                 {"en": "swelling", "snomed_hint": "442672001"},

    # ── Psikiyatrik ──
    "uykusuzluk":             {"en": "insomnia", "snomed_hint": "193462001"},
    "anksiyete":              {"en": "anxiety", "snomed_hint": "48694002"},
    "depresyon":              {"en": "depression", "snomed_hint": "35489007"},

    # ── Kronik Hastalıklar ──
    "hipertansiyon":          {"en": "hypertension", "snomed_hint": "38341003"},
    "tansiyon hastası":       {"en": "hypertension", "snomed_hint": "38341003"},
    "şeker hastalığı":        {"en": "diabetes mellitus", "snomed_hint": "73211009"},
    "diyabet":                {"en": "diabetes mellitus", "snomed_hint": "73211009"},
    "astım":                  {"en": "asthma", "snomed_hint": "195967001"},
    "koah":                   {"en": "COPD", "snomed_hint": "13645005"},

    # ── Alerjenler ──
    "penisilin":              {"en": "penicillin allergy", "snomed_hint": "91936005"},
    "aspirin":                {"en": "aspirin allergy", "snomed_hint": "293586001"},

    # ── Cerrahi Prosedürler ──
    "apandisit ameliyatı":    {"en": "appendectomy", "snomed_hint": "80146002"},
    "apendektomi":            {"en": "appendectomy", "snomed_hint": "80146002"},
    "sezaryen":               {"en": "cesarean section", "snomed_hint": "11466000"},
    "kolesistektomi":         {"en": "cholecystectomy", "snomed_hint": "38102005"},
    "safra kesesi ameliyatı": {"en": "cholecystectomy", "snomed_hint": "38102005"},
}


# ─── Data Classes ────────────────────────────────────────────

class SemanticTag(str, Enum):
    FINDING = "finding"
    DISORDER = "disorder"
    PROCEDURE = "procedure"
    SUBSTANCE = "substance"
    BODY_STRUCTURE = "body structure"
    OBSERVABLE = "observable entity"
    SITUATION = "situation"


@dataclass
class SnomedMatch:
    """Snowstorm API'den dönen bir SNOMED CT eşleşmesi"""
    concept_id: str
    preferred_term: str
    semantic_tag: str
    score: float = 0.0
    is_from_hint: bool = False  # TR_EN_MAP'den mi geldi


@dataclass
class MappedSymptom:
    """Map edilmiş semptom, Neo4j'e yazılmaya hazır"""
    original_text_tr: str
    name_en: str
    snomed_code: str
    snomed_term: str
    semantic_tag: str
    confidence: float  # 0-1 arası
    body_site: Optional[str] = None
    body_site_name: Optional[str] = None
    alternatives: list[SnomedMatch] = field(default_factory=list)


@dataclass
class MappingResult:
    """Tüm mapping sonucu"""
    mapped: list[MappedSymptom] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ─── Snowstorm API Client ───────────────────────────────────

class SnowstormClient:
    """
    IHTSDO Snowstorm SNOMED CT Terminology Server Client
    
    Public endpoint: https://snowstorm.ihtsdotools.org/snowstorm/snomed-ct
    API docs: https://snowstorm.ihtsdotools.org/snowstorm/snomed-ct/swagger-ui.html
    
    Not: Production'da kendi Snowstorm instance'ınızı kurmanız önerilir.
    Public endpoint rate limit'e tabidir.
    """

    def __init__(self, base_url: str = SNOWSTORM_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=3.0,
            headers={
                "Accept": "application/json",
                "Accept-Language": ACCEPT_LANGUAGE,
            }
        )

    async def search_concepts(
        self,
        term: str,
        semantic_tag: Optional[str] = None,
        ecl: Optional[str] = None,
        limit: int = 5,
    ) -> list[SnomedMatch]:
        """
        Snowstorm concept search
        
        Args:
            term: Aranacak terim (İngilizce)
            semantic_tag: Filtreleme (finding, disorder, procedure, vb.)
            ecl: Expression Constraint Language sorgusu
            limit: Maksimum sonuç sayısı
        """
        params = {
            "term": term,
            "activeFilter": True,
            "limit": limit,
            "offset": 0,
        }

        if semantic_tag:
            params["semanticTag"] = semantic_tag
        if ecl:
            params["ecl"] = ecl

        url = f"{self.base_url}/browser/{SNOMED_EDITION}/descriptions"

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            matches = []
            for item in data.get("items", []):
                concept = item.get("concept", {})
                fsn = concept.get("fsn", {})
                matches.append(SnomedMatch(
                    concept_id=concept.get("conceptId", ""),
                    preferred_term=concept.get("pt", {}).get("term", ""),
                    semantic_tag=fsn.get("term", "").split("(")[-1].rstrip(")") if "(" in fsn.get("term", "") else "",
                    score=item.get("score", 0),
                ))
            return matches

        except httpx.HTTPError as e:
            print(f"Snowstorm API error: {e}")
            return []

    async def get_concept(self, concept_id: str) -> Optional[dict]:
        """Tek bir SNOMED CT concept'in detaylarını çek"""
        url = f"{self.base_url}/browser/{SNOMED_EDITION}/concepts/{concept_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def get_ancestors(self, concept_id: str) -> list[dict]:
        """Concept'in üst hiyerarşisini çek (ISA ilişkileri)"""
        url = f"{self.base_url}/{SNOMED_EDITION}/concepts/{concept_id}/ancestors"
        params = {"form": "inferred", "limit": 50}
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return [
                {"concept_id": item["conceptId"], "term": item.get("pt", {}).get("term", "")}
                for item in data.get("items", [])
            ]
        except httpx.HTTPError:
            return []

    async def find_body_site(self, symptom_concept_id: str) -> Optional[dict]:
        """
        Semptomun vücut bölgesini SNOMED ilişkilerinden bul
        finding site (363698007) relationship
        """
        url = f"{self.base_url}/browser/{SNOMED_EDITION}/concepts/{symptom_concept_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            for rel_group in data.get("classAxioms", []):
                for rel in rel_group.get("relationships", []):
                    type_concept = rel.get("type", {})
                    if type_concept.get("conceptId") == "363698007":  # Finding site
                        target = rel.get("target", {})
                        return {
                            "concept_id": target.get("conceptId"),
                            "term": target.get("pt", {}).get("term", target.get("fsn", {}).get("term", ""))
                        }
            return None
        except httpx.HTTPError:
            return None

    async def close(self):
        await self.client.aclose()


# ─── Text Preprocessor ──────────────────────────────────────

class TurkishSymptomPreprocessor:
    """
    Türkçe şikayet metnini normalize eder ve token'lara ayırır.
    Production'da bu katman bir Türkçe NLP pipeline'ı (Zemberek, vb.) ile güçlendirilmeli.
    """

    # Hasta metninden çıkarılacak gereksiz kelimeler
    STOP_PHRASES = [
        "şikayetim var", "şikayetlerim var", "rahatsızlığım var",
        "bende", "benim", "var", "yok", "oldu", "oluyor",
        "çok", "biraz", "bazen", "sürekli", "arada bir",
        "yaklaşık", "tahminen", "gibi", "kadar",
    ]

    @staticmethod
    def normalize(text: str) -> str:
        """Temel metin normalizasyonu"""
        text = text.lower().strip()
        text = text.replace("ı", "ı").replace("İ", "i")
        # Fazla boşlukları temizle
        import re
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def extract_symptom_tokens(text: str) -> list[str]:
        """
        Serbest metinden semptom token'larını çıkar.
        Örnek: "Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü" 
               -> ["ateş", "göğüs ağrısı", "nefes alma güçlüğü"]
        """
        import re
        text = TurkishSymptomPreprocessor.normalize(text)
        
        # Virgül, noktalı virgül, "ve", satır sonu ile ayır
        tokens = re.split(r'[,;.\n]|\bve\b', text)
        
        # Temizle
        cleaned = []
        for token in tokens:
            token = token.strip()
            if len(token) >= 2:
                cleaned.append(token)
        
        return cleaned

    @staticmethod
    def extract_severity(text: str) -> Optional[int]:
        """Şiddet skorunu metinden çıkar"""
        import re
        patterns = [
            r'(\d+)\s*(?:üzerinden|/)\s*10',
            r'şiddet(?:i|inde)?\s*(\d+)',
            r'(\d+)\s*(?:puan|derece)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 10:
                    return val
        return None

    @staticmethod
    def extract_onset_days(text: str) -> Optional[float]:
        """Başlangıç süresini gün cinsinden çıkar"""
        import re
        patterns = [
            (r'(\d+)\s*gün', 1.0),
            (r'(\d+)\s*hafta', 7.0),
            (r'(\d+)\s*ay', 30.0),
            (r'(\d+)\s*saat', 1/24),
            (r'(\d+)\s*yıl', 365.0),
        ]
        for pattern, multiplier in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1)) * multiplier
        return None


# ─── Main Mapper ─────────────────────────────────────────────

class SnomedMapper:
    """
    Ana mapping servisi.
    Türkçe semptom -> İngilizce çeviri -> Snowstorm API -> SNOMED CT kodu
    """

    def __init__(self):
        self.snowstorm = SnowstormClient()
        self.preprocessor = TurkishSymptomPreprocessor()

    async def map_symptom(self, symptom_text_tr: str) -> Optional[MappedSymptom]:
        """
        Tek bir Türkçe semptomu SNOMED CT'ye map et.
        
        Strateji:
        1. Önce TR_EN_MAP'den bak (hızlı, güvenilir)
        2. Hint varsa Snowstorm'dan doğrula
        3. Hint yoksa Snowstorm'da ara
        4. Body site'ı otomatik bul
        """
        normalized = self.preprocessor.normalize(symptom_text_tr)

        # Step 1: Local map'den bak
        local_match = TR_EN_SYMPTOM_MAP.get(normalized)
        
        if local_match:
            en_term = local_match["en"]
            hint_code = local_match.get("snomed_hint")

            # Step 2: Hint code varsa Snowstorm'dan doğrulamayı dene, başarısızsa local'den dön
            if hint_code:
                concept = await self.snowstorm.get_concept(hint_code)
                if concept:
                    fsn = concept.get("fsn", {}).get("term", "")
                    semantic_tag = fsn.split("(")[-1].rstrip(")") if "(" in fsn else "finding"
                    pt = concept.get("pt", {}).get("term", en_term)
                    body_site_info = await self.snowstorm.find_body_site(hint_code)
                    return MappedSymptom(
                        original_text_tr=symptom_text_tr,
                        name_en=pt,
                        snomed_code=hint_code,
                        snomed_term=pt,
                        semantic_tag=semantic_tag,
                        confidence=0.95,
                        body_site=body_site_info.get("concept_id") if body_site_info else None,
                        body_site_name=body_site_info.get("term") if body_site_info else None,
                    )
                else:
                    # Snowstorm ulaşılamadı — local hint'ten dön
                    return MappedSymptom(
                        original_text_tr=symptom_text_tr,
                        name_en=en_term,
                        snomed_code=hint_code,
                        snomed_term=en_term,
                        semantic_tag="finding",
                        confidence=0.85,
                    )

            # Hint yok ama en_term var, Snowstorm'da ara
            matches = await self.snowstorm.search_concepts(en_term, limit=5)
            if matches:
                best = matches[0]
                return MappedSymptom(
                    original_text_tr=symptom_text_tr,
                    name_en=best.preferred_term,
                    snomed_code=best.concept_id,
                    snomed_term=best.preferred_term,
                    semantic_tag=best.semantic_tag,
                    confidence=0.80,
                    alternatives=matches[1:],
                )

            # Snowstorm da boş döndü, local hint varsa onu kullan
            return MappedSymptom(
                original_text_tr=symptom_text_tr,
                name_en=en_term,
                snomed_code=hint_code or "unknown",
                snomed_term=en_term,
                semantic_tag="finding",
                confidence=0.70,
            )

        # Step 3: Local map'de yok, fuzzy search dene
        # Kelime kelime Snowstorm'a sor
        matches = await self._fuzzy_search(normalized)
        if matches:
            best = matches[0]
            return MappedSymptom(
                original_text_tr=symptom_text_tr,
                name_en=best.preferred_term,
                snomed_code=best.concept_id,
                snomed_term=best.preferred_term,
                semantic_tag=best.semantic_tag,
                confidence=0.50,
                alternatives=matches[1:],
            )

        return None

    async def _fuzzy_search(self, text: str) -> list[SnomedMatch]:
        """Bilinmeyen terimler için fuzzy arama"""
        # Türkçe'den İngilizce'ye basit kelime eşleştirme
        # Production'da LLM çeviri API'si kullanılmalı
        words = text.split()
        all_matches = []
        
        for word in words:
            if len(word) >= 3:
                matches = await self.snowstorm.search_concepts(word, limit=3)
                all_matches.extend(matches)
        
        # Deduplicate by concept_id
        seen = set()
        unique = []
        for m in all_matches:
            if m.concept_id not in seen:
                seen.add(m.concept_id)
                unique.append(m)
        
        return sorted(unique, key=lambda x: x.score, reverse=True)[:5]

    async def map_complaint_form(self, form_data: dict) -> MappingResult:
        """
        Tam bir hasta şikayet formunu map et.
        
        form_data format (görüntüdeki example_complaints.txt yapısı):
        {
            "chief_complaints": "Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü",
            "onset_time": "Şikayetlerim 3 gün önce başladı.",
            "symptom_course_variation": "Nefes alıp vermede zorluk...",
            "previous_occurrence": "2 yıl önce bronşit teşhisi...",
            "allergies": "Penisiline alerjim var",
            "regular_medications": "Ramipril 5 mg...",
            "chronic_conditions": "Tansiyon Hastası",
            "surgical_history": "2015 apandisit ameliyatı",
            "last_oral_intake_time": "5 saat önce kahvaltı...",
            "pain_presence": "Göğsümde ve sırtımda ağrı var",
            "pain_severity_1_10": "7",
            "additional_complaints": "Öksürük var, sarı-yeşil balgam"
        }
        """
        result = MappingResult()

        # 1. Ana şikayetleri map et
        if chief := form_data.get("chief_complaints"):
            tokens = self.preprocessor.extract_symptom_tokens(chief)
            for token in tokens:
                mapped = await self.map_symptom(token)
                if mapped:
                    # Onset bilgisini ekle
                    onset_text = form_data.get("onset_time", "")
                    mapped_onset = self.preprocessor.extract_onset_days(onset_text)
                    # severity bilgisini ekle
                    if sev := form_data.get("pain_severity_1_10"):
                        try:
                            sev_int = int(sev.strip().split()[0])
                        except (ValueError, IndexError):
                            sev_int = self.preprocessor.extract_severity(sev)
                    result.mapped.append(mapped)
                else:
                    result.unmapped.append(token)

        # 2. Ağrı lokasyonlarını map et
        if pain := form_data.get("pain_presence"):
            pain_tokens = self.preprocessor.extract_symptom_tokens(pain)
            for token in pain_tokens:
                # Zaten chief complaint'te varsa skip
                existing_codes = {m.snomed_code for m in result.mapped}
                mapped = await self.map_symptom(token)
                if mapped and mapped.snomed_code not in existing_codes:
                    result.mapped.append(mapped)

        # 3. Ek şikayetleri map et
        if additional := form_data.get("additional_complaints"):
            add_tokens = self.preprocessor.extract_symptom_tokens(additional)
            for token in add_tokens:
                existing_codes = {m.snomed_code for m in result.mapped}
                mapped = await self.map_symptom(token)
                if mapped and mapped.snomed_code not in existing_codes:
                    result.mapped.append(mapped)

        # 4. Alerji map et
        if allergy := form_data.get("allergies"):
            allergy_tokens = self.preprocessor.extract_symptom_tokens(allergy)
            for token in allergy_tokens:
                mapped = await self.map_symptom(token)
                if mapped:
                    result.mapped.append(mapped)

        # 5. Kronik hastalıkları map et
        if chronic := form_data.get("chronic_conditions"):
            chronic_tokens = self.preprocessor.extract_symptom_tokens(chronic)
            for token in chronic_tokens:
                mapped = await self.map_symptom(token)
                if mapped:
                    result.mapped.append(mapped)

        # 6. Cerrahi geçmişi map et
        if surgery := form_data.get("surgical_history"):
            surgery_tokens = self.preprocessor.extract_symptom_tokens(surgery)
            for token in surgery_tokens:
                mapped = await self.map_symptom(token)
                if mapped:
                    result.mapped.append(mapped)

        return result

    async def close(self):
        await self.snowstorm.close()


# ─── Neo4j Cypher Generator ─────────────────────────────────

class CypherGenerator:
    """
    MappingResult'tan Neo4j Cypher sorguları üretir.
    Production'da neo4j Python driver kullanılmalı.
    """

    @staticmethod
    def generate_symptom_nodes(mapped_symptoms: list[MappedSymptom]) -> list[str]:
        """Map edilmiş semptomlar için CREATE sorguları üret"""
        queries = []
        for sym in mapped_symptoms:
            props = {
                "symptom_id": "randomUUID()",
                "name_tr": sym.original_text_tr,
                "name_en": sym.name_en,
                "snomed_code": sym.snomed_code,
                "snomed_term": sym.snomed_term,
                "confidence": sym.confidence,
            }
            if sym.body_site:
                props["body_site"] = sym.body_site
                props["body_site_name"] = sym.body_site_name or ""

            prop_str = ", ".join(
                f'{k}: "{v}"' if isinstance(v, str) and k != "symptom_id"
                else f"{k}: {v}"
                for k, v in props.items()
            )
            queries.append(f"CREATE (:Symptom {{{prop_str}}})")

        return queries

    @staticmethod
    def generate_encounter_graph(
        patient_id: str,
        encounter_id: str,
        mapping_result: MappingResult,
    ) -> str:
        """Tam bir encounter graph'ı için Cypher üret"""
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
                f'snomed_term: "{sym.snomed_term}", '
                f'confidence: {sym.confidence}'
                f'}})'
            )
            lines.append(f'CREATE (e)-[:PRESENTS_WITH]->({var})')
            lines.append('')

        return '\n'.join(lines)


# ─── Usage Example ───────────────────────────────────────────

async def main():
    """Örnek kullanım - görüntüdeki hasta verisi ile"""
    
    mapper = SnomedMapper()

    # Görüntüdeki form verisi
    form_data = {
        "chief_complaints": "Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü",
        "onset_time": "Şikayetlerim 3 gün önce başladı.",
        "symptom_course_variation": "Nefes alıp vermede zorluk yürürken. Son 2 gündür. Özellikle derin nefes alınca artıyor.",
        "previous_occurrence": "Aslında buna benzer bir durum 2 yıl önce de yaşamıştım, o zaman bronşit teşhisi konmuştu.",
        "allergies": "Penisiline alerjim var, kesinlikle kullanamam.",
        "regular_medications": "Düzenli olarak tansiyon ilacı kullanıyorum, adı Ramipril 5 mg, sabahları bir tane.",
        "chronic_conditions": "Tansiyon Hastası",
        "surgical_history": "2015 yılında apandisit ameliyatı oldum, başka ameliyatım yok.",
        "last_oral_intake_time": "En son 5 saat önce kahvaltı yaptım, iki dilim ekmek ve çay içtim.",
        "pain_presence": "Göğsümde ve sırtımda ağrı var",
        "pain_severity_1_10": "Yaklaşık 10 üzerinden 7 şiddetinde.",
        "additional_complaints": "Öksürük var ve sabahları sarı-yeşil renkli balgam çıkarıyorum.",
    }

    print("=" * 60)
    print("SNOMED CT MAPPING - Hasta Şikayet Formu")
    print("=" * 60)

    result = await mapper.map_complaint_form(form_data)

    print(f"\n✅ Başarıyla map edilen: {len(result.mapped)}")
    print(f"❌ Map edilemeyen: {len(result.unmapped)}")

    for sym in result.mapped:
        print(f"\n  📌 {sym.original_text_tr}")
        print(f"     EN: {sym.name_en}")
        print(f"     SNOMED: {sym.snomed_code} | {sym.snomed_term}")
        print(f"     Tag: {sym.semantic_tag}")
        print(f"     Confidence: {sym.confidence:.0%}")
        if sym.body_site:
            print(f"     Body Site: {sym.body_site} ({sym.body_site_name})")
        if sym.alternatives:
            print(f"     Alternatives: {', '.join(a.concept_id for a in sym.alternatives[:3])}")

    if result.unmapped:
        print(f"\n⚠️  Map edilemeyenler: {result.unmapped}")

    # Cypher üret
    print("\n" + "=" * 60)
    print("GENERATED CYPHER")
    print("=" * 60)
    cypher = CypherGenerator.generate_encounter_graph(
        patient_id="P-2026-00142",
        encounter_id="ENC-2026-03-04-001",
        mapping_result=result,
    )
    print(cypher)

    await mapper.close()


if __name__ == "__main__":
    asyncio.run(main())
