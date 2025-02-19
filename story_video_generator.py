import os
import re
import random
import logging
from gtts import gTTS  # pip install gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, VideoClip  # pip install moviepy
from moviepy.config import change_settings
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import math
from pydub import AudioSegment  # pip install pydub
import speech_recognition as sr  # pip install SpeechRecognition
from typing import List, Tuple
from config import (
    IMAGEMAGICK_PATH, FONT_SIZE, FONT_NAME,
    MIN_WORDS_PER_SEGMENT, MAX_WORDS_PER_SEGMENT, OUTPUT_DIR,
    get_project_dirs
)

logger = logging.getLogger(__name__)

# Set the ImageMagick binary path (update as needed)
change_settings({"IMAGEMAGICK_BINARY": IMAGEMAGICK_PATH})

def split_text_into_segments(story: str, min_words: int = MIN_WORDS_PER_SEGMENT, max_words: int = MAX_WORDS_PER_SEGMENT) -> list:
    """
    Splits the story into segments at sentence boundaries with overlap.
    Returns a list of (segment_text, last_sentence) tuples.
    """
    sentences = re.split(r'(?<=[.!?])\s+', story)
    segments = []
    current_segment = ""
    current_count = 0
    last_sentence = None
    
    for sentence in sentences:
        words = sentence.split()
        count = len(words)
        
        if current_count + count <= max_words:
            current_segment = f"{current_segment} {sentence}".strip()
            current_count += count
            last_sentence = sentence
        else:
            if current_count < min_words:
                current_segment = f"{current_segment} {sentence}".strip()
                current_count += count
                last_sentence = sentence
            else:
                segments.append(current_segment)
                current_segment = sentence
                current_count = count
                last_sentence = sentence
    
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

# Replace the dynamic text clip with a fixed TextClip for 5-word groups.
def create_dynamic_text_clip(text: str, total_duration: float, video_width: int, fontsize: int = FONT_SIZE, font: str = FONT_NAME, position: str = 'center') -> VideoClip:
    """
    Creates a text clip with enhanced visibility and contrast.
    """
    from moviepy.editor import TextClip, CompositeVideoClip
    
    margin = int(video_width * 0.05)
    processed_text = text.upper().replace("-", "-\n")
    
    # Créer le texte principal
    main_text = TextClip(
        processed_text,
        fontsize=fontsize,
        font=font,
        color='white',
        method='caption',
        size=(video_width - 2 * margin, None),
        align='center',
        stroke_color='black',
        stroke_width=2.5  # Contour noir plus épais
    )
    
    # Créer une ombre du texte
    shadow = TextClip(
        processed_text,
        fontsize=fontsize,
        font=font,
        color='black',
        method='caption',
        size=(video_width - 2 * margin, None),
        align='center',
    ).set_position(lambda t: (2, 2))  # Décalage de l'ombre
    
    # Combiner l'ombre et le texte principal
    final_clip = CompositeVideoClip([
        shadow,
        main_text
    ], size=main_text.size)
    
    return final_clip.set_duration(total_duration).set_position(position)

def split_into_dynamic_groups(segment: str, is_title: bool = False) -> list:
    """
    Splits the segment into groups of words.
    If is_title is True, returns the entire segment as one group.
    Otherwise splits into groups of 3-6 words based on punctuation.
    """
    if is_title:
        return [segment]
    
    words = segment.split()
    groups = []
    i = 0
    n = len(words)
    while i < n:
        group = []
        for j in range(6):
            if i + j >= n:
                break
            word = words[i+j]
            group.append(word)
            if j >= 2:  # at least 3 words in group
                if word and word[-1] in ".!,;:?":
                    break
                if j == 4:
                    if i + 5 < n and words[i+5] and words[i+5][-1] in ".!,;:?":
                        group.append(words[i+5])
                    break
        groups.append(" ".join(group).strip())
        i += len(group)
    return groups

def estimate_word_timings(audio_duration: float, segment: str) -> list:
    """
    Estimates word timings based on total audio duration and word count.
    Returns a list of (word_group, start_time, end_time) tuples.
    """
    # Split into title, part info (if exists), and content
    parts = segment.split('\n\n')
    title = parts[0]
    content_start_idx = 1
    part_info = None
    
    # Check if second part is a "Part X/Y" line
    if len(parts) > 2 and parts[1].strip().startswith('Part '):
        part_info = parts[1]
        content_start_idx = 2
    
    content = '\n\n'.join(parts[content_start_idx:])
    
    words = segment.split()
    total_words = len(words)
    time_per_word = audio_duration / total_words
    
    groups = []
    start_time = 0
    
    # Handle title as one group
    title_words = len(title.split())
    title_duration = title_words * time_per_word
    groups.append((title, start_time, start_time + title_duration))
    start_time += title_duration
    
    # Handle part info if exists
    if part_info:
        part_words = len(part_info.split())
        part_duration = part_words * time_per_word
        groups.append((part_info, start_time, start_time + part_duration))
        start_time += part_duration
    
    # Process content words into regular groups
    content_words = content.split()
    current_group = []
    current_word_count = 0
    
    for i, word in enumerate(content_words):
        current_group.append(word)
        current_word_count += 1
        
        is_end = False
        if current_word_count >= 3:
            if word[-1] in ".!?":
                is_end = True
            elif current_word_count >= 5:
                is_end = True
        
        if is_end or i == len(content_words) - 1:
            group_text = " ".join(current_group)
            end_time = start_time + (current_word_count * time_per_word)
            groups.append((group_text, start_time, end_time))
            
            current_group = []
            current_word_count = 0
            start_time = end_time
    
    return groups

