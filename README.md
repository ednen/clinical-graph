# Clinical Complaint Graph System

> Digital anamnesis → SNOMED CT mapping → Neo4j knowledge graph → Clinical decision support report

A clinical decision support system that transforms patient-reported complaints (in Turkish) into a structured **SNOMED CT**-coded **Neo4j knowledge graph**, enabling automated clinical reasoning, drug interaction checks, and physician-ready reports.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐     ┌──────────────┐
│  Patient     │────▶│  SNOMED Mapper   │────▶│  Neo4j      │────▶│  Clinical    │
│  Complaint   │     │  (TR → EN → CT)  │     │  Graph DB   │     │  Report +    │
│  Form        │     │  Snowstorm API   │     │             │     │  Alerts      │
└─────────────┘     └──────────────────┘     └─────────────┘     └──────────────┘
```

## Features

- **Turkish NLP preprocessing** — Tokenizes free-text patient complaints, extracts severity scores and onset durations
- **SNOMED CT mapping** — Maps Turkish symptoms to SNOMED CT codes via local dictionary (80+ terms) with Snowstorm API validation
- **Neo4j knowledge graph** — Stores patient encounters, symptoms, allergies, medications, chronic conditions, and surgical history as a connected graph
- **Clinical reasoning engine** — Traverses symptom→diagnosis paths with weighted probabilities
- **Drug safety alerts** — Detects allergy contraindications (e.g., Penicillin allergy → Beta-lactam group) and medication side effects (e.g., ACE inhibitor → cough)
- **REST API** — FastAPI backend with Swagger docs for form submission, graph retrieval, and report generation
- **React dashboard** — Interactive force-directed graph visualization, complaint form, and clinical report view

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | Neo4j 5.17 (Community) |
| Backend | Python 3.11, FastAPI, neo4j-driver |
| Terminology | SNOMED CT via Snowstorm API (IHTSDO) |
| Frontend | React, Canvas API (force-directed graph) |
| Infrastructure | Docker Compose |

## Quick Start

```bash
# 1. Start Neo4j
docker compose up neo4j -d

# 2. Install Python dependencies
cd backend
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 3. Seed the database with sample patient data
python seed_neo4j.py

# 4. Start the API server
uvicorn api:app --reload --port 8000

# 5. Run end-to-end tests (new terminal)
python test_pipeline.py
```

## Service URLs

| Service | URL |
|---------|-----|
| Neo4j Browser | http://localhost:7474 (`neo4j` / `clinical2026`) |
| API Swagger UI | http://localhost:8000/docs |
| API Health | http://localhost:8000/api/health |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/complaints/submit` | Submit patient complaint form → SNOMED map → write to Neo4j |
| `GET` | `/api/patients/{id}/graph` | Get patient graph (D3/vis.js compatible nodes + edges) |
| `GET` | `/api/encounters/{id}/report` | Generate clinical report with diagnoses and alerts |
| `GET` | `/api/snomed/search?term=fever` | Search SNOMED CT concepts via Snowstorm |

## Graph Model

```
(:Patient)-[:HAS_ENCOUNTER]->(:Encounter)
(:Encounter)-[:PRESENTS_WITH]->(:Symptom)
(:Patient)-[:HAS_ALLERGY]->(:Allergy)
(:Patient)-[:TAKES_MEDICATION]->(:Medication)
(:Patient)-[:HAS_CONDITION]->(:ChronicCondition)
(:Patient)-[:HAD_SURGERY]->(:Surgery)
(:Symptom)-[:MAY_INDICATE]->(:PotentialDiagnosis)
(:Symptom)-[:ASSOCIATED_WITH]->(:Symptom)
(:Allergy)-[:CONTRAINDICATES]->(:DrugClass)
(:Medication)-[:MAY_CAUSE]->(:SnomedConcept)
```

## Sample Patient (from seed data)

| Field | Value | SNOMED CT |
|-------|-------|-----------|
| Chief complaints | Fever, Chest pain, Dyspnea | 386661006, 29857009, 267036007 |
| Allergy | Penicillin (severe) | 91936005 |
| Medication | Ramipril 5mg daily | ATC: C09AA05 |
| Chronic condition | Hypertension | 59621000 |
| Surgical history | Appendectomy (2015) | 80146002 |

**Generated alerts:**
- Penicillin allergy → Beta-lactam antibiotics contraindicated
- Ramipril (ACE inhibitor) → May cause cough (matches patient symptom)

## Project Structure

```
clinical-graph/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── api.py                  # FastAPI endpoints
│   ├── snomed_mapper.py        # Turkish → SNOMED CT mapping service
│   ├── seed_neo4j.py           # Database seeder with sample data
│   ├── test_pipeline.py        # End-to-end test suite
│   ├── schema.cypher           # Neo4j schema reference & queries
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    └── src/
        └── App.jsx             # React clinical dashboard
```

## SNOMED CT Mapping Strategy

```
Turkish free text → Normalize → Token split
                                    ↓
                            Local dictionary (80+ terms)
                                    ↓
                    ┌───── Match found? ─────┐
                    ↓ Yes                    ↓ No
            Snowstorm API              Fuzzy search
            validate code              via Snowstorm
                    ↓                        ↓
              Return with               Return best
              95% confidence            50% confidence
                    ↓ (API fail)
              Local fallback
              85% confidence
```

## License

MIT
