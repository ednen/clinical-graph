"""
Patient Complaint API
─────────────────────
FastAPI backend - Hasta şikayet formu -> SNOMED mapping -> Neo4j graph -> Klinik rapor

Çalıştırma:
  pip install fastapi uvicorn neo4j httpx pydantic
  uvicorn api:app --reload --port 8000

Endpoints:
  POST /api/complaints/submit     → Form submit, SNOMED map, Neo4j'e yaz
  GET  /api/patients/{id}/graph   → Patient graph (Neo4j traversal)
  GET  /api/encounters/{id}/report → Doktor raporu
  GET  /api/encounters/{id}/alerts → Klinik uyarılar
  GET  /api/snomed/search          → Manuel SNOMED arama
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from neo4j import AsyncGraphDatabase
import uuid
import os

from snomed_mapper import SnomedMapper, MappingResult

# ─── Config ──────────────────────────────────────────────────

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

app = FastAPI(
    title="Hasta Şikayet Sistemi",
    description="Dijital anamnez → SNOMED CT → Neo4j Graph → Klinik Rapor",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Models ──────────────────────────────────────────────────

class ComplaintForm(BaseModel):
    """Hasta şikayet formu - frontend'den gelen veri"""
    patient_id: Optional[str] = None
    chief_complaints: str = Field(..., description="Ana şikayetler, virgülle ayrılmış")
    onset_time: str = Field(..., description="Şikayetlerin başlangıç zamanı")
    symptom_course_variation: str = Field(default="", description="Semptom seyri")
    previous_occurrence: str = Field(default="", description="Daha önce benzer durum")
    allergies: str = Field(default="", description="Alerjiler")
    regular_medications: str = Field(default="", description="Düzenli ilaçlar")
    chronic_conditions: str = Field(default="", description="Kronik hastalıklar")
    surgical_history: str = Field(default="", description="Cerrahi geçmiş")
    last_oral_intake_time: str = Field(default="", description="Son oral alım")
    pain_presence: str = Field(default="", description="Ağrı lokasyonu")
    pain_severity_1_10: str = Field(default="", description="Ağrı şiddeti (1-10)")
    additional_complaints: str = Field(default="", description="Ek şikayetler")


class SnomedSearchRequest(BaseModel):
    term: str
    semantic_tag: Optional[str] = None
    limit: int = 10


class SubmitResponse(BaseModel):
    encounter_id: str
    patient_id: str
    mapped_count: int
    unmapped_count: int
    mapped_symptoms: list[dict]
    unmapped_terms: list[str]
    warnings: list[str]
    graph_url: str


# ─── Services ────────────────────────────────────────────────

mapper = SnomedMapper()


def get_neo4j_driver():
    return AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ─── Endpoints ───────────────────────────────────────────────