def create_group_subtitles(segment: str, duration: float, video_width: int, audio_file: str = None) -> list:
    """Creates subtitle clips synchronized with TTS timing."""
    # Get word timings based on duration
    all_text = segment
    timings = estimate_word_timings(duration, all_text)
    
    clips = []
    # Create content clips
    for group_text, start_time, end_time in timings:
        clip = create_dynamic_text_clip(
            text=group_text,
            total_duration=end_time - start_time,
            video_width=video_width,
            fontsize=FONT_SIZE,  # Utiliser FONT_SIZE au lieu de la valeur codée en dur
            position='center'
        ).set_start(start_time)
        clips.append(clip)
    
    return clips

def save_story_parts(title: str, segments: list, project_id: str):
    """Saves the story to text files. Creates multiple part files only if needed."""
    dirs = get_project_dirs(project_id)
    script_dir = dirs['script']
    os.makedirs(script_dir, exist_ok=True)
    
    if len(segments) == 1:
        script_path = os.path.join(script_dir, "script.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f"{title}\n\n{segments[0]}")
    else:
        # Save full story
        full_script_path = os.path.join(script_dir, "full_script.txt")
        with open(full_script_path, "w", encoding="utf-8") as f:
            # Remove overlapping sentences for full story
            full_text = []
            for i, segment in enumerate(segments):
                if i > 0:
                    segment = segment.split('\n\n', 1)[1] if '\n\n' in segment else segment
                full_text.append(segment)
            f.write(f"{title}\n\n{''.join(full_text)}")
        
        # Save individual parts
        for i, segment in enumerate(segments):
            part_path = os.path.join(script_dir, f"part_{i+1}.txt")
            part_info = f"Part {i+1}/{len(segments)}"
            with open(part_path, "w", encoding="utf-8") as f:
                f.write(f"{title}\n\n{part_info}\n\n{segment}")

def process_story_video(full_video_path: str, title: str, story: str, project_id: str) -> List[str]:
    """
    Process the story into one or more video segments with TTS and subtitles.
    
    Args:
        full_video_path: Path to the base background video
        title: Story title
        story: Main story content
        project_id: Unique identifier for the project
        
    Returns:
        List of paths to generated video files
        
    Raises:
        FileNotFoundError: If input video doesn't exist
        RuntimeError: If video processing fails
    """
    try:
        if not os.path.exists(full_video_path):
            raise FileNotFoundError(f"Base video not found: {full_video_path}")

        segments = split_text_into_segments(story, MIN_WORDS_PER_SEGMENT, MAX_WORDS_PER_SEGMENT)
        logger.info(f"Split story into {len(segments)} segment(s)")
        
        # Save story parts to files
        save_story_parts(title, segments, project_id)
        
        full_clip = VideoFileClip(full_video_path)
        full_duration = full_clip.duration
        output_files = []
        
        dirs = get_project_dirs(project_id)
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        for i, segment in enumerate(segments):
            # Create full text including title and part info
            part_info = f"\nPart {i+1}/{len(segments)}" if len(segments) > 1 else ""
            full_text = f"{title}{part_info}\n\n{segment}"
            
            voice_filename = os.path.join(dirs['voice'], f"audio_{i+1}.mp3")
            tts = gTTS(text=full_text, lang='en')
            tts.save(voice_filename)
            audio = AudioFileClip(voice_filename)
            
            # Calculate total duration including end decay
            total_duration = audio.duration + 3  # add 3s decay at the end
            
            # Extract video segment
            max_start = full_duration - total_duration
            start_time = random.uniform(0, max_start) if max_start > 0 else 0
            video_segment = full_clip.subclip(start_time, start_time + total_duration)
            
            # Create subtitles with precise timing from audio analysis
            subs = create_group_subtitles(full_text, audio.duration, int(video_segment.w))
            
            # Create final composite with synchronized audio and subtitles
            composite = CompositeVideoClip([
                video_segment.set_audio(audio)  # audio starts at 0s
            ] + subs)
            
            # Configure progress bar and save
            from proglog import ProgressBarLogger
            class MyBarLogger(ProgressBarLogger):
                def bars_callback(self, bar, attr, value, old_value=None):
                    percentage = (value / self.bars[bar]['total']) * 100
                    print(f"Writing video: {percentage:.0f}% complete", end='\r')

            if len(segments) == 1:
                label = f"video{project_id}Final"
            else:
                label = f"video{project_id}PartFinal" if i == len(segments) - 1 else f"video{project_id}Part{i+1}"
            out_filename = os.path.join(dirs['final'], f"video_{label}.mp4")
            
            composite.write_videofile(out_filename, 
                                    audio_codec="aac",
                                    logger=MyBarLogger())
            print("\nVideo writing completed!")
            output_files.append(out_filename)
        
        return output_files
        
    except Exception as e:
        logger.error(f"Failed to process video: {str(e)}", exc_info=True)
        raise RuntimeError(f"Video processing failed: {str(e)}")
    finally:
        if 'full_clip' in locals(): 
            full_clip.close()
