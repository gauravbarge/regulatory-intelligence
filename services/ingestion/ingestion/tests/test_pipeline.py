"""Ingestion pipeline unit tests (no external services)."""

import pytest
from ingestion.pipeline import chunk_text, detect_artifact_type, extract_text


def test_chunk_text_splits_on_paragraphs():
    text = "\n\n".join([f"Section {i}: " + "word " * 40 for i in range(8)])
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) >= 150


def test_chunk_text_single_large_paragraph():
    text = "word " * 500
    chunks = chunk_text(text)
    assert len(chunks) >= 1


def test_detect_artifact_type_release_notes():
    assert detect_artifact_type("release_notes_2026.3.pdf", "Release Notes for 2026.3") == "release_notes"


def test_detect_artifact_type_rtm():
    assert detect_artifact_type("rtm_clinical_view.xlsx", "Requirements Traceability Matrix") == "rtm"


def test_detect_artifact_type_sop():
    assert detect_artifact_type("sop_change_control.pdf", "Standard Operating Procedure for change control") == "sop"


def test_detect_artifact_type_unknown():
    assert detect_artifact_type("random.txt", "some random content here") == "unknown"


def test_extract_text_utf8():
    data = "Hello regulatory world".encode("utf-8")
    result = extract_text(data, "doc.txt")
    assert "regulatory" in result
