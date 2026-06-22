"""Gallery artifact response schema tests."""
from datetime import datetime
from types import SimpleNamespace

from app.schemas.gallery import ArtifactDetail, ArtifactSummary


def test_artifact_summary_validates_from_attributes() -> None:
    created_at = datetime(2026, 6, 22, 12, 0, 0)
    row = SimpleNamespace(
        id=7,
        job_id="job-video",
        artifact_type="video",
        mime_type="video/mp4",
        gallery_path="2026-06-22/video.mp4",
        artifact_url="/gallery/2026-06-22/video.mp4",
        file_size=1234,
        source_node_id="42",
        source_node_type="VHS_VideoCombine",
        created_at=created_at,
    )

    data = ArtifactSummary.model_validate(row).model_dump()

    assert data == {
        "id": 7,
        "job_id": "job-video",
        "artifact_type": "video",
        "mime_type": "video/mp4",
        "gallery_path": "2026-06-22/video.mp4",
        "artifact_url": "/gallery/2026-06-22/video.mp4",
        "file_size": 1234,
        "source_node_id": "42",
        "source_node_type": "VHS_VideoCombine",
        "created_at": created_at,
    }


def test_artifact_detail_includes_delivery_and_workflow_metadata() -> None:
    detail = ArtifactDetail(
        id=8,
        job_id="job-video",
        artifact_type="video",
        mime_type="video/webm",
        gallery_path="2026-06-22/video.webm",
        file_size=2048,
        source_node_id="9",
        source_node_type="VideoSave",
        created_at=datetime(2026, 6, 22, 12, 0, 0),
        local_path="/tmp/gallery/2026-06-22/video.webm",
        workflow_json='{"9": {"class_type": "VideoSave"}}',
        prompt="slow pan",
        negative_prompt="blur",
        metadata_json='{"output_key": "videos"}',
        fps=12.0,
        frame_count=24,
        duration=2.0,
        width=512,
        height=512,
    )

    assert detail.local_path == "/tmp/gallery/2026-06-22/video.webm"
    assert detail.workflow_json == '{"9": {"class_type": "VideoSave"}}'
    assert detail.prompt == "slow pan"
    assert detail.metadata_json == '{"output_key": "videos"}'
    assert detail.fps == 12.0
    assert detail.frame_count == 24
    assert detail.duration == 2.0
    assert detail.width == 512
    assert detail.height == 512
