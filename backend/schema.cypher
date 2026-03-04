// ============================================================
// PATIENT COMPLAINT GRAPH - NEO4J SCHEMA & CYPHER QUERIES
// SNOMED CT Integrated Clinical Decision Support
// ============================================================

// ────────────────────────────────────────────────────────────
// 1. CONSTRAINTS & INDEXES
// ────────────────────────────────────────────────────────────

// Unique constraints
CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE;
CREATE CONSTRAINT encounter_id IF NOT EXISTS FOR (e:Encounter) REQUIRE e.encounter_id IS UNIQUE;
CREATE CONSTRAINT snomed_concept IF NOT EXISTS FOR (s:SnomedConcept) REQUIRE s.concept_id IS UNIQUE;
CREATE CONSTRAINT medication_id IF NOT EXISTS FOR (m:Medication) REQUIRE m.medication_id IS UNIQUE;
CREATE CONSTRAINT allergy_id IF NOT EXISTS FOR (a:Allergy) REQUIRE a.allergy_id IS UNIQUE;

// Performance indexes
CREATE INDEX symptom_name IF NOT EXISTS FOR (s:Symptom) ON (s.name_tr);
CREATE INDEX symptom_snomed IF NOT EXISTS FOR (s:Symptom) ON (s.snomed_code);
CREATE INDEX condition_snomed IF NOT EXISTS FOR (c:ChronicCondition) ON (c.snomed_code);
CREATE INDEX medication_name IF NOT EXISTS FOR (m:Medication) ON (m.name);
CREATE INDEX encounter_date IF NOT EXISTS FOR (e:Encounter) ON (e.created_at);
CREATE FULLTEXT INDEX symptom_fulltext IF NOT EXISTS FOR (s:Symptom) ON EACH [s.name_tr, s.description_tr];

// ────────────────────────────────────────────────────────────
// 2. NODE LABELS & PROPERTIES
// ────────────────────────────────────────────────────────────

// (:Patient)
//   patient_id        : String (UUID)
//   tc_kimlik         : String (encrypted)
//   birth_year        : Integer
//   gender            : String (M/F/Other)
//   created_at        : DateTime

// (:Encounter)
//   encounter_id      : String (UUID)
//   created_at        : DateTime
//   encounter_type    : String (emergency | outpatient | inpatient)
//   status            : String (active | completed | cancelled)
//   last_oral_intake  : String
//   last_oral_hours   : Float

// (:Symptom)
//   symptom_id        : String (UUID)
//   name_tr           : String (Turkish display name)
//   name_en           : String (English name)
//   snomed_code       : String (SNOMED CT Concept ID)
//   snomed_term       : String (SNOMED CT Preferred Term)
//   severity          : Integer (1-10, nullable)
//   onset_text        : String (patient's own words)
//   onset_days        : Float (calculated)
//   body_site         : String (SNOMED body site code)
//   body_site_name    : String
//   course            : String (improving | stable | worsening)
//   trigger           : String (nullable - e.g. "eforla", "istirahatte")
//   character         : String (nullable - e.g. "prodüktif", "kuru")
//   associated_detail : String (nullable - e.g. sputum color)

// (:Allergy)
//   allergy_id        : String (UUID)
//   substance         : String
//   snomed_code       : String
//   severity          : String (mild | moderate | severe)
//   reaction_type     : String (anaphylaxis | rash | gi | respiratory)
//   verified          : Boolean

// (:Medication)
//   medication_id     : String (UUID)
//   name              : String
//   generic_name      : String
//   dose              : String
//   unit              : String
//   frequency         : String
//   route             : String (oral | iv | im | topical)
//   atc_code          : String (ATC classification)
//   snomed_code       : String (nullable)
//   is_current        : Boolean

// (:ChronicCondition)
//   condition_id      : String (UUID)
//   name_tr           : String
//   name_en           : String
//   snomed_code       : String
//   status            : String (active | remission | resolved)
//   diagnosed_year    : Integer (nullable)

// (:Surgery)
//   surgery_id        : String (UUID)
//   procedure_name_tr : String
//   procedure_name_en : String
//   snomed_code       : String
//   year              : Integer
//   notes             : String (nullable)

// (:SnomedConcept) - Reference/Ontology node
//   concept_id        : String (SNOMED CT ID)
//   preferred_term    : String
//   semantic_tag      : String (finding | disorder | procedure | substance)
//   hierarchy         : List<String> (ancestor codes)

