# Lab Report AI Interpretation API – Comprehensive Specification (v2.1)

---

## 1. Intent

The **Lab Report AI Interpretation API** is a full-stack system designed to:
- Interpret clinical lab reports (blood, urine, stool, and standard clinical tests) for **educational insights**, **not diagnosis**.
- Provide structured outputs in Markdown and PDF with visual indicators (Red/Yellow/Green) and bar + gauge charts for abnormal or critical values.
- Support multi-language output (English + Urdu for v1) while **preserving medical terms** in parenthetical English.
- Ensure privacy via **PII sanitization** (all personal info scrubbed) and temporary storage (24–48 hours).
- Support **Website** uploads (Next.js) and **WhatsApp** chat interface (Twilio).
- Provide reference range sourcing (extracted from report; fallback to LLM medical knowledge with explicit note).

**Non-Goals / Out-of-Scope:**
- No medical diagnosis or treatment recommendation.
- No mobile app (v1).
- No multi-language input reports (English only).
- No EHR/EMR integration.
- No permanent data storage beyond retention period.
- No user accounts or authentication (v1) — reCAPTCHA only.
- No CI/CD pipeline (deferred to later stages).
- No advanced analytics beyond WhatsApp trends.

---

## 2. Architecture & Tech Stack

### Architecture Overview
- **Monorepo** structure: `/frontend` (Next.js) and `/backend` (FastAPI) in a single repository.
- **Async processing** via Celery workers — upload returns a `job_id`, frontend polls for status.
- **Docker Compose** orchestrates all services.

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js (React) | Website UI |
| UI Components | Tailwind CSS + shadcn/ui | Styling and component library |
| Bot Protection | Google reCAPTCHA v3 | Invisible CAPTCHA on website |
| Backend API | FastAPI | REST API |
| Async Tasks | Celery + Redis | Background report processing |
| LLM Framework | LangChain | LLM orchestration (prompts, chains, output parsing) |
| LLM Analysis | GPT-4o (configurable) | Main report interpretation |
| LLM Validation | GPT-4o-mini (configurable) | Pre-validation (is it a lab report?) |
| OCR | PaddleOCR | Text extraction from images/PDFs |
| PDF Generation | WeasyPrint | HTML-to-PDF conversion |
| Charts | Matplotlib | Bar charts + gauge charts |
| Database | MySQL (SQLAlchemy + Alembic) | Report records persistence |
| Cache/Broker | Redis | Celery broker + WhatsApp session state |
| WhatsApp | Twilio WhatsApp Business API | Chat interface |
| Deployment | Docker Compose | Container orchestration |
| File Storage | Docker Volume | Uploaded files + generated PDFs |
| Logging | Python standard logging | Application logging |
| Prompts | Separate `.txt` files in `/prompts` | LLM prompt templates |

---

## 3. Success Criteria

- **Functional:**
  - Reports analyzed and returned in Markdown + PDF with all 7 output sections.
  - Bar + gauge charts generated for abnormal/critical values.
  - Reference ranges clearly identified with source noted.
  - WhatsApp bot collects age/gender before processing report.
- **Performance:**
  - Response time: 5–15 seconds per report.
  - Handles concurrent uploads without failure.
  - Polling-based async — instant job acknowledgment.
- **Safety / Accuracy:**
  - Mandatory disclaimers on all outputs.
  - Color coding (green/yellow/red) reflects LLM severity + rule-based mapping.
  - Urdu translation preserves medical terms in parenthetical English.
- **Configurability:**
  - File limits, page limits, LLM models, OCR engine, retention period, rate limits, and validation thresholds adjustable via environment variables.

---

## 4. Inputs / Outputs / Interfaces

### Inputs

| Field | Type | Notes |
|-------|------|-------|
| `user_id` | string | Unique session identifier; tracks WhatsApp flow |
| `age` | integer | Patient age; mandatory for WhatsApp, optional for website |
| `gender` | string | Male / Female / Other; mandatory for WhatsApp, optional for website |
| `language` | string | ISO code: `en` or `ur` (v1); defaults to `en` |
| `file` | file (multipart) | Uploaded report (PDF/JPG/PNG) — website uses multipart upload |
| `file_type` | string | MIME type: `application/pdf`, `image/jpeg`, `image/png` |
| `captcha_token` | string | Google reCAPTCHA v3 token (website only) |

### Outputs

