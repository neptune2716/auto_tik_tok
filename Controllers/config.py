import os
from dotenv import load_dotenv
from settings_manager import load_settings

load_dotenv()

# Load settings for dynamic values
settings = load_settings()

# Paths
# Set BASE_DIR explicitly to the project root with proper Windows path syntax
BASE_DIR = r"C:\Users\cyril\OneDrive\Documents\code\test_vacances"
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "generated")
# Ensure OUTPUT_DIR exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Add missing BASE_VIDEO variable pointing to the base video file
BASE_VIDEO = os.path.join(DATA_DIR, "base_video.mp4")

# Video settings
IMAGEMAGICK_PATH = os.getenv('IMAGEMAGICK_PATH', r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe")
FONT_SIZE = 80  # Taille de base pour une vidéo 1080p
FONT_SIZE_TITLE = FONT_SIZE * 1.2  # 20% plus grand pour les titres
FONT_NAME = "Impact"

# Dynamic segment lengths from settings
MIN_WORDS_PER_SEGMENT = settings.get('min_words_segment', 150)
MAX_WORDS_PER_SEGMENT = settings.get('max_words_segment', 225)

# Reddit settings
SUBREDDIT = "funnystories"
USER_AGENT = "reel_app/0.1"

# TTS Voice settings
VOICE_OPTIONS = [
    "en-US-JennyNeural",     # Female, natural and clear
    "en-US-GuyNeural",       # Male, professional
    "en-GB-SoniaNeural",     # British female
    "en-AU-NatashaNeural"    # Australian female
]

# Update history file path
HISTORY_FILE = os.path.join(DATA_DIR, "story_history.json")

def get_project_dirs(project_id: str) -> dict:
    """Returns dictionary of project-specific directory paths."""
    project_dir = os.path.join(OUTPUT_DIR, project_id)
    return {
        'project': project_dir,
        'final': os.path.join(project_dir, 'final'),
        'voice': os.path.join(project_dir, 'voice'),
        'script': os.path.join(project_dir, 'script')
    }
