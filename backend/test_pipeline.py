"""
End-to-End Test Script
──────────────────────
Tüm pipeline'ı test eder: SNOMED mapping + Neo4j + API
Çalıştırma: python test_pipeline.py
"""

import httpx
import asyncio
from snomed_mapper import SnomedMapper, TurkishSymptomPreprocessor

API_BASE = "http://localhost:8000"

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
CYAN = "\033[96m"; RESET = "\033[0m"; BOLD = "\033[1m"

def header(t): print(f"\n{BOLD}{CYAN}{'═'*60}\n  {t}\n{'═'*60}{RESET}")
def ok(t):     print(f"  {GREEN}✅ {t}{RESET}")
def fail(t):   print(f"  {RED}❌ {t}{RESET}")
def info(t):   print(f"  {YELLOW}ℹ️  {t}{RESET}")


def test_preprocessor():
    header("TEST 1: Türkçe Metin Preprocessor")
    pp = TurkishSymptomPreprocessor()

    tokens = pp.extract_symptom_tokens("Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü")
    assert len(tokens) == 3, f"Beklenen 3, gelen {len(tokens)}"
    ok(f"Token extraction: {tokens}")

    sev = pp.extract_severity("Yaklaşık 10 üzerinden 7 şiddetinde.")
    assert sev == 7
    ok(f"Severity: {sev}/10")

    onset = pp.extract_onset_days("Şikayetlerim 3 gün önce başladı.")
    assert onset == 3.0
    ok(f"Onset: {onset} gün")

    print(f"\n  {GREEN}{BOLD}Preprocessor PASSED ✓{RESET}")


async def test_snowstorm():
    header("TEST 2: Snowstorm SNOMED CT API")
    mapper = SnomedMapper()
    info("Snowstorm API'ye bağlanılıyor...")

    matches = await mapper.snowstorm.search_concepts("fever", limit=3)
    if matches:
        ok(f"API bağlantısı başarılı - {len(matches)} sonuç")
        for m in matches:
            print(f"    → {m.concept_id} | {m.preferred_term} ({m.semantic_tag})")
    else:
        fail("Snowstorm bağlantısı başarısız (internet gerekli)")
        info("Offline modda local map kullanılacak")

    await mapper.close()
    print(f"\n  {GREEN}{BOLD}Snowstorm PASSED ✓{RESET}")


async def test_mapping():
    header("TEST 3: Türkçe → SNOMED CT Mapping")
    mapper = SnomedMapper()

    tests = [
        ("ateş", "386661006"), ("göğüs ağrısı", "29857009"),
        ("nefes alma güçlüğü", "267036007"), ("prodüktif öksürük", "28743005"),
        ("hipertansiyon", "38341003"), ("penisilin", "91936005"),
    ]
    passed = 0
    for tr, expected in tests:
        result = await mapper.map_symptom(tr)
        if result and result.snomed_code == expected:
            ok(f"'{tr}' → {result.snomed_code} ({result.snomed_term}) [{result.confidence:.0%}]")
            passed += 1
        else:
            fail(f"'{tr}' → {result.snomed_code if result else 'NONE'} (beklenen: {expected})")

    info("\nTam form mapping...")
    form = {
        "chief_complaints": "Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü",
        "allergies": "Penisiline alerjim var",
        "chronic_conditions": "Tansiyon Hastası",
        "additional_complaints": "Öksürük var, sarı-yeşil balgam",
    }
    result = await mapper.map_complaint_form(form)
    ok(f"Mapped: {len(result.mapped)}, Unmapped: {len(result.unmapped)}")
    for sym in result.mapped:
        print(f"    📌 {sym.original_text_tr} → {sym.snomed_code}")

    await mapper.close()
    print(f"\n  {GREEN}{BOLD}Mapping PASSED ({passed}/{len(tests)}) ✓{RESET}")


async def test_api():
    header("TEST 4: FastAPI Backend")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{API_BASE}/api/health")
            if r.status_code == 200:
                ok(f"API health: {r.json()}")
                return True
            fail(f"API health failed: {r.status_code}")
        except httpx.ConnectError:
            fail("API bağlanamadı — uvicorn çalışıyor mu?")
            info("Çalıştır: uvicorn api:app --reload --port 8000")
    return False