// (:PotentialDiagnosis)
//   diagnosis_id      : String (UUID)
//   name_tr           : String
//   name_en           : String
//   snomed_code       : String
//   confidence        : Float (0.0 - 1.0)
//   evidence_count    : Integer
//   urgency           : String (low | medium | high | critical)

// (:DrugClass)
//   class_id          : String
//   name              : String
//   atc_prefix        : String

// (:ClinicalAlert)
//   alert_id          : String (UUID)
//   type              : String (contraindication | interaction | side_effect | allergy_warning)
//   severity          : String (info | warning | critical)
//   message_tr        : String
//   message_en        : String


// ────────────────────────────────────────────────────────────
// 3. RELATIONSHIP TYPES
// ────────────────────────────────────────────────────────────

// Patient -> Encounter
// (:Patient)-[:HAS_ENCOUNTER {role: "patient"}]->(:Encounter)

// Encounter -> Symptoms
// (:Encounter)-[:PRESENTS_WITH {reported_at: DateTime, is_chief: Boolean}]->(:Symptom)

// Patient -> Medical History
// (:Patient)-[:HAS_ALLERGY {since: Date, confirmed_by: String}]->(:Allergy)
// (:Patient)-[:TAKES_MEDICATION {start_date: Date, prescribed_by: String}]->(:Medication)
// (:Patient)-[:HAS_CONDITION {diagnosed_date: Date}]->(:ChronicCondition)
// (:Patient)-[:HAD_SURGERY {date: Date}]->(:Surgery)

// Symptom Correlations
// (:Symptom)-[:ASSOCIATED_WITH {correlation: Float}]->(:Symptom)
// (:Symptom)-[:LOCATED_AT]->(:SnomedConcept)  // body site

// Clinical Reasoning
// (:Symptom)-[:MAY_INDICATE {probability: Float, evidence_level: String}]->(:PotentialDiagnosis)
// (:PotentialDiagnosis)-[:REQUIRES_WORKUP {test_name: String, priority: String}]->(:SnomedConcept)

// Safety
// (:Allergy)-[:CONTRAINDICATES {mechanism: String}]->(:DrugClass)
// (:Medication)-[:BELONGS_TO]->(:DrugClass)
// (:Medication)-[:INTERACTS_WITH {severity: String, mechanism: String}]->(:Medication)
// (:Medication)-[:MAY_CAUSE {frequency: String}]->(:SnomedConcept) // side effects

// Alerts (generated at query time, optionally persisted)
// (:Encounter)-[:HAS_ALERT]->(:ClinicalAlert)
// (:ClinicalAlert)-[:RELATED_TO]->(:Medication|:Allergy|:Symptom)


// ────────────────────────────────────────────────────────────
// 4. SAMPLE DATA - Based on the example_complaints.txt
// ────────────────────────────────────────────────────────────

// Create Patient
CREATE (p:Patient {
  patient_id: "P-2026-00142",
  birth_year: 1978,
  gender: "M",
  created_at: datetime()
})

// Create Encounter
CREATE (e:Encounter {
  encounter_id: "ENC-2026-03-04-001",
  created_at: datetime(),
  encounter_type: "outpatient",
  status: "active",
  last_oral_intake: "kahvaltı - 2 dilim ekmek, çay",
  last_oral_hours: 5.0
})

// Link Patient -> Encounter
MATCH (p:Patient {patient_id: "P-2026-00142"})
MATCH (e:Encounter {encounter_id: "ENC-2026-03-04-001"})
CREATE (p)-[:HAS_ENCOUNTER]->(e);

// ── Chief Complaints (Symptoms) ──

// Ateş
CREATE (s1:Symptom {
  symptom_id: randomUUID(),
  name_tr: "Ateş",
  name_en: "Fever",
  snomed_code: "386661006",
  snomed_term: "Fever (finding)",
  onset_text: "3 gün önce başladı",
  onset_days: 3.0,
  course: "stable"
});

// Göğüs Ağrısı
CREATE (s2:Symptom {
  symptom_id: randomUUID(),
  name_tr: "Göğüs ağrısı",
  name_en: "Chest pain",
  snomed_code: "29857009",
  snomed_term: "Chest pain (finding)",
  severity: 7,
  onset_days: 3.0,
  body_site: "51185008",
  body_site_name: "Göğüs / Thorax",
  course: "stable"
});

