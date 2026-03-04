# Hasta Şikayet Graph Sistemi

Dijital anamnez → SNOMED CT → Neo4j Graph → Klinik Rapor

## Hızlı Başlangıç

```bash
# 1. Neo4j başlat
docker compose up neo4j -d

# 2. Python ortamını kur
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Örnek veri yükle
python seed_neo4j.py

# 4. API başlat
uvicorn api:app --reload --port 8000

# 5. Test et (yeni terminal, venv aktif)
python test_pipeline.py
```

## Kontrol Adresleri

| Servis | URL |
|--------|-----|
| Neo4j Browser | http://localhost:7474 (neo4j / clinical2026) |
| API Swagger | http://localhost:8000/docs |
| API Health | http://localhost:8000/api/health |

## Klasör Yapısı

```
clinical-graph/
├── docker-compose.yml          ← Neo4j container
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── api.py                  ← FastAPI backend
│   ├── snomed_mapper.py        ← Türkçe→SNOMED CT mapping
│   ├── seed_neo4j.py           ← Örnek veri yükleyici
│   ├── test_pipeline.py        ← End-to-end test suite
│   └── schema.cypher           ← Neo4j şema referansı
└── frontend/
    └── src/
        └── App.jsx             ← React dashboard
```

## Detaylı Kurulum

Tüm adımlar ve troubleshooting için bakınız: aşağıdaki 6 aşama.

### Aşama 1 — Neo4j

```bash
docker compose up neo4j -d
docker compose logs -f neo4j     # "Started." yazana kadar bekle (~30sn)
```

Docker yoksa: [Neo4j Desktop](https://neo4j.com/download/) indir, şifre `clinical2026` yap.

### Aşama 2 — Python Paketleri

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### Aşama 3 — Seed (Örnek Veri)

```bash
python seed_neo4j.py
# ✅ Seed tamamlandı!
# 🎉 Neo4j başarıyla dolduruldu.
```

Kontrol: http://localhost:7474 → `MATCH (n) RETURN n LIMIT 50`

### Aşama 4 — API Başlat

```bash
uvicorn api:app --reload --port 8000
```

Test:
```bash
curl http://localhost:8000/api/health
curl "http://localhost:8000/api/snomed/search?term=fever&limit=3"
```

### Aşama 5 — Full Test

```bash
python test_pipeline.py
```

6 test çalıştırır: preprocessor → Snowstorm API → SNOMED mapping → API health → full pipeline → Neo4j sorguları.

### Aşama 6 — Frontend (opsiyonel)

```bash
cd ../frontend
npm create vite@latest . -- --template react
npm install
# src/App.jsx zaten mevcut
npm run dev
# → http://localhost:5173
```

## Sık Sorunlar

| Hata | Çözüm |
|------|-------|
| `ServiceUnavailable` | `docker compose up neo4j -d` |
| `ConnectTimeout` (Snowstorm) | İnternet gerekli, offline'da local map kullanılır |
| `Address already in use :8000` | `lsof -i :8000` → `kill <PID>` |
| `authentication failure` | Neo4j şifresi: `clinical2026` |
