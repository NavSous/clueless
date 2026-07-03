# Clueless

Local cross-platform offline desktop SLM assistant overlay.

## Prerequisites

1. Install Tesseract OCR:
   - Windows: Run `winget install UB-Mannheim.TesseractOCR`
   - macOS: Run `brew install tesseract`
2. Run LMStudio locally on http://localhost:1234 with a loaded model.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

## Core Features

- Always-on-top borderless translucent chat interface.
- OS-level window display affinity exclusion (invisible to Zoom, Teams, Meet, OBS).
- Built-in screen region capture and OCR context feed.
- Offline streaming completions from local LMStudio.
- Live screen OCR context awareness (automatic background capture of visible desktop contents).