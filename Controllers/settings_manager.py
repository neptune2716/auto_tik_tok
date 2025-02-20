import os
import json

# Path for persistent settings
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "settings.json")

# Default settings
DEFAULT_SETTINGS = {
    "voice": "random",  # Change default to random
    "subreddit": "funnystories",
    "subreddits": ["funnystories", "shortstories", "stories"],  # Add default subreddits
    "theme": "black",
    "min_words_segment": 150,
    "max_words_segment": 225
}

def load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> None:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
