# PRAMAN AI Agent Handoff

## 1) Project purpose and goals

PRAMAN AI is a packaged-goods inspection and evidence workflow for field inspections, package image capture, OCR extraction, human review, and later legal/compliance validation. The repository is intentionally scoped to the approved architecture and the project phases already implemented in this branch.

The codebase currently demonstrates:
- evidence-first inspection capture
- package image upload and review
- OCR-based declaration extraction using real PaddleOCR when the runtime is available
- human review and finalization workflow
- deterministic demo validation logic separated from legal compliance logic
- legal-source documentation work without implementing rule execution

Important constraint: the repository is not intended to become an LLM-driven legal system. The legal/compliance authority remains in deterministic, versioned legal-rule sources and rules-engine logic, not in model output.

## 2) Current architecture and tech stack

Confirmed stack in the repository:
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy + Alembic + Pydantic
- Database: PostgreSQL-first domain model with SQLite fallback used for local/test execution
- OCR/CV: OpenCV + PaddleOCR + PaddlePaddle
- Deterministic validation: Python service layer separated from legal decisioning
- Deployment/dev environment: Docker Compose + environment configuration

Notable runtime/version state seen in the project environment during Phase 5 compatibility work:
- Python: 3.12.10
- PaddlePaddle: 2.6.2
- PaddleOCR: 2.7.3
- OpenCV: 4.6.0
- NumPy: 1.26.4

This combination is the known working OCR runtime for the project venv at the time of the last verified run.

## 3) Important folder and file structure

- `backend/` — FastAPI app, SQLAlchemy models, migrations, services, tests
  - `backend/app/main.py` — FastAPI app bootstrap, CORS, startup migration call
  - `backend/app/api/v1/inspections.py` — inspection lifecycle API
  - `backend/app/services/ocr_service.py` — canonical OCR service implementation
  - `backend/app/models/` — inspection, image, analysis, finding, review models
  - `backend/alembic/` — database migrations
  - `backend/tests/` — backend verification tests
- `frontend/` — React app
  - `frontend/src/pages/NewInspectionPage.tsx` — create inspection entry screen
  - `frontend/src/pages/InspectionWorkflowPage.tsx` — upload, analysis, findings, review, finalize flow
  - `frontend/src/App.tsx` — route definitions
- `legal/` — legal source inventory and candidate provision work
  - `legal/source_documents/` — downloaded legal PDFs
  - `legal/rule_catalog/LEGAL_SOURCE_INVENTORY.md` — legal source inventory
  - `legal/rule_catalog/CANDIDATE_LEGAL_PROVISIONS.md` — candidate provision extraction
- `docs/` — specification documents referenced for product requirements
- `docker/` and `docker-compose.yml` — local environment configuration
- `.venv/` — project Python environment used for backend/OCR verification

## 4) Implemented features by phase

### Phase 0 — foundation
- Monorepo structure and environment scaffolding
- FastAPI app, health endpoints, config, Docker setup
- PostgreSQL configuration and migration scaffolding
- basic developer documentation

### Phase 1 — frontend shell
- dashboard layout with navigation and KPIs
- pages for overview, inspections, products, reports, rules, users, settings
- inspection creation entry flow

### Phase 2 — backend foundation
- SQLAlchemy models for users, products, inspections, inspection images, analysis, findings, review decisions
- Alembic migrations for the domain model
- CRUD/API endpoints for core entities
- SQLite fallback for local/test execution

### Phase 3+4 — MVP workflow
- create inspection
- upload image(s)
- run analysis
- generate findings
- review decision flow
- finalize inspection
- end-to-end browser flow validated

### Phase 5 — OCR runtime and inspection evidence extraction
- OCR abstraction in `OCRService`
- real PaddleOCR path with OpenCV preprocessing
- structured declaration extraction fields such as commodity name, address, quantity, price, month/year, contact, country of origin
- confidence and bounding-box extraction preserved in analysis results
- fallback path retained as explicit dev fallback; not counted as real OCR success
- runtime compatibility for the current project venv was corrected

