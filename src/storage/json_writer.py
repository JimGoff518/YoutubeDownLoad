"""JSON output formatting and storage"""

import json
import tempfile
from pathlib import Path
from typing import Union

from ..models import ExtractionResult


class JSONWriter:
    """Write extraction results to JSON files"""

    @staticmethod
    def write_output(
        result: ExtractionResult, output_path: Union[str, Path], pretty: bool = True
    ) -> None:
        """Write extraction result to JSON file

        Args:
            result: ExtractionResult to write
            output_path: Output file path
            pretty: Whether to pretty-print JSON (default: True)

        Raises:
            IOError: If file cannot be written
        """
        output_path = Path(output_path)

        # Create output directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict using Pydantic's model_dump
        data = result.model_dump(mode="json")

        # Prepare JSON string
        if pretty:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            json_str = json.dumps(data, ensure_ascii=False)

        # Atomic write using temporary file
        try:
            # Write to temporary file in the same directory
            temp_fd, temp_path = tempfile.mkstemp(
                dir=output_path.parent, prefix=".tmp_", suffix=".json"
            )

            try:
                # Write JSON to temp file
                with open(temp_fd, "w", encoding="utf-8") as f:
                    f.write(json_str)

                # Rename temp file to final path (atomic on most systems)
                Path(temp_path).replace(output_path)

            except Exception:
                # Clean up temp file if something went wrong
                try:
                    Path(temp_path).unlink()
                except Exception:
                    pass
                raise

        except Exception as e:
            raise IOError(f"Failed to write output file: {str(e)}")

        print(f"\nOutput saved to: {output_path.absolute()}")

    @staticmethod
    def validate_output(output_path: Union[str, Path]) -> bool:
        """Validate a JSON output file

        Args:
            output_path: Path to JSON file

        Returns:
            True if valid, False otherwise
        """
        try:
            output_path = Path(output_path)

            if not output_path.exists():
                print(f"Error: File not found: {output_path}")
                return False

            # Try to load and parse JSON
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Try to create ExtractionResult from data
            result = ExtractionResult(**data)

            # Basic validation
            print(f"Valid extraction result:")
            print(f"  Schema version: {result.schema_version}")
            print(f"  Channel: {result.channel.title}")
            print(
                f"  Videos processed: {result.extraction_metadata.total_videos_processed}"
            )
            print(
                f"  Successful extractions: {result.extraction_metadata.successful_extractions}"
            )
            print(f"  Videos in output: {len(result.videos)}")
            print(f"  Errors: {len(result.errors)}")

            return True

        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {str(e)}")
            return False

        except Exception as e:
            print(f"Error: Validation failed: {str(e)}")
            return False

    @staticmethod
    def get_summary(result: ExtractionResult) -> str:
        """Get a summary of extraction results

        Args:
            result: ExtractionResult

        Returns:
            Summary string
        """
        lines = [
            "",
            "=" * 60,
            "Extraction Summary",
            "=" * 60,
            f"Channel: {result.channel.title}",
            f"Channel ID: {result.channel.id}",
            f"Subscribers: {result.channel.subscriber_count:,}",
            f"Total Channel Videos: {result.channel.video_count:,}",
            "",
            f"Videos Processed: {result.extraction_metadata.total_videos_processed}",
            f"Transcripts Extracted: {result.extraction_metadata.successful_extractions}",
            f"Failed Extractions: {result.extraction_metadata.failed_extractions}",
            "",
        ]

        if result.errors:
            lines.append(f"Errors ({len(result.errors)}):")
            for i, error in enumerate(result.errors[:5], 1):  # Show first 5 errors
                lines.append(
                    f"  {i}. {error.video_id}: {error.error_type} - {error.error_message}"
                )
            if len(result.errors) > 5:
                lines.append(f"  ... and {len(result.errors) - 5} more errors")
            lines.append("")

        # Statistics about transcripts
        if result.videos:
            total_words = sum(
                v.transcript.word_count for v in result.videos if v.transcript.available
            )
            total_tokens = sum(v.ml_features.transcript_token_count for v in result.videos)
            avg_engagement = sum(v.ml_features.engagement_rate for v in result.videos) / len(
                result.videos
            )

            lines.extend(
                [
                    "Transcript Statistics:",
                    f"  Total Words: {total_words:,}",
                    f"  Total Tokens (estimated): {total_tokens:,}",
                    f"  Average Engagement Rate: {avg_engagement:.4%}",
                ]
            )

        lines.append("=" * 60)
        return "\n".join(lines)
