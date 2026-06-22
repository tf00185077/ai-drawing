"""Generated artifact helper tests."""

from app.core.artifacts import detect_artifact_type


def test_detect_artifact_type_for_supported_image_and_video_extensions() -> None:
    assert detect_artifact_type("image.png") == ("image", "image/png")
    assert detect_artifact_type("IMAGE.JPG") == ("image", "image/jpeg")
    assert detect_artifact_type("render.jpeg") == ("image", "image/jpeg")
    assert detect_artifact_type("preview.webp") == ("image", "image/webp")
    assert detect_artifact_type("loop.gif") == ("video", "image/gif")
    assert detect_artifact_type("movie.mp4") == ("video", "video/mp4")
    assert detect_artifact_type("clip.webm") == ("video", "video/webm")


def test_detect_artifact_type_rejects_unsupported_extensions() -> None:
    assert detect_artifact_type("notes.txt") is None
    assert detect_artifact_type("archive.zip") is None
    assert detect_artifact_type("no_extension") is None
