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

## Minimizing & System Tray

To keep your workspace clean, Clueless is configured as a floating desktop overlay that does not display in the taskbar.

* **Minimizing:** Click the minimize (`-`) button to hide the overlay.
* **Restoring/Reopening:** Single-click the circular **"C" icon** in the **system tray** (in the notification area on the bottom-right corner of the screen next to the clock). If it's hidden, click the upward arrow (`^`) icon to reveal it.
* **Context Menu:** Right-click the system tray icon to reveal options to show the assistant or exit the application completely.