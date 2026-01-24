"""Video, channel, and extraction result models"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, computed_field

from .transcript import Transcript


class MLFeatures(BaseModel):
    """Machine learning features for video analysis"""

    title_token_count: int = Field(..., description="Approximate token count in title")
    description_token_count: int = Field(..., description="Approximate token count in description")
    transcript_token_count: int = Field(0, description="Approximate token count in transcript")
    total_engagement: int = Field(..., description="Sum of likes and comments")
    engagement_rate: float = Field(..., description="Engagement rate (likes+comments)/views")
    views_per_day: float = Field(..., description="Average views per day since publication")


class Video(BaseModel):
    """Complete video data with metadata and transcript"""

    id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    description: str = Field(..., description="Video description")
    published_at: datetime = Field(..., description="Publication timestamp")
    duration_seconds: int = Field(..., description="Video duration in seconds")
    duration_iso: str = Field(..., description="ISO 8601 duration format")
    view_count: int = Field(0, description="View count")
    like_count: int = Field(0, description="Like count")
    comment_count: int = Field(0, description="Comment count")
    thumbnail_url: str = Field(..., description="Thumbnail URL")
    tags: List[str] = Field(default_factory=list, description="Video tags")
    category_id: str = Field(..., description="YouTube category ID")
    category_name: Optional[str] = Field(None, description="Category name")
    default_language: Optional[str] = Field(None, description="Default language code")
    default_audio_language: Optional[str] = Field(None, description="Default audio language code")
    license: Optional[str] = Field(None, description="License type")
    privacy_status: Optional[str] = Field(None, description="Privacy status")
    made_for_kids: bool = Field(False, description="Whether video is made for kids")
    transcript: Transcript = Field(..., description="Video transcript")
    ml_features: MLFeatures = Field(..., description="ML-specific features")


class Channel(BaseModel):
    """YouTube channel metadata"""

    id: str = Field(..., description="Channel ID")
    title: str = Field(..., description="Channel name")
    description: str = Field(..., description="Channel description")
    custom_url: Optional[str] = Field(None, description="Custom channel URL (e.g., @username)")
    published_at: datetime = Field(..., description="Channel creation date")
    subscriber_count: int = Field(0, description="Subscriber count")
    video_count: int = Field(0, description="Total video count")
    view_count: int = Field(0, description="Total channel views")
    thumbnail_url: str = Field(..., description="Channel thumbnail URL")
    country: Optional[str] = Field(None, description="Country code")
    topics: List[str] = Field(default_factory=list, description="Channel topics/categories")


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process"""

    extracted_at: datetime = Field(default_factory=datetime.utcnow, description="Extraction timestamp")
    extractor_version: str = Field("1.0.0", description="Extractor version")
    channel_id: str = Field(..., description="Extracted channel ID")
    total_videos_processed: int = Field(..., description="Total videos processed")
    successful_extractions: int = Field(..., description="Successful transcript extractions")
    failed_extractions: int = Field(..., description="Failed transcript extractions")


class ErrorEntry(BaseModel):
    """Error information for failed video processing"""

    video_id: str = Field(..., description="Video ID that failed")
    video_title: Optional[str] = Field(None, description="Video title if available")
    error_type: str = Field(..., description="Error type/category")
    error_message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When error occurred")


class ExtractionResult(BaseModel):
    """Complete extraction result for a channel"""

    schema_version: str = Field("1.0.0", description="Output schema version")
    extraction_metadata: ExtractionMetadata = Field(..., description="Extraction metadata")
    channel: Channel = Field(..., description="Channel information")
    videos: List[Video] = Field(default_factory=list, description="Extracted videos")
    errors: List[ErrorEntry] = Field(default_factory=list, description="Processing errors")