@app.post("/api/complaints/submit", response_model=SubmitResponse)
async def submit_complaints(form: ComplaintForm):
    """
    Hasta şikayet formunu al → SNOMED map et → Neo4j'e yaz → sonuç dön
    """
    patient_id = form.patient_id or f"P-{datetime.now().strftime('%Y')}-{uuid.uuid4().hex[:5].upper()}"
    encounter_id = f"ENC-{datetime.now().strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:5].upper()}"

    # 1. SNOMED Mapping
    form_dict = form.model_dump()
    mapping_result: MappingResult = await mapper.map_complaint_form(form_dict)

    # 2. Neo4j'e yaz
    driver = get_neo4j_driver()
    try:
        async with driver.session() as session:
            # Patient ve Encounter oluştur
            await session.run("""
                MERGE (p:Patient {patient_id: $patient_id})
                CREATE (e:Encounter {
                    encounter_id: $encounter_id,
                    created_at: datetime(),
                    status: 'active',
                    last_oral_intake: $last_oral,
                    raw_form_data: $raw_form
                })
                CREATE (p)-[:HAS_ENCOUNTER]->(e)
            """, {
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "last_oral": form.last_oral_intake_time,
                "raw_form": str(form_dict),
            })

            # Semptomları yaz
            for sym in mapping_result.mapped:
                await session.run("""
                    MATCH (e:Encounter {encounter_id: $enc_id})
                    CREATE (s:Symptom {
                        symptom_id: randomUUID(),
                        name_tr: $name_tr,
                        name_en: $name_en,
                        snomed_code: $snomed_code,
                        snomed_term: $snomed_term,
                        icd11_code: $icd11_code,
                        icd11_title: $icd11_title,
                        semantic_tag: $semantic_tag,
                        confidence: $confidence
                    })
                    CREATE (e)-[:PRESENTS_WITH]->(s)
                """, {
                    "enc_id": encounter_id,
                    "name_tr": sym.original_text_tr,
                    "name_en": sym.name_en,
                    "snomed_code": sym.snomed_code,
                    "snomed_term": sym.snomed_term,
                    "icd11_code": sym.icd11_code,
                    "icd11_title": sym.icd11_title,
                    "semantic_tag": sym.semantic_tag,
                    "confidence": sym.confidence,
                })

            # Alerji
            if form.allergies:
                await session.run("""
                    MATCH (p:Patient {patient_id: $pid})
                    CREATE (a:Allergy {
                        allergy_id: randomUUID(),
                        substance: $substance,
                        raw_text: $raw
                    })
                    CREATE (p)-[:HAS_ALLERGY]->(a)
                """, {
                    "pid": patient_id,
                    "substance": form.allergies,
                    "raw": form.allergies,
                })

            # Kronik hastalık
            if form.chronic_conditions:
                await session.run("""
                    MATCH (p:Patient {patient_id: $pid})
                    CREATE (cc:ChronicCondition {
                        condition_id: randomUUID(),
                        name_tr: $name,
                        status: 'active'
                    })
                    CREATE (p)-[:HAS_CONDITION]->(cc)
                """, {
                    "pid": patient_id,
                    "name": form.chronic_conditions,
                })

            # İlaç
            if form.regular_medications:
                await session.run("""
                    MATCH (p:Patient {patient_id: $pid})
                    CREATE (m:Medication {
                        medication_id: randomUUID(),
                        raw_text: $raw,
                        is_current: true
                    })
                    CREATE (p)-[:TAKES_MEDICATION]->(m)
                """, {
                    "pid": patient_id,
                    "raw": form.regular_medications,
                })

    finally:
        await driver.close()

    return SubmitResponse(
        encounter_id=encounter_id,
        patient_id=patient_id,
        mapped_count=len(mapping_result.mapped),
        unmapped_count=len(mapping_result.unmapped),
        mapped_symptoms=[
            {
                "original_tr": s.original_text_tr,
                "name_en": s.name_en,
                "snomed_code": s.snomed_code,
                "snomed_term": s.snomed_term,
                "icd11_code": s.icd11_code,
                "icd11_title": s.icd11_title,
                "confidence": s.confidence,
                "body_site": s.body_site_name,
            }
            for s in mapping_result.mapped
        ],
        unmapped_terms=mapping_result.unmapped,
        warnings=mapping_result.warnings,
        graph_url=f"/api/patients/{patient_id}/graph",
    )