// Nefes Alma Güçlüğü (Dispne)
CREATE (s3:Symptom {
  symptom_id: randomUUID(),
  name_tr: "Nefes alma güçlüğü",
  name_en: "Dyspnea",
  snomed_code: "267036007",
  snomed_term: "Dyspnea (finding)",
  onset_text: "Son 2 gündür, yürürken zorlanıyor",
  onset_days: 2.0,
  trigger: "eforla",
  course: "worsening",
  associated_detail: "Derin nefes alınca artıyor"
});

// Sırt Ağrısı
CREATE (s4:Symptom {
  symptom_id: randomUUID(),
  name_tr: "Sırt ağrısı",
  name_en: "Back pain",
  snomed_code: "161891005",
  snomed_term: "Backache (finding)",
  severity: 7,
  body_site: "77568009",
  body_site_name: "Sırt / Back"
});

// Prodüktif Öksürük
CREATE (s5:Symptom {
  symptom_id: randomUUID(),
  name_tr: "Prodüktif öksürük",
  name_en: "Productive cough",
  snomed_code: "28743005",
  snomed_term: "Productive cough (finding)",
  character: "prodüktif",
  associated_detail: "Sarı-yeşil renkli balgam, sabahları belirgin"
});

// Link Encounter -> Symptoms
MATCH (e:Encounter {encounter_id: "ENC-2026-03-04-001"})
MATCH (s1:Symptom {snomed_code: "386661006"})
MATCH (s2:Symptom {snomed_code: "29857009"})
MATCH (s3:Symptom {snomed_code: "267036007"})
MATCH (s4:Symptom {snomed_code: "161891005"})
MATCH (s5:Symptom {snomed_code: "28743005"})
CREATE (e)-[:PRESENTS_WITH {is_chief: true}]->(s1)
CREATE (e)-[:PRESENTS_WITH {is_chief: true}]->(s2)
CREATE (e)-[:PRESENTS_WITH {is_chief: true}]->(s3)
CREATE (e)-[:PRESENTS_WITH {is_chief: false}]->(s4)
CREATE (e)-[:PRESENTS_WITH {is_chief: false}]->(s5);

// ── Allergy ──
CREATE (a:Allergy {
  allergy_id: randomUUID(),
  substance: "Penisilin",
  snomed_code: "91936005",
  severity: "severe",
  reaction_type: "anaphylaxis",
  verified: true
});

MATCH (p:Patient {patient_id: "P-2026-00142"})
MATCH (a:Allergy {snomed_code: "91936005"})
CREATE (p)-[:HAS_ALLERGY]->(a);

// ── Medication ──
CREATE (m:Medication {
  medication_id: randomUUID(),
  name: "Ramipril",
  generic_name: "Ramipril",
  dose: "5",
  unit: "mg",
  frequency: "Günde 1 kez, sabah",
  route: "oral",
  atc_code: "C09AA05",
  is_current: true
});

MATCH (p:Patient {patient_id: "P-2026-00142"})
MATCH (m:Medication {name: "Ramipril"})
CREATE (p)-[:TAKES_MEDICATION]->(m);

// ── Chronic Condition ──
CREATE (cc:ChronicCondition {
  condition_id: randomUUID(),
  name_tr: "Hipertansiyon",
  name_en: "Essential hypertension",
  snomed_code: "59621000",
  status: "active"
});

MATCH (p:Patient {patient_id: "P-2026-00142"})
MATCH (cc:ChronicCondition {snomed_code: "59621000"})
CREATE (p)-[:HAS_CONDITION]->(cc);

// ── Surgery ──
CREATE (sx:Surgery {
  surgery_id: randomUUID(),
  procedure_name_tr: "Apendektomi",
  procedure_name_en: "Appendectomy",
  snomed_code: "80146002",
  year: 2015
});

MATCH (p:Patient {patient_id: "P-2026-00142"})
MATCH (sx:Surgery {snomed_code: "80146002"})
CREATE (p)-[:HAD_SURGERY]->(sx);

// ── Previous Occurrence ──
CREATE (prev:Encounter {
  encounter_id: "ENC-HIST-BRONCHITIS",
  created_at: datetime("2024-03-01T00:00:00Z"),
  encounter_type: "outpatient",
  status: "completed"
});