| Output | Type | Notes |
|--------|------|-------|
| Markdown | string | Full 7-section interpretation with color indicators |
| PDF | file | Includes bar + gauge charts, color-coded tables (WeasyPrint) |
| Charts | image | Bar charts + gauge charts via Matplotlib, embedded in PDF |
| Error | JSON | Standardized: `{ "status": "error", "code": int, "message": str }` |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/analyze-report` | Submit report; returns `{ "job_id": "..." }` |
| GET | `/v1/status/{job_id}` | Poll status; returns status, markdown, pdf_url, error |
| GET | `/v1/download/{job_id}` | Download generated PDF |
| POST | `/v1/whatsapp/webhook` | Twilio WhatsApp incoming webhook |
| GET | `/v1/health` | Health check for all services |

### Interfaces
- **Website:** Next.js upload form (file, age, gender, language selector) with reCAPTCHA v3. Polling-based loading UX with spinner — "Your report is being processed." Results rendered as formatted markdown with PDF download button.
- **WhatsApp:** Twilio webhook. Bot sends brief text message ("Your report is ready") + PDF attachment. No raw markdown over WhatsApp.
- **Storage:** Docker volume for uploaded files and generated PDFs. Auto-deleted after 24–48 hours.

---

## 5. Workflow / Logic

### Website Flow
1. User enters age/gender (optional), selects language, uploads report file. reCAPTCHA v3 validates.
2. System validates file type, size (≤20 MB), and page count (≤30 pages).
3. Backend saves file, creates DB record, dispatches Celery task, returns `job_id`.
4. Frontend redirects to results page, polls `GET /v1/status/{job_id}` every 2–3 seconds with loading spinner.
5. **Celery task pipeline:**
   a. OCR extraction (PaddleOCR) — extract text from image/PDF.
   b. Pre-validation — cheap LLM (GPT-4o-mini) confirms extracted text is a lab report.
   c. PII scrubbing — remove all personal info from OCR text.
   d. LLM analysis — GPT-4o interprets scrubbed text (English), returns structured JSON.
   e. Translation — if language ≠ English, translate via LLM (medical terms preserved with English in parentheses).
   f. Chart generation — Matplotlib creates bar + gauge charts for abnormal/critical values.
   g. PDF generation — WeasyPrint renders HTML template with charts and color-coded tables.
6. Frontend detects completion, renders markdown interpretation, shows PDF download button.
7. Error handling: invalid file, unreadable scan, unsupported lab, LLM failure — all return user-friendly messages.

### WhatsApp Flow (Twilio)
1. Bot prompts sequentially: Age → Gender → Report upload.
2. Redis state machine per phone number: `AWAITING_AGE` → `AWAITING_GENDER` → `AWAITING_REPORT` → `PROCESSING`.
3. System validates file, runs same Celery pipeline as website.
4. On completion, bot sends brief text message + PDF attachment via Twilio.
5. Incomplete sessions auto-expire after 30 minutes (Redis TTL).
6. Handle edge cases: invalid age/gender input (retry prompt), blurred images, unsupported labs.

### Edge Cases / Exceptions
- **Blurred / low-quality images:** Attempt OCR → detect garbage text via heuristic → reject with re-upload message.
- **Unsupported/excessively long reports:** Enforce file size and page limits.
- **Non-English input:** Reports must be English; translation applied only to output.
- **Non-lab documents:** Pre-validation rejects with "This does not appear to be a lab report."
- **LLM failure:** Retry once; on second failure, return error message.
- **Chart/PDF failure:** Still return markdown (graceful degradation); log warning.

---

## 6. Output Format

### Interpretation Sections (ordered)
1. **Patient Info** — Age, gender (if provided), report date
2. **Summary** — 2–3 sentence high-level overview of findings
3. **Category-wise Results** — Grouped by: CBC, Liver Panel, Kidney Panel, Thyroid, Lipid Profile, etc. Each test shows: name, value, unit, reference range, source, severity
4. **Abnormal Values Analysis** — Detailed explanation of out-of-range values
5. **Clinical Associations** — Educational associations (not diagnostic)
6. **Lifestyle Tips** — General wellness recommendations related to findings
7. **Disclaimer** — Mandatory on every output

### Color Coding (Hybrid)
LLM assigns severity categories per test value. System applies consistent color mapping:
- 🟢 **Green (Normal)** — Within reference range
- 🟡 **Yellow (Borderline)** — Slightly outside reference range
- 🔴 **Red (Critical)** — Significantly abnormal

**Severity indicators in markdown:** Use emoji circles (🟢 🟡 🔴) for universal rendering in markdown, web, and terminals. Frontend renders backend-generated markdown via `react-markdown` (not custom React components from JSON).

### Charts
- **Bar charts** — Horizontal bars per test category. Each test value vs. reference range. Color-coded green/yellow/red. Only generated for numeric test values (string values like "Positive" are skipped).
- **Gauge charts** — Speedometer-style for both **critical and borderline** values. Shows where patient's value falls within the overall range. Only for numeric values.
- **Placement in PDF** — Charts placed inline after each category table (bar chart → gauge charts for that category's abnormal values).

### PDF Layout
- **Header** on each page: "Lab Report AI - Analysis Report"
- **Footer** on each page: page number + brief disclaimer note
- Professional, clean layout with color-coded table rows

### Reference Ranges
- LLM extracts reference ranges from the lab report text.
- If not present on the report, LLM uses its medical knowledge and the output explicitly states: *"Reference values not available in the report; ranges based on standard medical knowledge."*

### Translation (v1)
- **Languages:** English + Urdu
- **Medical terms:** Translated to target language with English in parentheses.
  - Example: ہیموگلوبن (Hemoglobin) کی سطح نارمل ہے۔
- **RTL support** in PDF output for Urdu.

### Mandatory Disclaimer
> "This report provides educational insights and clinical associations only. It is not a diagnosis or treatment recommendation. Please consult a qualified physician."

---

## 7. Configuration Options

All options configurable via environment variables (`.env` file).

| Option | Default | Purpose |
|--------|---------|---------|
| `MAX_FILE_SIZE` | 20 MB | Maximum upload file size |
| `MAX_PAGES` | 30 | Maximum page count per report |
| `RETENTION_PERIOD` | 48h | Temporary storage auto-deletion period |
| `VALIDATION_THRESHOLD` | 0.8 | Pre-validation LLM confidence threshold |
| `LLM_ANALYSIS_MODEL` | gpt-4o | Primary LLM model for report analysis |
| `LLM_VALIDATION_MODEL` | gpt-4o-mini | Cheap LLM for pre-validation |
| `LLM_API_KEY` | (required) | OpenAI API key |
| `OCR_ENGINE` | PaddleOCR | OCR engine; alternative: `aws_textract` |
| `RATE_LIMIT_PER_IP` | 10/hour | Maximum report submissions per IP per hour |
| `RECAPTCHA_SECRET_KEY` | (required) | Google reCAPTCHA v3 server-side secret |
| `RECAPTCHA_SITE_KEY` | (required) | Google reCAPTCHA v3 client-side key |
| `TWILIO_ACCOUNT_SID` | (required for WhatsApp) | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | (required for WhatsApp) | Twilio auth token |
| `TWILIO_WHATSAPP_NUMBER` | (required for WhatsApp) | Twilio WhatsApp sender number |
| `MYSQL_URL` | mysql://localhost:3306/labreportai | MySQL connection string |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection string |

---

## 8. Safety, Security & Privacy

### PII Sanitization
All personal information scrubbed from OCR text **before** sending to the LLM:

| PII Type | Action |
|----------|--------|
| Patient Name | Replaced with `[REDACTED]` |
| Patient ID / MRN | Removed |
| Phone Number | Replaced with `[PHONE_REDACTED]` |
| Address | Removed |
| Date of Birth | Replaced with `[DOB_REDACTED]` (age passed separately) |
| Doctor Name | Replaced with `[DOCTOR_REDACTED]` |
| Hospital / Lab Name | Replaced with `[LAB_REDACTED]` |

### Security Measures
- **HTTPS** required for all communications.
- **Google reCAPTCHA v3** (invisible, score-based) on website uploads.
- **Per-IP rate limiting** — 10 requests/hour (configurable).
- **No user authentication** for v1 — anonymous usage.
- Temporary file storage with **24–48h auto-deletion** via Celery Beat.
- No permanent storage of uploaded lab reports or generated outputs.

---

## 9. Database Schema

### MySQL — `reports` Table (v1)

| Column | Type | Notes |
|--------|------|-------|
| `id` | VARCHAR(36) PK | UUID |
| `job_id` | VARCHAR(36) UNIQUE | Celery task ID |
| `status` | ENUM | `pending`, `processing`, `completed`, `failed` |
| `file_path` | VARCHAR(500) | Path to uploaded file in storage volume |
| `file_type` | VARCHAR(50) | MIME type |
| `age` | INTEGER | Nullable |
| `gender` | VARCHAR(10) | Nullable |
| `language` | VARCHAR(5) | Default `en` |
| `ocr_text` | LONGTEXT | Scrubbed OCR text; nullable |
| `result_json` | LONGTEXT | Structured LLM output as JSON; nullable |
| `result_markdown` | LONGTEXT | Rendered markdown; nullable |
| `result_pdf_path` | VARCHAR(500) | Path to generated PDF; nullable |
| `error_message` | TEXT | Error details if failed; nullable |
| `source` | ENUM | `web`, `whatsapp`; default `web` |
| `whatsapp_number` | VARCHAR(20) | Phone number for WhatsApp reports; nullable |
| `ip_address` | VARCHAR(45) | Client IP for rate limiting |
| `expires_at` | DATETIME | Auto-deletion timestamp |
| `created_at` | DATETIME | Server default NOW |
| `updated_at` | DATETIME | On update NOW |

**Note:** User management tables deferred to future versions.

### Redis Keys
- `celery` — Celery broker and result backend
- `whatsapp:{phone_number}` — JSON hash: `{ state, age, gender, job_id }`. TTL: 30 minutes.
- `rate_limit:{ip}` — Integer counter. TTL: 1 hour.

---

## 10. Acceptance Criteria / Test Scenarios

1. Upload PDF/JPG/PNG → validated → OCR → LLM analysis → Markdown + PDF returned
2. WhatsApp flow: sequential Age/Gender/Report capture via Twilio → text + PDF delivered
3. WhatsApp sends brief text message + PDF attachment (no raw markdown)
4. Blurred/low-quality images → rejected with re-upload message
5. Non-lab documents (receipt, letter) → rejected with "not a lab report" message
6. Urdu translation preserves medical terms in parenthetical English
7. Bar + gauge charts accurately reflect abnormal/critical values in PDF
8. All configuration options applied correctly (file size, pages, LLM model, OCR engine)
9. Reference range sources displayed; fallback note shown when ranges not on report
10. Disclaimers present on all Markdown and PDF outputs
11. reCAPTCHA v3 blocks bot submissions on website
12. Per-IP rate limiting enforced — 11th request in 1 hour returns 429
13. PII fully scrubbed — no personal info reaches the LLM
14. Files auto-deleted after retention period (24–48h)
15. Polling endpoint returns correct status transitions: `pending` → `processing` → `completed`/`failed`
16. Docker Compose starts all services: FastAPI, Celery worker, Celery Beat, Redis, MySQL, Next.js

---

## 11. Project Structure

```
labreportai/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Caddyfile
├── deploy.sh
├── .env.example
├── .env.production.example
├── .gitignore
├── README.md
├── spec.md
│
├── frontend/
│   ├── Dockerfile
│   ├── Dockerfile.prod
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── .env.local.example
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx
│       │   ├── globals.css
│       │   └── report/[jobId]/page.tsx
│       ├── components/
│       │   ├── ui/                  (shadcn/ui components)
│       │   ├── UploadForm.tsx
│       │   ├── ReportView.tsx
│       │   ├── StatusPoller.tsx
│       │   └── DisclaimerBanner.tsx
│       ├── lib/
│       │   ├── api.ts
│       │   └── utils.ts
│       └── types/
│           └── index.ts
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  (FastAPI app factory)
│   │   ├── config.py                (Pydantic Settings)
│   │   ├── dependencies.py
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   ├── v1/
│   │   │   │   ├── reports.py       (POST /analyze-report, GET /status, GET /download)
│   │   │   │   ├── whatsapp.py      (Twilio webhook)
│   │   │   │   └── health.py        (GET /health)
│   │   │   └── middleware.py        (rate limiting, CORS)
│   │   ├── models/
│   │   │   └── report.py            (SQLAlchemy model)
│   │   ├── schemas/
│   │   │   └── report.py            (Pydantic request/response schemas)
│   │   ├── services/
│   │   │   ├── ocr.py               (PaddleOCR wrapper)
│   │   │   ├── pii_scrubber.py      (Regex-based PII removal)
│   │   │   ├── llm_validator.py     (Pre-validation with GPT-4o-mini)
│   │   │   ├── llm_analyzer.py      (Main analysis with GPT-4o)
│   │   │   ├── translator.py        (English → Urdu translation)
│   │   │   ├── chart_generator.py   (Matplotlib bar + gauge charts)
│   │   │   ├── pdf_generator.py     (WeasyPrint HTML → PDF)
│   │   │   ├── markdown_renderer.py (JSON → formatted Markdown)
│   │   │   ├── file_validator.py    (Type, size, page count validation)
│   │   │   ├── file_cleanup.py      (Auto-deletion logic)
│   │   │   └── whatsapp_sender.py   (Twilio outbound messages)
│   │   ├── tasks/
│   │   │   ├── celery_app.py        (Celery configuration)
│   │   │   ├── analyze.py           (Main pipeline task)
│   │   │   └── cleanup.py           (Periodic cleanup task)
│   │   ├── db/
│   │   │   └── session.py           (SQLAlchemy engine + session)
│   │   └── utils/
│   │       ├── logging.py           (Logging configuration)
│   │       └── recaptcha.py         (reCAPTCHA v3 verification)
│   ├── prompts/
│   │   ├── pre_validation.txt
│   │   ├── analysis.txt
│   │   └── translation.txt
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/               (Sample lab reports for testing)
│       ├── test_file_validator.py
│       ├── test_pii_scrubber.py
│       ├── test_ocr.py
│       ├── test_llm_analyzer.py
│       ├── test_chart_generator.py
│       ├── test_pdf_generator.py
│       ├── test_api_reports.py
│       ├── test_whatsapp.py
│       └── e2e/
│           ├── test_full_pipeline_web.py
│           └── test_full_pipeline_whatsapp.py
│
├── templates/
│   └── pdf/
│       ├── report.html              (Jinja2 template for WeasyPrint)
│       └── styles.css
│
└── storage/                          (Docker volume mount)
    ├── uploads/
    └── outputs/