### Legal-source documentation phase (current repo status)
- legal inventory generated from source PDFs
- candidate legal provision extraction document created
- these are documentation-only and not implemented in app logic

## 5) Current frontend routes and workflow

Frontend routes from `frontend/src/App.tsx`:
- `/` → Overview
- `/inspections` → Inspections list
- `/inspections/new` → New inspection form
- `/inspections/:inspectionId` → inspection workflow
- `/products`
- `/violations`
- `/reports`
- `/analytics`
- `/rules`
- `/users`
- `/settings`

Current inspection workflow:
1. Create inspection
2. Select/create product context
3. Upload images or capture with camera
4. Select image side/grouping (front/back/left/right/other)
5. Analyze inspection
6. Review OCR result and generated findings
7. Accept/reject/manual review decision
8. Finalize inspection status

Important: the flow is working as a browser workflow and is designed for evidence-first review, not final legal judgment.

## 6) Backend APIs

Main endpoints in `backend/app/api/v1/inspections.py`:
- `GET /api/v1/inspections` — list inspections
- `POST /api/v1/inspections` — create inspection
- `GET /api/v1/inspections/{inspection_id}` — fetch inspection
- `POST /api/v1/inspections/{inspection_id}/upload-image` — single-file upload
- `POST /api/v1/inspections/{inspection_id}/upload-images` — multi-file upload
- `PATCH /api/v1/inspections/{inspection_id}/barcode` — barcode or QR value update
- `GET /api/v1/inspections/{inspection_id}/images` — list stored images
- `POST /api/v1/inspections/{inspection_id}/analyze` — run OCR analysis and generate findings
- `GET /api/v1/inspections/{inspection_id}/analysis` — fetch latest analysis result
- `GET /api/v1/inspections/{inspection_id}/findings` — fetch findings
- `POST /api/v1/inspections/{inspection_id}/review` — review decision (confirm/reject/manual_review)
- `POST /api/v1/inspections/{inspection_id}/finalize` — completed status

Other API areas exist for products and users, but the inspection workflow is the operational heart of the current app.

## 7) Database models and migrations

Core SQLAlchemy models:
- `Inspection` — inspection lifecycle master record
- `InspectionImage` — stored image metadata and side grouping
- `AnalysisResult` — OCR and declaration extraction output
- `Finding` — demo/structured findings from validation pass
- `ReviewDecision` — reviewer decisions
- `Product` — product/reference record
- `User` — user record

Important model properties:
- `Inspection.status` includes draft/review/completed states in the current workflow
- `Inspection.barcode_or_qr` stores optional barcode/QR lookup value
- `InspectionImage.image_type` stores front/back/left_side/right_side/other
- `AnalysisResult.ocr_text`, `ocr_confidence`, `ocr_regions`, `extraction_metadata` store OCR output metadata

Migration history in `backend/alembic/versions/` includes the project foundation and the inspection/OCR evolution. The startup hook in `backend/app/main.py` calls Alembic upgrade at app startup.

## 8) OCR/CV implementation and runtime versions

Canonical OCR service:
- `backend/app/services/ocr_service.py`

Current implementation includes:
- OpenCV preprocessing via `cv2.imread`, grayscale conversion, resize, thresholding
- PaddleOCR initialization in `OCRService.analyze_image`
- parsing of OCR output into:
  - raw text
  - confidence
  - bounding boxes
- structured declaration extraction by regex heuristics over OCR text
- explicit fallback path for environment/runtime error conditions

The actual working OCR runtime values in the project venv are:
- Python 3.12.10
- PaddlePaddle 2.6.2
- PaddleOCR 2.7.3
- OpenCV 4.6.0
- NumPy 1.26.4

Important note: the repository intentionally keeps the legal/compliance engine separate from OCR. OCR is evidence extraction only, not legal truth.

## 9) Legal source workflow

Legal documentation is intentionally isolated:
- `legal/source_documents/` contains the raw PDFs used for legal-source review.
- `legal/rule_catalog/LEGAL_SOURCE_INVENTORY.md` classifies legal documents by type and marks uncertainty as `Needs verification`.
- `legal/rule_catalog/CANDIDATE_LEGAL_PROVISIONS.md` captures candidate compliance provisions from executable or potentially executable PCR sources.