CREATE (prevDx:PotentialDiagnosis {
  diagnosis_id: randomUUID(),
  name_tr: "Akut Bronşit",
  name_en: "Acute bronchitis",
  snomed_code: "10509002",
  confidence: 1.0,
  urgency: "medium"
});

MATCH (p:Patient {patient_id: "P-2026-00142"})
MATCH (prev:Encounter {encounter_id: "ENC-HIST-BRONCHITIS"})
MATCH (prevDx:PotentialDiagnosis {snomed_code: "10509002"})
CREATE (p)-[:HAS_ENCOUNTER]->(prev)
CREATE (prev)-[:RESULTED_IN]->(prevDx);

// ── Symptom Correlations ──
MATCH (s1:Symptom {snomed_code: "386661006"})  // Ateş
MATCH (s5:Symptom {snomed_code: "28743005"})   // Prodüktif öksürük
CREATE (s1)-[:ASSOCIATED_WITH {correlation: 0.85}]->(s5);

MATCH (s2:Symptom {snomed_code: "29857009"})   // Göğüs ağrısı
MATCH (s3:Symptom {snomed_code: "267036007"})  // Dispne
CREATE (s2)-[:ASSOCIATED_WITH {correlation: 0.78}]->(s3);

// ── Potential Diagnoses ──
CREATE (dx1:PotentialDiagnosis {
  diagnosis_id: randomUUID(),
  name_tr: "Pnömoni (Toplum Kökenli)",
  name_en: "Community-acquired pneumonia",
  snomed_code: "385093006",
  confidence: 0.82,
  evidence_count: 5,
  urgency: "high"
});

CREATE (dx2:PotentialDiagnosis {
  diagnosis_id: randomUUID(),
  name_tr: "Akut Bronşit",
  name_en: "Acute bronchitis",
  snomed_code: "10509002",
  confidence: 0.65,
  evidence_count: 3,
  urgency: "medium"
});

CREATE (dx3:PotentialDiagnosis {
  diagnosis_id: randomUUID(),
  name_tr: "Plevral Efüzyon",
  name_en: "Pleural effusion",
  snomed_code: "60046008",
  confidence: 0.45,
  evidence_count: 2,
  urgency: "high"
});

// Link Symptoms -> Diagnoses
MATCH (s1:Symptom {snomed_code: "386661006"})
MATCH (s2:Symptom {snomed_code: "29857009"})
MATCH (s3:Symptom {snomed_code: "267036007"})
MATCH (s5:Symptom {snomed_code: "28743005"})
MATCH (dx1:PotentialDiagnosis {snomed_code: "385093006"})
MATCH (dx2:PotentialDiagnosis {snomed_code: "10509002"})
MATCH (dx3:PotentialDiagnosis {snomed_code: "60046008"})
CREATE (s1)-[:MAY_INDICATE {probability: 0.9, evidence_level: "strong"}]->(dx1)
CREATE (s2)-[:MAY_INDICATE {probability: 0.7, evidence_level: "moderate"}]->(dx1)
CREATE (s3)-[:MAY_INDICATE {probability: 0.8, evidence_level: "strong"}]->(dx1)
CREATE (s5)-[:MAY_INDICATE {probability: 0.95, evidence_level: "strong"}]->(dx1)
CREATE (s1)-[:MAY_INDICATE {probability: 0.7, evidence_level: "moderate"}]->(dx2)
CREATE (s5)-[:MAY_INDICATE {probability: 0.85, evidence_level: "strong"}]->(dx2)
CREATE (s2)-[:MAY_INDICATE {probability: 0.5, evidence_level: "weak"}]->(dx3)
CREATE (s3)-[:MAY_INDICATE {probability: 0.6, evidence_level: "moderate"}]->(dx3);

// ── Drug Class & Contraindication ──
CREATE (dc:DrugClass {
  class_id: "BETA_LACTAM",
  name: "Beta-laktam Antibiyotikler",
  atc_prefix: "J01C"
});

MATCH (a:Allergy {snomed_code: "91936005"})
MATCH (dc:DrugClass {class_id: "BETA_LACTAM"})
CREATE (a)-[:CONTRAINDICATES {mechanism: "Cross-reactivity with penicillin allergy"}]->(dc);

// ACE Inhibitor side effect - cough
CREATE (ace_class:DrugClass {
  class_id: "ACE_INHIBITOR",
  name: "ACE İnhibitörleri",
  atc_prefix: "C09A"
});

