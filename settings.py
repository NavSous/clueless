class AppSettings:
    def __init__(self):
        # Default settings
        self.api_url = "http://localhost:1234/v1"
        self.model_name = "local-model"
        self.tesseract_path = ""
        self.overlay_opacity = 0.85
        self.always_on_top = True
        self.live_screen_enabled = False

    def get_live_screen_enabled(self) -> bool:
        return self.live_screen_enabled

    def set_live_screen_enabled(self, enable: bool):
        self.live_screen_enabled = enable


    def get_api_url(self) -> str:
        return self.api_url

    def set_api_url(self, url: str):
        self.api_url = url

    def get_model_name(self) -> str:
        return self.model_name

    def set_model_name(self, name: str):
        self.model_name = name

    def get_tesseract_path(self) -> str:
        return self.tesseract_path

    def set_tesseract_path(self, path: str):
        self.tesseract_path = path

    def get_overlay_opacity(self) -> float:
        return self.overlay_opacity

    def set_overlay_opacity(self, opacity: float):
        # Bound opacity between 0.2 and 1.0
        self.overlay_opacity = max(0.2, min(1.0, opacity))

    def get_always_on_top(self) -> bool:
        return self.always_on_top

    def set_always_on_top(self, enable: bool):
        self.always_on_top = enable


# Shared global instance of settings for this running instance
settings = AppSettings()
