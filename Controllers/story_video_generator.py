import os
import re
import random
import logging
import asyncio
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, VideoClip
from moviepy.config import change_settings
from typing import List, Tuple
from config import (
    IMAGEMAGICK_PATH, FONT_SIZE, FONT_NAME,
    MIN_WORDS_PER_SEGMENT, MAX_WORDS_PER_SEGMENT, OUTPUT_DIR,
    get_project_dirs, VOICE_OPTIONS
)
from proglog import ProgressBarLogger

logger = logging.getLogger(__name__)

# Set the ImageMagick binary path (update as needed)
change_settings({"IMAGEMAGICK_BINARY": IMAGEMAGICK_PATH})

def split_text_into_segments(story: str, min_words: int = MIN_WORDS_PER_SEGMENT, max_words: int = MAX_WORDS_PER_SEGMENT) -> list:
    """
    Splits the story into segments at sentence boundaries with overlap.
    Returns a list of segments.
    """
    sentences = re.split(r'(?<=[.!?])\s+', story)
    segments = []
    current_segment = ""
    current_count = 0
    
    for sentence in sentences:
        words = sentence.split()
        count = len(words)
        
        if current_count + count <= max_words:
            current_segment = f"{current_segment} {sentence}".strip()
            current_count += count
        else:
            if current_count < min_words:
                current_segment = f"{current_segment} {sentence}".strip()
                current_count += count
            else:
                segments.append(current_segment)
                current_segment = sentence
                current_count = count
    
    if current_segment:
        segments.append(current_segment)
    
    # Add overlap between segments
    final_segments = []
    for i, segment in enumerate(segments):
        if i > 0:
            # Get last sentence from previous segment
            prev_segment = segments[i-1]
            last_sentence = re.split(r'(?<=[.!?])\s+', prev_segment)[-1]
            segment = f"{last_sentence}\n\n{segment}"
        final_segments.append(segment)
    
    return final_segments

def create_dynamic_text_clip(text: str, total_duration: float, video_width: int, fontsize: int = FONT_SIZE, font: str = FONT_NAME, position: str = 'center') -> VideoClip:
    """
    Creates a text clip with enhanced visibility and contrast.
    """
    margin = int(video_width * 0.05)
    processed_text = text.upper().replace("-", "-\n")
    
    # Create main text
    main_text = TextClip(
        processed_text,
        fontsize=fontsize,
        font=font,
        color='white',
        method='caption',
        size=(video_width - 2 * margin, None),
        align='center',
        stroke_color='black',
        stroke_width=2.5
    )
    
    # Create shadow text
    shadow = TextClip(
        processed_text,
        fontsize=fontsize,
        font=font,
        color='black',
        method='caption',
        size=(video_width - 2 * margin, None),
        align='center'
    ).set_position(lambda t: (2, 2))
    
    final_clip = CompositeVideoClip([shadow, main_text], size=main_text.size)
    return final_clip.set_duration(total_duration).set_position(position)

def create_group_subtitles(segment: str, duration: float, video_width: int, word_timings: List[Tuple[str, float, float]]) -> list:
    """Creates subtitle clips synchronized with TTS timing."""
    parts = segment.split('\n\n')
    title = parts[0]
    clips = []
    
    # Find timings for the title
    title_words = title.split()
    title_start = None
    title_end = None
    
    for word, start, end in word_timings:
        if word.lower() == title_words[0].lower() and title_start is None:
            title_start = start
        if word.lower() == title_words[-1].lower():
            title_end = end
            break
    
    if title_start is not None and title_end is not None:
        title_clip = create_dynamic_text_clip(
            text=title,
            total_duration=title_end - title_start,
            video_width=video_width,
            fontsize=int(FONT_SIZE * 1.2),
            position='center'
        ).set_start(title_start)
        clips.append(title_clip)
    
    # Process remaining text as groups
    if len(parts) > 1:
        # Process all timings after the title words
        non_title_timings = word_timings[len(title_words):]
        current_group = []
        group_start = None
        for i, (word, start, end) in enumerate(non_title_timings):
            if not current_group:
                group_start = start
            current_group.append(word)
            should_create_group = (len(current_group) >= 5 or word[-1] in ".!?" or i == len(non_title_timings) - 1)
            if should_create_group:
                group_text = " ".join(current_group)
                clip = create_dynamic_text_clip(
                    text=group_text,
                    total_duration=end - group_start,
                    video_width=video_width,
                    position='center'
                ).set_start(group_start)
                clips.append(clip)
                current_group = []
    return clips

