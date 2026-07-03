import sys
import os
from PySide6.QtCore import Qt, QRect, QPoint, Signal, Slot, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QIcon, QFont, QCursor, QGuiApplication, QFontMetrics
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QTextEdit, QPushButton, QSlider, QStackedWidget,
    QFileDialog, QFrame, QSizePolicy, QSizeGrip, QScrollArea
)

from settings import settings
from capture import CaptureOverlay
from ocr import OCROperator
from llm import LLMWorker, LMStudioChecker
from audio_stub import AudioLoopbackRecorder, WhisperSTTEngine

# A custom QTextEdit that captures the Enter/Return key to send messages,
# allowing Shift+Enter to input new lines.
class ChatInput(QTextEdit):
    enter_pressed = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.enter_pressed.emit()
        else:
            super().keyPressEvent(event)


def format_text_to_html(text: str) -> str:
    """
    Lightweight custom formatter to render bold, inline code, LaTeX math, and line breaks.
    """
    import html
    import re

    # Common LaTeX symbol mappings to standard Unicode characters
    latex_replacements = {
        # Greek letters (lowercase)
        r"\alpha": "α",
        r"\beta": "β",
        r"\gamma": "γ",
        r"\delta": "δ",
        r"\epsilon": "ε",
        r"\zeta": "ζ",
        r"\eta": "η",
        r"\theta": "θ",
        r"\iota": "ι",
        r"\kappa": "κ",
        r"\lambda": "λ",
        r"\mu": "μ",
        r"\nu": "ν",
        r"\xi": "ξ",
        r"\pi": "π",
        r"\rho": "ρ",
        r"\sigma": "σ",
        r"\tau": "τ",
        r"\upsilon": "υ",
        r"\phi": "φ",
        r"\chi": "χ",
        r"\psi": "ψ",
        r"\omega": "ω",
        # Greek letters (uppercase)
        r"\Delta": "Δ",
        r"\Gamma": "Γ",
        r"\Theta": "Θ",
        r"\Lambda": "Λ",
        r"\Xi": "Ξ",
        r"\Pi": "Π",
        r"\Sigma": "Σ",
        r"\Upsilon": "Υ",
        r"\Phi": "Φ",
        r"\Psi": "Ψ",
        r"\Omega": "Ω",
        # Math operators and relations
        r"\times": "×",
        r"\div": "÷",
        r"\cdot": "·",
        r"\pm": "±",
        r"\mp": "∓",
        r"\leq": "≤",
        r"\geq": "≥",
        r"\le": "≤",
        r"\ge": "≥",
        r"\neq": "≠",
        r"\approx": "≈",
        r"\equiv": "≡",
        r"\propto": "∝",
        r"\infty": "∞",
        r"\partial": "∂",
        r"\sum": "∑",
        r"\int": "∫",
        r"\prod": "∏",
        r"\sqrt": "√",
        r"\nabla": "∇",
        r"\in": "∈",
        r"\notin": "∉",
        r"\subset": "⊂",
        r"\supset": "⊃",
        r"\subseteq": "⊆",
        r"\supseteq": "⊇",
        r"\cap": "∩",
        r"\cup": "∪",
        r"\forall": "∀",
        r"\exists": "∃",
        # Arrows
        r"\leftarrow": "←",
        r"\rightarrow": "→",
        r"\to": "→",
        r"\leftrightarrow": "↔",
        r"\Leftarrow": "⇐",
        r"\Rightarrow": "⇒",
        r"\Leftrightarrow": "⇔",
    }

    # 1. Escape basic HTML first
    escaped_text = html.escape(text)

    # 2. Block math $$ ... $$ and \[ ... \]
    escaped_text = re.sub(
        r'\$\$(.*?)\$\$', 
        r'<div style="text-align: center; margin: 6px 0; font-style: italic; font-size: 13px;">\1</div>', 
        escaped_text, 
        flags=re.DOTALL
    )
    escaped_text = re.sub(
        r'\\\[(.*?)\\\]', 
        r'<div style="text-align: center; margin: 6px 0; font-style: italic; font-size: 13px;">\1</div>', 
        escaped_text, 
        flags=re.DOTALL
    )

    # 3. Inline math $ ... $ and \( ... \)
    escaped_text = re.sub(
        r'\$([^\$]+?)\$', 
        r'<span style="font-style: italic;">\1</span>', 
        escaped_text
    )
    escaped_text = re.sub(
        r'\\\((.*?)\\\)', 
        r'<span style="font-style: italic;">\1</span>', 
        escaped_text
    )

    # 4. Math fractions (\frac{a}{b})
    escaped_text = re.sub(
        r'\\frac\{(.*?)\}\{(.*?)\}',
        r'<sup>\1</sup>&frasl;<sub>\2</sub>',
        escaped_text
    )

    # 5. Superscripts and Subscripts
    escaped_text = re.sub(r'\^\{(.*?)\}', r'<sup>\1</sup>', escaped_text)
    escaped_text = re.sub(r'\_\{(.*?)\}', r'<sub>\1</sub>', escaped_text)
    escaped_text = re.sub(r'\^([a-zA-Z0-9])', r'<sup>\1</sup>', escaped_text)
    escaped_text = re.sub(r'\_([a-zA-Z0-9])', r'<sub>\1</sub>', escaped_text)

    # 6. Apply LaTeX replacements
    for latex_sym, unicode_sym in latex_replacements.items():
        escaped_text = escaped_text.replace(latex_sym, unicode_sym)

    # 7. Bold (**text**)
    parts = escaped_text.split("**")
    formatted_parts = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            formatted_parts.append(f"<b>{part}</b>")
        else:
            # 8. Inline code (`code`)
            inline_parts = part.split("`")
            formatted_inline = []
            for inline_idx, inline_part in enumerate(inline_parts):
                if inline_idx % 2 == 1:
                    formatted_inline.append(f"<code>{inline_part}</code>")
                else:
                    formatted_inline.append(inline_part)
            formatted_parts.append("".join(formatted_inline))
            
    result = "".join(formatted_parts)
    result = result.replace("\n", "<br/>")
    return result


