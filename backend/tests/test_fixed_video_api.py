from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"payload"


def _mp4() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42" + b"payload"


def test_animegen_multipart_stages_opaque_file_and_queues_fixed_graph(client, tmp_path: Path) -> None:
    settings = SimpleNamespace(video_staging_dir=str(tmp_path))
    with patch("app.api.generate.get_settings", return_value=settings), patch(
        "app.api.generate.submit", return_value="video-job"
    ) as submit:
        response = client.post(
            "/api/generate/video/animegen-i2v",
            data={"prompt": "wave", "width": "1024", "height": "1024", "total_seconds": "5", "source_frames": "81", "film_target_frames": "321"},
            files={"image": ("../../person.png", _png(), "image/png")},
        )
    assert response.status_code == 201
    params = submit.call_args.args[0]
    staged = Path(params["staged_input_paths"][0])
    assert staged.parent == tmp_path.resolve()
    assert staged.name != "person.png"
    assert staged.is_file()
    assert params["server_owned_verbatim"] is True
    assert params["film_postprocess"] == {"target_frames": 321, "total_seconds": 5.0}
    assert params["workflow"]["93"]["inputs"]["text"] == "wave"
    assert params["workflow"]["98"]["inputs"]["width"] == 1024
    assert params["workflow"]["98"]["inputs"]["height"] == 1024


def test_animegen_multipart_rejects_dimensions_not_divisible_by_16(client, tmp_path: Path) -> None:
    with patch("app.api.generate.get_settings", return_value=SimpleNamespace(video_staging_dir=str(tmp_path))):
        response = client.post(
            "/api/generate/video/animegen-i2v",
            data={"prompt": "wave", "width": "1000", "height": "1024", "total_seconds": "5", "source_frames": "81", "film_target_frames": "321"},
            files={"image": ("person.png", _png(), "image/png")},
        )
    assert response.status_code == 422
    assert "multiple" in response.json()["detail"]
    assert not list(tmp_path.glob("*"))


def test_wan_multipart_stages_reference_and_driver_and_rejects_spoofed_content(client, tmp_path: Path) -> None:
    settings = SimpleNamespace(video_staging_dir=str(tmp_path))
    with patch("app.api.generate.get_settings", return_value=settings), patch(
        "app.api.generate.submit", return_value="wan-job"
    ) as submit:
        response = client.post(
            "/api/generate/video/wan22-animate",
            data={"prompt": "copy motion", "total_seconds": "4", "source_frames": "65", "film_target_frames": "257"},
            files={
                "reference_image": ("ref.png", _png(), "image/png"),
                "driver_video": ("driver.mp4", _mp4(), "video/mp4"),
            },
        )
    assert response.status_code == 201
    params = submit.call_args.args[0]
    assert len(params["staged_input_paths"]) == 2
    assert params["workflow"]["15"]["inputs"]["face_video"] == ["3", 0]
    assert params["workflow"]["15"]["inputs"]["pose_video"] == ["4", 0]

    bad = client.post(
        "/api/generate/video/animegen-i2v",
        data={"prompt": "wave", "total_seconds": "5", "source_frames": "81", "film_target_frames": "321"},
        files={"image": ("fake.png", b"executable", "image/png")},
    )
    assert bad.status_code == 422


def test_minimax_h3_multipart_queues_argus_mlx_contract(client, tmp_path: Path) -> None:
    settings = SimpleNamespace(video_staging_dir=str(tmp_path))
    with patch("app.api.generate.get_settings", return_value=settings), patch(
        "app.api.generate.submit", return_value="h3-job"
    ) as submit:
        response = client.post(
            "/api/generate/video/minimax-h3-i2v",
            data={
                "prompt": "wave gently",
                "width": "768",
                "height": "512",
                "total_seconds": "5",
            },
            files={"image": ("person.png", _png(), "image/png")},
        )
    assert response.status_code == 201
    params = submit.call_args.args[0]
    assert params["execution_engine"] == "argus_mlx_i2v"
    assert params["prompt"] == "wave gently"
    assert params["argus_mlx_i2v"] == {
        "staged_image": params["staged_input_paths"][0],
        "width": 768,
        "height": 512,
        "total_seconds": 5,
        "native_frames": 124,
    }
    assert "execution_target" not in params
    assert "negative_prompt" not in params
    assert "film_postprocess" not in params
    assert "124 frames" in response.json()["message"]


def test_minimax_h3_rejects_removed_legacy_fields_before_staging(client, tmp_path: Path) -> None:
    settings = SimpleNamespace(video_staging_dir=str(tmp_path))
    with patch("app.api.generate.get_settings", return_value=settings), patch(
        "app.api.generate.submit"
    ) as submit:
        response = client.post(
            "/api/generate/video/minimax-h3-i2v",
            data={
                "prompt": "wave gently",
                "width": "768",
                "height": "512",
                "total_seconds": "5",
                "negative_prompt": "camera shake",
                "film_target_frames": "321",
                "execution_target": "worker",
            },
            files={"image": ("person.png", _png(), "image/png")},
        )
    assert response.status_code == 422
    assert "unsupported MiniMax H3 fields" in response.json()["detail"]
    assert not submit.called
    assert not list(tmp_path.glob("*"))


def test_minimax_h3_rejects_dimensions_not_divisible_by_32_before_staging(client, tmp_path: Path) -> None:
    with patch("app.api.generate.get_settings", return_value=SimpleNamespace(video_staging_dir=str(tmp_path))):
        response = client.post(
            "/api/generate/video/minimax-h3-i2v",
            data={"prompt": "wave", "width": "752", "height": "512", "total_seconds": "5"},
            files={"image": ("person.png", _png(), "image/png")},
        )
    assert response.status_code == 422
    assert "32" in response.json()["detail"]
    assert not list(tmp_path.glob("*"))


def test_minimax_h3_rejects_decimal_coercion_before_staging(client, tmp_path: Path) -> None:
    with patch("app.api.generate.get_settings", return_value=SimpleNamespace(video_staging_dir=str(tmp_path))):
        response = client.post(
            "/api/generate/video/minimax-h3-i2v",
            data={"prompt": "wave", "width": "256.0", "height": "256", "total_seconds": "1.0"},
            files={"image": ("person.png", _png(), "image/png")},
        )
    assert response.status_code == 422
    assert "decimal integers" in response.json()["detail"]
    assert not list(tmp_path.glob("*"))


def test_fixed_video_multipart_rejects_invalid_4n_plus_1_before_staging(client, tmp_path: Path) -> None:
    with patch("app.api.generate.get_settings", return_value=SimpleNamespace(video_staging_dir=str(tmp_path))):
        response = client.post(
            "/api/generate/video/animegen-i2v",
            data={"prompt": "wave", "total_seconds": "5", "source_frames": "80", "film_target_frames": "321"},
            files={"image": ("person.png", _png(), "image/png")},
        )
    assert response.status_code == 422
    assert not list(tmp_path.glob("*"))
