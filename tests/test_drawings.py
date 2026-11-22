from pathlib import Path

import ezdxf
import pytest

from autocad_mcp.drawings import DrawingError, DrawingStore


@pytest.fixture
def store(tmp_path: Path) -> DrawingStore:
    return DrawingStore(tmp_path / "drawings")


def test_new_drawing_reports_defaults(store: DrawingStore) -> None:
    info = store.new("plan")
    assert info["name"] == "plan"
    assert info["dxf_version"] == "R2013"
    assert info["units"] == "mm"
    assert info["entity_count"] == 0
    assert info["path"] is None


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b", "", "x" * 101, "/abs"])
def test_rejects_unsafe_names(store: DrawingStore, bad: str) -> None:
    with pytest.raises(DrawingError):
        store.new(bad)


def test_unknown_drawing_raises(store: DrawingStore) -> None:
    with pytest.raises(DrawingError, match="not open"):
        store.add_line("nope", [0, 0], [1, 1])


def test_round_trip_all_entities_and_audit_clean(store: DrawingStore, tmp_path: Path) -> None:
    store.new("rt", units="m")
    line = store.add_line("rt", [0, 0], [10, 0], layer="WALLS")
    circle = store.add_circle("rt", [5, 5], 2.5)
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    poly = store.add_polyline("rt", square, closed=True, layer="WALLS")
    text = store.add_text("rt", "Kitchen", [1, 1], height=0.3, rotation=15, layer="LABELS")

    assert line["start"] == [0.0, 0.0] and line["end"] == [10.0, 0.0] and line["layer"] == "WALLS"
    assert circle["radius"] == 2.5 and circle["layer"] == "0"
    assert poly["closed"] is True and len(poly["points"]) == 4
    assert text["text"] == "Kitchen" and text["insert"] == [1.0, 1.0] and text["rotation"] == 15.0

    saved = store.save("rt")
    path = Path(saved["path"])
    assert path == tmp_path / "drawings" / "rt.dxf"
    assert path.is_file()

    doc = ezdxf.readfile(path)
    auditor = doc.audit()
    assert not auditor.has_errors, [str(e) for e in auditor.errors]
    assert doc.units == ezdxf.units.M
    types = sorted(e.dxftype() for e in doc.modelspace())
    assert types == ["CIRCLE", "LINE", "LWPOLYLINE", "TEXT"]
    assert {"WALLS", "LABELS"} <= {layer.dxf.name for layer in doc.layers}

    # reopening through the store yields the same entities
    fresh = DrawingStore(tmp_path / "drawings")
    info = fresh.open("rt")
    assert info["entity_count"] == 4
    assert info["units"] == "m"


def test_list_entities_filters(store: DrawingStore) -> None:
    store.new("f")
    store.add_line("f", [0, 0], [1, 0], layer="A")
    store.add_line("f", [0, 1], [1, 1], layer="B")
    store.add_circle("f", [0, 0], 1, layer="A")

    assert len(store.list_entities("f")) == 3
    assert {e["layer"] for e in store.list_entities("f", layer="A")} == {"A"}
    assert len(store.list_entities("f", layer="A")) == 2
    assert [e["type"] for e in store.list_entities("f", entity_type="circle")] == ["CIRCLE"]
    assert len(store.list_entities("f", layer="A", entity_type="LINE")) == 1
    assert len(store.list_entities("f", limit=1)) == 1


def test_delete_entity(store: DrawingStore) -> None:
    store.new("d")
    handle = store.add_line("d", [0, 0], [1, 1])["handle"]
    removed = store.delete_entity("d", handle)
    assert removed["handle"] == handle
    assert store.list_entities("d") == []
    with pytest.raises(DrawingError, match="No entity"):
        store.delete_entity("d", handle)


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.add_circle("v", [0, 0], 0),
        lambda s: s.add_circle("v", [0, 0], -1),
        lambda s: s.add_polyline("v", [[0, 0]]),
        lambda s: s.add_text("v", "x", [0, 0], height=0),
        lambda s: s.add_line("v", [0], [1, 1]),
        lambda s: s.new("v2", dxf_version="R12"),
        lambda s: s.new("v3", units="furlong"),
    ],
)
def test_geometry_validation(store: DrawingStore, call) -> None:  # type: ignore[no-untyped-def]
    store.new("v")
    with pytest.raises(DrawingError):
        call(store)


def test_render_png(store: DrawingStore) -> None:
    store.new("r")
    store.add_circle("r", [0, 0], 10)
    store.add_text("r", "hello", [0, 12])
    png = store.render_png("r", width_px=400, height_px=300)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000
