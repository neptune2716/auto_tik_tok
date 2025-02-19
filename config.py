import os
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_VIDEO = os.path.join(BASE_DIR, "base_video.mp4")
OUTPUT_DIR = os.path.join(BASE_DIR, "generated")

# Video settings
IMAGEMAGICK_PATH = os.getenv('IMAGEMAGICK_PATH', r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe")
FONT_SIZE = 60
FONT_NAME = "THEBOLDFONT-FREEVERSION"
MIN_WORDS_PER_SEGMENT = 150
MAX_WORDS_PER_SEGMENT = 225

# Reddit settings
SUBREDDIT = "funnystories"
USER_AGENT = "reel_app/0.1"

def get_project_dirs(project_id: str) -> dict:
    """Returns dictionary of project-specific directory paths."""
    project_dir = os.path.join(OUTPUT_DIR, f"Video{project_id}")
    return {
        'project': project_dir,
        'final': os.path.join(project_dir, 'final'),
        'voice': os.path.join(project_dir, 'voice'),
        'script': os.path.join(project_dir, 'script')
    }
