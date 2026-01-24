"""Audio downloader for YouTube videos"""

import os
from pathlib import Path
from typing import Optional
import yt_dlp


class AudioDownloader:
    """Download audio from YouTube videos"""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize audio downloader

        Args:
            output_dir: Directory to save audio files (default: ./temp/audio)
        """
        self.output_dir = output_dir or Path("./temp/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_audio(self, video_id: str) -> Optional[Path]:
        """Download audio from a YouTube video

        Args:
            video_id: YouTube video ID

        Returns:
            Path to downloaded audio file, or None if download failed
        """
        # Check for both MP3 and WebM (fallback if FFmpeg not available)
        mp3_path = self.output_dir / f"{video_id}.mp3"
        webm_path = self.output_dir / f"{video_id}.webm"
        m4a_path = self.output_dir / f"{video_id}.m4a"

        # Return existing file if already downloaded
        for path in [mp3_path, webm_path, m4a_path]:
            if path.exists():
                print(f"Audio already exists: {path}")
                return path

        # Check for FFmpeg in PATH, otherwise use explicit location
        ffmpeg_location = None
        try:
            import shutil
            if not shutil.which('ffmpeg'):
                # Try default Windows installation location
                default_ffmpeg = Path(r"C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin")
                if default_ffmpeg.exists():
                    ffmpeg_location = str(default_ffmpeg)
        except Exception:
            pass

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.output_dir / f"{video_id}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
        }

        # Only add FFmpeg postprocessing if FFmpeg is available
        if ffmpeg_location:
            ydl_opts['ffmpeg_location'] = ffmpeg_location
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Check which file was created (prefer MP3, fallback to WebM/M4A)
            for path in [mp3_path, webm_path, m4a_path]:
                if path.exists():
                    return path

            print(f"Warning: Audio file not created for {video_id}")
            return None

        except Exception as e:
            print(f"Error downloading audio for {video_id}: {str(e)}")
            return None

    def cleanup(self, video_id: str) -> None:
        """Delete downloaded audio file

        Args:
            video_id: YouTube video ID
        """
        # Clean up all possible audio file formats
        for ext in ['.mp3', '.webm', '.m4a']:
            audio_path = self.output_dir / f"{video_id}{ext}"
            if audio_path.exists():
                try:
                    audio_path.unlink()
                    print(f"Cleaned up: {audio_path}")
                except Exception as e:
                    print(f"Warning: Could not delete {audio_path}: {str(e)}")
