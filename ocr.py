import os
import io
import sys
import pytesseract
from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QPixmap

def get_default_tesseract_paths():
    """
    Returns a list of common paths where Tesseract might be installed on Windows and macOS.
    """
    paths = []
    if sys.platform == "win32":
        paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        # Also check local app data
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            paths.append(os.path.join(local_appdata, "Tesseract-OCR", "tesseract.exe"))
    elif sys.platform == "darwin":
        paths = [
            "/opt/homebrew/bin/tesseract",       # Apple Silicon Homebrew
            "/usr/local/bin/tesseract",         # Intel Homebrew
            "/usr/bin/tesseract",
        ]
    return paths

def detect_tesseract_binary() -> str:
    """
    Attempts to auto-detect the Tesseract binary path.
    Returns the absolute path if found, or an empty string otherwise.
    """
    # 1. First, check if tesseract is already on the system PATH
    try:
        # We can test if executing 'tesseract' works
        import subprocess
        # On Windows, creationflags prevent opening a blank command prompt window
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        subprocess.run(["tesseract", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags, check=True)
        return "tesseract"  # Ready to run directly from PATH
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 2. Check common search paths
    for path in get_default_tesseract_paths():
        if os.path.exists(path):
            return path
            
    return ""

class OCROperator:
    def __init__(self, settings):
        self.settings = settings

    def extract_text(self, pixmap: QPixmap) -> str:
        """
        Converts QPixmap to PIL Image and extracts text using pytesseract.
        Raises an exception with a helpful user-facing error message if Tesseract is missing or fails.
        """
        if pixmap.isNull():
            return ""

        # 1. Convert QPixmap to PIL Image using an in-memory PNG buffer
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        png_bytes = buffer.data().data()
        buffer.close()

        try:
            pil_image = Image.open(io.BytesIO(png_bytes))
        except Exception as e:
            raise RuntimeError(f"Failed to load image structure: {str(e)}")

        # 2. Configure pytesseract path
        # Use custom settings path if configured, otherwise auto-detected path, otherwise rely on system PATH
        tesseract_bin = self.settings.get_tesseract_path()
        if not tesseract_bin:
            tesseract_bin = detect_tesseract_binary()

        if tesseract_bin and tesseract_bin != "tesseract":
            pytesseract.pytesseract.tesseract_cmd = tesseract_bin

        # 3. Perform OCR
        try:
            text = pytesseract.image_to_string(pil_image)
            return text.strip()
        except pytesseract.TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract OCR executable not found.\n\n"
                "Please make sure Tesseract is installed and configured:\n"
                "- On Windows: Install Tesseract and set its path in the Settings tab.\n"
                "- On macOS: Run 'brew install tesseract' in your terminal."
            )
        except Exception as e:
            raise RuntimeError(f"OCR Error: {str(e)}")
