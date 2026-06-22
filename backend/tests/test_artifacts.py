"""Generated artifact helper tests."""

from app.core.artifacts import (
    detect_artifact_type,
    gallery_output_filename,
    get_output_artifacts,
    get_output_images,
)


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


def test_get_output_artifacts_collects_images_and_video_from_history() -> None:
    history = {
        "prompt-1": {
            "prompt": {
                "10": {"class_type": "SaveImage"},
                "20": {"class_type": "VHS_VideoCombine"},
                "30": {"class_type": "PreviewAny"},
            },
            "outputs": {
                "10": {
                    "images": [
                        {"filename": "still.png", "subfolder": "images", "type": "output"}
                    ]
                },
                "20": {
                    "gifs": [
                        {"filename": "motion.mp4", "subfolder": "videos", "type": "output"}
                    ],
                    "videos": [
                        {"filename": "preview.webm", "subfolder": "", "type": "temp"}
                    ],
                },
                "30": {
                    "files": [
                        {"filename": "notes.txt", "subfolder": "", "type": "output"}
                    ]
                },
            },
        }
    }

    artifacts = get_output_artifacts(history, "prompt-1")

    assert artifacts == [
        {
            "filename": "still.png",
            "subfolder": "images",
            "type": "output",
            "artifact_type": "image",
            "mime_type": "image/png",
            "source_node_id": "10",
            "source_node_type": "SaveImage",
            "output_key": "images",
        },
        {
            "filename": "motion.mp4",
            "subfolder": "videos",
            "type": "output",
            "artifact_type": "video",
            "mime_type": "video/mp4",
            "source_node_id": "20",
            "source_node_type": "VHS_VideoCombine",
            "output_key": "gifs",
        },
        {
            "filename": "preview.webm",
            "subfolder": "",
            "type": "temp",
            "artifact_type": "video",
            "mime_type": "video/webm",
            "source_node_id": "20",
            "source_node_type": "VHS_VideoCombine",
            "output_key": "videos",
        },
    ]


def test_get_output_images_preserves_legacy_image_projection() -> None:
    history = {
        "prompt-1": {
            "outputs": {
                "10": {
                    "images": [
                        {"filename": "still.png", "subfolder": "images", "type": "output"}
                    ],
                    "gifs": [
                        {"filename": "motion.mp4", "subfolder": "videos", "type": "output"}
                    ],
                }
            }
        }
    }

    assert get_output_images(history, "prompt-1") == [
        {"filename": "still.png", "subfolder": "images", "type": "output"}
    ]


def test_gallery_output_filename_preserves_extension_and_sanitizes_name() -> None:
    assert gallery_output_filename("video render.mp4", "abcdef123456", 2) == (
        "video_render_abcdef12_2.mp4"
    )
    assert gallery_output_filename("../bad name.WEBM", "job", 0) == "bad_name_job_0.webm"
    assert gallery_output_filename("???", "job", 1) == "artifact_job_1.bin"
