import pytest
from app.agents.llm_provider import KimiProvider

def test_parse_valid_json():
    # Valid JSON should be parsed as-is
    data = '{"a": 1, "b": [2, 3], "c": {"d": "hello"}}'
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1, "b": [2, 3], "c": {"d": "hello"}}

def test_parse_json_with_fences():
    # JSON wrapped in markdown code blocks should be parsed
    data = '```json\n{"a": 1, "b": [2, 3]}\n```'
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1, "b": [2, 3]}

def test_repair_truncated_string():
    # Truncated in the middle of a string value
    data = '{"a": 1, "b": "hello'
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1, "b": "hello"}

def test_repair_truncated_mid_key():
    # Truncated mid-key
    data = '{"a": 1, "b": "hello", "c'
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1, "b": "hello"}

def test_repair_truncated_mid_val():
    # Truncated mid-value syntax
    data = '{"a": 1, "b": '
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1}

def test_repair_truncated_array():
    # Truncated inside a nested array
    data = '{"a": 1, "b": [1, 2, 3'
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1, "b": [1, 2, 3]}

def test_repair_truncated_nested_object():
    # Truncated inside a nested object
    data = '{"a": 1, "b": {"c": 2, "d": "val'
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1, "b": {"c": 2, "d": "val"}}

def test_repair_escaped_string_truncation():
    # Truncated after an escape character inside a string
    data = '{"a": 1, "b": "escaped\\'
    result = KimiProvider.parse_json_content(data)
    assert result == {"a": 1, "b": "escaped"}

def test_repair_invalid_json_fails():
    # Mismatched/invalid JSON with no '{' should fail
    data = 'hello world'
    with pytest.raises(Exception):
        KimiProvider.parse_json_content(data)
