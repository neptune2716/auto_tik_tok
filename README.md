# Reddit Stories to Video Generator

Automatically creates TikTok/Reels style videos from Reddit stories with text-to-speech and synchronized subtitles.

## Features

- Fetches stories from Reddit
- Maintains history of used stories to avoid duplicates
- Edge TTS for natural-sounding narration
- Synchronized subtitles with word-level timing
- Handles long stories by splitting into multiple parts
- Background video randomization

## Requirements

- Python 3.7+
- ImageMagick (for text rendering)
- A base background video file
- edge-tts (`pip install edge-tts`)

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd test_vacances
   ```

2. Create and activate virtual environment:

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Unix/Mac
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Install ImageMagick from [ImageMagick website](https://imagemagick.org/script/download.php)

5. Create `.env` file with your ImageMagick path:
   ```
   IMAGEMAGICK_PATH=C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe
   ```

## Project Structure

```
test_vacances/
├── base_video.mp4          # Your background video
├── main.py                # Main script
├── reddit_story.py        # Reddit story fetcher
├── story_video_generator.py # Video generation logic
├── story_history.py       # Story tracking system
├── story_history.json     # Used stories database (auto-generated)
├── requirements.txt       # Python dependencies
└── generated/            # Generated content (gitignored)
    ├── final/           # Final videos
    ├── voice/           # TTS audio files
    └── story/           # Story text files
```

## Usage

1. Place your background video as `base_video.mp4` in the project root

2. Run the script:
   ```bash
   python main.py
   ```

The script will:

- Check story_history.json to avoid duplicate stories
- Fetch a fresh story from r/funnystories
- Split it into segments if needed
- Generate natural speech using Edge TTS
- Create synchronized subtitles
- Only add the story to history after successful video generation
- Produce final video(s) in the `final` directory

## Output Format

- Each video has the title shown as a single block at the start
- Story text appears in synchronized groups with the TTS
- For long stories, multiple parts are created with proper overlap
- Videos include a 3-second quiet period at the end

## Note

The generated directories (final/, voice/, story/) are gitignored. Make sure you have sufficient disk space for the generated content.
