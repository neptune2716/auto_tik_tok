import os
import logging
from typing import Tuple
import requests
import random
from config import USER_AGENT, get_project_dirs

logger = logging.getLogger(__name__)

def get_story(subreddit: str, project_id: str) -> Tuple[str, str]:
    """
    Fetches a random story from specified subreddit.
    
    Args:
        subreddit: Name of the subreddit to fetch from
        project_id: Current project identifier
        
    Returns:
        Tuple containing (title, story_text)
        
    Raises:
        requests.RequestException: If Reddit API request fails
        IOError: If story file cannot be written
    """
    logger.info(f"Fetching story from r/{subreddit}")
    
    headers = {'User-Agent': USER_AGENT}
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        valid_posts = []
        if response.status_code == 200:
            data = response.json().get("data", {}).get("children", [])
            for post in data:
                post_data = post.get("data", {})
                if post_data.get("selftext") and post_data.get("id"):
                    valid_posts.append(post_data)
        
        if valid_posts:
            chosen = random.choice(valid_posts)
            title = chosen.get("title", "")
            story_text = chosen.get("selftext", "")
        else:
            title = "No story found"
            story_text = "No story found."
        
        # Use the correct path from config
        dirs = get_project_dirs(project_id)
        script_dir = dirs['script']
        os.makedirs(script_dir, exist_ok=True)
        story_file = os.path.join(script_dir, "raw_story.txt")
        
        with open(story_file, "w", encoding="utf-8") as f:
            f.write(f"{title}\n\n{story_text}")
        
        return title, story_text

    except requests.RequestException as e:
        logger.error(f"Failed to fetch from Reddit: {str(e)}")
        raise

    except IOError as e:
        logger.error(f"Failed to write story file: {str(e)}")
        raise