Current state:
- The inventory and candidate extraction work are documentation-only.
- They do not implement legal rules, compliance logic, or app/database changes.
- They are a traceable evidence base for future legal-engine work, but they are not the legal engine itself.

## 10) Important files created or modified

Core files checked in the repo include:
- `README.md`
- `.env.example`
- `docker-compose.yml`
- `backend/requirements.txt`
- `backend/app/main.py`
- `backend/app/api/v1/inspections.py`
- `backend/app/models/inspection.py`
- `backend/app/models/analysis_result.py`
- `backend/app/services/ocr_service.py`
- `frontend/src/App.tsx`
- `frontend/src/pages/NewInspectionPage.tsx`
- `frontend/src/pages/InspectionWorkflowPage.tsx`
- `legal/rule_catalog/LEGAL_SOURCE_INVENTORY.md`
- `legal/rule_catalog/CANDIDATE_LEGAL_PROVISIONS.md`

## 11) Tests, builds, and verification completed

Verified commands and results in the repository state:

Backend tests:
- Command run from inside `backend/`: `..\.venv\Scripts\python -m pytest tests -q`
- Result: passed (exit code 0)

Important note:
- Running pytest from repo root without the backend package path configuration caused `ModuleNotFoundError: No module named 'app'`.
- This is a working-directory/import-path issue, not an app runtime failure.

Frontend build:
- Command run from `frontend/` with policy bypass for the current shell: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; npm run build`
- Result: success (exit code 0)
- Vite completed production build successfully.

Playwright suite:
- Command run from `frontend/`: `npx playwright test`
- Result: 3 passed in 13.7s

## 12) Known limitations and unresolved issues

- The repository is not a full legal/compliance system yet. The legal inventory and candidate provision docs are not executable logic.
- The app has a deterministic demo validation layer for workflow progression, but it is explicitly not legal truth.
- OCR confidence and bounding boxes exist in the analysis result, but the later legal/compliance engine is intentionally deferred.
- Root-level backend test invocation is sensitive to import path configuration; future agents should execute tests from `backend/` or set `PYTHONPATH` appropriately.
- The app uses local file storage rather than object storage, consistent with the current scope and architecture.
- The legal source inventory remains partially dependent on PDF readability and official text extraction; uncertain items are intentionally marked `Needs verification`.

## 13) Important architectural decisions

- Keep the approved stack: React, FastAPI, Python, PostgreSQL, PaddleOCR, OpenCV, deterministic rule engine, no unrelated backend stack changes.
- Keep legal/compliance authority separated from raw OCR and model output.
- Keep OCR evidence extraction separate from legal decisions.
- Preserve the inspection lifecycle and workflow rather than redesigning the app.
- Treat legal source documents as traceable evidence, not as assumptions or prompts.

## 14) Things intentionally not implemented

The repository currently does not include:
- real government legal rules execution
- formal compliance engine
- PDF report generation
- authentication/RBAC
- S3/object storage
- Redis/Celery
- Kafka or other event buses
- heavy MLOps pipeline or multi-provider model services
- Phase 6+ legal automation work

## 15) Current exact project status

Current repo state: working foundation, end-to-end inspection workflow, and real OCR runtime support in the project environment, with legal-source inventory and candidate provisions documented but not operationalized.

This is a valid intermediate-state project handoff, not a finished legal/compliance system.

## 16) Exact recommended next phase/task

Recommended next task: continue only with the approved phase boundaries and maintain traceability. If the next work is legal/compliance, it should be limited to:
- confirming executable legal sources from the PDF set
- converting the candidate provisions into a versioned, deterministic rule catalog
- implementing only the next legal-rule stage, without changing the existing UI/API/OCR architecture

If the next work is product/engineering, keep it focused on the existing inspection workflow and verification discipline. Do not invent legal requirements or convert OCR output into legal truth.
