from pathlib import Path

from app.services.film_postprocess import build_audio_preserving_mux_command


def test_audio_preserving_mux_maps_optional_h3_audio_and_copies_video() -> None:
    command = build_audio_preserving_mux_command(
        ffmpeg="ffmpeg",
        video_path=Path("film-video.mp4"),
        audio_source_path=Path("h3-source.mp4"),
        output_path=Path("final.mp4"),
        duration_seconds=5.1666666667,
    )
    assert command[:5] == ["ffmpeg", "-y", "-i", "film-video.mp4", "-i"]
    assert "1:a:0?" in command
    assert command[command.index("-c:v") + 1] == "copy"
    assert command[command.index("-c:a") + 1] == "aac"
    assert "-shortest" in command
    assert command[-1] == "final.mp4"
