from __future__ import annotations

from lce.scanner.language_detector import detect_language, is_supported_file


def test_detects_supported_languages() -> None:
    assert detect_language("app.py") == "Python"
    assert detect_language("component.tsx") == "TypeScript TSX"
    assert detect_language("Dockerfile") == "Dockerfile"
    assert detect_language("docker-compose.yml") == "YAML"


def test_rejects_unsupported_file() -> None:
    assert detect_language("image.png") is None
    assert not is_supported_file("image.png")