MATCH (m:Medication {name: "Ramipril"})
MATCH (ace:DrugClass {class_id: "ACE_INHIBITOR"})
CREATE (m)-[:BELONGS_TO]->(ace);

// ACE inhibitor -> may cause cough (SNOMED: 49727002 = Cough)
CREATE (cough_effect:SnomedConcept {
  concept_id: "49727002",
  preferred_term: "Cough (finding)",
  semantic_tag: "finding"
});

MATCH (m:Medication {name: "Ramipril"})
MATCH (ce:SnomedConcept {concept_id: "49727002"})
CREATE (m)-[:MAY_CAUSE {frequency: "common (5-20%)"}]->(ce);


// ────────────────────────────────────────────────────────────
// 5. CLINICAL QUERY LIBRARY
// ────────────────────────────────────────────────────────────

// ── Q1: Hastanın tüm graph'ını çek (Doktor Dashboard) ──
MATCH (p:Patient {patient_id: $patientId})-[:HAS_ENCOUNTER]->(e:Encounter {status: "active"})
OPTIONAL MATCH (e)-[:PRESENTS_WITH]->(s:Symptom)
OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(a:Allergy)
OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication {is_current: true})
OPTIONAL MATCH (p)-[:HAS_CONDITION]->(cc:ChronicCondition)
OPTIONAL MATCH (p)-[:HAD_SURGERY]->(sx:Surgery)
RETURN p, e,
  collect(DISTINCT s) AS symptoms,
  collect(DISTINCT a) AS allergies,
  collect(DISTINCT m) AS medications,
  collect(DISTINCT cc) AS conditions,
  collect(DISTINCT sx) AS surgeries;


// ── Q2: Semptom -> Olası Tanı Zinciri (Clinical Reasoning Path) ──
MATCH (e:Encounter {encounter_id: $encounterId})-[:PRESENTS_WITH]->(s:Symptom)
MATCH (s)-[mi:MAY_INDICATE]->(dx:PotentialDiagnosis)
WITH dx, 
     collect({symptom: s.name_tr, probability: mi.probability, evidence: mi.evidence_level}) AS evidence,
     avg(mi.probability) AS avg_probability,
     count(s) AS supporting_symptoms
ORDER BY avg_probability DESC, supporting_symptoms DESC
RETURN dx.name_tr AS diagnosis,
       dx.snomed_code AS snomed,
       dx.urgency AS urgency,
       round(avg_probability * 100) AS confidence_pct,
       supporting_symptoms,
       evidence;


// ── Q3: Alerji Kontrol - Kontrendike İlaçlar ──
MATCH (p:Patient {patient_id: $patientId})-[:HAS_ALLERGY]->(a:Allergy)
MATCH (a)-[:CONTRAINDICATES]->(dc:DrugClass)
OPTIONAL MATCH (dc)<-[:BELONGS_TO]-(contraindicated_med:Medication)
RETURN a.substance AS allergen,
       a.severity AS allergy_severity,
       dc.name AS drug_class,
       dc.atc_prefix AS atc_prefix,
       collect(contraindicated_med.name) AS avoid_medications;


// ── Q4: ACE İnhibitör Yan Etki Kontrolü ──
// Hasta öksürük şikayeti + ACE inhibitör kullanımı = uyarı
MATCH (p:Patient {patient_id: $patientId})-[:TAKES_MEDICATION]->(m:Medication)
MATCH (m)-[:MAY_CAUSE]->(effect:SnomedConcept)
MATCH (p)-[:HAS_ENCOUNTER]->(e:Encounter {status: "active"})-[:PRESENTS_WITH]->(s:Symptom)
WHERE s.snomed_code = effect.concept_id
   OR s.name_en CONTAINS effect.preferred_term
RETURN m.name AS medication,
       m.dose + " " + m.unit AS dosage,
       effect.preferred_term AS potential_side_effect,
       s.name_tr AS matching_symptom,
       "Bu semptom ilaç yan etkisi olabilir" AS alert_message;


// ── Q5: Tüm Klinik Uyarıları Üret ──
MATCH (p:Patient {patient_id: $patientId})-[:HAS_ENCOUNTER]->(e:Encounter {status: "active"})

// Allergy alerts
OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(a:Allergy)-[:CONTRAINDICATES]->(dc:DrugClass)
WITH p, e, collect({
  type: "ALLERGY_CONTRAINDICATION",
  severity: "critical",
  message: "⚠️ " + a.substance + " alerjisi - " + dc.name + " grubu kontrendike"
}) AS allergy_alerts

