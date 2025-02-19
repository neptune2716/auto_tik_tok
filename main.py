import os
import re
import logging
from typing import List
from reddit_story import get_story
from story_video_generator import process_story_video
from config import BASE_VIDEO, OUTPUT_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_next_project_id(output_dir: str = OUTPUT_DIR) -> str:
    """Find the next available project ID by looking at existing Video folders."""
    os.makedirs(output_dir, exist_ok=True)
    ids = []
    for name in os.listdir(output_dir):
        m = re.match(r'^Video(\d+)$', name)
        if m:
            ids.append(int(m.group(1)))
    return str(max(ids)+1) if ids else "1"

def main() -> None:
    """Main execution function that orchestrates the video generation process."""
    try:
        project_id = find_next_project_id()
        logger.info(f"Starting new project with ID: {project_id}")

        if not os.path.exists(BASE_VIDEO):
            raise FileNotFoundError(f"Base video not found at {BASE_VIDEO}")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                title, story, history = get_story("funnystories", project_id)
                break
            except RuntimeError as e:
                if "No unused stories found" in str(e):
                    if attempt == max_attempts - 1:
                        raise RuntimeError("No new stories available after maximum attempts")
                    logger.warning(f"Attempt {attempt + 1}: No unused stories found, retrying...")
                    continue
                raise

        word_count = len(story.split())
        logger.info(f"Fetched story: {word_count} words")
        logger.info(f"Title: {title}")

        # Générer la vidéo
        output_videos = process_story_video(BASE_VIDEO, title, story, project_id)
        
        # Si on arrive ici, la génération a réussi, on peut mettre à jour l'historique
        history.add_story(title)
        logger.info(f"Story '{title}' added to history")
        
        logger.info(f"Successfully generated {len(output_videos)} video parts")
        for video in output_videos:
            logger.info(f"Generated: {video}")

    except Exception as e:
        logger.error(f"Error during video generation: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()

