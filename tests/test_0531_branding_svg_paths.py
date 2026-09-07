from pathlib import Path
import xml.etree.ElementTree as ET


def _assets():
    base = Path(__file__).resolve().parents[1] / "src" / "panopilot" / "assets"
    return [base / "panopilot_logo.svg", base / "panopilot_icon.svg"]


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def test_branding_drawables_are_path_only():
    allowed = {"svg", "defs", "linearGradient", "stop", "path"}
    for asset in _assets():
        root = ET.parse(asset).getroot()
        tags = {_local(node.tag) for node in root.iter()}
        assert tags <= allowed, (asset.name, sorted(tags - allowed))
        assert "path" in tags
        assert "text" not in tags
        assert "ellipse" not in tags
        assert "rect" not in tags


def test_branding_paths_do_not_depend_on_strokes_or_fonts():
    for asset in _assets():
        text = asset.read_text(encoding="utf-8")
        assert "font-family" not in text
        assert "font-size" not in text
        assert "<text" not in text
        assert "stroke=" not in text
        assert "stroke:" not in text
