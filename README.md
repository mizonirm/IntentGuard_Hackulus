# 🛡️ IntentGuard

**IntentGuard** is a metadata privacy scanner and cleaner that helps you detect and strip sensitive hidden information from files before sharing them. Built as a working prototype for the Hackulus hackathon.

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
| 🎨 **Dark-mode UI** | Drag-and-drop interface with color-coded risk display (red/yellow/green) |
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
