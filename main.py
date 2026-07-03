import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from overlay import OverlayWindow

def main():
    # 1. Initialize PySide6 application
    app = QApplication(sys.argv)
    app.setApplicationName("Clueless")
    app.setApplicationDisplayName("Clueless Desktop Assistant Overlay")

    # Allow terminal Ctrl+C (SIGINT) to terminate the Qt event loop
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    timer = QTimer()
    timer.start(500)  # wake up the interpreter every 500ms to catch keyboard interrupts
    timer.timeout.connect(lambda: None)

    # 2. Instantiate the main assistant overlay window
    window = OverlayWindow()
    
    # 3. Render the window
    window.show()

    # 4. Apply platform-specific window-sharing / display affinity exclusion flags.
    # Note: This is executed AFTER show() to ensure the platform backing handle 
    # (HWND or NSWindow) is fully initialized and registered by the OS window manager.
    window.apply_capture_exclusion()

    # 5. Start the Qt event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
