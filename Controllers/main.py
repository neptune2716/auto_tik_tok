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

def sanitize_filename(title: str) -> str:
    """Convert title to a valid folder name"""
    # Remove or replace invalid characters
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    # Replace spaces with underscores and limit length
    return safe_title.replace(' ', '_')[:100]

def find_next_project_id(title: str, output_dir: str = OUTPUT_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)  # Ensure OUTPUT_DIR exists
    if not any(os.scandir(output_dir)):
        # No folder exists yet, use "1" as project_id
        return "1"
    base_name = sanitize_filename(title)
    project_id = base_name
    counter = 1
    while os.path.exists(os.path.join(output_dir, project_id)):
        project_id = f"{base_name}_{counter}"
        counter += 1
    return project_id

def main(subreddit: str, project_id: str, selected_voice: str = "random") -> None:
    """Main execution function that orchestrates the video generation process."""
    try:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # First get the story
                title, story, history = get_story(subreddit, project_id)
                # Then generate project ID from title
                project_id = find_next_project_id(title)
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

        if not os.path.isfile(BASE_VIDEO):
            raise FileNotFoundError(f"Base video not found at {BASE_VIDEO}")

        logger.info(f"Starting new project with ID: {project_id}")

        # Generate the video using the selected voice
        output_videos = process_story_video(BASE_VIDEO, title, story, project_id, voice=selected_voice)
        
        # Si on arrive ici, la génération a réussi, on peut mettre à jour l'historique
        history.add_story(title)
        logger.info(f"Story '{title}' added to history")
        
        logger.info(f"Successfully generated {len(output_videos)} video parts")
        for video in output_videos:
            logger.info(f"Generated: {video}")

    except Exception as e:
        logger.error(f"Error during video generation: {str(e)}", exc_info=True)
        raise

def generate_video(self, selected_voice):
    try:
        # Update progress (10%)
        def update_progress_10():
            self.overall_progress.config(value=10)
        
        self.master.after(0, update_progress_10)
        self.set_status("Fetching story...", "info")
        # Now generate Project ID with title
        project_id = find_next_project_id(subreddit)  # Pass the subreddit argument here

        # Fetch story with the correct project_id
        title, story, _ = get_story(subreddit, project_id)

        # Now generate Project ID with title
        project_id = find_next_project_id(title)  # Pass the title argument here
        self.log_info(f"Starting new project: {project_id}")

        # Update progress (30%)
        self.master.after(0, lambda: self.overall_progress.config(value=30))
        self.set_status("Generating video...", "info")

        # Process video with the correct project_id
        output_files = process_story_video(
            BASE_VIDEO,
            title,
            story,
            project_id,
            voice=selected_voice,
            progress_callback=self.update_progress
        )
        # Update progress (70%)
        self.master.after(0, lambda: self.overall_progress.config(value=70))
        self.set_status("Finalizing video...", "info")

        # Move output files to the final directory
        final_output_dir = os.path.join(OUTPUT_DIR, project_id)
        os.makedirs(final_output_dir, exist_ok=True)
        for file in output_files:
            final_path = os.path.join(final_output_dir, os.path.basename(file))
            os.rename(file, final_path)
            self.log_info(f"Moved {file} to {final_path}")

        # Update progress (100%)
        self.master.after(0, lambda: self.overall_progress.config(value=100))
        self.set_status("Video generation complete!", "success")

    except Exception as e:
        self.set_status(f"Error: {str(e)}", "error")
        self.log_info(f"Error during video generation: {str(e)}")

if __name__ == "__main__":
    subreddit = "funnystories"  # Replace with desired subreddit
    project_id = "temp"  # Replace with desired project_id
    selected_voice = "random"  # Replace with desired voice
    main(subreddit, project_id, selected_voice)

