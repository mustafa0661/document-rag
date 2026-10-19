"""Teslimat denetim betiğinin kural testleri (git gerekmez)."""

import pytest

from app.scripts.release_check import (
    CRITICAL,
    WARNING,
    classify_tracked_files,
    missing_gitignore_entries,
    requirement_mismatches,
    scan_secrets,
)


@pytest.mark.parametrize(
    "path, level",
    [
        (".venv/Lib/site-packages/x.py", CRITICAL),
        (".env", CRITICAL),
        (".env.local", CRITICAL),
        ("models/bge.safetensors", CRITICAL),
        ("data/chroma/chroma.sqlite3", CRITICAL),
        ("data/uploads/ab12/rapor.pdf", CRITICAL),
        ("inspect_out/rapor.md", WARNING),
        ("debug_scanned.py", WARNING),
        ("app/__pycache__/x.cpython-311.pyc", WARNING),
        ("eval/documents/kub.pdf", WARNING),
        ("hasta_raporu.pdf", WARNING),
    ],
    ids=["venv", "env", "env-local", "model", "chroma", "uploads", "inspect-out", "debug-betik",
         "pycache", "eval-belgesi", "kok-dizinde-pdf"],
)
def test_risky_tracked_files_are_flagged(path, level):
    findings = classify_tracked_files([path], {})
    assert findings and findings[0].level == level


@pytest.mark.parametrize(
    "path",
    [".env.example", "app/core/config.py", "README.md", "eval/retrieval_eval.json", "docs/mimari.png",
     "eval/results/retrieval_20261019.md", "app/scripts/download_models.py"],
)
def test_normal_project_files_are_not_flagged(path):
    assert classify_tracked_files([path], {}) == []


def test_large_files_are_flagged():
    findings = classify_tracked_files(["app/x.py"], {"app/x.py": 6 * 1024 * 1024})
    assert [f.level for f in findings] == [WARNING]


@pytest.mark.parametrize(
    "line, flagged",
    [
        # Örnekler parçalanarak yazıldı: denetim betiği bu test dosyasını gerçek sızıntı sanmasın.
        ("HF_TOKEN=" + "hf" + "_" + "a" * 34, True),
        ("api" + '_key = "' + "sk" + "-" + "b" * 30 + '"', True),
        ("pass" + 'word: "' + "gizli-sifre-123" + '"', True),
        ("RAG_OLLAMA_HOST=http://localhost:11434", False),
        ('token_count: int = 0', False),
        ('"hf_token" ortam değişkeni', False),
    ],
    ids=["hf-token", "sk-anahtar", "parola", "normal-ayar", "token-kelimesi", "aciklama"],
)
def test_secret_scan(line, flagged):
    assert bool(scan_secrets("f.py", line)) is flagged


def test_missing_gitignore_entries_are_reported():
    text = "# yorum\n.venv\n/data/\n__pycache__/\n"
    assert missing_gitignore_entries(text) == [".env", ".pytest_cache/", "inspect_out/"]


def test_requirement_pins_are_compared_with_installed_versions():
    lines = ["docling[easyocr]==2.138.0", "chromadb==1.5.9  # yorum", "fpdf2", "streamlit==1.66.0", "-r requirements.txt"]
    installed = {"docling": "2.138.0", "chromadb": "1.5.8"}
    assert requirement_mismatches(lines, installed) == [("chromadb", "1.5.9", "1.5.8"), ("streamlit", "1.66.0", "yok")]
