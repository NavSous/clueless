import os
import tempfile
import wave
import requests
from PySide6.QtCore import QObject, Signal, QThread, QFile, QIODevice
from PySide6.QtMultimedia import QAudioSource, QAudioFormat, QMediaDevices

class AudioLoopbackRecorder(QObject):
    """
    Audio recorder using Qt's native raw audio capture (QAudioSource).
    Captures raw PCM bytes and compiles a standard PCM WAV file using Python's wave library.
    This guarantees 100% compatibility with SpeechRecognition and local transcription endpoints.
    """
    status_message = Signal(str)

    def __init__(self):
        super().__init__()
        # Set up the standard mono 16kHz Int16 format
        self.format = QAudioFormat()
        self.format.setSampleRate(16000)
        self.format.setChannelCount(1)
        self.format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self.audio_source = None
        self.raw_file = QFile()
        
        self.temp_raw_path = os.path.join(tempfile.gettempdir(), "clueless_voice_input.raw")
        self.temp_wav_path = os.path.join(tempfile.gettempdir(), "clueless_voice_input.wav")

    def start_recording(self) -> bool:
        if self.is_recording():
            return True

        # Clean up existing files
        for path in [self.temp_raw_path, self.temp_wav_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        self.raw_file.setFileName(self.temp_raw_path)
        if not self.raw_file.open(QIODevice.OpenModeFlag.WriteOnly):
            self.status_message.emit("Failed to open temporary file for writing.")
            return False

        device = QMediaDevices.defaultAudioInput()
        # Fallback if preferred format doesn't support our default
        if not device.isFormatSupported(self.format):
            self.format = device.preferredFormat()
            self.format.setChannelCount(1) # Keep it mono

        self.audio_source = QAudioSource(device, self.format, self)
        self.audio_source.start(self.raw_file)
        self.status_message.emit("Recording...")
        return True

    def stop_recording(self) -> str:
        if not self.is_recording():
            return self.temp_wav_path

        if self.audio_source:
            self.audio_source.stop()
            self.audio_source = None

        self.raw_file.close()

        # Convert raw PCM to standard WAV
        try:
            sample_width = 2  # Int16 is 2 bytes
            if self.format.sampleFormat() == QAudioFormat.SampleFormat.Int32:
                sample_width = 4
            elif self.format.sampleFormat() == QAudioFormat.SampleFormat.UInt8:
                sample_width = 1
            elif self.format.sampleFormat() == QAudioFormat.SampleFormat.Float:
                sample_width = 4
                
            self.convert_raw_to_wav(
                self.temp_raw_path, 
                self.temp_wav_path, 
                self.format.sampleRate(), 
                self.format.channelCount(),
                sample_width
            )
            self.status_message.emit("Recording stopped.")
        except Exception as e:
            self.status_message.emit(f"Failed to compile WAV file: {str(e)}")

        return self.temp_wav_path

    def is_recording(self) -> bool:
        return self.audio_source is not None

    def convert_raw_to_wav(self, raw_path, wav_path, sample_rate, channels, sample_width):
        with open(raw_path, "rb") as raw_file:
            pcm_data = raw_file.read()
            
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)


class STTWorker(QThread):
    """
    Background worker thread to perform audio transcription without freezing the UI.
    """
    finished = Signal(str)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, api_url: str, file_path: str, model_name: str = "whisper-1"):
        super().__init__()
        self.api_url = api_url.rstrip('/')
        self.file_path = file_path
        self.model_name = model_name

    def run(self):
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            self.error.emit("Audio file is empty or missing. Please speak clearly.")
            return

        self.status.emit("Uploading audio for transcription...")

        # 1. Attempt LMStudio/OpenAI-compatible local endpoint first
        url = f"{self.api_url}/audio/transcriptions"
        try:
            with open(self.file_path, "rb") as f:
                files = {"file": (os.path.basename(self.file_path), f, "audio/wav")}
                data = {"model": self.model_name}
                response = requests.post(url, files=files, data=data, timeout=20.0)

            if response.status_code == 200:
                text = response.json().get("text", "").strip()
                if text:
                    self.finished.emit(text)
                    return
                else:
                    self.error.emit("Received empty transcription from local server.")
                    return
            else:
                self.status.emit(f"LMStudio STT failed (HTTP {response.status_code}). Trying SpeechRecognition fallback...")
        except Exception as e:
            self.status.emit("LMStudio STT unavailable. Trying SpeechRecognition fallback...")

        # 2. Fallback to local SpeechRecognition package (Google/Sphinx APIs)
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(self.file_path) as source:
                audio = recognizer.record(source)

            # Try free online Google API (highly accurate, no API key needed)
            try:
                self.status.emit("Transcribing via Google Speech API...")
                text = recognizer.recognize_google(audio).strip()
                if text:
                    self.finished.emit(text)
                    return
            except Exception:
                pass

            # Try pocketsphinx (fully offline if installed)
            try:
                self.status.emit("Transcribing via pocketsphinx offline fallback...")
                text = recognizer.recognize_sphinx(audio).strip()
                if text:
                    self.finished.emit(text)
                    return
            except Exception:
                pass

            self.error.emit("Could not transcribe audio using SpeechRecognition fallbacks.")
        except ImportError:
            self.error.emit(
                "STT failed. Please make sure a Whisper model is loaded in LMStudio,\n"
                "or install the local speech recognition library:\n"
                "'pip install SpeechRecognition'"
            )
        except Exception as e:
            self.error.emit(f"Transcription failed: {str(e)}")


class WhisperSTTEngine(QObject):
    """
    Local Speech-To-Text (STT) Engine wrapper.
    Spawns background STTWorker threads to process audio files.
    """
    transcription_complete = Signal(str)
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.model_loaded = True
        self._worker = None

    def load_model(self, model_size="base") -> bool:
        # Not needed since we offload transcription to LMStudio/SpeechRecognition API
        return True

    def transcribe_audio_file(self, api_url: str, file_path: str, model_name: str = "whisper-1"):
        # Terminate active worker if running to avoid overlaps
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

        self._worker = STTWorker(api_url, file_path, model_name)
        self._worker.status.connect(self.status_message.emit)
        self._worker.finished.connect(self.transcription_complete.emit)
        self._worker.error.connect(self.error_occurred.emit)
        self._worker.start()

    def transcribe_audio_chunk(self, audio_data: bytes) -> str:
        # Provided for backward-compatibility with older stubs
        return "[Legacy API Chunk Transcription Not Supported]"
