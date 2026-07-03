import json
import requests
from PySide6.QtCore import QThread, Signal

class LLMWorker(QThread):
    # Signals for UI communication
    token_received = Signal(str)  # Emitted for each streaming chunk
    finished = Signal(str)        # Emitted when stream completes, passing full text
    error = Signal(str)           # Emitted on connection error or status failure

    def __init__(self, api_url: str, model_name: str, messages: list):
        super().__init__()
        self.api_url = api_url.rstrip('/')
        self.model_name = model_name
        self.messages = messages
        self._is_cancelled = False

    def cancel(self):
        """
        Interrupts the active network stream.
        """
        self._is_cancelled = True

    def run(self):
        url = f"{self.api_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model_name,
            "messages": self.messages,
            "stream": True
        }

        try:
            # We set a 5-second connect timeout, but omit read timeout to allow streaming
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=(5.0, None))
            
            if response.status_code != 200:
                self.error.emit(f"Server returned HTTP status code {response.status_code}: {response.text}")
                return

            full_text = ""
            for line in response.iter_lines():
                if self._is_cancelled:
                    break
                
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    # Server-Sent Events (SSE) format prefix
                    if decoded_line.startswith("data: "):
                        data_str = decoded_line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data_json = json.loads(data_str)
                            choices = data_json.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_text += content
                                    self.token_received.emit(content)
                        except json.JSONDecodeError:
                            continue

            if not self._is_cancelled:
                self.finished.emit(full_text)

        except requests.exceptions.Timeout:
            self.error.emit("Connection timed out. Ensure LMStudio server is running.")
        except requests.exceptions.ConnectionError:
            self.error.emit("Connection refused. Is LMStudio running on this address/port?")
        except Exception as e:
            self.error.emit(f"Request failed: {str(e)}")


class LMStudioChecker(QThread):
    status_checked = Signal(bool, list)  # Emits (is_available, list_of_models)

    def __init__(self, api_url: str):
        super().__init__()
        self.api_url = api_url.rstrip('/')

    def run(self):
        url = f"{self.api_url}/models"
        try:
            response = requests.get(url, timeout=3.0)
            if response.status_code == 200:
                data = response.json()
                models = [model["id"] for model in data.get("data", [])]
                self.status_checked.emit(True, models)
            else:
                self.status_checked.emit(False, [])
        except Exception:
            self.status_checked.emit(False, [])
