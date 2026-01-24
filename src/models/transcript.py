"""Transcript data models"""

from typing import List, Optional
from pydantic import BaseModel, Field, computed_field


class TranscriptSegment(BaseModel):
    """A single segment of a transcript with timestamp"""

    text: str = Field(..., description="The text content of this segment")
    start: float = Field(..., description="Start time in seconds")
    duration: float = Field(..., description="Duration in seconds")

    @computed_field
    @property
    def end(self) -> float:
        """End time calculated from start + duration"""
        return self.start + self.duration


class Transcript(BaseModel):
    """Complete transcript with metadata"""

    available: bool = Field(..., description="Whether transcript is available")
    language: Optional[str] = Field(None, description="Language code (e.g., 'en', 'es')")
    is_auto_generated: Optional[bool] = Field(None, description="Whether transcript is auto-generated")
    segments: List[TranscriptSegment] = Field(default_factory=list, description="Transcript segments with timestamps")

    @computed_field
    @property
    def full_text(self) -> str:
        """Complete transcript text joined from all segments"""
        return " ".join(segment.text for segment in self.segments)

    @computed_field
    @property
    def word_count(self) -> int:
        """Approximate word count"""
        return len(self.full_text.split())

    @computed_field
    @property
    def character_count(self) -> int:
        """Total character count"""
        return len(self.full_text)