```

---

## 12. Implementation Plan (7 Phases)

Development follows a **vertical slice** approach — each phase delivers a working increment. Minimal unit tests per phase; comprehensive E2E tests in the final phase.

### Phase 1: Foundation & Infrastructure

**Goal:** Establish the monorepo, Docker Compose infrastructure, database, Celery plumbing, and a minimal end-to-end loop with a stub task. Upload a file → see a placeholder result.

**What to build:**
- Monorepo scaffold: `/frontend` (Next.js + Tailwind + shadcn/ui), `/backend` (FastAPI)
- `docker-compose.yml` with services: `backend`, `celery-worker`, `redis`, `mysql`, `frontend`
- `.env.example` with all configuration variables
- SQLAlchemy + Alembic setup; initial migration creates `reports` table
- Pydantic Settings (`config.py`) reading env vars
- `POST /v1/analyze-report` — saves file to storage volume, creates DB row (status=`pending`), dispatches Celery task, returns `{ "job_id": "..." }`
- `GET /v1/status/{job_id}` — queries DB, returns status + results
- Stub Celery task: sleeps 3 seconds, updates DB to `completed` with placeholder markdown
- File validation service: checks MIME type, file size, page count
- Next.js upload form (file input, age, gender, language selector)
- Polling component: redirects to `/report/{jobId}`, polls every 3 seconds, shows spinner
- Basic result display (raw text for now)

**Verify:** `docker-compose up --build` → open `http://localhost:3000` → upload a PDF → see placeholder text after ~3 seconds. Invalid files rejected.

---

### Phase 2: OCR, PII Scrubbing & Pre-Validation

**Goal:** Replace the stub with real OCR extraction, PII scrubbing, and pre-validation. Upload a real lab report → see scrubbed extracted text. Non-lab documents rejected.

**What to build:**
- `ocr.py` — PaddleOCR wrapper. Handles images (direct OCR) and PDFs (convert pages to images via `pdf2image`, then OCR). Garbage text detection heuristic.
- `pii_scrubber.py` — Regex-based scrubbing for all 7 PII categories (name, ID, phone, address, DOB, doctor, hospital).
- `llm_validator.py` — LangChain + GPT-4o-mini. Loads prompt from `prompts/pre_validation.txt`. Returns `(is_lab_report, confidence)`. Compares against `VALIDATION_THRESHOLD`.
- `prompts/pre_validation.txt` — Prompt instructing LLM to classify document as lab report or not.
- Update Celery task: OCR → PII scrub → pre-validate → store scrubbed text in DB.
- Alembic migration: add `ocr_text` column.
- Update Dockerfile: add PaddleOCR system dependencies, `poppler-utils`.
- Tests: `test_file_validator.py`, `test_pii_scrubber.py`, `test_ocr.py`.

**Verify:** Upload real lab report → see scrubbed text (placeholder for analysis). Upload receipt → rejected. Upload blurred image → rejected.

---

### Phase 3: LLM Analysis (Core Intelligence)

**Goal:** Full LLM interpretation. Upload a lab report → see a complete, meaningful 7-section interpretation with color-coded indicators.

**What to build:**
- `llm_analyzer.py` — LangChain + GPT-4o. Sends scrubbed text + age/gender. Returns structured JSON matching the output schema below. Uses LangChain output parsers. Retry logic (up to 2 retries).
- `prompts/analysis.txt` — Main analysis prompt (most critical prompt in the system). Instructs LLM to produce structured JSON with all 7 sections, severity classification, reference range sourcing.
- **Structured JSON output schema:**
  ```json
  {
    "patient_info": { "age": null, "gender": null, "report_date": null },
    "summary": "...",
    "categories": [
      {
        "name": "Complete Blood Count (CBC)",
        "tests": [
          {
            "test_name": "Hemoglobin",
            "value": 12.5,
            "unit": "g/dL",
            "reference_range": "13.0 - 17.0",
            "reference_source": "report | standard_knowledge",
            "severity": "normal | borderline | critical",
            "interpretation": "..."
          }
          // Note: `value` supports both numeric (12.5) and string ("Positive", "Reactive", "1+")
          // for qualitative lab results.
        ]
      }
    ],
    "abnormal_analysis": "...",
    "clinical_associations": "...",
    "lifestyle_tips": "...",
    "disclaimer": "..."
  }
  ```
- `markdown_renderer.py` — Converts JSON to formatted markdown with emoji circle indicators (🟢/🟡/🔴), tables per category, and all 7 sections.
- Frontend: install `react-markdown` + `remark-gfm`, render backend-generated markdown in `ReportView.tsx`. No custom React components from JSON — markdown-only rendering approach.
- `value` field supports both numeric and string types for qualitative lab results (e.g., "Positive", "Reactive").
- Alembic migration: add `result_json` column if not already present.
- Tests: `test_llm_analyzer.py` (mock LLM API).

**Verify:** Upload a CBC report → see full interpretation with color-coded tables, severity labels, reference ranges, clinical associations, lifestyle tips, disclaimer.

