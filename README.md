# 🛡️ IntentGuard

**IntentGuard** is a metadata privacy scanner and selective cleaner that helps you detect and surgically strip sensitive hidden information from files before sharing them. Built as a working prototype for the Hackulus hackathon.

---

## 🚨 The Problem

Every file you share — a photo, a Word doc, a spreadsheet, a PDF — silently carries hidden metadata:

- 📍 **GPS coordinates** embedded in photos can reveal your home or office address
- 👤 **Author names and revision history** in documents can expose real identities
- 🗂️ **Hidden sheets, rows, and columns** in Excel files can contain confidential data invisible to recipients
- 🔗 **External file references** in formulas leak local file paths and usernames
- 🖥️ **Device information and timestamps** can reveal your OS, software versions, and work schedule
- ✂️ **Fake redactions** in PDFs (black boxes drawn over text) leave the original text fully extractable
- 🖼️ **EXIF thumbnail mismatch** — an edited/cropped photo can still contain the uncropped original embedded in its EXIF data

Most people never check. IntentGuard does it for them.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Metadata Extraction** | Extracts hidden metadata from JPG/PNG/TIFF, DOCX, XLSX, and PDF files |
| 📍 **GPS Detection** | Converts raw EXIF GPS data to decimal lat/lon coordinates |
| 🤖 **ML Risk Scoring** | Random Forest classifier predicts risk level (high / medium / safe) with confidence score |
| ✅ **Selective Metadata Cleaning** | Choose exactly which fields to strip — clean only GPS but keep device info, or vice versa |
| 🗺️ **Cross-File GPS Clustering** | Upload multiple images — DBSCAN with Haversine distance detects shared physical locations across files |
| 🌍 **Real Address Resolution** | Cluster centers are reverse-geocoded to real street addresses (not just raw lat/lon) |
| 🗾 **Live Map Embeds** | Each detected location cluster shows an interactive OpenStreetMap embed in the results |
| ⚡ **Context-Aware Risk** | Risk scoring adapts to who you're sharing with (public / team / anonymous) |
| 📝 **DOCX Tracked Changes** | Detects and extracts `<w:ins>` / `<w:del>` / formatting changes + comments with author and date |
| 📊 **XLSX Hidden Rows/Columns + External Refs** | Detects hidden rows/columns in visible sheets and formulas referencing external workbook paths |
| 🚫 **PDF Fake Redaction Detection** | Finds text hidden under opaque vector shapes (black-box redactions) — a known critical data leak class |
| 🖼️ **EXIF Thumbnail Mismatch** | Side-by-side visual comparison of visible image vs. original embedded in EXIF metadata |

---

## 🏗️ Architecture

```
IntentGuard/
├── frontend/
│   └── index.html              # Single-file dark-mode UI (vanilla HTML/CSS/JS)
├── backend/
│   ├── main.py                 # FastAPI app — /scan, /clean, /cross-check, /health
│   ├── requirements.txt
│   ├── extractors/
│   │   ├── image_extractor.py  # EXIF + GPS + thumbnail mismatch (exifread, piexif)
│   │   ├── docx_extractor.py   # Core properties + tracked changes via direct XML (lxml/ElementTree)
│   │   ├── xlsx_extractor.py   # Workbook props + hidden sheets/rows/cols + external refs (openpyxl)
│   │   ├── pdf_extractor.py    # /Info dict + XMP + fake-redaction detection (pikepdf, pdfplumber)
│   │   └── normalizer.py       # Unifies all extractor output + tags risk category per field
│   ├── ml/
│   │   ├── generate_synthetic_data.py  # Generates 800-row synthetic training dataset
│   │   ├── train_risk_model.py         # Trains Random Forest, saves model
│   │   ├── risk_scorer.py              # Loads model, scores files; rule-based fallback
│   │   ├── cluster_matcher.py          # DBSCAN GPS clustering (Haversine metric)
│   │   └── geocoder.py                 # Reverse geocoding: lat/lon → real street address
│   ├── cleaner/
│   │   └── clean_file.py       # Selective metadata stripping per field key (piexif, PIL, docx, xlsx, pikepdf)
│   └── tests/
│       └── test_extractors.py  # Pytest smoke tests for all extractors
├── sample_files/               # Regenerate with generate_test_files.py
│   └── .gitkeep
└── generate_test_files.py      # Creates realistic fake-metadata test files
```

