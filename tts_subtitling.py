import os
import logging
from typing import Optional
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
from config import OUTPUT_DIR, get_project_dirs

logger = logging.getLogger(__name__)

def add_tts_and_subs(video_path: str, story: str, project_id: str) -> Optional[str]:
    """
    Applies text-to-speech on the provided story and adds subtitles to the video.
    
    Args:
        video_path: Path to the input video file
        story: Text content to convert to speech
        project_id: Unique identifier for the project
        
    Returns:
        Path to the final video file or None if failed
        
    Raises:
        IOError: If file operations fail
        RuntimeError: If video processing fails
    """
    try:
        logger.info(f"Processing TTS and subtitles for video: {video_path}")
        dirs = get_project_dirs(project_id)
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
            
        base_name = os.path.basename(video_path).rsplit(".", 1)[0]
        audio_path = os.path.join(dirs['voice'], f"audio_{base_name}.mp3")
        
        tts = gTTS(text=story, lang='en')
        tts.save(audio_path)
        
        # Load video and audio, then combine them.
        clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)
        video_with_audio = clip.set_audio(audio_clip)
        
        final_video = os.path.join(dirs['final'], f"final_{os.path.basename(video_path)}")
        
        logger.info("Writing final video file...")
        video_with_audio.write_videofile(final_video, audio_codec="aac")
        logger.info(f"Successfully created video: {final_video}")
        
        return final_video
        
    except Exception as e:
        logger.error(f"Failed to process video: {str(e)}", exc_info=True)
        raise RuntimeError(f"Video processing failed: {str(e)}")
    finally:
        # Cleanup resources
        if 'clip' in locals(): clip.close()
        if 'audio_clip' in locals(): audio_clip.close()
        if 'video_with_audio' in locals(): video_with_audio.close()