---

### Phase 4: Charts & PDF Generation

**Goal:** Generate bar + gauge charts and a polished PDF. Upload a report → download a professional PDF with embedded charts.

**What to build:**
- `chart_generator.py` — Matplotlib:
  - `generate_bar_chart()` — Horizontal bar chart per test category. Value vs. reference range. Color-coded bars (green/yellow/red).
  - `generate_gauge_chart()` — Speedometer-style gauge for each critical/abnormal value. Green/yellow/red zones, needle pointer.
  - `generate_all_charts()` — Orchestrator. Saves PNGs to `/storage/outputs/{job_id}/charts/`.
- `pdf_generator.py` — WeasyPrint:
  - Loads Jinja2 template from `templates/pdf/report.html`.
  - Renders all 7 sections, color-coded table rows, embedded chart images.
  - Outputs PDF to `/storage/outputs/{job_id}/report.pdf`.
- `templates/pdf/report.html` — Full Jinja2 HTML template with professional layout.
- `templates/pdf/styles.css` — Print-optimized CSS: color badges, page margins, chart sizing, page breaks, disclaimer styling.
- `GET /v1/download/{job_id}` — Returns PDF via `FileResponse`.
- Frontend: "Download PDF Report" button in `ReportView.tsx`.
- Tests: `test_chart_generator.py`, `test_pdf_generator.py`.

**Verify:** Upload report with abnormal values → download PDF → verify: professional layout, color tables, bar charts per category, gauge charts for critical values, all 7 sections, disclaimer.

---

### Phase 5: Security, Rate Limiting & File Cleanup

**Goal:** Production-harden the website. reCAPTCHA blocks bots, rate limiting prevents abuse, old files auto-deleted.

**What to build:**
- `recaptcha.py` — Verifies reCAPTCHA v3 token via Google API. Returns `(success, score)`. Configurable score threshold.
- Frontend: integrate reCAPTCHA v3 script. Execute before form submit, include token in request.
- `middleware.py` — Redis-based per-IP rate limiter. Uses `INCR` + `EXPIRE` on `rate_limit:{ip}` key. Returns 429 with `Retry-After` header when exceeded.
- `file_cleanup.py` — Queries expired reports from DB, deletes files from storage, updates/removes DB records.
- `tasks/cleanup.py` — Celery task wrapping cleanup logic.
- Celery Beat schedule: run cleanup every hour.
- `docker-compose.yml` — Add `celery-beat` service.
- Alembic migration: add `expires_at` column.
- Global exception handlers in `main.py`: consistent error JSON for 422, 429, 500.
- Tests: `test_api_reports.py` (reCAPTCHA mock, rate limiting, cleanup).

**Decisions:**
- **reCAPTCHA enforcement**: Optional — auto-skipped when `RECAPTCHA_SECRET_KEY` is empty. Enforced only when keys are configured. Allows development without Google keys.
- **File cleanup behavior**: Hard delete — delete uploaded files, generated PDFs/charts, AND remove the database record entirely. No trace remains after expiry.
- **Rate limiting scope**: Upload endpoint only (`POST /v1/analyze-report`, 10/hour per IP). Status polling and PDF downloads remain unlimited.
- **Celery Beat deployment**: Separate `celery-beat` Docker container in docker-compose.yml (same image, different command). Avoids duplicate runs with multiple workers.

**Verify:** reCAPTCHA blocks invalid tokens (when keys configured). 11th request from same IP returns 429. Old records with expired files cleaned up by Celery Beat.

---

### Phase 6: Translation & WhatsApp Integration

**Goal:** Add Urdu translation and the full Twilio WhatsApp bot. Both interfaces fully functional.

**What to build:**
- `translator.py` — LangChain LLM call. Translates structured JSON from English to Urdu. Medical terms preserved with English in parentheses. Loads prompt from `prompts/translation.txt`.
- `prompts/translation.txt` — Translation prompt with strict rules for medical term preservation.
- RTL support in `templates/pdf/report.html` for Urdu output.
- Urdu fonts added to backend Docker image (`fonts-noto-extra` or bundled `.ttf`).
- Frontend: language selector triggers translation when set to Urdu.
- `v1/whatsapp.py` — Twilio webhook endpoint:
  - Receives messages, manages Redis state machine: `AWAITING_AGE` → `AWAITING_GENDER` → `AWAITING_REPORT` → `PROCESSING`.
  - Validates inputs (age: 1-120, gender: Male/Female/Other).
  - Downloads media from Twilio URL, dispatches Celery task.
  - Returns TwiML XML responses.
- `whatsapp_sender.py` — Twilio outbound: send text message + PDF media via Twilio API.
- Update Celery task: after completion for WhatsApp reports, call sender to deliver text + PDF.
- Alembic migration: add `source` (web/whatsapp) and `whatsapp_number` columns.
- Redis keys: `whatsapp:{phone_number}` with 30-minute TTL.
- Tests: `test_whatsapp.py`.

**Decisions:**
- **Twilio/WhatsApp**: Optional — endpoint registered but returns 503 when Twilio keys are empty/placeholder. No crash in dev mode.
- **Translation LLM**: Use validation model (8B) by default, but configurable via `LLM_TRANSLATION_MODEL` env var. Add `get_translation_llm()` factory.
- **Pipeline flow**: Translate JSON → render Urdu markdown → generate Urdu PDF. Charts stay numeric (language-neutral). One coherent Urdu output.
- **Urdu fonts**: Install `fonts-noto-extra` Debian package in Dockerfile.

**Verify:** Website with Urdu translation — medical terms in parentheses. WhatsApp: send age → gender → photo → receive text + PDF.

---

### Phase 7: E2E Testing, Polish & Production Readiness

**Goal:** Comprehensive testing, error hardening, frontend polish, production Docker config. System ready for deployment.

**What to build:**
- `tests/e2e/test_full_pipeline_web.py` — 10+ test scenarios: valid reports, multi-panel, blurred, receipt, oversized, Urdu, rate limit, reCAPTCHA, concurrent uploads.
- `tests/e2e/test_full_pipeline_whatsapp.py` — Full flow, invalid inputs, session timeout, message during processing.
- `tests/fixtures/` — Sample lab report files for testing.
- Error handling hardening: specific error messages per failure type in Celery task. Graceful degradation (PDF fails → still return markdown).
- Logging audit: ensure no PII or sensitive data in logs.
- Frontend polish:
  - File drag-and-drop zone.
  - Client-side file validation (type, size).
  - Progress steps during processing ("Extracting text...", "Analyzing report...", "Generating PDF...").
  - Responsive design (desktop + mobile).
  - Accessible: ARIA attributes, keyboard navigation.
  - "Upload Another Report" button.
- `v1/health.py` — Health check verifying MySQL, Redis, Celery connectivity.
- `docker-compose.prod.yml` — Production overrides: multi-stage Docker builds, `next build && next start`, uvicorn with 4 workers, health checks, restart policies, resource limits.
- Frontend Dockerfile: multi-stage build (build → standalone production).
- Backend Dockerfile: non-root user, smaller image.
- `README.md` — Setup instructions, architecture, environment variables, API docs, troubleshooting.

**Verify:**
- `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build` — all services start.
- `pytest tests/` — all unit + E2E tests pass.
- Manual: full website flow on desktop + mobile.
- Manual: full WhatsApp flow.
- `GET /v1/health` returns all services healthy.
- Docker logs: structured, no sensitive data.

**Phase 7 Implementation Decisions:**

**Decision 1 — Test Data & Fixtures:**
- Use existing sample files in `samples/` folder (no additional fixtures needed)
- Valid lab reports for positive testing:
  - `samples/Culture-Urine.pdf`
  - `samples/HIGH SENSITIVE TROPONIN -I.pdf`
  - `samples/Urine DR.pdf`
- Non-lab documents for rejection testing:
  - `samples/Lab Receipt.pdf`
  - `samples/Lab Receipt2.pdf`
- Total: 3 valid reports + 2 rejection test cases