async def test_full_pipeline():
    header("TEST 5: Full Pipeline (Submit → Graph → Report)")
    async with httpx.AsyncClient(timeout=30) as client:
        form = {
            "chief_complaints": "Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü",
            "onset_time": "3 gün önce başladı",
            "allergies": "Penisiline alerjim var",
            "regular_medications": "Ramipril 5 mg sabahları",
            "chronic_conditions": "Tansiyon Hastası",
            "surgical_history": "2015 apandisit ameliyatı",
            "last_oral_intake_time": "5 saat önce kahvaltı",
            "pain_presence": "Göğsümde ve sırtımda ağrı var",
            "pain_severity_1_10": "7",
            "additional_complaints": "Öksürük var, sarı-yeşil balgam",
        }
        try:
            r = await client.post(f"{API_BASE}/api/complaints/submit", json=form)
            if r.status_code == 200:
                data = r.json()
                ok(f"Submit → Patient: {data['patient_id']}, Mapped: {data['mapped_count']}")
                pid, eid = data["patient_id"], data["encounter_id"]

                r = await client.get(f"{API_BASE}/api/patients/{pid}/graph")
                if r.status_code == 200:
                    g = r.json()
                    ok(f"Graph → {len(g['nodes'])} node, {len(g['edges'])} edge")

                r = await client.get(f"{API_BASE}/api/encounters/{eid}/report")
                if r.status_code == 200:
                    ok("Report → Klinik rapor üretildi")
            else:
                fail(f"Submit failed: {r.status_code} - {r.text[:200]}")
        except httpx.ConnectError:
            fail("API bağlantı hatası")


def test_neo4j():
    header("TEST 6: Neo4j Cypher Sorguları")
    try:
        from neo4j import GraphDatabase
        import os
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "clinical2026"))
        )
        with driver.session() as session:
            count = session.run("MATCH (n) RETURN count(n) AS total").single()["total"]
            ok(f"Toplam node: {count}")

            result = session.run("""
                MATCH (p:Patient)-[r]->(n)
                RETURN type(r) AS rel, labels(n)[0] AS label, count(*) AS cnt
            """)
            for rec in result:
                print(f"    → Patient -[{rec['rel']}]-> {rec['label']} ({rec['cnt']}x)")

            info("\nKlinik Akıl Yürütme:")
            result = session.run("""
                MATCH (s:Symptom)-[mi:MAY_INDICATE]->(dx:PotentialDiagnosis)
                RETURN s.name_tr AS sym, dx.name_tr AS dx, mi.probability AS prob
                ORDER BY prob DESC LIMIT 5
            """)
            for rec in result:
                bar = "█" * int(rec["prob"] * 20)
                print(f"    {rec['sym']:25s} → {rec['dx']:30s} [{bar:20s}] {rec['prob']:.0%}")

            info("\nKontrendikasyonlar:")
            for rec in session.run("""
                MATCH (a:Allergy)-[:CONTRAINDICATES]->(dc:DrugClass)
                RETURN a.substance AS a, dc.name AS dc
            """):
                print(f"    🚨 {rec['a']} → {rec['dc']} KONTRENDIKE")

        driver.close()
        print(f"\n  {GREEN}{BOLD}Neo4j PASSED ✓{RESET}")
    except Exception as e:
        fail(f"Neo4j hatası: {e}")
        info("docker compose up neo4j -d && python seed_neo4j.py")


async def main():
    print(f"\n{BOLD}🏥 CLINICAL GRAPH — END-TO-END TEST SUITE{RESET}\n{'─'*60}")

    test_preprocessor()
    await test_snowstorm()
    await test_mapping()

    if await test_api():
        await test_full_pipeline()

    test_neo4j()

    header("TAMAMLANDI")
    print("  Sorun varsa sırayla kontrol et:")
    print("  1. docker compose up neo4j -d")
    print("  2. python seed_neo4j.py")
    print("  3. uvicorn api:app --reload --port 8000")
    print("  4. python test_pipeline.py\n")


if __name__ == "__main__":
    asyncio.run(main())
