"""YouTube Data API v3 client"""

import time
import isodate
from datetime import datetime
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import config


class YouTubeClient:
    """Client for YouTube Data API v3"""

    # Category ID to name mapping (common categories)
    CATEGORY_NAMES = {
        "1": "Film & Animation",
        "2": "Autos & Vehicles",
        "10": "Music",
        "15": "Pets & Animals",
        "17": "Sports",
        "18": "Short Movies",
        "19": "Travel & Events",
        "20": "Gaming",
        "21": "Videoblogging",
        "22": "People & Blogs",
        "23": "Comedy",
        "24": "Entertainment",
        "25": "News & Politics",
        "26": "Howto & Style",
        "27": "Education",
        "28": "Science & Technology",
        "29": "Nonprofits & Activism",
        "30": "Movies",
        "31": "Anime/Animation",
        "32": "Action/Adventure",
        "33": "Classics",
        "34": "Documentary",
        "35": "Drama",
        "36": "Family",
        "37": "Foreign",
        "38": "Horror",
        "39": "Sci-Fi/Fantasy",
        "40": "Thriller",
        "41": "Shorts",
        "42": "Shows",
        "43": "Trailers",
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube API client

        Args:
            api_key: YouTube Data API key. If not provided, uses config.
        """
        self.api_key = api_key or config.youtube_api_key
        self.youtube = build("youtube", "v3", developerKey=self.api_key)

    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel metadata

        Args:
            channel_id: YouTube channel ID

        Returns:
            Channel metadata dictionary

        Raises:
            ValueError: If channel not found
            HttpError: If API request fails
        """
        try:
            request = self.youtube.channels().list(
                part="snippet,statistics,topicDetails",
                id=channel_id,
            )
            response = request.execute()

            if not response.get("items"):
                raise ValueError(f"Channel not found: {channel_id}")

            channel_data = response["items"][0]
            snippet = channel_data["snippet"]
            statistics = channel_data.get("statistics", {})
            topic_details = channel_data.get("topicDetails", {})

            return {
                "id": channel_data["id"],
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "custom_url": snippet.get("customUrl"),
                "published_at": datetime.fromisoformat(
                    snippet["publishedAt"].replace("Z", "+00:00")
                ),
                "subscriber_count": int(statistics.get("subscriberCount", 0)),
                "video_count": int(statistics.get("videoCount", 0)),
                "view_count": int(statistics.get("viewCount", 0)),
                "thumbnail_url": snippet["thumbnails"]["high"]["url"],
                "country": snippet.get("country"),
                "topics": topic_details.get("topicCategories", []),
            }

        except HttpError as e:
            if e.resp.status == 404:
                raise ValueError(f"Channel not found: {channel_id}")
            elif e.resp.status == 403:
                raise ValueError(
                    "API quota exceeded or API key invalid. "
                    "Please check your API key and quota limits."
                )
            raise

    def get_channel_videos(
        self, channel_id: str, max_results: Optional[int] = None
    ) -> List[str]:
        """Get all video IDs from a channel

        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of videos to retrieve (None for all)

        Returns:
            List of video IDs

        Raises:
            ValueError: If channel not found
            HttpError: If API request fails
        """
        video_ids = []
        page_token = None

        # First, get the uploads playlist ID
        request = self.youtube.channels().list(part="contentDetails", id=channel_id)
        response = request.execute()

        if not response.get("items"):
            raise ValueError(f"Channel not found: {channel_id}")

        uploads_playlist_id = response["items"][0]["contentDetails"][
            "relatedPlaylists"
        ]["uploads"]

        # Paginate through all videos in the uploads playlist
        while True:
            request = self.youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,  # Maximum allowed per request
                pageToken=page_token,
            )
            response = request.execute()

            # Extract video IDs
            for item in response.get("items", []):
                video_id = item["contentDetails"]["videoId"]
                video_ids.append(video_id)

                # Check if we've reached max_results
                if max_results and len(video_ids) >= max_results:
                    return video_ids[:max_results]

            # Check for next page
            page_token = response.get("nextPageToken")
            if not page_token:
                break

            # Rate limiting
            time.sleep(0.1)

        return video_ids

    def get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """Get detailed metadata for videos

        Args:
            video_ids: List of video IDs (max 50 per call)

        Returns:
            List of video metadata dictionaries

        Raises:
            ValueError: If more than 50 video IDs provided
            HttpError: If API request fails
        """
        if len(video_ids) > 50:
            raise ValueError("Maximum 50 video IDs per request")

        if not video_ids:
            return []

        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(video_ids),
            )
            response = request.execute()

            videos = []
            for item in response.get("items", []):
                snippet = item["snippet"]
                content_details = item["contentDetails"]
                statistics = item.get("statistics", {})

                # Parse ISO 8601 duration (may be missing for live streams/premieres)
                duration_iso = content_details.get("duration")
                if not duration_iso:
                    # Skip videos without duration (live streams, etc.)
                    continue
                duration = isodate.parse_duration(duration_iso)
                duration_seconds = int(duration.total_seconds())

                video_data = {
                    "id": item["id"],
                    "title": snippet["title"],
                    "description": snippet.get("description", ""),
                    "published_at": datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    ),
                    "duration_seconds": duration_seconds,
                    "duration_iso": duration_iso,
                    "view_count": int(statistics.get("viewCount", 0)),
                    "like_count": int(statistics.get("likeCount", 0)),
                    "comment_count": int(statistics.get("commentCount", 0)),
                    "thumbnail_url": snippet["thumbnails"]["high"]["url"],
                    "tags": snippet.get("tags", []),
                    "category_id": snippet["categoryId"],
                    "category_name": self.CATEGORY_NAMES.get(snippet["categoryId"]),
                    "default_language": snippet.get("defaultLanguage"),
                    "default_audio_language": snippet.get("defaultAudioLanguage"),
                    "license": content_details.get("license", "youtube"),
                    "privacy_status": item.get("status", {}).get("privacyStatus"),
                    "made_for_kids": item.get("status", {}).get(
                        "madeForKids", False
                    ),
                }
                videos.append(video_data)

            return videos

        except HttpError as e:
            if e.resp.status == 403:
                raise ValueError(
                    "API quota exceeded. Please try again later or request a quota increase."
                )
            raise

    def get_video_details_batch(
        self, video_ids: List[str], batch_size: int = 50
    ) -> List[Dict[str, Any]]:
        """Get video details in batches

        Args:
            video_ids: List of video IDs
            batch_size: Batch size (max 50)

        Returns:
            List of all video metadata dictionaries
        """
        all_videos = []

        for i in range(0, len(video_ids), batch_size):
            batch = video_ids[i : i + batch_size]
            videos = self.get_video_details(batch)
            all_videos.extend(videos)

            # Rate limiting between batches
            if i + batch_size < len(video_ids):
                time.sleep(0.2)

        return all_videos

    @staticmethod
    def extract_channel_id(channel_input: str) -> str:
        """Extract channel ID from various input formats

        Args:
            channel_input: Channel ID, URL, or handle

        Returns:
            Channel ID

        Raises:
            ValueError: If channel ID cannot be extracted
        """
        # Already a channel ID (starts with UC)
        if channel_input.startswith("UC") and len(channel_input) == 24:
            return channel_input

        # Extract from URL
        if "youtube.com" in channel_input or "youtu.be" in channel_input:
            if "/channel/" in channel_input:
                # Extract from /channel/UCxxxxxx
                parts = channel_input.split("/channel/")
                if len(parts) > 1:
                    channel_id = parts[1].split("/")[0].split("?")[0]
                    if channel_id.startswith("UC") and len(channel_id) == 24:
                        return channel_id

            # For @username URLs, we can't extract the ID directly
            # The caller will need to use the API to resolve it
            raise ValueError(
                f"Cannot extract channel ID from @username URL: {channel_input}. "
                "Please provide the channel ID (starts with UC) instead."
            )

        raise ValueError(
            f"Invalid channel input: {channel_input}. "
            "Please provide a channel ID (UCxxxxxx) or channel URL."
        )

    @staticmethod
    def extract_video_id(video_input: str) -> str:
        """Extract video ID from various input formats

        Args:
            video_input: Video ID or URL

        Returns:
            Video ID (11 characters)

        Raises:
            ValueError: If video ID cannot be extracted
        """
        import re

        # Already a video ID (11 characters, alphanumeric + - and _)
        if re.match(r'^[a-zA-Z0-9_-]{11}$', video_input):
            return video_input

        # Extract from various YouTube URL formats
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',  # Standard and short URLs
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',  # Embed URLs
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',  # Old style URLs
        ]

        for pattern in patterns:
            match = re.search(pattern, video_input)
            if match:
                return match.group(1)

        raise ValueError(
            f"Invalid video input: {video_input}. "
            "Please provide a video ID or valid YouTube video URL."
        )

    @staticmethod
    def extract_playlist_id(playlist_input: str) -> str:
        """Extract playlist ID from various input formats

        Args:
            playlist_input: Playlist ID or URL

        Returns:
            Playlist ID (starts with PL)

        Raises:
            ValueError: If playlist ID cannot be extracted
        """
        import re

        # Already a playlist ID (starts with PL)
        if playlist_input.startswith("PL") and len(playlist_input) > 10:
            return playlist_input

        # Extract from URL (list= parameter)
        if "youtube.com" in playlist_input or "youtu.be" in playlist_input:
            match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', playlist_input)
            if match:
                playlist_id = match.group(1)
                if playlist_id.startswith("PL"):
                    return playlist_id

        raise ValueError(
            f"Invalid playlist input: {playlist_input}. "
            "Please provide a playlist ID (PLxxxxxx) or playlist URL with list= parameter."
        )

    def get_playlist_videos(
        self, playlist_id: str, max_results: Optional[int] = None
    ) -> List[str]:
        """Get all video IDs from a playlist

        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum number of videos to retrieve (None for all)

        Returns:
            List of video IDs

        Raises:
            ValueError: If playlist not found
            HttpError: If API request fails
        """
        video_ids = []
        page_token = None

        # Paginate through all videos in the playlist
        while True:
            try:
                request = self.youtube.playlistItems().list(
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,  # Maximum allowed per request
                    pageToken=page_token,
                )
                response = request.execute()

                # Extract video IDs
                for item in response.get("items", []):
                    video_id = item["contentDetails"]["videoId"]
                    video_ids.append(video_id)

                    # Check if we've reached max_results
                    if max_results and len(video_ids) >= max_results:
                        return video_ids[:max_results]

                # Check for next page
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

                # Rate limiting
                time.sleep(0.1)

            except HttpError as e:
                if e.resp.status == 404:
                    raise ValueError(f"Playlist not found: {playlist_id}")
                elif e.resp.status == 403:
                    raise ValueError(
                        "API quota exceeded or playlist is private. "
                        "Please check your API key and playlist permissions."
                    )
                raise

        return video_ids
