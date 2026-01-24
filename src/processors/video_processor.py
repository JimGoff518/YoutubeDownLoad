"""Video processing pipeline"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from ..api.youtube_client import YouTubeClient
from ..api.transcript_fetcher import TranscriptFetcher
from ..models import (
    Video,
    Channel,
    ExtractionMetadata,
    ExtractionResult,
    ErrorEntry,
    MLFeatures,
)


class VideoProcessor:
    """Process videos to extract metadata and transcripts"""

    def __init__(
        self,
        youtube_client: Optional[YouTubeClient] = None,
        transcript_fetcher: Optional[TranscriptFetcher] = None,
    ):
        """Initialize video processor

        Args:
            youtube_client: YouTube API client
            transcript_fetcher: Transcript fetcher
        """
        self.youtube_client = youtube_client or YouTubeClient()
        self.transcript_fetcher = transcript_fetcher or TranscriptFetcher()

    def calculate_ml_features(
        self, video_data: Dict[str, Any], transcript_word_count: int
    ) -> MLFeatures:
        """Calculate ML features for a video

        Args:
            video_data: Video metadata dictionary
            transcript_word_count: Word count from transcript

        Returns:
            MLFeatures object
        """
        # Approximate token counts (rough estimate: 1 token ≈ 0.75 words)
        title_tokens = max(1, len(video_data["title"].split()) * 4 // 3)
        description_tokens = max(1, len(video_data["description"].split()) * 4 // 3)
        transcript_tokens = max(0, transcript_word_count * 4 // 3)

        # Engagement metrics
        total_engagement = video_data["like_count"] + video_data["comment_count"]
        view_count = max(1, video_data["view_count"])  # Avoid division by zero
        engagement_rate = total_engagement / view_count

        # Views per day
        published_at = video_data["published_at"]
        days_since_published = max(
            1, (datetime.now(timezone.utc) - published_at).days
        )  # At least 1 day
        views_per_day = video_data["view_count"] / days_since_published

        return MLFeatures(
            title_token_count=title_tokens,
            description_token_count=description_tokens,
            transcript_token_count=transcript_tokens,
            total_engagement=total_engagement,
            engagement_rate=round(engagement_rate, 6),
            views_per_day=round(views_per_day, 2),
        )

    def process_video(self, video_data: Dict[str, Any]) -> Video:
        """Process a single video

        Args:
            video_data: Video metadata from YouTube API

        Returns:
            Video object with transcript and ML features
        """
        # Fetch transcript
        transcript = self.transcript_fetcher.fetch_transcript(video_data["id"])

        # Calculate ML features
        ml_features = self.calculate_ml_features(
            video_data, transcript.word_count if transcript.available else 0
        )

        # Create Video object
        return Video(
            id=video_data["id"],
            title=video_data["title"],
            description=video_data["description"],
            published_at=video_data["published_at"],
            duration_seconds=video_data["duration_seconds"],
            duration_iso=video_data["duration_iso"],
            view_count=video_data["view_count"],
            like_count=video_data["like_count"],
            comment_count=video_data["comment_count"],
            thumbnail_url=video_data["thumbnail_url"],
            tags=video_data["tags"],
            category_id=video_data["category_id"],
            category_name=video_data["category_name"],
            default_language=video_data["default_language"],
            default_audio_language=video_data["default_audio_language"],
            license=video_data["license"],
            privacy_status=video_data["privacy_status"],
            made_for_kids=video_data["made_for_kids"],
            transcript=transcript,
            ml_features=ml_features,
        )

    def process_channel(
        self, channel_id: str, max_videos: Optional[int] = None
    ) -> ExtractionResult:
        """Process entire channel

        Args:
            channel_id: YouTube channel ID
            max_videos: Maximum number of videos to process (None for all)

        Returns:
            ExtractionResult with all videos and metadata
        """
        print(f"Fetching channel information for {channel_id}...")
        channel_data = self.youtube_client.get_channel_info(channel_id)
        channel = Channel(**channel_data)

        print(f"Fetching video list from {channel.title}...")
        video_ids = self.youtube_client.get_channel_videos(channel_id, max_videos)

        if not video_ids:
            print("No videos found in channel.")
            return ExtractionResult(
                extraction_metadata=ExtractionMetadata(
                    channel_id=channel_id,
                    total_videos_processed=0,
                    successful_extractions=0,
                    failed_extractions=0,
                ),
                channel=channel,
                videos=[],
                errors=[],
            )

        print(f"Found {len(video_ids)} videos. Fetching video metadata...")
        video_metadata_list = self.youtube_client.get_video_details_batch(video_ids)

        # Create a mapping of video_id to metadata
        video_metadata_map = {vm["id"]: vm for vm in video_metadata_list}

        # Process videos with progress bar
        videos = []
        errors = []
        successful_count = 0

        print(f"Processing {len(video_ids)} videos...")
        for video_id in tqdm(video_ids, desc="Processing videos", unit="video"):
            try:
                # Get metadata for this video
                video_data = video_metadata_map.get(video_id)

                if not video_data:
                    # Video not found in metadata (might be private/deleted)
                    errors.append(
                        ErrorEntry(
                            video_id=video_id,
                            error_type="VideoNotFound",
                            error_message="Video metadata not available (private or deleted)",
                        )
                    )
                    continue

                # Process video
                video = self.process_video(video_data)
                videos.append(video)

                if video.transcript.available:
                    successful_count += 1

            except Exception as e:
                # Log error and continue
                errors.append(
                    ErrorEntry(
                        video_id=video_id,
                        video_title=video_data.get("title") if video_data else None,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
                print(f"\nError processing video {video_id}: {str(e)}")

        # Create extraction result
        print(
            f"\nProcessing complete! {len(videos)} videos processed, "
            f"{successful_count} transcripts extracted, {len(errors)} errors."
        )

        return ExtractionResult(
            extraction_metadata=ExtractionMetadata(
                channel_id=channel_id,
                total_videos_processed=len(video_ids),
                successful_extractions=successful_count,
                failed_extractions=len(video_ids) - successful_count,
            ),
            channel=channel,
            videos=videos,
            errors=errors,
        )