---

## 🧰 Tech Stack

### Backend
| Library | Purpose |
|---|---|
| **FastAPI** | REST API framework |
| **uvicorn** | ASGI server |
| **exifread** | Parse EXIF tags from images (GPS, device, datetime) |
| **piexif** | Selective EXIF tag removal by IFD/tag ID |
| **Pillow (PIL)** | Image processing + EXIF stripping |
| **python-docx** | Read/write DOCX core properties |
| **lxml / xml.etree** | Direct XML parsing of `word/document.xml` for tracked changes |
| **openpyxl** | Read/write XLSX workbook properties, hidden sheets/rows/cols, formulas |
| **pikepdf** | Read/write PDF `/Info` dictionary and XMP metadata stream |
| **pdfplumber** | Text bounding-box extraction for fake-redaction detection |
| **scikit-learn** | Random Forest classifier + DBSCAN clustering |
| **joblib** | Model serialization |
| **pandas / numpy** | Synthetic data generation and feature engineering |

### Frontend
| Technology | Purpose |
|---|---|
| **Vanilla HTML/CSS/JS** | Single-file UI, no framework needed |
| **Fetch API** | Calls `/scan`, `/clean`, `/cross-check` endpoints |
| **FormData** | Multipart file upload + selective `keys` parameter for clean |
| **CSS custom properties** | Dark-mode design system with risk color tokens |
| **OpenStreetMap iframes** | Live interactive map embeds for detected GPS clusters |

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Train the ML model

```bash
cd backend
python ml/generate_synthetic_data.py
python ml/train_risk_model.py
```

### 3. Start the backend

```bash
# From the IntentGuard root directory:
python -m uvicorn backend.main:app --reload --port 8000
```

### 4. Open the frontend

Serve the frontend with a local HTTP server:

```bash
cd frontend
python -m http.server 5500
```

Then open `http://localhost:5500` in your browser.

### 5. Generate test files (optional)

```bash
pip install piexif python-docx openpyxl pikepdf Pillow
python generate_test_files.py
```

This creates 5 test files in `sample_files/` with realistic fake metadata across all supported formats.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/scan` | Extract + score metadata from a file |
| `POST` | `/clean` | Selectively strip chosen metadata fields and download cleaned file |
| `POST` | `/cross-check` | Detect shared GPS locations across multiple files |

### `/scan` request
```
POST /scan
Content-Type: multipart/form-data

file: <your file>
context: public | team | anonymous   (default: public)
```

### `/scan` response
```json
{
  "filename": "photo.jpg",
  "file_type": "image",
  "context": "public",
  "metadata": [
    { "field": "GPS Location", "value": "13.0827°N, 80.2707°E", "raw_key": "gps", "category": "high" },
    { "field": "Device / Camera", "value": "Apple iPhone 13", "raw_key": "device", "category": "medium" }
  ],
  "overall_risk": { "risk_level": "high", "confidence": 0.88, "source": "ml" },
  "raw_metadata": {
    "thumbnail_b64": "data:image/jpeg;base64,..."
  }
}
```

### `/clean` request (selective)
```
POST /clean
Content-Type: multipart/form-data