**Decision 2 — LLM Testing Strategy:**
- Use real LLM calls for E2E tests (Option A)
- Tests will verify actual integration with LLM providers
- Requires valid API keys in test environment
- Expected test duration: ~5-10s per test
- Catches real API issues, response format changes, and integration problems

**Decision 3 — WhatsApp E2E Testing:**
- Use mocked Twilio webhook requests (Option A)
- Simulate Twilio POST requests with test payloads
- Mock Twilio media download API
- No actual WhatsApp messages sent during automated tests
- Real Twilio integration testing deferred to manual testing

**Decision 4 — Test Scenario Priorities:**
- Implement only must-have scenarios (Option A) - 5 core tests
- Test coverage:
  1. Valid lab report → successful analysis (English)
  2. Valid lab report → successful analysis (Urdu)
  3. Non-lab document (receipt) → rejected with clear error
  4. Oversized file → rejected
  5. Invalid file type → rejected
- Additional scenarios (multi-panel, blurred, rate limiting, concurrent uploads) deferred

**Decision 5 — Frontend Polish Features:**
- Implement all features (Option D) - complete polish
- Features to implement:
  1. File drag-and-drop zone with visual feedback
  2. Client-side file validation (type: PDF/PNG/JPEG, size: max 10MB)
  3. Real-time progress indicators with polling (steps: "Extracting text...", "Analyzing report...", "Generating PDF...")
  4. Responsive design with mobile-friendly layout (media queries, touch targets)
  5. Accessibility: ARIA attributes, keyboard navigation, screen reader support
  6. "Upload Another Report" button on results page

**Decision 6 — Health Check Endpoint Scope:**
- Implement dependency checks (Option B)
- Health checks to implement:
  1. MySQL connectivity check (simple SELECT 1 query)
  2. Redis connectivity check (PING command)
  3. Celery worker availability check (inspect active workers)
- Response format: `{"status": "healthy|unhealthy", "checks": {"mysql": "ok|error", "redis": "ok|error", "celery": "ok|error"}}`
- Fast response (~100-200ms)
- Skip LLM/Twilio API checks to avoid external dependencies

**Decision 7 — README Documentation Depth:**
- Quick Start documentation (Option A)
- Sections to include:
  1. Project overview and features
  2. Quick start (docker-compose up instructions)
  3. Basic usage (how to upload a report)
  4. Environment variables list with required/optional markers
  5. Brief troubleshooting (common Docker issues)
- Target length: 1-2 pages
- Focus on getting users up and running quickly

**Decision 8 — Logging Audit:**
- Comprehensive audit (Option B)
- Audit tasks:
  1. Review all logging statements across backend codebase
  2. Create PII detection patterns (phone numbers, emails, patient names, test values)
  3. Implement log sanitization utility function
  4. Update all logs to sanitize sensitive data
  5. Test with real sample reports to verify no PII leaks
- PII to scrub: patient names, phone numbers, email addresses, test result values, addresses
- Keep safe: job_id, file types, error types, processing steps, timing metrics

**Decision 9 — Error Handling Hardening:**
- Specific error messages (Option B)
- Error categories to implement:
  1. OCR errors: "Text extraction failed - image quality too low", "Text extraction failed - unsupported format"
  2. Pre-validation errors: "Document rejected - not a lab report", "Document rejected - insufficient medical data"
  3. LLM errors: "Analysis failed - LLM timeout", "Analysis failed - invalid response format", "Analysis failed - rate limit exceeded"
  4. PDF errors: "PDF generation failed - chart rendering error", "PDF generation failed - template error"
  5. Translation errors: Already handled - falls back to English
- User-facing messages: Clear, actionable guidance
- Backend logs: Detailed error codes + stack traces for debugging
- No graceful degradation (except translation) - full processing or clear failure

---

## 13. Phase Dependency Chain

```
Phase 1: Foundation & Infrastructure
    │
    ▼
Phase 2: OCR, PII Scrubbing & Pre-Validation
    │
    ▼
Phase 3: LLM Analysis (Core Intelligence)
    │
    ▼
Phase 4: Charts & PDF Generation
    │
    ▼
Phase 5: Security, Rate Limiting & File Cleanup
    │
    ▼
Phase 6: Translation & WhatsApp Integration
    │
    ▼
Phase 7: E2E Testing, Polish & Production Readiness
```

Each phase builds on the previous. After Phase 1, you have a working stub loop. After Phase 4, the entire website pipeline works end-to-end with real analysis. Phases 5–6 add security and the secondary interface. Phase 7 hardens everything for production.

---

## 14. Future Considerations (Post-v1)

- User accounts and authentication (registration/login, report history)
- Additional languages beyond English + Urdu
- CI/CD pipeline (GitHub Actions: lint, test, build, deploy)
- AWS S3 file storage option (for production scalability)
- Mobile app
- EHR/EMR integration
- Advanced analytics dashboard
- Multi-language input report support

---

## 15. Production Deployment

### Production Architecture

```
Internet → Caddy (HTTPS :443) → Frontend (:3000)
                                → Backend  (:8000)
         Internal only:
           MySQL (:3306), Redis (:6379), Celery Worker, Celery Beat
```

All 7 services run on a single VPS via Docker Compose. Caddy handles HTTPS termination and reverse proxying. Only ports 80 and 443 are exposed to the internet — all other services communicate internally via Docker networking.

### Hosting: Oracle Cloud Always-Free Tier

| Item | Details |
|------|---------|
| Provider | Oracle Cloud Infrastructure (OCI) |
| VM Shape | VM.Standard.A1.Flex (ARM Ampere) |
| Resources | 4 OCPUs, 24GB RAM, 200GB disk |
| Cost | $0/month (permanently free, not trial) |
| OS | Ubuntu 22.04 (ARM) |

Oracle Cloud's Always-Free Tier provides an ARM Ampere A1 instance with 4 CPUs and 24GB RAM — more than sufficient for all services. This is not a 12-month trial; the resources remain free indefinitely.

### Domain & SSL

| Item | Details |
|------|---------|
| Domain | DuckDNS free subdomain (e.g., `labreportai.duckdns.org`) |
| SSL | Automatic HTTPS via Caddy + Let's Encrypt |
| DNS Updates | Cron job updates DuckDNS IP every 5 minutes |

DuckDNS provides free dynamic DNS subdomains. A cron job keeps the DNS record updated with the server's current IP address. Caddy automatically provisions and renews SSL certificates from Let's Encrypt.

### Production Service Configuration

| Service | Image / Build | RAM Limit | Details |
|---------|--------------|-----------|---------|
| Caddy | `caddy:2-alpine` | 128 MB | Reverse proxy, auto-SSL, gzip compression |
| Frontend | `frontend/Dockerfile.prod` | 512 MB | Multi-stage build, Next.js standalone output (~150MB image) |
| Backend | `backend/Dockerfile` | 2 GB | 2 uvicorn workers, health checks every 30s |
| Celery Worker | Same as backend | 2 GB | 2 concurrency, restart always |
| Celery Beat | Same as backend | 256 MB | Periodic task scheduler |
| MySQL | `mysql:8.0` | 1 GB | Persistent volume, restart always |
| Redis | `redis:7-alpine` | 256 MB | Celery broker + session cache |

### Deployment Files

| File | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production overrides: resource limits, restart policies, Caddy service, no port exposure for internal services |
| `frontend/Dockerfile.prod` | Multi-stage Next.js build (`npm run build` → standalone `node server.js`, ~150MB image) |
| `Caddyfile` | Reverse proxy routes: `/v1/*` → backend, `/docs*` → backend, everything else → frontend. Auto-SSL. |
| `.env.production.example` | Production environment template with secure defaults and placeholder passwords |
| `deploy.sh` | One-command VPS setup: installs Docker, clones repo, configures environment, opens firewall, launches all services |

### Deployment Steps

