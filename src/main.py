"""CLI interface for YouTube transcript extractor"""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

from .api.youtube_client import YouTubeClient
from .processors.video_processor import VideoProcessor
from .storage.json_writer import JSONWriter
from .config import config
from .models import ErrorEntry

app = typer.Typer(
    name="youtube-transcript-extractor",
    help="Extract transcripts from YouTube channels with rich metadata for ML/AI applications",
)
console = Console()


@app.command()
def extract(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", "-c", help="YouTube channel ID (starts with UC)"
    ),
    channel_url: Optional[str] = typer.Option(
        None, "--channel-url", "-u", help="YouTube channel URL"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSON file path (default: output/channel_transcripts.json)",
    ),
    max_videos: Optional[int] = typer.Option(
        None, "--max-videos", "-m", help="Maximum number of videos to process (for testing)"
    ),
):
    """Extract transcripts from a YouTube channel

    Examples:
        python -m src.main extract --channel-id UCxxxxxx
        python -m src.main extract --channel-url https://www.youtube.com/@channelname
        python -m src.main extract -c UCxxxxxx -o my_output.json --max-videos 10
    """
    try:
        # Validate inputs
        if not channel_id and not channel_url:
            console.print(
                "[red]Error:[/red] Please provide either --channel-id or --channel-url",
                style="bold",
            )
            raise typer.Exit(1)

        # Extract channel ID from URL if provided
        if channel_url:
            try:
                channel_id = YouTubeClient.extract_channel_id(channel_url)
                console.print(f"[green]Extracted channel ID:[/green] {channel_id}")
            except ValueError as e:
                console.print(f"[red]Error:[/red] {str(e)}", style="bold")
                raise typer.Exit(1)

        # Set default output path
        if output is None:
            output = config.output_dir / "channel_transcripts.json"

        # Show configuration
        console.print("\n[bold cyan]YouTube Transcript Extractor[/bold cyan]")
        console.print(f"Channel ID: {channel_id}")
        console.print(f"Output: {output.absolute()}")
        if max_videos:
            console.print(f"Max videos: {max_videos}")
        console.print("")

        # Initialize processor
        processor = VideoProcessor()

        # Process channel
        try:
            result = processor.process_channel(channel_id, max_videos)
        except ValueError as e:
            console.print(f"\n[red]Error:[/red] {str(e)}", style="bold")
            raise typer.Exit(1)

        # Write output
        JSONWriter.write_output(result, output)

        # Print summary
        summary = JSONWriter.get_summary(result)
        console.print(summary)

        # Success
        console.print("\n[bold green]✓ Extraction completed successfully![/bold green]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Extraction cancelled by user[/yellow]")
        raise typer.Exit(130)

    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command()
def validate(
    output: Path = typer.Argument(..., help="Path to JSON output file to validate")
):
    """Validate a JSON output file

    Example:
        python -m src.main validate output/channel_transcripts.json
    """
    console.print(f"\n[bold cyan]Validating:[/bold cyan] {output}")
    console.print("")

    is_valid = JSONWriter.validate_output(output)

    if is_valid:
        console.print("\n[bold green]✓ File is valid![/bold green]")
        raise typer.Exit(0)
    else:
        console.print("\n[bold red]✗ File is invalid![/bold red]")
        raise typer.Exit(1)


