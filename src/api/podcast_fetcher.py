"""RSS feed parser for podcasts"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Tuple
from pathlib import Path

from ..models.podcast import Podcast, Episode


def parse_duration(duration_str: str) -> Optional[int]:
    """Parse duration string to seconds

    Handles formats like:
    - "01:23:45" (HH:MM:SS)
    - "23:45" (MM:SS)
    - "3600" (seconds)
    """
    if not duration_str:
        return None

    duration_str = duration_str.strip()

    # Try HH:MM:SS or MM:SS format
    if ":" in duration_str:
        parts = duration_str.split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            pass

    # Try pure seconds
    try:
        return int(duration_str)
    except ValueError:
        pass

    return None


def parse_pub_date(date_str: str) -> Optional[datetime]:
    """Parse RSS pubDate to datetime"""
    if not date_str:
        return None

    # Common RSS date formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    # Try without timezone
    try:
        # Remove timezone info and parse
        date_clean = re.sub(r'\s*[+-]\d{4}$', '', date_str.strip())
        date_clean = re.sub(r'\s*\w{3,4}$', '', date_clean)
        return datetime.strptime(date_clean, "%a, %d %b %Y %H:%M:%S")
    except ValueError:
        pass

    return None


class PodcastFetcher:
    """Fetch and parse podcast RSS feeds"""

    # XML namespaces commonly used in podcast feeds
    NAMESPACES = {
        'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
        'content': 'http://purl.org/rss/1.0/modules/content/',
        'atom': 'http://www.w3.org/2005/Atom',
    }

    def __init__(self, feed_url: str):
        """Initialize with RSS feed URL

        Args:
            feed_url: URL to the podcast RSS feed
        """
        self.feed_url = feed_url

    def fetch_feed(self) -> Tuple[Podcast, List[Episode]]:
        """Fetch and parse the RSS feed

        Returns:
            Tuple of (Podcast metadata, list of Episodes)
        """
        print(f"Fetching RSS feed: {self.feed_url}")

        response = requests.get(self.feed_url, timeout=30)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)
        channel = root.find('channel')

        if channel is None:
            raise ValueError("Invalid RSS feed: no channel element found")

        # Parse podcast metadata
        podcast = self._parse_podcast(channel)

        # Parse episodes
        episodes = self._parse_episodes(channel)

        print(f"Found {len(episodes)} episodes")

        return podcast, episodes

    def _parse_podcast(self, channel: ET.Element) -> Podcast:
        """Parse podcast metadata from channel element"""

        def get_text(tag: str, default: str = "") -> str:
            elem = channel.find(tag)
            return elem.text if elem is not None and elem.text else default

        def get_itunes_text(tag: str, default: str = "") -> str:
            elem = channel.find(f'itunes:{tag}', self.NAMESPACES)
            return elem.text if elem is not None and elem.text else default

        # Get image URL
        image_url = ""
        itunes_image = channel.find('itunes:image', self.NAMESPACES)
        if itunes_image is not None:
            image_url = itunes_image.get('href', '')
        if not image_url:
            image_elem = channel.find('image/url')
            if image_elem is not None:
                image_url = image_elem.text or ""

        # Get categories
        categories = []
        for cat in channel.findall('itunes:category', self.NAMESPACES):
            cat_text = cat.get('text')
            if cat_text:
                categories.append(cat_text)

        return Podcast(
            title=get_text('title', 'Unknown Podcast'),
            description=get_text('description') or get_itunes_text('summary'),
            author=get_itunes_text('author') or get_text('managingEditor'),
            website_url=get_text('link'),
            feed_url=self.feed_url,
            image_url=image_url,
            language=get_text('language'),
            categories=categories,
        )

    def _parse_episodes(self, channel: ET.Element) -> List[Episode]:
        """Parse all episodes from channel"""
        episodes = []

        for item in channel.findall('item'):
            episode = self._parse_episode(item)
            if episode:
                episodes.append(episode)

        return episodes

    def _parse_episode(self, item: ET.Element) -> Optional[Episode]:
        """Parse a single episode from item element"""

        def get_text(tag: str, default: str = "") -> str:
            elem = item.find(tag)
            return elem.text if elem is not None and elem.text else default

        def get_itunes_text(tag: str, default: str = "") -> str:
            elem = item.find(f'itunes:{tag}', self.NAMESPACES)
            return elem.text if elem is not None and elem.text else default

        # Get audio URL from enclosure
        enclosure = item.find('enclosure')
        if enclosure is None:
            return None

        audio_url = enclosure.get('url', '')
        if not audio_url:
            return None

        # Get GUID
        guid_elem = item.find('guid')
        guid = guid_elem.text if guid_elem is not None and guid_elem.text else audio_url

        # Get duration
        duration_str = get_itunes_text('duration')
        duration = parse_duration(duration_str)

        # Get image
        image_url = ""
        itunes_image = item.find('itunes:image', self.NAMESPACES)
        if itunes_image is not None:
            image_url = itunes_image.get('href', '')

        # Clean up description (remove HTML tags for plain text)
        description = get_text('description') or get_itunes_text('summary')
        description = re.sub(r'<[^>]+>', '', description)  # Strip HTML

        return Episode(
            guid=guid,
            title=get_text('title', 'Untitled Episode'),
            description=description,
            published_at=parse_pub_date(get_text('pubDate')),
            duration_seconds=duration,
            audio_url=audio_url,
            episode_url=get_text('link'),
            image_url=image_url,
        )


class AudioDownloader:
    """Download audio files from URLs"""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize downloader

        Args:
            output_dir: Directory to save audio files (default: ./temp/audio)
        """
        self.output_dir = output_dir or Path("./temp/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(self, url: str, filename: str) -> Optional[Path]:
        """Download audio file from URL

        Args:
            url: URL to download from
            filename: Base filename (without extension)

        Returns:
            Path to downloaded file, or None if failed
        """
        # Determine extension from URL
        ext = ".mp3"
        if ".m4a" in url.lower():
            ext = ".m4a"
        elif ".wav" in url.lower():
            ext = ".wav"

        output_path = self.output_dir / f"{filename}{ext}"

        # Skip if already exists
        if output_path.exists():
            print(f"Audio already exists: {output_path}")
            return output_path

        try:
            print(f"Downloading: {filename}{ext}")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            # Get total size for progress
            total_size = int(response.headers.get('content-length', 0))

            with open(output_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        pct = (downloaded / total_size) * 100
                        print(f"\r  {pct:.1f}% ({downloaded / 1024 / 1024:.1f}MB)", end="", flush=True)

            print()  # Newline after progress
            return output_path

        except Exception as e:
            print(f"Error downloading {filename}: {str(e)}")
            if output_path.exists():
                output_path.unlink()
            return None

    def cleanup(self, filename: str) -> None:
        """Delete downloaded audio file"""
        for ext in ['.mp3', '.m4a', '.wav']:
            path = self.output_dir / f"{filename}{ext}"
            if path.exists():
                try:
                    path.unlink()
                    print(f"Cleaned up: {path}")
                except Exception as e:
                    print(f"Warning: Could not delete {path}: {str(e)}")