class CodeBlockWidget(QWidget):
    def __init__(self, language: str, code_content: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        # 1. Header Bar
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #2a2a30;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 15);
                border-bottom: none;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        lang_label = QLabel(language.upper() if language else "CODE")
        lang_label.setStyleSheet("color: #a0a0a8; font-weight: bold; font-size: 9px; background: transparent; border: none;")
        header_layout.addWidget(lang_label)
        header_layout.addStretch()

        copy_btn = QPushButton("Copy")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #a0a0a8;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 6px;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: rgba(255, 255, 255, 20);
                border-radius: 3px;
            }
        """)
        header_layout.addWidget(copy_btn)
        layout.addWidget(header)

        # 2. Monospace Code Body
        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setPlainText(code_content)
        self.body.setFont(QFont("Consolas", 9))
        self.body.setStyleSheet("""
            QTextEdit {
                background-color: #121215;
                border: 1px solid rgba(255, 255, 255, 15);
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                color: #e0e0e8;
                padding: 6px;
            }
        """)
        layout.addWidget(self.body)
        
        # Connect click event after self.body is initialized
        copy_btn.clicked.connect(self.copy_to_clipboard)
        
        self.update_code(code_content)

    def update_code(self, new_code: str):
        self.body.setPlainText(new_code)
        font_metrics = QFontMetrics(self.body.font())
        line_height = font_metrics.lineSpacing()
        line_count = new_code.count('\n') + 1
        total_height = line_count * line_height + 16
        self.body.setFixedHeight(min(250, max(60, total_height)))

    def copy_to_clipboard(self):
        QGuiApplication.clipboard().setText(self.body.toPlainText())


class MessageBubbleWidget(QWidget):
    def __init__(self, role: str, raw_text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(0)
        
        # Outer bubble frame
        self.bubble_frame = QFrame()
        self.bubble_frame.setObjectName(f"Bubble_{role}")
        
        self.bubble_layout = QVBoxLayout(self.bubble_frame)
        self.bubble_layout.setContentsMargins(10, 8, 10, 8)
        self.bubble_layout.setSpacing(4)
        
        # Sender label
        sender_text = "You" if role == "user" else "Assistant" if role == "assistant" else "System"
        self.sender_label = QLabel(sender_text)
        self.sender_label.setObjectName("BubbleSender")
        self.sender_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.sender_label.setStyleSheet("color: rgba(255, 255, 255, 110); text-transform: uppercase;")
        self.bubble_layout.addWidget(self.sender_label)
        
        # Set alignment and margins based on role
        if role == "user":
            layout.addStretch()
            layout.addWidget(self.bubble_frame)
            self.bubble_frame.setStyleSheet("""
                QFrame#Bubble_user {
                    background-color: rgba(0, 120, 215, 140);
                    border: 1px solid rgba(0, 120, 215, 180);
                    border-radius: 14px;
                    border-bottom-right-radius: 3px;
                }
            """)
            self.bubble_frame.setMaximumWidth(310)
        elif role == "assistant":
            layout.addWidget(self.bubble_frame)
            layout.addStretch()
            self.bubble_frame.setStyleSheet("""
                QFrame#Bubble_assistant {
                    background-color: rgba(255, 255, 255, 18);
                    border: 1px solid rgba(255, 255, 255, 25);
                    border-radius: 14px;
                    border-bottom-left-radius: 3px;
                }
            """)
            self.bubble_frame.setMaximumWidth(310)
        else: # System message
            layout.addWidget(self.bubble_frame)
            self.sender_label.setVisible(False)
            self.bubble_frame.setStyleSheet("""
                QFrame#Bubble_system {
                    background-color: transparent;
                    border: none;
                }
            """)
            
        self.role = role
        self.widgets_list = [] # Store tuple of (is_code, widget)
        self.update_content(raw_text)

    def clear_widgets_from(self, start_idx: int):
        while self.bubble_layout.count() > start_idx + 1:
            item = self.bubble_layout.takeAt(start_idx + 1)
            w = item.widget()
            if w:
                w.deleteLater()
        self.widgets_list = self.widgets_list[:start_idx]

    def update_content(self, raw_text: str):
        is_loading = raw_text.startswith("Thinking.") or raw_text.startswith("Thinking..") or raw_text.startswith("Thinking...")
        
        segments = []
        if is_loading:
            segments.append((False, "", raw_text))
        else:
            parts = raw_text.split("```")
            for idx, part in enumerate(parts):
                if idx % 2 == 1:
                    lines = part.split("\n", 1)
                    lang = lines[0].strip() if len(lines) > 1 else ""
                    code_content = lines[1] if len(lines) > 1 else lines[0]
                    if code_content.strip() or idx == len(parts) - 1:
                        segments.append((True, lang, code_content))
                else:
                    if part.strip() or len(parts) == 1:
                        segments.append((False, "", part))

        # Sync widgets in self.widgets_list with parsed segments
        for i, seg in enumerate(segments):
            is_code, lang, content = seg
            
            if i < len(self.widgets_list):
                curr_is_code, w = self.widgets_list[i]
                if curr_is_code == is_code:
                    if is_code:
                        w.update_code(content)
                    else:
                        formatted = format_text_to_html(content) if self.role != "system" else content
                        w.setText(formatted)
                    continue
                else:
                    self.clear_widgets_from(i)

            # Create new segment widget
            if is_code:
                w = CodeBlockWidget(lang, content)
                self.bubble_layout.addWidget(w)
                self.widgets_list.append((True, w))
            else:
                if self.role == "system":
                    w = QLabel(content)
                    w.setFont(QFont("Segoe UI", 8.5))
                    w.setWordWrap(True)
                    w.setTextFormat(Qt.TextFormat.PlainText)
                    w.setStyleSheet("color: #b0b0b8; font-style: italic;")
                elif is_loading:
                    w = QLabel(content)
                    w.setFont(QFont("Segoe UI", 9))
                    w.setWordWrap(True)
                    w.setStyleSheet("color: #88888f; font-style: italic;")
                else:
                    formatted = format_text_to_html(content)
                    w = QLabel(formatted)
                    w.setFont(QFont("Segoe UI", 9.5))
                    w.setWordWrap(True)
                    w.setTextFormat(Qt.TextFormat.RichText)
                    w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    w.setStyleSheet("color: #ececf1; background-color: transparent;")
                
                self.bubble_layout.addWidget(w)
                self.widgets_list.append((False, w))

        if len(self.widgets_list) > len(segments):
            self.clear_widgets_from(len(segments))


class OverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ocr_operator = OCROperator(settings)
        self.active_llm_worker = None
        self.captured_context_text = ""
        self.chat_history = []  # List of {"role": "user"|"assistant"|"system", "content": "..."}

        # Initialize Phase 2 Stubs
        self.audio_recorder = AudioLoopbackRecorder()
        self.stt_engine = WhisperSTTEngine()

        # Loading animation timer for LLM responses
        from PySide6.QtCore import QTimer
        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(400)
        self.loading_timer.timeout.connect(self.update_loading_animation)
        self.loading_dots_count = 0

        # Set up window properties for a borderless floating overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(320, 480)
        self.resize(380, 600)

        # Variables for manual window dragging
        self.drag_position = QPoint()

        # Setup main container widget with custom style
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)

        # Create layouts
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        # 1. Custom Title Bar
        self.setup_title_bar()

        # 2. Stacked Content Area (Chat View & Settings View)
        self.content_stack = QStackedWidget(self)
        self.main_layout.addWidget(self.content_stack)

        self.setup_chat_view()
        self.setup_settings_view()

        # 3. Status Bar
        self.setup_status_bar()

        # Apply initial styles
        self.apply_stylesheets()

        # Instantiate the screen capture overlay
        self.capture_overlay = CaptureOverlay()
        self.capture_overlay.region_captured.connect(self.on_region_captured)

        # Add a size grip in the bottom-right corner for resizing
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        self.size_grip.setStyleSheet("background: transparent;")
        
        # Position size grip dynamically
        self.resizeEvent = self.on_resize_event

        # Check LMStudio connection on startup
        self.check_lmstudio_status()

    def on_resize_event(self, event):
        super().resizeEvent(event)
        # Place size grip at the bottom right corner
        self.size_grip.move(
            self.width() - self.size_grip.width() - 4,
            self.height() - self.size_grip.height() - 4
        )

    def apply_capture_exclusion(self):
        """
        Applies OS-specific flags to prevent window-capture (Zoom/OBS/Teams).
        Must be called after show() so native window handle (HWND/NSWindow) exists.
        """
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                hwnd = int(self.winId())
                # WDA_EXCLUDEFROMCAPTURE = 0x00000011
                result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
                if result:
                    self.log_system_message("Display affinity: EXCLUDEFROMCAPTURE enabled.")
                else:
                    self.log_system_message(f"Display affinity failed. Error: {ctypes.get_last_error()}")
            except Exception as e:
                self.log_system_message(f"Affinity error: {str(e)}")

        elif sys.platform == "darwin":
            try:
                import objc
                from ctypes import c_void_p
                view_ptr = int(self.winId())
                ns_view = objc.objc_object(c_void_p=view_ptr)
                ns_window = ns_view.window()
                if ns_window:
                    # NSWindowSharingNone = 0
                    ns_window.setSharingType_(0)
                    self.log_system_message("macOS: NSWindowSharingTypeNone enabled.")
                else:
                    self.log_system_message("macOS: Failed to retrieve NSWindow handle.")
            except Exception as e:
                self.log_system_message(f"macOS affinity error: {str(e)}")

    def setup_title_bar(self):
        self.title_bar = QWidget()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(36)
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 10, 0)
        title_layout.setSpacing(8)

        # Title Text
        self.title_label = QLabel("Clueless")
        self.title_label.setObjectName("TitleLabel")
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.title_label.setFont(font)
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        # Top-most lock toggle
        self.topmost_btn = QPushButton("Pin")
        self.topmost_btn.setObjectName("TitleButton")
        self.topmost_btn.setToolTip("Toggle Always on Top")
        self.topmost_btn.setCheckable(True)
        self.topmost_btn.setChecked(True)
        self.topmost_btn.clicked.connect(self.toggle_always_on_top)
        title_layout.addWidget(self.topmost_btn)

        # Settings toggle button
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("TitleButton")
        self.settings_btn.setToolTip("Open Settings")
        self.settings_btn.clicked.connect(self.toggle_settings_panel)
        title_layout.addWidget(self.settings_btn)

        # Minimize Button
        self.minimize_btn = QPushButton("-")
        self.minimize_btn.setObjectName("TitleButton")
        self.minimize_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(self.minimize_btn)

        # Close Button
        self.close_btn = QPushButton("X")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.clicked.connect(self.close)
        title_layout.addWidget(self.close_btn)

        self.main_layout.addWidget(self.title_bar)

        # Bind window dragging event handlers
        self.title_bar.mousePressEvent = self.title_bar_press
        self.title_bar.mouseMoveEvent = self.title_bar_move

    # Mouse dragging logic
    def title_bar_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def setup_chat_view(self):
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(6, 6, 6, 6)
        chat_layout.setSpacing(5)

        # Chat Scroll Area for native bubbles
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("ChatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(6, 6, 6, 6)
        self.scroll_layout.setSpacing(6)
        self.scroll_layout.addStretch() # Push messages to bottom
        
        self.chat_scroll.setWidget(self.scroll_content)
        chat_layout.addWidget(self.chat_scroll)

        # Captured Context Bar (Hidden until content exists)
        self.context_frame = QFrame()
        self.context_frame.setObjectName("ContextFrame")
        self.context_frame.setFixedHeight(28)
        self.context_frame.setVisible(False)
        
        context_layout = QHBoxLayout(self.context_frame)
        context_layout.setContentsMargins(6, 0, 6, 0)
        
        self.context_label = QLabel("Screen OCR Context Active")
        self.context_label.setObjectName("ContextLabel")
        context_layout.addWidget(self.context_label)
        
        context_layout.addStretch()
        
        clear_context_btn = QPushButton("Clear")
        clear_context_btn.setObjectName("ClearContextButton")
        clear_context_btn.clicked.connect(self.clear_screen_context)
        context_layout.addWidget(clear_context_btn)
        
        chat_layout.addWidget(self.context_frame)

        # Input Area Panel
        input_panel = QFrame()
        input_panel.setObjectName("InputPanel")
        input_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(4, 4, 4, 4)
        input_layout.setSpacing(4)

        # Text input field
        self.input_field = ChatInput()
        self.input_field.setObjectName("InputField")
        self.input_field.setPlaceholderText("Type a prompt... (Shift+Enter for newline)")
        self.input_field.setFixedHeight(36)
        self.input_field.enter_pressed.connect(self.send_user_message)
        input_layout.addWidget(self.input_field)

        # Buttons bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        # Capture Screen Button
        self.capture_btn = QPushButton("Capture Region")
        self.capture_btn.setObjectName("ActionButton")
        self.capture_btn.clicked.connect(self.start_region_capture)
        btn_layout.addWidget(self.capture_btn)

        # Phase 2 Microphone Button (STT Stub)
        self.mic_btn = QPushButton("Mic")
        self.mic_btn.setObjectName("ActionButton")
        self.mic_btn.setEnabled(True)
        self.mic_btn.setToolTip("Phase 2: Real-time Audio Loopback & Transcription")
        self.mic_btn.clicked.connect(self.trigger_mic_stub_alert)
        btn_layout.addWidget(self.mic_btn)

        btn_layout.addStretch()

        # Send Button
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("SendButton")
        self.send_btn.clicked.connect(self.send_user_message)
        btn_layout.addWidget(self.send_btn)

        input_layout.addLayout(btn_layout)
        chat_layout.addWidget(input_panel)

        self.content_stack.addWidget(chat_widget)
        self.log_system_message("Welcome! Click 'Capture Region' to capture any screen content for OCR context.")

    def setup_settings_view(self):
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("SettingsTitle")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        settings_layout.addWidget(title)

        # 1. API URL
        settings_layout.addWidget(QLabel("LMStudio API URL:"))
        self.api_input = QTextEdit()
        self.api_input.setFixedHeight(28)
        self.api_input.setPlaceholderText("http://localhost:1234/v1")
        self.api_input.setText(settings.get_api_url())
        settings_layout.addWidget(self.api_input)

        # 2. Model Name
        settings_layout.addWidget(QLabel("LMStudio Model ID:"))
        self.model_input = QTextEdit()
        self.model_input.setFixedHeight(28)
        self.model_input.setPlaceholderText("local-model")
        self.model_input.setText(settings.get_model_name())
        settings_layout.addWidget(self.model_input)

        # 3. Tesseract Path
        settings_layout.addWidget(QLabel("Tesseract OCR Binary Path:"))
        tess_layout = QHBoxLayout()
        self.tess_input = QTextEdit()
        self.tess_input.setFixedHeight(28)
        self.tess_input.setPlaceholderText("Auto-detected if blank")
        self.tess_input.setText(settings.get_tesseract_path())
        tess_layout.addWidget(self.tess_input)

        tess_browse = QPushButton("...")
        tess_browse.setObjectName("ActionButton")
        tess_browse.setFixedWidth(30)
        tess_browse.clicked.connect(self.browse_tesseract_path)
        tess_layout.addWidget(tess_browse)
        settings_layout.addLayout(tess_layout)

        # 4. Opacity
        settings_layout.addWidget(QLabel("Overlay Window Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(20)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(int(settings.get_overlay_opacity() * 100))
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        settings_layout.addWidget(self.opacity_slider)

        settings_layout.addStretch()

        # Save/Back Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_settings_btn = QPushButton("Save & Back")
        self.save_settings_btn.setObjectName("SendButton")
        self.save_settings_btn.clicked.connect(self.save_settings_and_return)
        btn_layout.addWidget(self.save_settings_btn)

        settings_layout.addLayout(btn_layout)
        self.content_stack.addWidget(settings_widget)

    def setup_status_bar(self):
        self.status_bar = QWidget()
        self.status_bar.setObjectName("StatusBar")
        self.status_bar.setFixedHeight(24)
        
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        
        self.status_label = QLabel("LMStudio: Checking...")
        self.status_label.setObjectName("StatusLabel")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.main_layout.addWidget(self.status_bar)

    def toggle_always_on_top(self):
        is_top = self.topmost_btn.isChecked()
        settings.set_always_on_top(is_top)
        
        # In Qt, changing window flags requires calling show() again
        pos = self.pos()
        size = self.size()
        if is_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(QRect(pos, size))
        self.show()
        # Re-apply window exclusion display affinity if needed
        self.apply_capture_exclusion()

    def toggle_settings_panel(self):
        if self.content_stack.currentIndex() == 0:
            self.content_stack.setCurrentIndex(1)
            self.settings_btn.setText("Chat")
            self.settings_btn.setToolTip("Back to Chat")
        else:
            self.toggle_settings_panel_back()

    def toggle_settings_panel_back(self):
        self.content_stack.setCurrentIndex(0)
        self.settings_btn.setText("Settings")
        self.settings_btn.setToolTip("Open Settings")

    def browse_tesseract_path(self):
        file_filter = "Executable Files (*.exe);;All Files (*)" if sys.platform == "win32" else "All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Tesseract Binary", "", file_filter)
        if file_path:
            self.tess_input.setText(file_path)

    def on_opacity_changed(self, value):
        opacity = value / 100.0
        settings.set_overlay_opacity(opacity)
        self.setWindowOpacity(opacity)

    def save_settings_and_return(self):
        settings.set_api_url(self.api_input.toPlainText().strip())
        settings.set_model_name(self.model_input.toPlainText().strip())
        settings.set_tesseract_path(self.tess_input.toPlainText().strip())
        
        self.toggle_settings_panel_back()
        self.check_lmstudio_status()

    def start_region_capture(self):
        # 1. Hide self to avoid occlusion (even if capture affinity is set, hiding is cleanest)
        self.hide()
        # 2. Wait briefly for window animation to complete, then show selection overlay
        self.capture_overlay.show_capture()

    @Slot(QRect)
    def on_region_captured(self, rect: QRect):
        # 1. Restore overlay window
        self.show()
        self.raise_()
        self.activateWindow()

        # 2. Grab screen area
        screen = QGuiApplication.primaryScreen()
        if not screen:
            self.log_system_message("Error: Screen capture interface unavailable.")
            return

        try:
            pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
            
            # 3. Perform OCR
            self.status_label.setText("OCR: Processing captured region...")
            extracted = self.ocr_operator.extract_text(pixmap)
            
            if extracted:
                self.captured_context_text = extracted
                chars_count = len(extracted)
                self.context_label.setText(f"Screen Context ({chars_count} chars)")
                self.context_frame.setVisible(True)
                self.log_system_message(f"OCR Successful! Captured {chars_count} characters.")
            else:
                self.log_system_message("OCR Complete: No text detected in the selected area.")
                
        except Exception as e:
            self.log_system_message(f"OCR Failed: {str(e)}")
        
        self.status_label.setText("OCR: Idle")

    def clear_screen_context(self):
        self.captured_context_text = ""
        self.context_frame.setVisible(False)
        self.log_system_message("Screen OCR context cleared.")

    def trigger_mic_stub_alert(self):
        self.log_system_message(
            "<b>Phase 2 Feature Stub:</b> Real-time system audio and microphone loopback capture.<br/>"
            "This will stream raw audio buffers to a local Whisper STT model instance to feed live conversational context into the SLM prompt chain."
        )

    def check_lmstudio_status(self):
        self.status_label.setText("LMStudio: Connecting...")
        self.checker = LMStudioChecker(settings.get_api_url())
        self.checker.status_checked.connect(self.on_lmstudio_status_checked)
        self.checker.start()

    @Slot(bool, list)
    def on_lmstudio_status_checked(self, is_alive: bool, models: list):
        if is_alive:
            models_str = f" [{', '.join(models)}]" if models else ""
            self.status_label.setText(f"LMStudio: Online{models_str}")
            # If the user's config model name is default, and models are returned, auto-select first model
            if settings.get_model_name() == "local-model" and models:
                settings.set_model_name(models[0])
                self.model_input.setText(models[0])
        else:
            self.status_label.setText("LMStudio: Offline (Verify endpoint in Settings)")

    def log_system_message(self, text: str):
        self.chat_history.append({"role": "system", "content": text})
        self.add_chat_message("system", text)

    def add_chat_message(self, role: str, text: str) -> MessageBubbleWidget:
        bubble = MessageBubbleWidget(role, text)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.scroll_to_bottom(force=True))
        return bubble

    def scroll_to_bottom(self, force=False):
        scrollbar = self.chat_scroll.verticalScrollBar()
        if force or scrollbar.value() >= scrollbar.maximum() - 40:
            scrollbar.setValue(scrollbar.maximum())

    def update_loading_animation(self):
        self.loading_dots_count = (self.loading_dots_count % 3) + 1
        dots = "." * self.loading_dots_count
        if hasattr(self, "active_assistant_bubble") and self.active_assistant_bubble:
            self.active_assistant_bubble.update_content(f"Thinking{dots}")

    def send_user_message(self):
        user_text = self.input_field.toPlainText().strip()
        if not user_text and not self.captured_context_text:
            return

        # Cancel any active running model generation
        if self.active_llm_worker and self.active_llm_worker.isRunning():
            self.active_llm_worker.cancel()
            self.active_llm_worker.wait()

        # Display user message in chat
        display_text = user_text if user_text else "[Sent Screen OCR Context Only]"
        self.chat_history.append({"role": "user", "content": display_text})
        self.add_chat_message("user", display_text)
        self.input_field.clear()

        # Formulate messages prompt
        # We append OCR text as hidden system prompt context
        messages = []
        if self.captured_context_text:
            system_prompt = (
                "You are an offline desktop AI assistant overlay. "
                "The user has captured a portion of their screen containing text. "
                "Here is the text extracted via OCR from the user's screen:\n"
                "--------------------------------------------------\n"
                f"{self.captured_context_text}\n"
                "--------------------------------------------------\n"
                "Use this screen content as context to answer their question."
            )
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system", 
                "content": "You are a helpful offline desktop AI assistant overlay."
            })

        # Append previous conversation history (excluding system logs)
        for msg in self.chat_history:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Setup streaming worker
        self.status_label.setText("LMStudio: Generating response...")
        self.chat_history.append({"role": "assistant", "content": ""}) # placeholder for streamed content
        self.active_assistant_bubble = self.add_chat_message("assistant", "")
        self.loading_dots_count = 0
        self.update_loading_animation()
        self.loading_timer.start()
        
        self.active_llm_worker = LLMWorker(
            settings.get_api_url(),
            settings.get_model_name(),
            messages
        )
        self.active_llm_worker.token_received.connect(self.on_token_received)
        self.active_llm_worker.finished.connect(self.on_generation_finished)
        self.active_llm_worker.error.connect(self.on_generation_error)
        self.active_llm_worker.start()

    @Slot(str)
    def on_token_received(self, token: str):
        if self.loading_timer.isActive():
            self.loading_timer.stop()
            self.active_assistant_bubble.update_content("")

        if self.chat_history and self.chat_history[-1]["role"] == "assistant":
            self.chat_history[-1]["content"] += token
            self.active_assistant_bubble.update_content(self.chat_history[-1]["content"])
            self.scroll_to_bottom(force=False)

    @Slot(str)
    def on_generation_finished(self, full_response: str):
        if self.loading_timer.isActive():
            self.loading_timer.stop()
        self.status_label.setText("LMStudio: Ready")
        # Clear OCR context after it's been consumed in a prompt to avoid stale context
        self.clear_screen_context()

    @Slot(str)
    def on_generation_error(self, err_msg: str):
        if self.loading_timer.isActive():
            self.loading_timer.stop()
        self.status_label.setText("LMStudio: Error")
        if self.chat_history and self.chat_history[-1]["role"] == "assistant":
            self.chat_history[-1]["content"] = f"<span style='color: #ff5555;'>[Error: {err_msg}]</span>"
            self.active_assistant_bubble.update_content(self.chat_history[-1]["content"])

    def simple_markdown_to_html(self, text: str) -> str:
        """
        Lightweight custom Markdown-like formatter to render structured formatting 
        without external python dependencies.
        """
        import html
        escaped_text = html.escape(text)

        # 1. Code blocks (```code```)
        parts = escaped_text.split("```")
        formatted_parts = []
        for idx, part in enumerate(parts):
            if idx % 2 == 1:
                # Inside code block
                # Attempt to extract language if any
                lines = part.split("\n", 1)
                code = part
                if len(lines) > 1 and len(lines[0]) < 15 and not any(c in lines[0] for c in (' ', '{', '=')):
                    code = lines[1]
                formatted_parts.append(f"<pre><code>{code}</code></pre>")
            else:
                # Outside code block, format bold and inline code
                sub_parts = part.split("**")
                formatted_sub = []
                for sub_idx, sub_part in enumerate(sub_parts):
                    if sub_idx % 2 == 1:
                        formatted_sub.append(f"<b>{sub_part}</b>")
                    else:
                        # Inline code (`code`)
                        inline_parts = sub_part.split("`")
                        formatted_inline = []
                        for inline_idx, inline_part in enumerate(inline_parts):
                            if inline_idx % 2 == 1:
                                formatted_inline.append(f"<code>{inline_part}</code>")
                            else:
                                formatted_inline.append(inline_part)
                        formatted_sub.append("".join(formatted_inline))
                formatted_parts.append("".join(formatted_sub))
        
        result = "".join(formatted_parts)
        # Convert newlines to breaks
        result = result.replace("\n", "<br/>")
        return result

    def apply_stylesheets(self):
        # Global CSS-like rules for QT styling (QSS)
        self.setStyleSheet("""
            #CentralWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(32, 32, 40, 240), stop:1 rgba(20, 20, 25, 240));
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 12px;
            }
            #TitleBar {
                background-color: rgba(0, 0, 0, 60);
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
                border-bottom: 1px solid rgba(255, 255, 255, 20);
            }
            #TitleLabel {
                color: #ffffff;
            }
            #TitleButton {
                background-color: transparent;
                border: none;
                color: #bbbbbb;
                padding: 2px 6px;
                font-size: 11px;
            }
            #TitleButton:hover {
                color: #ffffff;
                background-color: rgba(255, 255, 255, 20);
                border-radius: 4px;
            }
            #TitleButton:checked {
                color: #00a2e8;
                background-color: rgba(0, 162, 232, 25);
                border-radius: 4px;
            }
            #CloseButton {
                background-color: transparent;
                border: none;
                color: #ff5555;
                padding: 2px 6px;
                font-size: 11px;
            }
            #CloseButton:hover {
                color: #ffffff;
                background-color: #ff3333;
                border-radius: 4px;
            }
            #ChatScroll {
                background-color: rgba(0, 0, 0, 70);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 8px;
            }
            #ScrollContent {
                background-color: transparent;
            }
            #ContextFrame {
                background-color: rgba(0, 162, 232, 25);
                border: 1px solid rgba(0, 162, 232, 50);
                border-radius: 6px;
            }
            #ContextLabel {
                color: #00cbff;
                font-size: 11px;
            }
            #ClearContextButton {
                background-color: rgba(255, 255, 255, 15);
                border: none;
                color: #ffffff;
                font-size: 9px;
                padding: 2px 6px;
                border-radius: 3px;
            }
            #ClearContextButton:hover {
                background-color: rgba(255, 85, 85, 150);
            }
            #InputPanel {
                background-color: rgba(0, 0, 0, 50);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 8px;
            }
            #InputField {
                background-color: transparent;
                border: none;
                color: #ffffff;
                font-size: 13px;
            }
            #ActionButton {
                background-color: rgba(255, 255, 255, 15);
                border: 1px solid rgba(255, 255, 255, 20);
                color: #e2e2e2;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
            }
            #ActionButton:hover {
                background-color: rgba(255, 255, 255, 25);
                color: #ffffff;
            }
            #ActionButton:disabled {
                color: #666666;
                border-color: rgba(255, 255, 255, 8);
                background-color: rgba(255, 255, 255, 3);
            }
            #SendButton {
                background-color: #0078d7;
                border: none;
                color: #ffffff;
                border-radius: 5px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            #SendButton:hover {
                background-color: #0086f0;
            }
            #StatusBar {
                background-color: rgba(0, 0, 0, 80);
                border-bottom-left-radius: 11px;
                border-bottom-right-radius: 11px;
                border-top: 1px solid rgba(255, 255, 255, 15);
            }
            #StatusLabel {
                color: #a0a0a8;
                font-size: 10px;
            }
            QLabel {
                color: #dddddd;
                font-size: 11px;
            }
            QTextEdit {
                background-color: rgba(0, 0, 0, 100);
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 4px;
                color: #ffffff;
                padding: 3px;
            }
            #SettingsTitle {
                color: #ffffff;
            }
        """)
        self.setWindowOpacity(settings.get_overlay_opacity())
