import json
import senza


def test_roundtrip_primitives():
    assert senza.to_json(None) == "null"
    assert senza.to_json(True) == "true"
    assert senza.to_json(42) == "42"
    assert senza.to_json(3.14) == "3.14"
    assert senza.to_json("hello") == '"hello"'


def test_roundtrip_nested():
    data = {"name": "test", "items": [1, 2, {"x": None}], "flag": True}
    json_str = senza.to_json(data)
    parsed = json.loads(json_str)
    assert parsed == data


def test_from_json():
    obj = senza.from_json('{"a": [1, 2, 3], "b": null}')
    assert obj["a"] == [1, 2, 3]
    assert obj["b"] is None


def test_from_json_roundtrip():
    original = {"nested": {"list": [1, "two", False, None]}}
    json_str = json.dumps(original)
    obj = senza.from_json(json_str)
    assert json.loads(senza.to_json(obj)) == original