@app.get("/api/patients/{patient_id}/graph")
async def get_patient_graph(patient_id: str):
    """Hastanın tüm graph yapısını çek - frontend visualization için"""
    driver = get_neo4j_driver()
    try:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Patient {patient_id: $pid})-[:HAS_ENCOUNTER]->(e:Encounter)
                OPTIONAL MATCH (e)-[:PRESENTS_WITH]->(s:Symptom)
                OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(a:Allergy)
                OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)
                OPTIONAL MATCH (p)-[:HAS_CONDITION]->(cc:ChronicCondition)
                OPTIONAL MATCH (p)-[:HAD_SURGERY]->(sx:Surgery)
                OPTIONAL MATCH (s)-[mi:MAY_INDICATE]->(dx:PotentialDiagnosis)
                RETURN p, e,
                    collect(DISTINCT s{.*, labels: labels(s)}) AS symptoms,
                    collect(DISTINCT a{.*, labels: labels(a)}) AS allergies,
                    collect(DISTINCT m{.*, labels: labels(m)}) AS medications,
                    collect(DISTINCT cc{.*, labels: labels(cc)}) AS conditions,
                    collect(DISTINCT sx{.*, labels: labels(sx)}) AS surgeries,
                    collect(DISTINCT dx{.*, labels: labels(dx)}) AS diagnoses
            """, {"pid": patient_id})

            records = [record.data() async for record in result]

            if not records:
                raise HTTPException(status_code=404, detail="Patient not found")

            # D3.js / vis.js uyumlu nodes + edges formatına çevir
            nodes = []
            edges = []
            
            record = records[0]
            
            # Patient node
            nodes.append({"id": patient_id, "label": f"Hasta\n{patient_id}", "group": "patient"})
            
            # Encounter node
            if enc := record.get("e"):
                enc_id = enc.get("encounter_id", "")
                nodes.append({"id": enc_id, "label": f"Muayene\n{enc_id[:15]}", "group": "encounter"})
                edges.append({"from": patient_id, "to": enc_id, "label": "HAS_ENCOUNTER"})
                
                # Symptom nodes
                for s in record.get("symptoms", []):
                    if s and s.get("snomed_code"):
                        sid = s["snomed_code"]
                        nodes.append({
                            "id": sid,
                            "label": f"{s.get('name_tr', '')}\n{sid}",
                            "group": "symptom",
                            "properties": s,
                        })
                        edges.append({"from": enc_id, "to": sid, "label": "PRESENTS_WITH"})

            # Allergy nodes
            for a in record.get("allergies", []):
                if a:
                    aid = a.get("allergy_id", str(uuid.uuid4()))
                    nodes.append({"id": aid, "label": f"⚠️ {a.get('substance', '')}", "group": "allergy"})
                    edges.append({"from": patient_id, "to": aid, "label": "HAS_ALLERGY"})

            # Medication nodes
            for m in record.get("medications", []):
                if m:
                    mid = m.get("medication_id", str(uuid.uuid4()))
                    nodes.append({"id": mid, "label": f"💊 {m.get('name', m.get('raw_text', '')[:20])}", "group": "medication"})
                    edges.append({"from": patient_id, "to": mid, "label": "TAKES_MEDICATION"})

            # Condition nodes
            for cc in record.get("conditions", []):
                if cc:
                    cid = cc.get("condition_id", str(uuid.uuid4()))
                    nodes.append({"id": cid, "label": f"🏥 {cc.get('name_tr', '')}", "group": "condition"})
                    edges.append({"from": patient_id, "to": cid, "label": "HAS_CONDITION"})

            # Diagnosis nodes
            for dx in record.get("diagnoses", []):
                if dx:
                    did = dx.get("snomed_code", str(uuid.uuid4()))
                    nodes.append({
                        "id": did,
                        "label": f"🔍 {dx.get('name_tr', '')}\n{dx.get('confidence', 0):.0%}",
                        "group": "diagnosis",
                    })

            return {"nodes": nodes, "edges": edges}

    finally:
        await driver.close()


@app.get("/api/encounters/{encounter_id}/report")
async def get_encounter_report(encounter_id: str):
    """Doktor için okunabilir klinik rapor"""
    driver = get_neo4j_driver()
    try:
        async with driver.session() as session:
            # Ana rapor verisi
            result = await session.run("""
                MATCH (p:Patient)-[:HAS_ENCOUNTER]->(e:Encounter {encounter_id: $eid})
                OPTIONAL MATCH (e)-[pw:PRESENTS_WITH]->(s:Symptom)
                WITH p, e, s, pw
                ORDER BY pw.is_chief DESC, s.severity DESC
                WITH p, e, collect(s{.*, is_chief: pw.is_chief}) AS symptoms
                
                OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(a:Allergy)
                WITH p, e, symptoms, collect(a{.*}) AS allergies
                
                OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication {is_current: true})
                WITH p, e, symptoms, allergies, collect(m{.*}) AS medications
                
                OPTIONAL MATCH (p)-[:HAS_CONDITION]->(cc:ChronicCondition)
                WITH p, e, symptoms, allergies, medications, collect(cc{.*}) AS conditions
                
                OPTIONAL MATCH (p)-[:HAD_SURGERY]->(sx:Surgery)
                RETURN p{.*} AS patient,
                       e{.*} AS encounter,
                       symptoms, allergies, medications, conditions,
                       collect(sx{.*}) AS surgeries
            """, {"eid": encounter_id})

            records = [record.data() async for record in result]
            if not records:
                raise HTTPException(status_code=404, detail="Encounter not found")

            data = records[0]

            # Olası tanıları çek
            dx_result = await session.run("""
                MATCH (e:Encounter {encounter_id: $eid})-[:PRESENTS_WITH]->(s:Symptom)
                MATCH (s)-[mi:MAY_INDICATE]->(dx:PotentialDiagnosis)
                WITH dx, 
                     collect({symptom: s.name_tr, probability: mi.probability}) AS evidence,
                     avg(mi.probability) AS avg_prob,
                     count(s) AS support_count
                ORDER BY avg_prob DESC
                RETURN dx{.*} AS diagnosis, evidence, avg_prob, support_count
            """, {"eid": encounter_id})

            diagnoses = [record.data() async for record in dx_result]

            # Uyarıları çek
            alert_result = await session.run("""
                MATCH (p:Patient)-[:HAS_ENCOUNTER]->(e:Encounter {encounter_id: $eid})
                OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)-[:MAY_CAUSE]->(effect:SnomedConcept)
                OPTIONAL MATCH (e)-[:PRESENTS_WITH]->(s:Symptom)
                WHERE s.snomed_code = effect.concept_id
                WITH m, s, collect({medication: m.name, symptom: s.name_tr, effect: effect.preferred_term}) AS side_effects
                
                OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(a:Allergy)-[:CONTRAINDICATES]->(dc:DrugClass)
                RETURN side_effects,
                       collect({allergen: a.substance, drug_class: dc.name}) AS contraindications
            """, {"eid": encounter_id})

            alerts = [record.data() async for record in alert_result]

            return {
                "report": {
                    "patient": data["patient"],
                    "encounter": data["encounter"],
                    "symptoms": data["symptoms"],
                    "allergies": data["allergies"],
                    "medications": data["medications"],
                    "chronic_conditions": data["conditions"],
                    "surgical_history": data["surgeries"],
                },
                "clinical_reasoning": {
                    "potential_diagnoses": diagnoses,
                },
                "alerts": alerts[0] if alerts else {},
                "generated_at": datetime.now().isoformat(),
            }
    finally:
        await driver.close()


@app.get("/api/snomed/search")
async def search_snomed(term: str, lang: str = "en", limit: int = 10):
    """SNOMED + ICD-11 arama (local dict + WHO ICD-11 API)"""
    from snomed_mapper import TR_EN_SYMPTOM_MAP

    # Local dictionary'den ara
    results = []
    term_lower = term.lower()
    for tr_term, data in TR_EN_SYMPTOM_MAP.items():
        if term_lower in tr_term or term_lower in data["en"].lower():
            results.append({
                "snomed_code": data.get("snomed", "unknown"),
                "icd11_code": data.get("icd11", ""),
                "preferred_term": data["en"],
                "turkish_term": tr_term,
                "source": "local_dictionary",
            })
        if len(results) >= limit:
            break

    # ICD-11 API'den de ara (varsa)
    icd11_results = []
    if mapper.icd11:
        api_results = await mapper.icd11.search(term, lang=lang, max_results=limit)
        for r in api_results:
            icd11_results.append({
                "snomed_code": "",
                "icd11_code": r.get("icd11_code", ""),
                "preferred_term": r.get("title", ""),
                "turkish_term": "",
                "source": "icd11_api",
            })

    return {
        "query": term,
        "local_results": results,
        "icd11_results": icd11_results,
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ─── Startup / Shutdown ─────────────────────────────────────

@app.on_event("shutdown")
async def shutdown():
    await mapper.close()
