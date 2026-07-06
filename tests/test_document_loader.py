from __future__ import annotations

from pathlib import Path

import pytest

from src.document_loader import DocumentLoadingError, load_document, load_txt


def test_load_txt_from_path(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello from ResumeAdjuster", encoding="utf-8")

    result = load_txt(test_file)

    assert result == "Hello from ResumeAdjuster"


def test_load_document_txt_from_path(tmp_path: Path) -> None:
    test_file = tmp_path / "resume.txt"
    test_file.write_text("Python\nMachine Learning\nData Analysis", encoding="utf-8")

    result = load_document(test_file)

    assert "Python" in result
    assert "Machine Learning" in result
    assert "Data Analysis" in result


def test_load_document_rejects_unsupported_file_type(tmp_path: Path) -> None:
    test_file = tmp_path / "resume.csv"
    test_file.write_text("name,skill\nStudent,Python", encoding="utf-8")

    with pytest.raises(DocumentLoadingError, match="Unsupported file type"):
        load_document(test_file)