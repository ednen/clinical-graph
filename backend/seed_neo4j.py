"""
Neo4j Seed Script — Veritabanını örnek hasta verisiyle doldurur.
Çalıştırma: python seed_neo4j.py
"""

from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "clinical2026")


def create_constraints(session):
    for c in [
        "CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE",
        "CREATE CONSTRAINT encounter_id IF NOT EXISTS FOR (e:Encounter) REQUIRE e.encounter_id IS UNIQUE",
        "CREATE CONSTRAINT snomed_concept IF NOT EXISTS FOR (s:SnomedConcept) REQUIRE s.concept_id IS UNIQUE",
    ]:
        try:
            session.run(c)
        except Exception as e:
            print(f"  Constraint zaten var: {e}")


def seed(tx):
    tx.run("MATCH (n) DETACH DELETE n")

    tx.run("""
        CREATE (p:Patient {
            patient_id: 'P-2026-00142', birth_year: 1978,
            gender: 'M', created_at: datetime()
        })
    """)

    tx.run("""
        CREATE (e:Encounter {
            encounter_id: 'ENC-2026-03-04-001', created_at: datetime(),
            encounter_type: 'outpatient', status: 'active',
            last_oral_intake: 'kahvaltı - 2 dilim ekmek, çay', last_oral_hours: 5.0
        })
    """)
    tx.run("""
        MATCH (p:Patient {patient_id: 'P-2026-00142'})
        MATCH (e:Encounter {encounter_id: 'ENC-2026-03-04-001'})
        CREATE (p)-[:HAS_ENCOUNTER]->(e)
    """)

    symptoms = [
        {"name_tr": "Ateş", "name_en": "Fever", "snomed_code": "386661006",
         "snomed_term": "Fever (finding)", "onset_days": 3.0, "course": "stable", "severity": None, "is_chief": True},
        {"name_tr": "Göğüs ağrısı", "name_en": "Chest pain", "snomed_code": "29857009",
         "snomed_term": "Chest pain (finding)", "onset_days": 3.0, "course": "stable", "severity": 7, "is_chief": True},
        {"name_tr": "Nefes alma güçlüğü", "name_en": "Dyspnea", "snomed_code": "267036007",
         "snomed_term": "Dyspnea (finding)", "onset_days": 2.0, "course": "worsening", "severity": None, "is_chief": True},
        {"name_tr": "Sırt ağrısı", "name_en": "Back pain", "snomed_code": "161891005",
         "snomed_term": "Backache (finding)", "onset_days": 0, "course": "unknown", "severity": 7, "is_chief": False},
        {"name_tr": "Prodüktif öksürük", "name_en": "Productive cough", "snomed_code": "28743005",
         "snomed_term": "Productive cough (finding)", "onset_days": 0, "course": "unknown", "severity": None, "is_chief": False},
    ]
    for s in symptoms:
        tx.run("""
            MATCH (e:Encounter {encounter_id: 'ENC-2026-03-04-001'})
            CREATE (sym:Symptom {
                symptom_id: randomUUID(), name_tr: $name_tr, name_en: $name_en,
                snomed_code: $snomed_code, snomed_term: $snomed_term,
                onset_days: $onset_days, course: $course, severity: $severity
            })
            CREATE (e)-[:PRESENTS_WITH {is_chief: $is_chief}]->(sym)
        """, {
            "name_tr": s["name_tr"], "name_en": s["name_en"],
            "snomed_code": s["snomed_code"], "snomed_term": s["snomed_term"],
            "onset_days": s["onset_days"], "course": s["course"],
            "severity": s["severity"], "is_chief": s["is_chief"],
        })

    tx.run("""
        MATCH (p:Patient {patient_id: 'P-2026-00142'})
        CREATE (a:Allergy {
            allergy_id: randomUUID(), substance: 'Penisilin',
            snomed_code: '91936005', severity: 'severe',
            reaction_type: 'anaphylaxis', verified: true
        })
        CREATE (p)-[:HAS_ALLERGY]->(a)
    """)

    tx.run("""
        MATCH (p:Patient {patient_id: 'P-2026-00142'})
        CREATE (m:Medication {
            medication_id: randomUUID(), name: 'Ramipril', generic_name: 'Ramipril',
            dose: '5', unit: 'mg', frequency: 'Günde 1 kez, sabah',
            route: 'oral', atc_code: 'C09AA05', is_current: true
        })
        CREATE (p)-[:TAKES_MEDICATION]->(m)
    """)

    tx.run("""
        MATCH (p:Patient {patient_id: 'P-2026-00142'})
        CREATE (cc:ChronicCondition {
            condition_id: randomUUID(), name_tr: 'Hipertansiyon',
            name_en: 'Essential hypertension', snomed_code: '59621000', status: 'active'
        })
        CREATE (p)-[:HAS_CONDITION]->(cc)
    """)

    tx.run("""
        MATCH (p:Patient {patient_id: 'P-2026-00142'})
        CREATE (sx:Surgery {
            surgery_id: randomUUID(), procedure_name_tr: 'Apendektomi',
            procedure_name_en: 'Appendectomy', snomed_code: '80146002', year: 2015
        })
        CREATE (p)-[:HAD_SURGERY]->(sx)
    """)

    tx.run("CREATE (:DrugClass {class_id: 'BETA_LACTAM', name: 'Beta-laktam Antibiyotikler', atc_prefix: 'J01C'})")
    tx.run("""
        MATCH (a:Allergy {snomed_code: '91936005'})
        MATCH (dc:DrugClass {class_id: 'BETA_LACTAM'})
        CREATE (a)-[:CONTRAINDICATES {mechanism: 'Penicillin cross-reactivity'}]->(dc)
    """)

    tx.run("CREATE (:DrugClass {class_id: 'ACE_INHIBITOR', name: 'ACE Inhibitorleri', atc_prefix: 'C09A'})")
    tx.run("""
        MATCH (m:Medication {name: 'Ramipril'})
        MATCH (ace:DrugClass {class_id: 'ACE_INHIBITOR'})
        CREATE (m)-[:BELONGS_TO]->(ace)
    """)
    tx.run("CREATE (:SnomedConcept {concept_id: '49727002', preferred_term: 'Cough (finding)', semantic_tag: 'finding'})")
    tx.run("""
        MATCH (m:Medication {name: 'Ramipril'})
        MATCH (ce:SnomedConcept {concept_id: '49727002'})
        CREATE (m)-[:MAY_CAUSE {frequency: 'common (5-20%)'}]->(ce)
    """)

    tx.run("""
        MATCH (s1:Symptom {snomed_code: '386661006'})
        MATCH (s5:Symptom {snomed_code: '28743005'})
        CREATE (s1)-[:ASSOCIATED_WITH {correlation: 0.85}]->(s5)
    """)
    tx.run("""
        MATCH (s2:Symptom {snomed_code: '29857009'})
        MATCH (s3:Symptom {snomed_code: '267036007'})
        CREATE (s2)-[:ASSOCIATED_WITH {correlation: 0.78}]->(s3)
    """)

    for name_tr, name_en, snomed, conf, urgency in [
        ("Pnomoni (Toplum Kokenli)", "Community-acquired pneumonia", "385093006", 0.82, "high"),
        ("Akut Bronsit", "Acute bronchitis", "10509002", 0.65, "medium"),
        ("Plevral Efuzyon", "Pleural effusion", "60046008", 0.45, "high"),
    ]:
        tx.run("""
            CREATE (:PotentialDiagnosis {
                diagnosis_id: randomUUID(), name_tr: $name_tr, name_en: $name_en,
                snomed_code: $snomed, confidence: $conf, urgency: $urgency
            })
        """, {"name_tr": name_tr, "name_en": name_en, "snomed": snomed, "conf": conf, "urgency": urgency})

    for s_code, dx_code, prob, evidence in [
        ("386661006", "385093006", 0.90, "strong"),
        ("29857009",  "385093006", 0.70, "moderate"),
        ("267036007", "385093006", 0.80, "strong"),
        ("28743005",  "385093006", 0.95, "strong"),
        ("386661006", "10509002",  0.70, "moderate"),
        ("28743005",  "10509002",  0.85, "strong"),
        ("29857009",  "60046008",  0.50, "weak"),
        ("267036007", "60046008",  0.60, "moderate"),
    ]:
        tx.run("""
            MATCH (s:Symptom {snomed_code: $s_code})
            MATCH (dx:PotentialDiagnosis {snomed_code: $dx_code})
            CREATE (s)-[:MAY_INDICATE {probability: $prob, evidence_level: $evidence}]->(dx)
        """, {"s_code": s_code, "dx_code": dx_code, "prob": prob, "evidence": evidence})

    print("  Data yazildi!")


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("1/2 Constraint'ler olusturuluyor...")
    with driver.session() as session:
        create_constraints(session)

    print("2/2 Veriler yukleniyor...")
    with driver.session() as session:
        session.execute_write(seed)

    driver.close()
    print("Neo4j basariyla dolduruldu!")
    print("  -> Neo4j Browser: http://localhost:7474")
    print("  -> Cypher: MATCH (n) RETURN n LIMIT 50")


if __name__ == "__main__":
    main()