@app.command()
def video(
    video_id: Optional[str] = typer.Option(
        None, "--video-id", "-v", help="YouTube video ID (11 characters)"
    ),
    video_url: Optional[str] = typer.Option(
        None, "--video-url", "-u", help="YouTube video URL"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSON file path (default: output/video_transcript.json)",
    ),
):
    """Extract transcript from a single YouTube video

    Examples:
        python -m src.main video --video-id DIC-E6W4QBw
        python -m src.main video --video-url https://www.youtube.com/watch?v=DIC-E6W4QBw
        python -m src.main video -u "https://www.youtube.com/watch?v=DIC-E6W4QBw" -o my_video.json
    """
    try:
        # Validate inputs
        if not video_id and not video_url:
            console.print(
                "[red]Error:[/red] Please provide either --video-id or --video-url",
                style="bold",
            )
            raise typer.Exit(1)

        # Extract video ID from URL if provided
        if video_url:
            try:
                video_id = YouTubeClient.extract_video_id(video_url)
                console.print(f"[green]Extracted video ID:[/green] {video_id}")
            except ValueError as e:
                console.print(f"[red]Error:[/red] {str(e)}", style="bold")
                raise typer.Exit(1)

        # Set default output path
        if output is None:
            output = config.output_dir / f"video_{video_id}.json"

        # Show configuration
        console.print("\n[bold cyan]YouTube Video Transcript Extractor[/bold cyan]")
        console.print(f"Video ID: {video_id}")
        console.print(f"Output: {output.absolute()}")
        console.print("")

        # Initialize clients
        youtube_client = YouTubeClient()
        processor = VideoProcessor(youtube_client=youtube_client)

        # Fetch video metadata
        console.print("Fetching video metadata...")
        video_metadata_list = youtube_client.get_video_details([video_id])

        if not video_metadata_list:
            console.print(
                f"[red]Error:[/red] Video not found or unavailable: {video_id}",
                style="bold",
            )
            raise typer.Exit(1)

        video_metadata = video_metadata_list[0]

        # Process video
        console.print(f"Processing video: {video_metadata['title']}")
        video_obj = processor.process_video(video_metadata)

        # Create a simplified single-video output
        from datetime import datetime, timezone
        output_data = {
            "extraction_metadata": {
                "extracted_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "extractor_version": "1.0.0",
                "video_id": video_id,
            },
            "video": video_obj.model_dump(mode="json"),
        }

        # Write output
        import json
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        console.print(f"\n[green]Output saved to:[/green] {output.absolute()}")

        # Print summary
        console.print("\n" + "=" * 60)
        console.print("[bold]Video Information[/bold]")
        console.print("=" * 60)
        console.print(f"Title: {video_obj.title}")
        console.print(f"Published: {video_obj.published_at.strftime('%Y-%m-%d')}")
        console.print(f"Duration: {video_obj.duration_seconds}s ({video_obj.duration_iso})")
        console.print(f"Views: {video_obj.view_count:,}")
        console.print(f"Likes: {video_obj.like_count:,}")
        console.print(f"Comments: {video_obj.comment_count:,}")
        console.print("")
        console.print("[bold]Transcript[/bold]")
        console.print(f"Available: {'Yes' if video_obj.transcript.available else 'No'}")
        if video_obj.transcript.available:
            console.print(f"Language: {video_obj.transcript.language}")
            console.print(f"Auto-generated: {video_obj.transcript.is_auto_generated}")
            console.print(f"Word count: {video_obj.transcript.word_count:,}")
            console.print(f"Segments: {len(video_obj.transcript.segments)}")
            console.print("")
            console.print("[bold]ML Features[/bold]")
            console.print(f"Transcript tokens: {video_obj.ml_features.transcript_token_count:,}")
            console.print(f"Engagement rate: {video_obj.ml_features.engagement_rate:.4%}")
            console.print(f"Views per day: {video_obj.ml_features.views_per_day:,.2f}")
        console.print("=" * 60)

        # Success
        console.print("\n[bold green]✓ Extraction completed successfully![/bold green]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Extraction cancelled by user[/yellow]")
        raise typer.Exit(130)

    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}", style="bold")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def playlist(
    playlist_id: Optional[str] = typer.Option(
        None, "--playlist-id", "-p", help="YouTube playlist ID (starts with PL)"
    ),
    playlist_url: Optional[str] = typer.Option(
        None, "--playlist-url", "-u", help="YouTube playlist URL"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSON file path (default: output/playlist_<ID>.json)",
    ),
    max_videos: Optional[int] = typer.Option(
        None, "--max-videos", "-m", help="Maximum number of videos to process (for testing)"
    ),
):
    """Extract transcripts from all videos in a YouTube playlist

    Examples:
        python -m src.main playlist --playlist-id PLxxxxxx
        python -m src.main playlist --playlist-url "https://www.youtube.com/playlist?list=PLxxxxxx"
        python -m src.main playlist -u "PLAYLIST_URL" --max-videos 10
    """
    try:
        # Validate inputs
        if not playlist_id and not playlist_url:
            console.print(
                "[red]Error:[/red] Please provide either --playlist-id or --playlist-url",
                style="bold",
            )
            raise typer.Exit(1)

        # Extract playlist ID from URL if provided
        if playlist_url:
            try:
                playlist_id = YouTubeClient.extract_playlist_id(playlist_url)
                console.print(f"[green]Extracted playlist ID:[/green] {playlist_id}")
            except ValueError as e:
                console.print(f"[red]Error:[/red] {str(e)}", style="bold")
                raise typer.Exit(1)

        # Set default output path
        if output is None:
            output = config.output_dir / f"playlist_{playlist_id}.json"

        # Show configuration
        console.print("\n[bold cyan]YouTube Playlist Transcript Extractor[/bold cyan]")
        console.print(f"Playlist ID: {playlist_id}")
        console.print(f"Output: {output.absolute()}")
        if max_videos:
            console.print(f"Max videos: {max_videos}")
        console.print("")

        # Initialize processor
        youtube_client = YouTubeClient()
        processor = VideoProcessor(youtube_client=youtube_client)

        # Get video IDs from playlist
        console.print("Fetching playlist videos...")
        try:
            video_ids = youtube_client.get_playlist_videos(playlist_id, max_videos)
        except ValueError as e:
            console.print(f"\n[red]Error:[/red] {str(e)}", style="bold")
            raise typer.Exit(1)

        if not video_ids:
            console.print("No videos found in playlist.")
            raise typer.Exit(0)

        console.print(f"Found {len(video_ids)} videos in playlist.")

        # Fetch video metadata
        console.print("Fetching video metadata...")
        video_metadata_list = youtube_client.get_video_details_batch(video_ids)

        # Create a mapping of video_id to metadata
        video_metadata_map = {vm["id"]: vm for vm in video_metadata_list}

        # Process videos with progress bar
        from datetime import datetime, timezone
        from tqdm import tqdm

        videos = []
        errors = []
        successful_count = 0

        console.print(f"Processing {len(video_ids)} videos...")
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
                video = processor.process_video(video_data)
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
                console.print(f"\nError processing video {video_id}: {str(e)}")

        # Create output
        output_data = {
            "extraction_metadata": {
                "extracted_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "extractor_version": "1.0.0",
                "playlist_id": playlist_id,
                "total_videos_processed": len(video_ids),
                "successful_extractions": successful_count,
                "failed_extractions": len(video_ids) - successful_count,
            },
            "videos": [v.model_dump(mode="json") for v in videos],
            "errors": [e.model_dump(mode="json") for e in errors],
        }

        # Write output
        import json
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        console.print(f"\n[green]Output saved to:[/green] {output.absolute()}")

        # Print summary
        console.print("\n" + "=" * 60)
        console.print("[bold]Playlist Extraction Summary[/bold]")
        console.print("=" * 60)
        console.print(f"Playlist ID: {playlist_id}")
        console.print(f"Videos Processed: {len(video_ids)}")
        console.print(f"Transcripts Extracted: {successful_count}")
        console.print(f"Failed Extractions: {len(errors)}")
        console.print("=" * 60)

        # Success
        console.print("\n[bold green]Extraction completed successfully![/bold green]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Extraction cancelled by user[/yellow]")
        raise typer.Exit(130)

    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}", style="bold")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information"""
    from . import __version__

    console.print(f"[bold cyan]YouTube Transcript Extractor[/bold cyan] v{__version__}")
    console.print("Extract YouTube channel transcripts with rich ML metadata")


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main()