// Side effect alerts
OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)-[:MAY_CAUSE]->(effect:SnomedConcept)
OPTIONAL MATCH (e)-[:PRESENTS_WITH]->(s:Symptom)
WHERE s.snomed_code = effect.concept_id
WITH p, e, allergy_alerts, collect(CASE WHEN s IS NOT NULL THEN {
  type: "SIDE_EFFECT_MATCH",
  severity: "warning",
  message: "💊 " + s.name_tr + " semptomu " + m.name + " yan etkisi olabilir"
} END) AS side_effect_alerts

// High severity symptoms
OPTIONAL MATCH (e)-[:PRESENTS_WITH]->(hs:Symptom)
WHERE hs.severity >= 7
WITH allergy_alerts, side_effect_alerts, collect({
  type: "HIGH_SEVERITY",
  severity: "warning",
  message: "🔴 " + hs.name_tr + " - Şiddet: " + toString(hs.severity) + "/10"
}) AS severity_alerts

RETURN allergy_alerts + side_effect_alerts + severity_alerts AS all_alerts;


// ── Q6: Encounter Özet Raporu (Doktor için) ──
MATCH (p:Patient {patient_id: $patientId})-[:HAS_ENCOUNTER]->(e:Encounter {encounter_id: $encounterId})
OPTIONAL MATCH (e)-[pw:PRESENTS_WITH]->(s:Symptom)
WITH p, e, s, pw
ORDER BY pw.is_chief DESC, s.severity DESC
WITH p, e, collect({
  name: s.name_tr,
  snomed: s.snomed_code,
  severity: s.severity,
  onset_days: s.onset_days,
  is_chief: pw.is_chief,
  course: s.course,
  detail: s.associated_detail
}) AS symptom_list

OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(a:Allergy)
WITH p, e, symptom_list, collect({
  substance: a.substance,
  severity: a.severity,
  reaction: a.reaction_type
}) AS allergy_list

OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication {is_current: true})
WITH p, e, symptom_list, allergy_list, collect({
  name: m.name,
  dose: m.dose + " " + m.unit,
  frequency: m.frequency
}) AS med_list

OPTIONAL MATCH (p)-[:HAS_CONDITION]->(cc:ChronicCondition)
WITH p, e, symptom_list, allergy_list, med_list, collect({
  condition: cc.name_tr,
  status: cc.status
}) AS condition_list

OPTIONAL MATCH (p)-[:HAD_SURGERY]->(sx:Surgery)
RETURN p {.patient_id, .birth_year, .gender} AS patient,
       e {.encounter_id, .created_at, .last_oral_intake, .last_oral_hours} AS encounter,
       symptom_list AS symptoms,
       allergy_list AS allergies,
       med_list AS current_medications,
       condition_list AS chronic_conditions,
       collect({procedure: sx.procedure_name_tr, year: sx.year}) AS surgical_history;


// ── Q7: Semptom Korelasyon Ağı ──
MATCH (e:Encounter {encounter_id: $encounterId})-[:PRESENTS_WITH]->(s1:Symptom)
MATCH (e)-[:PRESENTS_WITH]->(s2:Symptom)
WHERE id(s1) < id(s2)
OPTIONAL MATCH (s1)-[assoc:ASSOCIATED_WITH]-(s2)
RETURN s1.name_tr AS symptom_1,
       s2.name_tr AS symptom_2,
       s1.snomed_code AS snomed_1,
       s2.snomed_code AS snomed_2,
       COALESCE(assoc.correlation, 0) AS correlation;


// ── Q8: Geçmiş Karşılaştırma (Previous Occurrence) ──
MATCH (p:Patient {patient_id: $patientId})-[:HAS_ENCOUNTER]->(e:Encounter)
OPTIONAL MATCH (e)-[:PRESENTS_WITH]->(s:Symptom)
OPTIONAL MATCH (e)-[:RESULTED_IN]->(dx:PotentialDiagnosis)
WITH e, collect(DISTINCT s.name_tr) AS symptoms, collect(DISTINCT dx.name_tr) AS diagnoses
ORDER BY e.created_at DESC
RETURN e.encounter_id AS encounter,
       e.created_at AS date,
       e.status AS status,
       symptoms,
       diagnoses;
