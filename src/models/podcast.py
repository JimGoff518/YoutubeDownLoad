"""Podcast and episode models"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, computed_field

from .transcript import Transcript


class Episode(BaseModel):
    """Podcast episode with metadata and transcript"""

    guid: str = Field(..., description="Unique episode identifier")
    title: str = Field(..., description="Episode title")
    description: str = Field("", description="Episode description/show notes")
    published_at: Optional[datetime] = Field(None, description="Publication date")
    duration_seconds: Optional[int] = Field(None, description="Episode duration in seconds")
    audio_url: str = Field(..., description="Direct URL to audio file")
    episode_url: Optional[str] = Field(None, description="Episode webpage URL")
    image_url: Optional[str] = Field(None, description="Episode artwork URL")
    transcript: Transcript = Field(default_factory=lambda: Transcript(available=False), description="Episode transcript")

    @computed_field
    @property
    def word_count(self) -> int:
        """Approximate word count from transcript"""
        if self.transcript.available:
            return self.transcript.word_count
        return 0


class Podcast(BaseModel):
    """Podcast metadata"""

    title: str = Field(..., description="Podcast title")
    description: str = Field("", description="Podcast description")
    author: Optional[str] = Field(None, description="Podcast author/host")
    website_url: Optional[str] = Field(None, description="Podcast website")
    feed_url: str = Field(..., description="RSS feed URL")
    image_url: Optional[str] = Field(None, description="Podcast artwork URL")
    language: Optional[str] = Field(None, description="Podcast language")
    categories: List[str] = Field(default_factory=list, description="Podcast categories")


class PodcastExtractionMetadata(BaseModel):
    """Metadata about the podcast extraction process"""

    extracted_at: datetime = Field(default_factory=datetime.utcnow, description="Extraction timestamp")
    extractor_version: str = Field("1.0.0", description="Extractor version")
    feed_url: str = Field(..., description="RSS feed URL used")
    total_episodes_processed: int = Field(0, description="Total episodes processed")
    successful_extractions: int = Field(0, description="Successful transcript extractions")
    failed_extractions: int = Field(0, description="Failed transcript extractions")


class PodcastErrorEntry(BaseModel):
    """Error information for failed episode processing"""

    episode_guid: str = Field(..., description="Episode GUID that failed")
    episode_title: Optional[str] = Field(None, description="Episode title if available")
    error_type: str = Field(..., description="Error type/category")
    error_message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When error occurred")


class PodcastExtractionResult(BaseModel):
    """Complete extraction result for a podcast"""

    schema_version: str = Field("1.0.0", description="Output schema version")
    extraction_metadata: PodcastExtractionMetadata = Field(..., description="Extraction metadata")
    podcast: Podcast = Field(..., description="Podcast information")
    episodes: List[Episode] = Field(default_factory=list, description="Extracted episodes")
    errors: List[PodcastErrorEntry] = Field(default_factory=list, description="Processing errors")