def save_story_parts(title: str, segments: list, project_id: str):
    """Saves the story to text files. Creates multiple part files if needed."""
    dirs = get_project_dirs(project_id)
    script_dir = dirs['script']
    os.makedirs(script_dir, exist_ok=True)
    
    if len(segments) == 1:
        script_path = os.path.join(script_dir, "script.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f"{title}\n\n{segments[0]}")
    else:
        full_script_path = os.path.join(script_dir, "full_script.txt")
        with open(full_script_path, "w", encoding="utf-8") as f:
            full_text = []
            for i, segment in enumerate(segments):
                if i > 0 and '\n\n' in segment:
                    segment = segment.split('\n\n', 1)[1]
                full_text.append(segment)
            f.write(f"{title}\n\n{''.join(full_text)}")
        
        for i, segment in enumerate(segments):
            part_path = os.path.join(script_dir, f"part_{i+1}.txt")
            part_info = f"Part {i+1}/{len(segments)}"
            with open(part_path, "w", encoding="utf-8") as f:
                f.write(f"{title}\n\n{part_info}\n\n{segment}")

async def async_generate_speech(text: str, output_path: str, voice_name: str) -> List[Tuple[str, float, float]]:
    """
    Generates speech and returns word timing information.
    Returns: List of (word, start_time, end_time) tuples.
    """
    try:
        communicate_timing = edge_tts.Communicate(text, voice_name)
        word_timings = []
        async for event in communicate_timing.stream():
            if event["type"] == "WordBoundary":
                word_timings.append((
                    event["text"],
                    event["offset"] / 10000000,
                    (event["offset"] + event["duration"]) / 10000000
                ))
        
        communicate_save = edge_tts.Communicate(text, voice_name)
        await communicate_save.save(output_path)
        
        logger.info(f"Successfully generated speech at {output_path} using voice {voice_name}")
        return word_timings
    except Exception as e:
        logger.error(f"Failed to generate speech: {str(e)}")
        raise

def generate_speech(text: str, output_path: str, voice_name: str) -> List[Tuple[str, float, float]]:
    """Generate speech from text using Edge TTS and return word timings."""
    return asyncio.run(async_generate_speech(text, output_path, voice_name))

class VideoProgressLogger(ProgressBarLogger):
    def __init__(self, callback=None):
        super().__init__()
        self.callback = callback
        self._bars = {}
        self.current_bar = None

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar not in self._bars:
            self._bars[bar] = {'total': 100, 'index': 0}
        
        if attr == 'total':
            self._bars[bar]['total'] = value
        elif attr == 'index':
            self._bars[bar]['index'] = value
            self.current_bar = bar
            self._update_progress()

    def _update_progress(self):
        if self.current_bar and self.current_bar in self._bars:
            bar_data = self._bars[self.current_bar]
            if bar_data['total'] > 0:
                progress = int((bar_data['index'] / bar_data['total']) * 100)
                if callable(self.callback):
                    try:
                        self.callback(progress)
                    except Exception as e:
                        print(f"Progress callback error: {e}")

    def __call__(self, **kwargs):
        super().__call__(**kwargs)

def get_voice_name(selected_voice: str) -> str:
    """Get the voice name, handling 'random' selection"""
    if selected_voice == "random":
        return random.choice(VOICE_OPTIONS)
    return selected_voice

def process_story_video(base_video: str, title: str, story: str, project_id: str, voice: str = None, progress_callback=None) -> List[str]:
    """
    Process a story into a video with voiceover and subtitles.
    Args:
        base_video: Path to the base video file
        title: Title of the story
        story: Text content of the story
        project_id: Unique identifier for the project
        voice: Voice name to use for TTS (optional)
        progress_callback: Optional callback function for progress updates
    """
    try:
        logger.info(f"Using voice: {voice}")
        selected_voice = get_voice_name(voice) if voice else get_voice_name("random")
        logger.info(f"Selected voice: {selected_voice}")

        if not os.path.exists(base_video):
            raise FileNotFoundError(f"Base video not found: {base_video}")
        
        segments = split_text_into_segments(story, MIN_WORDS_PER_SEGMENT, MAX_WORDS_PER_SEGMENT)
        total_parts = len(segments)
        logger.info(f"Split story into {total_parts} part(s)")
        
        dirs = get_project_dirs(project_id)
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        save_story_parts(title, segments, project_id)
        full_clip = VideoFileClip(base_video)
        full_duration = full_clip.duration
        output_files = []
        
        for i, segment in enumerate(segments, 1):  # Start counting from 1
            if progress_callback:
                # Update part progress (0-100 for each part)
                progress_callback(0, f"Processing part {i}/{total_parts}")
            
            part_info = f"\nPart {i}/{total_parts}" if total_parts > 1 else ""
            full_text = f"{title}{part_info}\n\n{segment}"
            
            voice_filename = os.path.join(dirs['voice'], f"audio_{i}.mp3")
            word_timings = generate_speech(full_text, voice_filename, selected_voice)
            audio = AudioFileClip(voice_filename)
            
            total_duration = audio.duration + 3  # extra time for last subtitle
            if full_duration < total_duration:
                raise RuntimeError("Base video is shorter than required segment duration")
            
            max_start = full_duration - total_duration
            start_time = random.uniform(0, max_start) if max_start > 0 else 0
            video_segment = full_clip.subclip(start_time, start_time + total_duration)
            
            subs = create_group_subtitles(full_text, audio.duration, int(video_segment.w), word_timings)
            if subs:
                last_sub = subs[-1]
                subs[-1] = last_sub.set_duration(total_duration - last_sub.start)
            
            composite = CompositeVideoClip([video_segment.set_audio(audio)] + subs)
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            filename = f"{safe_title}.mp4" if len(segments) == 1 else f"{safe_title}_part{i}.mp4"
            out_filename = os.path.join(dirs['final'], filename)
            
            # Fix: Update lambda to handle prog argument correctly
            def make_progress_callback(part_num, total_parts):
                def callback(progress=0, message=f"Processing part {part_num}/{total_parts}", **kwargs):
                    if progress_callback:
                        progress_callback(progress, message)
                return callback
            
            progress_logger = VideoProgressLogger(make_progress_callback(i, total_parts))
            
            composite.write_videofile(
                out_filename,
                audio_codec="aac",
                logger=progress_logger
            )
            logger.info(f"Part {i}/{total_parts} written: {out_filename}")
            output_files.append(out_filename)
        
        return output_files
        
    except Exception as e:
        logger.error(f"Failed to process video: {str(e)}", exc_info=True)
        raise RuntimeError(f"Video processing failed: {str(e)}")
    finally:
        if 'full_clip' in locals():
            full_clip.close()
        # Clean up temporary video files at project root
        cleanup_temp_videos()


def cleanup_temp_videos() -> None:
    """
    Deletes temporary video files created at the project's root.
    This function searches for files with names starting with 'temp' and ending with '.mp4'.
    """
    import glob
    root_dir = "/c:/Users/cyril/OneDrive/Documents/code/test_vacances"
    temp_pattern = os.path.join(root_dir, "temp*.mp4")
    temp_files = glob.glob(temp_pattern)
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
            logger.info(f"Deleted temporary file: {temp_file}")
        except Exception as err:
            logger.error(f"Failed to delete temp file {temp_file}: {err}")