file: <your file>
keys: gps,device          ← comma-separated field keys to remove (omit to strip all)
```

### `/cross-check` response
```json
{
  "clusters_found": 1,
  "clusters": [
    {
      "center_lat": 13.0827,
      "center_lon": 80.2707,
      "radius_meters": 250,
      "matched_address": "Raja Muthiah Road, Periamet, Chennai",
      "files": ["photo1.jpg", "photo2.jpg"]
    }
  ],
  "message": "1 cluster detected — 2 files share a location within 250m"
}
```

---

## ✅ Selective Metadata Cleaning

The `/clean` endpoint now supports **surgical field removal** instead of stripping everything:

- The scan results UI displays a **checkbox next to every metadata field**
- High/Medium risk fields are **pre-checked** by default; safe fields are unchecked
- A **Select All / Deselect All** master toggle lets you quickly invert your selection
- Only the checked fields are sent to `/clean` via the `keys` form parameter
- The backend uses `piexif` (images), `python-docx` (DOCX), `openpyxl` (XLSX), and `pikepdf` (PDF) to remove only the requested fields while preserving everything else

---

## 🤖 ML Model Details

- **Algorithm**: Random Forest Classifier (scikit-learn)
- **Training data**: 800 synthetic rows generated with realistic noise (5% random label flips)
- **Features**: `has_gps`, `has_author_pii`, `has_timestamp`, `has_hidden_content`, `has_device_info`, `has_revision_history`, `context`
- **Labels**: `high`, `medium`, `safe`
- **Fallback**: If the model file is missing, a deterministic rule-based scorer is used automatically

---

## 🗺️ GPS Clustering (Cross-File Analysis)

Upload multiple images and IntentGuard uses **DBSCAN with Haversine distance** to find files taken within **250 metres** of each other — even when no single image alone would be flagged.

Each detected cluster is enriched with:

- 🌍 **Reverse-geocoded street address** — the raw `center_lat`/`center_lon` is resolved to a real human-readable address (e.g. *"Raja Muthiah Road, Periamet, Chennai"*) via `geocoder.py`
- 🗾 **Live interactive map** — an embedded OpenStreetMap iframe shows exactly where the cluster is
- 🔗 **Open in Maps** — direct link to the location on openstreetmap.org

> *"2 files share a location within 250m — this may reveal an address or routine location even though neither file alone looked risky."*

The 250m threshold is a named constant (`CLUSTER_RADIUS_METERS`) in `cluster_matcher.py` and can be adjusted.

---

## 📄 DOCX Tracked Changes (Phase 6)

`docx_extractor.py` opens the `.docx` archive directly as a ZIP and parses `word/document.xml` and `word/comments.xml` using `xml.etree.ElementTree` with the correct WordprocessingML namespace. It extracts:

| Element | Meaning |
|---|---|
| `<w:ins>` | Tracked text insertions |
| `<w:del>` | Tracked text deletions |
| `<w:pPrChange>` | Paragraph formatting changes |
| `<w:rPrChange>` | Character/run formatting changes |
| `<w:comment>` | Document comments |

Each entry captures `w:author` and `w:date`, making reviewer identity fully visible.

---

## 📊 XLSX Hidden Data + External References (Phase 7)

`xlsx_extractor.py` now detects three additional risk categories beyond hidden sheets:

1. **Hidden rows** — iterates `ws.row_dimensions` per visible sheet; flags rows where `.hidden = True`
2. **Hidden columns** — iterates `ws.column_dimensions`; flags columns where `.hidden = True`
3. **External workbook references** — scans cell formulas for `[` patterns (e.g. `='C:\Users\john\Documents\[Budget.xlsx]Sheet1'!A1`) which leak local file system paths and usernames. Also checks `xl/externalLinks/` inside the ZIP archive.

---

## 🚫 PDF Fake Redaction Detection (Phase 8)

A common real-world leak: drawing a black box over sensitive PDF text instead of using a proper redaction tool. The box hides the text visually, but the original text remains in the PDF content stream — fully extractable via copy-paste.

`pdf_extractor.py` detects this by:
1. Extracting text bounding boxes per page (via `pdfplumber`)
2. Extracting filled vector rectangles/paths per page (via `pikepdf` content-stream parsing)
3. Computing overlap: any text whose bounding box is substantially covered by an opaque filled shape is flagged

Findings are reported as **CRITICAL** risk with exact page numbers and overlap counts.

> ⚠️ Fake redactions **cannot be automatically cleaned** without corrupting PDF layout — IntentGuard flags them and advises using a certified PDF redaction tool.

---

## 📂 Supported File Types

| Extension | Extractor |
|---|---|
| `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff` | `image_extractor.py` |
| `.docx` | `docx_extractor.py` |
| `.xlsx`, `.xlsm` | `xlsx_extractor.py` |
| `.pdf` | `pdf_extractor.py` |

---

## ⚠️ Limitations (Prototype)

- No authentication on API endpoints
- ML model trained on synthetic data only — not validated against real-world file distributions
- PDF cleaning removes `/Info` and XMP metadata only; fake-redaction removal requires manual intervention
- No persistent storage — all processing is in-memory/temp files
- Reverse geocoding depends on a public nominatim endpoint; may be rate-limited for bulk uploads

---

## 👥 Team

Built for **Hackulus** hackathon.


---

## 🚨 The Problem

Every file you share — a photo, a Word doc, a spreadsheet, a PDF — silently carries hidden metadata:

- 📍 **GPS coordinates** embedded in photos can reveal your home or office address
- 👤 **Author names and revision history** in documents can expose real identities
- 🗂️ **Hidden sheets** in Excel files can contain confidential data invisible to recipients
- 🖥️ **Device information and timestamps** can reveal your OS, software versions, and work schedule

Most people never check. IntentGuard does it for them.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Metadata Extraction** | Extracts hidden metadata from JPG/PNG/TIFF, DOCX, XLSX, and PDF files |
| 📍 **GPS Detection** | Converts raw EXIF GPS data to decimal lat/lon coordinates |
| 🤖 **ML Risk Scoring** | Random Forest classifier predicts risk level (high / medium / safe) with confidence score |
| 🧹 **Metadata Cleaning** | Strips all sensitive metadata and returns a clean copy for download |
| 🗺️ **Cross-File GPS Clustering** | Upload multiple images — DBSCAN with Haversine distance detects shared physical locations across files even when no single file looks risky |
| ⚡ **Context-Aware Risk** | Risk scoring adapts to who you're sharing with (public / team / anonymous) |

---

## 🏗️ Architecture

```
IntentGuard/
├── frontend/
│   └── index.html              # Single-file dark-mode UI (vanilla HTML/CSS/JS)
├── backend/
│   ├── main.py                 # FastAPI app — /scan, /clean, /cross-check, /health
│   ├── requirements.txt
│   ├── extractors/
│   │   ├── image_extractor.py  # EXIF + GPS (exifread)
│   │   ├── docx_extractor.py   # Core properties + tracked changes (python-docx)
│   │   ├── xlsx_extractor.py   # Workbook props + hidden sheets (openpyxl)
│   │   ├── pdf_extractor.py    # /Info dict + XMP metadata (pikepdf)
│   │   └── normalizer.py       # Unifies all extractor output + tags risk category per field
│   ├── ml/
│   │   ├── generate_synthetic_data.py  # Generates 800-row synthetic training dataset
│   │   ├── train_risk_model.py         # Trains Random Forest, saves model
│   │   ├── risk_scorer.py              # Loads model, scores files; rule-based fallback
│   │   └── cluster_matcher.py          # DBSCAN GPS clustering (Haversine metric)
│   ├── cleaner/
│   │   └── clean_file.py       # Strips metadata: image (PIL), docx, xlsx, pdf (pikepdf)
│   └── tests/
│       └── test_extractors.py  # Pytest smoke tests for all extractors
├── sample_files/               # Regenerate with generate_test_files.py
│   └── .gitkeep
└── generate_test_files.py      # Creates realistic fake-metadata test files
```

---

## 🧰 Tech Stack

### Backend
| Library | Purpose |
|---|---|
| **FastAPI** | REST API framework |
| **uvicorn** | ASGI server |
| **exifread** | Parse EXIF tags from images (GPS, device, datetime) |
| **Pillow (PIL)** | Image processing + EXIF stripping for clean |
| **python-docx** | Read/write DOCX core properties and tracked changes |
| **openpyxl** | Read/write XLSX workbook properties and hidden sheets |
| **pikepdf** | Read/write PDF `/Info` dictionary and XMP metadata stream |
| **scikit-learn** | Random Forest classifier + DBSCAN clustering |
| **joblib** | Model serialization |
| **pandas / numpy** | Synthetic data generation and feature engineering |

### Frontend
| Technology | Purpose |
|---|---|
| **Vanilla HTML/CSS/JS** | Single-file UI, no framework needed |
| **Fetch API** | Calls `/scan`, `/clean`, `/cross-check` endpoints |
| **FormData** | Multipart file upload |
| **CSS custom properties** | Dark-mode design system with risk color tokens |

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Train the ML model

```bash
cd backend
python ml/generate_synthetic_data.py
python ml/train_risk_model.py
```

### 3. Start the backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the frontend

Open `frontend/index.html` directly in your browser — or navigate to `http://localhost:8000` if served from the backend root.

### 5. Generate test files (optional)

```bash
pip install piexif python-docx openpyxl pikepdf Pillow
python generate_test_files.py
```

This creates 5 test files in `sample_files/` with realistic fake metadata across all supported formats.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/scan` | Extract + score metadata from a file |
| `POST` | `/clean` | Strip metadata and download cleaned file |
| `POST` | `/cross-check` | Detect shared GPS locations across multiple images |

### `/scan` request
```
POST /scan
Content-Type: multipart/form-data

file: <your file>
context: public | team | anonymous   (default: public)
```

### `/scan` response
```json
{
  "filename": "photo.jpg",
  "file_type": "image",
  "context": "public",
  "metadata": [
    { "field": "GPS Location", "value": "13.0827°N, 80.2707°E", "category": "high" },
    { "field": "Device", "value": "Apple iPhone 13", "category": "medium" }
  ],
  "overall_risk": { "risk_level": "high", "confidence": 0.88, "source": "ml" }
}
```

---

## 🤖 ML Model Details

- **Algorithm**: Random Forest Classifier (scikit-learn)
- **Training data**: 800 synthetic rows generated with realistic noise (5% random label flips)
- **Features**: `has_gps`, `has_author_pii`, `has_timestamp`, `has_hidden_content`, `has_device_info`, `has_revision_history`, `context`
- **Labels**: `high`, `medium`, `safe`
- **Fallback**: If the model file is missing, a deterministic rule-based scorer is used automatically

---

## 🗺️ GPS Clustering (Cross-File Analysis)

Upload multiple images and IntentGuard uses **DBSCAN with Haversine distance** to find files that were taken within **250 metres** of each other — even when no single image alone would be flagged:

> *"2 files share a location within 250m — this may reveal an address or routine location even though neither file alone looked risky."*

The 250m threshold is a named constant (`CLUSTER_RADIUS_METERS`) in `cluster_matcher.py` and can be adjusted.

---

## 📂 Supported File Types

| Extension | Extractor |
|---|---|
| `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff` | `image_extractor.py` |
| `.docx` | `docx_extractor.py` |
| `.xlsx`, `.xlsm` | `xlsx_extractor.py` |
| `.pdf` | `pdf_extractor.py` |

---

## ⚠️ Limitations (Prototype)

- No authentication on API endpoints
- ML model trained on synthetic data only — not validated against real-world file distributions
- DOCX tracked-changes content is detected (flag only) but not extracted in full
- PDF cleaning uses pikepdf; encrypted PDFs will fail gracefully
- No persistent storage — all processing is in-memory/temp files

---

## 👥 Team

Built for **Hackulus** hackathon.