1. **Create Oracle Cloud account** at cloud.oracle.com (free, credit card for identity verification only)
2. **Create ARM Compute Instance**: Shape `VM.Standard.A1.Flex`, 4 OCPU, 24GB RAM, Ubuntu 22.04, 100GB boot volume
3. **Open ports 80 and 443** in OCI Security List (VCN → Subnet → Security List → Ingress Rules)
4. **Create DuckDNS subdomain** at duckdns.org (sign in with GitHub), point to instance public IP
5. **SSH into the instance** and run `deploy.sh`:
   ```bash
   # Clone and deploy
   git clone <repo-url> labreportai
   cd labreportai
   cp .env.production.example .env
   # Edit .env with real passwords and API keys
   nano .env
   # Launch all services
   bash deploy.sh
   ```
6. **Verify deployment**:
   - `https://labreportai.duckdns.org` — Frontend loads
   - `https://labreportai.duckdns.org/v1/health` — Returns `{"status": "healthy"}`
   - Upload a sample lab report — Full pipeline works
   - `docker compose logs -f` — No errors in logs

### Production Commands

```bash
# Start all services (production mode)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# View logs (follow)
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# View logs for a specific service
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend

# Restart a service
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# Stop all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Update and redeploy
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Security Checklist

- [ ] Strong unique MySQL password in `.env` (not defaults)
- [ ] LLM API key set in `.env` (not committed to git)
- [ ] Caddy provides HTTPS (auto-SSL via Let's Encrypt)
- [ ] Only ports 80 and 443 open to internet
- [ ] Backend, MySQL, Redis not directly accessible from internet
- [ ] Oracle Cloud firewall configured (Security List ingress rules)
- [ ] CORS origins set to production domain only

### Cost Summary

| Item | Cost |
|------|------|
| Oracle Cloud VM (ARM A1, 4 CPU / 24 GB) | $0/month (always free) |
| DuckDNS subdomain | $0 (free) |
| SSL certificate (Let's Encrypt via Caddy) | $0 (free) |
| Groq API (LLM — free tier: 30 req/min) | $0 (free) |
| **Total** | **$0/month** |

---

## 16. Detailed Deployment Guide

### Prerequisites

- Windows machine with Docker Desktop installed (for building images)
- SSH key for Oracle Cloud instance
- Oracle Cloud instance running Ubuntu (x86 or ARM)
- DuckDNS subdomain pointing to server IP
- OCI Security List with ports 80 and 443 open

### Step 1: Server Initial Setup (One-time)

SSH into your Oracle Cloud instance:

```bash
ssh -i "path/to/your/ssh-key.key" ubuntu@YOUR_SERVER_IP
```

Install Docker and Docker Compose:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Log out and back in for group changes
exit
```

SSH back in and clone the repository:

```bash
ssh -i "path/to/your/ssh-key.key" ubuntu@YOUR_SERVER_IP

# Clone repository
git clone https://github.com/YOUR_USERNAME/LabReportAI.git ~/labreportai
cd ~/labreportai

# Create environment file
cp .env.production.example .env
nano .env  # Edit with your actual values
```

### Step 2: Build Frontend Image (Windows)

The frontend must be built locally and transferred because:
- Next.js standalone build embeds environment variables at build time
- ARM/x86 architecture differences may cause issues building on server

```powershell
# Navigate to frontend directory
cd "path\to\labreportai\frontend"

# Build the production image with environment variables
docker build -f Dockerfile.prod `
  --build-arg NEXT_PUBLIC_API_URL=https://YOUR_DOMAIN.duckdns.org `
  --build-arg NEXT_PUBLIC_RECAPTCHA_SITE_KEY=placeholder `
  -t labreportai-frontend:latest .

# Save image to tar file
docker save labreportai-frontend:latest -o frontend-image.tar

# Transfer to server
scp -i "path\to\your\ssh-key.key" frontend-image.tar ubuntu@YOUR_SERVER_IP:~/
```

### Step 3: Deploy on Server

```bash
cd ~/labreportai

# Pull latest code
git pull

# Stop existing services
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Remove old frontend image (if exists)
docker image rm labreportai-frontend:latest 2>/dev/null || true

# Prune old volumes (removes cached/stale data)
docker volume prune -f

# Load the new frontend image
docker load < ~/frontend-image.tar

# Start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

### Step 4: Verify Deployment

```bash
# Check all containers are running
docker ps

# Check frontend logs
docker compose logs frontend

# Check backend logs
docker compose logs backend

# Test health endpoint
curl https://YOUR_DOMAIN.duckdns.org/v1/health
```

Visit `https://YOUR_DOMAIN.duckdns.org` in browser to verify the site loads correctly.

### Redeployment (After Code Changes)

**For frontend changes:**

On Windows:
```powershell
cd "path\to\labreportai\frontend"
docker build -f Dockerfile.prod `
  --build-arg NEXT_PUBLIC_API_URL=https://YOUR_DOMAIN.duckdns.org `
  --build-arg NEXT_PUBLIC_RECAPTCHA_SITE_KEY=placeholder `
  -t labreportai-frontend:latest .
docker save labreportai-frontend:latest -o frontend-image.tar
scp -i "path\to\ssh-key.key" frontend-image.tar ubuntu@YOUR_SERVER_IP:~/
```

On Server:
```bash
cd ~/labreportai
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker image rm labreportai-frontend:latest 2>/dev/null || true
docker volume prune -f
docker load < ~/frontend-image.tar
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**For backend-only changes:**

On Server:
```bash
cd ~/labreportai
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build backend celery-worker celery-beat
```

---

## 17. Known Issues & Fixes

### React Hydration Error #418

**Problem:** After deploying Next.js 15 with React 19 in standalone mode, the page would show briefly with correct styling, then break with console error:
```
Uncaught Error: Minified React error #418
```

This error means "Hydration failed because the initial UI does not match what was rendered on the server."

**Root Cause:** Server-side rendered HTML differed from what React expected on the client during hydration. This can happen due to:
- Browser extensions modifying DOM
- Dynamic content rendered differently on server vs client
- Whitespace differences in JSX
- Next.js standalone build quirks with React 19

**Solution:** Use the "mounted pattern" - render nothing until the component mounts on the client, guaranteeing no server/client mismatch.

**Fixed Code (frontend/src/app/page.tsx):**
```tsx
"use client";

import { useState, useEffect } from "react";
import UploadForm from "@/components/UploadForm";

export default function HomePage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Return null until mounted - guarantees no hydration mismatch
  if (!mounted) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Page content here */}
    </div>
  );
}
```

**Fixed Code (frontend/src/app/layout.tsx):**
```tsx
<html lang="en" suppressHydrationWarning>
  <body className="..." suppressHydrationWarning>
    {/* Layout content */}
  </body>
</html>
```

**Key Changes:**
1. Add `"use client"` directive to page.tsx
2. Use `useState(false)` + `useEffect` to track mount state
3. Return `null` before mount (server and client both render nothing initially)
4. After hydration succeeds, `useEffect` runs, `mounted` becomes `true`, real content renders
5. Add `suppressHydrationWarning` to both `<html>` and `<body>` tags in layout.tsx
6. Remove explicit `<head>` tag from layout (Next.js manages it automatically)

### Docker Volume Override Issue

**Problem:** Frontend container crashes with "MODULE_NOT_FOUND" for `/app/.next/standalone/server.js` even though the image was built correctly.

**Root Cause:** Anonymous Docker volumes from base `docker-compose.yml` were mounting over the image's files, replacing the built standalone output with empty directories.

**Solution:**
1. In `docker-compose.prod.yml`, explicitly set `volumes: []` for frontend service
2. Before redeploying, prune volumes: `docker volume prune -f`
3. Remove and recreate containers completely (not just restart)

### Caddy SSL Certificate Timeout

**Problem:** Caddy fails to obtain SSL certificate with "Timeout during connect (likely firewall problem)".

**Root Cause:** OCI Security List doesn't have ingress rules for ports 80 and 443.

**Solution:** In OCI Console:
1. Go to Networking → Virtual Cloud Networks → Your VCN
2. Click on the public subnet
3. Click on the Security List
4. Add Ingress Rules:
   - Source: `0.0.0.0/0`, Protocol: TCP, Destination Port: 80
   - Source: `0.0.0.0/0`, Protocol: TCP, Destination Port: 443

---

## 18. Post-Analysis Chat Feature (Phase 8)

### Overview

After a lab report is analyzed, users can interact with an AI chatbot to ask questions about their results. The chat provides personalized health insights based on the analysis, answering questions like "How is my lipid profile?" or "How can I improve my cholesterol with diet changes?"

**Key Principles:**
- Educational only — no diagnosis or treatment recommendations
- Context-aware — AI has full access to the analysis results
- Rate-limited — prevents abuse while allowing meaningful conversations
- Ephemeral — no chat history persistence (MVP)

---

### User Experience

#### Chat Widget
- **Location**: Two access points on the report results page:
  1. **Floating chat button** (bottom-right corner) — circular blue button with chat icon
  2. **"Discuss your Report" button** — purple action button between "Download PDF Report" and "Upload Another Report"
- **Trigger**: Both buttons appear only after report analysis is complete
- **Initial State**: Floating button visible; inline button in action bar
- **Expanded State**: Chat panel (550px × 650px on desktop; almost full-screen with 8px margins on mobile)
- **Close Behavior**: Collapse to buttons; conversation preserved until page refresh

#### Conversation Flow

1. User clicks floating chat button
2. Chat panel expands showing:
   - Welcome message with context acknowledgment
   - 3-4 starter question suggestions based on the report
   - Message input field
   - "X of 20 messages remaining" indicator
3. User types a question or clicks a suggestion
4. AI response streams in real-time (token by token)
5. After AI responds, 2-3 contextual follow-up suggestions appear
6. Conversation continues until user closes panel or exhausts message limit

#### Message Limit UX
- Display: "X of 20 messages remaining" at bottom of chat panel
- Warning: When 5 messages remain, show subtle warning color
- Final message: "You've used all 20 messages for this report. Download the PDF for a complete summary."
- Counter only tracks user messages (not AI responses)

---

### Starter Questions (Initial Suggestions)

Generated dynamically based on the analysis results. Examples:

**For a CBC report with low hemoglobin:**
- "What does my low hemoglobin mean?"
- "How can I improve my hemoglobin levels naturally?"
- "Should I be concerned about my CBC results?"

**For a lipid panel with high LDL:**
- "Explain my cholesterol results"
- "What dietary changes can help lower my LDL?"
- "How does my lipid profile affect heart health?"

**For a thyroid panel:**
- "What do my thyroid results indicate?"
- "How does TSH relate to metabolism?"
- "Are my T3 and T4 levels concerning?"

**Generation Logic:**
- Extract categories with abnormal/critical values from analysis JSON
- Generate 3-4 relevant questions per report
- Prioritize critical values, then borderline, then normal summaries
- Fall back to generic questions if analysis lacks detail

---

### Contextual Follow-up Suggestions

After each AI response, show 2-3 follow-up suggestions based on:
- The topic of the previous question
- Abnormal values not yet discussed
- Natural conversation flow (e.g., after explaining a value → suggest lifestyle changes)

**Example Flow:**
1. User asks: "What does my high LDL mean?"
2. AI explains LDL cholesterol
3. Follow-ups appear:
   - "How can I lower my LDL with diet?"
   - "What exercise helps reduce cholesterol?"
   - "Tell me about my other lipid values"

---

### API Specification

#### Endpoint: Chat Message

```
POST /v1/chat/{job_id}
```

**Request Body:**
```json
{
  "message": "What does my low hemoglobin mean?",
  "conversation_history": [
    {"role": "user", "content": "Previous question..."},
    {"role": "assistant", "content": "Previous answer..."}
  ]
}
```

**Response:** Server-Sent Events (SSE) stream

```
event: token
data: {"content": "Low "}

event: token
data: {"content": "hemoglobin "}

event: token
data: {"content": "indicates..."}

event: done
data: {"suggestions": ["How can I improve my hemoglobin?", "What foods are rich in iron?"], "messages_remaining": 18}

event: error
data: {"message": "Rate limit exceeded for this report"}
```

**Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

#### Endpoint: Get Starter Questions

```
GET /v1/chat/{job_id}/suggestions
```

**Response:**
```json
{
  "suggestions": [
    "What does my low hemoglobin mean?",
    "How is my lipid profile overall?",
    "Should I be concerned about any values?",
    "What lifestyle changes do you recommend?"
  ],
  "messages_remaining": 20
}
```

#### Error Responses

| Status | Code | Message |
|--------|------|---------|
| 404 | REPORT_NOT_FOUND | Report not found or expired |
| 400 | REPORT_NOT_READY | Report analysis not yet complete |
| 429 | CHAT_LIMIT_EXCEEDED | Message limit (20) reached for this report |
| 400 | MESSAGE_TOO_LONG | Message exceeds 500 character limit |
| 503 | LLM_UNAVAILABLE | Chat service temporarily unavailable |

---

### Backend Implementation

#### Chat Service (`backend/app/services/chat.py`)

```python
class ChatService:
    def __init__(self, analysis_json: dict, job_id: str):
        self.analysis = analysis_json
        self.job_id = job_id
        self.llm = get_chat_llm()  # Configurable, default 8B model

    async def generate_response(
        self,
        message: str,
        history: list[dict]
    ) -> AsyncGenerator[str, None]:
        """Stream chat response tokens."""
        prompt = self._build_prompt(message, history)
        async for token in self.llm.astream(prompt):
            yield token

    def generate_suggestions(self) -> list[str]:
        """Generate starter questions from analysis."""
        # Extract abnormal values, generate relevant questions
        pass

    def generate_followups(self, last_response: str) -> list[str]:
        """Generate contextual follow-up suggestions."""
        pass
```

#### Chat Prompt Template (`backend/prompts/chat.txt`)

```
You are a friendly health education assistant helping a user understand their lab report results.

CONTEXT - Analysis Results:
{analysis_json}

RULES:
1. You are NOT a doctor. Never diagnose or prescribe treatment.
2. Provide educational information only.
3. Reference specific values from the user's report when relevant.
4. Suggest lifestyle changes when appropriate (diet, exercise, sleep).
5. Recommend consulting a doctor for concerning values.
6. Keep responses concise (2-3 paragraphs max).
7. Use simple language; explain medical terms.
8. Be encouraging and supportive.
9. If asked about topics outside the lab report, politely redirect to health topics.

MANDATORY DISCLAIMER (include at end of responses about concerning values):
"This is educational information only. Please consult your healthcare provider for personalized medical advice."

CONVERSATION HISTORY:
{history}

USER QUESTION:
{message}

Respond helpfully:
```

#### Rate Limiting

Track message count per report in Redis:

```python
# Redis key: chat_count:{job_id}
# Value: integer (0-20)
# TTL: Same as report retention (48 hours)

async def check_chat_limit(job_id: str) -> tuple[bool, int]:
    """Check if user can send more messages. Returns (allowed, remaining)."""
    key = f"chat_count:{job_id}"
    count = await redis.get(key) or 0
    remaining = 20 - int(count)
    return remaining > 0, remaining

async def increment_chat_count(job_id: str) -> int:
    """Increment message count, return remaining."""
    key = f"chat_count:{job_id}"
    count = await redis.incr(key)
    if count == 1:
        # Set TTL on first message
        await redis.expire(key, 48 * 60 * 60)
    return 20 - count
```

---

### Frontend Implementation

#### Components

| Component | Purpose |
|-----------|---------|
| `ChatWidget.tsx` | Complete chat component with floating button, expandable panel, messages, input, and suggestions. Exposes `open()` method via `forwardRef` for external triggering. |

**Note:** The chat is implemented as a single `ChatWidget` component rather than separate components. It includes:
- Floating circular button (bottom-right)
- Expandable chat panel (550×650px desktop, near full-screen mobile)
- Message bubbles for user and AI
- Suggestion chips for starter and follow-up questions
- Text input with send button and remaining message counter

The widget can be opened via:
1. Clicking the floating button
2. Clicking the "Discuss your Report" button (calls `chatWidgetRef.current.open()`)

#### State Management

```typescript
interface ChatState {
  isOpen: boolean;
  messages: ChatMessage[];
  isStreaming: boolean;
  currentStreamedResponse: string;
  suggestions: string[];
  messagesRemaining: number;
  error: string | null;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}
```

#### Streaming Handler

```typescript
async function sendMessage(message: string) {
  setIsStreaming(true);
  setCurrentStreamedResponse("");

  const response = await fetch(`/v1/chat/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_history: messages }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        if (data.content) {
          setCurrentStreamedResponse(prev => prev + data.content);
        }
        if (data.suggestions) {
          setSuggestions(data.suggestions);
          setMessagesRemaining(data.messages_remaining);
        }
      }
    }
  }

  // Finalize message
  setMessages(prev => [...prev,
    { role: "user", content: message },
    { role: "assistant", content: currentStreamedResponse }
  ]);
  setIsStreaming(false);
}
```

---

### Configuration Options

| Option | Default | Purpose |
|--------|---------|---------|
| `CHAT_ENABLED` | true | Enable/disable chat feature |
| `CHAT_MESSAGE_LIMIT` | 20 | Max messages per report |
| `CHAT_MAX_MESSAGE_LENGTH` | 500 | Max characters per user message |
| `LLM_CHAT_MODEL` | (validation model) | LLM for chat (configurable, default 8B) |
| `CHAT_RESPONSE_MAX_TOKENS` | 500 | Max tokens per AI response |

---

### Database Changes

No new tables required. Chat state is ephemeral:
- Message count stored in Redis (`chat_count:{job_id}`)
- Conversation history passed in each request (stateless backend)
- Chat history not persisted (MVP decision)

---

### Files to Create/Modify

#### New Files

| File | Purpose |
|------|---------|
| `backend/app/api/v1/chat.py` | Chat API endpoints (SSE streaming + suggestions) |
| `backend/app/services/chat.py` | Chat service with LLM integration and rate limiting |
| `backend/app/schemas/chat.py` | Pydantic schemas for chat requests/responses |
| `backend/prompts/chat.txt` | Chat system prompt |
| `frontend/src/components/ChatWidget.tsx` | Complete chat widget (floating button + panel + messages + input) |
| `frontend/src/lib/chat.ts` | Chat API client with SSE handling |

#### Modified Files

| File | Changes |
|------|---------|
| `backend/app/api/router.py` | Register chat routes |
| `backend/app/config.py` | Add chat configuration options (llm_chat_model, chat_enabled, chat_message_limit, etc.) |
| `backend/app/services/llm_provider.py` | Add `get_chat_llm()` factory function |
| `frontend/src/components/ReportView.tsx` | Add ChatWidget with ref, add purple "Discuss your Report" button |
| `frontend/src/types/index.ts` | Add chat-related types (ChatMessage, ChatStreamDoneEvent, etc.) |

---

### Acceptance Criteria

1. ✅ Floating chat button appears on completed report page
2. ✅ Chat panel opens/closes smoothly with animation
3. ✅ Starter questions generated based on report content
4. ✅ AI responses stream in real-time (visible token-by-token)
5. ✅ Follow-up suggestions appear after each AI response
6. ✅ Message counter shows "X of 20 messages remaining"
7. ✅ Chat blocked after 20 messages with clear message
8. ✅ 404 returned for expired/non-existent reports
9. ✅ Mandatory disclaimer on health-related responses
10. ✅ Chat works on mobile (responsive design)
11. ✅ Chat only discusses health topics; redirects off-topic questions
12. ✅ Streaming gracefully handles connection interruptions

---

### Out of Scope (Future Enhancements)

- Chat history persistence across sessions
- Urdu language support for chat
- Voice input/output
- Export chat transcript
- WhatsApp chat integration
- Multi-report context (compare with previous results)
- Saved/favorite responses

---

## 19. Medical Imaging Analysis (Future - Phase 9)

### Overview

Extend LabReportAI to analyze medical imaging (ultrasound, X-ray, MRI, CT scans) using LLM vision APIs. This leverages existing LLM infrastructure rather than deploying specialized ML models, keeping memory usage low for resource-constrained servers.

### Architecture Approach

```
Current:  Image → OCR → Text → LLM Text Analysis → Results
New:      Image → Detect Type → Branch:
          ├─ Lab Report → OCR → Text Analysis (existing)
          └─ Medical Image → Vision LLM → Image Analysis (new)
```

### Scope Decisions

- **Imaging Types:** All (X-ray, Ultrasound, MRI, CT) from the start
- **File Formats:** Standard images only (PNG, JPG) - no DICOM initially
- **LLM Provider:** Configurable via .env (like existing text analysis)

---

### New Files to Create

| File | Purpose |
|------|---------|
| `backend/app/services/vision_analyzer.py` | Analyze images via LLM vision API |
| `backend/app/services/imaging_validator.py` | Detect if image is medical imaging |
| `backend/app/services/image_preprocessor.py` | Resize/encode images for API |
| `backend/prompts/imaging_classification.txt` | Prompt for modality detection |
| `backend/prompts/imaging_analysis.txt` | Prompt for medical image analysis |
| `templates/pdf/imaging_report.html` | PDF template for imaging reports |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/app/models/report.py` | Add `report_type`, `imaging_modality`, `body_region` columns |
| `backend/app/tasks/analyze.py` | Add branching logic: lab report vs imaging |
| `backend/app/services/llm_provider.py` | Add `get_vision_llm()` for vision-capable models |
| `backend/app/config.py` | Add `llm_vision_model`, `max_image_dimension` settings |
| `backend/app/services/markdown_renderer.py` | Add `render_imaging_markdown()` function |
| `backend/app/services/pdf_generator.py` | Add `generate_imaging_pdf()` function |
| `frontend/src/components/UploadForm.tsx` | Add report type selector (auto/lab/imaging) |
| `frontend/src/types/index.ts` | Add imaging-related types |

### Database Migration

```sql
ALTER TABLE reports ADD COLUMN report_type ENUM('lab_report', 'imaging') DEFAULT 'lab_report';
ALTER TABLE reports ADD COLUMN imaging_modality VARCHAR(50);
ALTER TABLE reports ADD COLUMN imaging_body_region VARCHAR(100);
```

### Configuration (.env)

```bash
# Vision LLM settings (configurable like existing text analysis)
LLM_VISION_PROVIDER=groq          # groq, openai, google, anthropic
LLM_VISION_MODEL=llama-3.2-90b-vision-preview  # or gpt-4o, gemini-pro-vision, claude-3-5-sonnet
LLM_VISION_VALIDATION_MODEL=      # Cheaper model for classification (optional)
MAX_IMAGE_DIMENSION=1024          # Resize larger images for API efficiency
```

### Output Structure for Imaging

```json
{
  "study_info": { "modality": "xray", "body_region": "chest", "view": "PA" },
  "findings": [
    { "structure": "...", "observation": "...", "severity": "normal|mild|moderate|severe" }
  ],
  "measurements": [...],
  "impression": "Summary",
  "recommendations": "Follow-up suggestions",
  "disclaimer": "Educational only"
}
```

### Cost Estimation (Per Image)

| Provider | Model | Cost |
|----------|-------|------|
| Groq | llama-3.2-90b-vision | Free tier available |
| OpenAI | gpt-4o-mini (validation) | ~$0.002 |
| OpenAI | gpt-4o (analysis) | ~$0.02-0.05 |
| Anthropic | claude-3-5-sonnet | ~$0.03-0.08 |

### Implementation Sequence

1. **Backend Core** - Database migration, vision_analyzer.py service, imaging prompts
2. **Pipeline Integration** - Modify analyze.py with branching, imaging markdown/PDF templates
3. **Frontend** - Report type selector in upload form, imaging-specific results display
4. **Testing** - Test with sample X-ray/ultrasound/MRI/CT images

### Future: DICOM Support (Phase 10)

- Add `pydicom` dependency for DICOM file parsing
- Extract metadata from DICOM headers
- Handle multi-slice 3D volumes (MRI, CT)
- Select key slices for analysis
