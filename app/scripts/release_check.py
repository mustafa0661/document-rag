"""Teslimat öncesi repository denetimi.

Kullanım (proje kökünden):
    python -m app.scripts.release_check              # denetim
    python -m app.scripts.release_check --run-tests  # + birim testleri

Git'te takip edilen dosyaları kurallara göre tarar (sanal ortam, .env, veri ve
model dosyaları, kullanıcı belgeleri, büyük dosyalar, olası gizli anahtarlar),
.gitignore eksiklerini, requirements sürüm uyumunu ve `pip check` sonucunu
raporlar. Hiçbir dosyayı değiştirmez veya silmez; yalnızca rapor yazar:
data/release_check_report.md (data/ git'e girmez).
"""

import argparse
import importlib.metadata
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPORT_PATH = Path("data/release_check_report.md")
LARGE_FILE_BYTES = 5 * 1024 * 1024
CRITICAL, WARNING = "KRİTİK", "UYARI"

REQUIRED_GITIGNORE = (".venv/", ".env", "data/", "__pycache__/", ".pytest_cache/", "inspect_out/")
MODEL_EXTENSIONS = (".safetensors", ".bin", ".pt", ".pth", ".onnx", ".gguf", ".ckpt")
DOCUMENT_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".docx")
SECRET_PATTERNS = (
    re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),                     # Hugging Face token
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),                    # OpenAI/Anthropic benzeri
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
)


@dataclass(frozen=True)
class Finding:
    level: str
    path: str
    reason: str


# --- Kurallar (saf fonksiyonlar) ------------------------------------------------


def classify_tracked_files(paths: list[str], sizes: dict[str, int]) -> list[Finding]:
    findings = []
    for path in paths:
        parts = path.split("/")
        name, lower = parts[-1], path.lower()
        if parts[0] in (".venv", "venv", "env") or "site-packages" in parts:
            findings.append(Finding(CRITICAL, path, "sanal ortam dosyası commit edilmiş"))
        elif name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            findings.append(Finding(CRITICAL, path, "ortam değişkeni dosyası (gizli bilgi içerebilir)"))
        elif lower.endswith(MODEL_EXTENSIONS):
            findings.append(Finding(CRITICAL, path, "model ağırlık dosyası"))
        elif parts[0] == "data" or lower.endswith((".sqlite3", ".sqlite")):
            findings.append(Finding(CRITICAL, path, "uygulama verisi (ChromaDB, yüklenen dosyalar)"))
        elif parts[0] in ("inspect_out", "debug_out", ".pytest_cache") or "__pycache__" in parts \
                or lower.endswith(".pyc") or (len(parts) == 1 and name.startswith("debug_")):
            findings.append(Finding(WARNING, path, "geçici / hata ayıklama dosyası"))
        elif parts[0] == "eval" and len(parts) > 1 and parts[1] == "documents":
            findings.append(Finding(WARNING, path, "değerlendirme belgesi: yeniden dağıtım izni ve hasta verisi içermediğini kontrol edin"))
        elif lower.endswith(DOCUMENT_EXTENSIONS) and parts[0] not in ("docs",):
            findings.append(Finding(WARNING, path, "belge/görsel: kullanıcıya ait veya özel olmadığını kontrol edin"))
        if sizes.get(path, 0) > LARGE_FILE_BYTES:
            findings.append(Finding(WARNING, path, f"büyük dosya ({sizes[path] / 1024 / 1024:.1f} MB)"))
    return findings


def scan_secrets(path: str, text: str) -> list[Finding]:
    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if any(pattern.search(line) for pattern in SECRET_PATTERNS):
            findings.append(Finding(CRITICAL, f"{path}:{line_number}", "olası gizli anahtar/token"))
    return findings


def missing_gitignore_entries(gitignore_text: str) -> list[str]:
    present = {line.strip().strip("/") for line in gitignore_text.splitlines()
               if line.strip() and not line.strip().startswith("#")}
    return [entry for entry in REQUIRED_GITIGNORE if entry.strip("/") not in present]


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_mismatches(requirement_lines: list[str], installed: dict[str, str]) -> list[tuple[str, str, str]]:
    """`ad[ekstra]==sürüm` satırlarını kurulu sürümlerle karşılaştırır: (ad, istenen, kurulu|'yok')."""
    mismatches = []
    for raw in requirement_lines:
        line = raw.split("#", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9_.-]+)(\[[^\]]*\])?==([^\s;]+)", line)
        if not match:
            continue
        name, wanted = match.group(1), match.group(3)
        actual = installed.get(_normalize(name), "yok")
        if actual != wanted:
            mismatches.append((name, wanted, actual))
    return mismatches


# --- Çalıştırma -------------------------------------------------------------


def _run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 127, f"{command[0]} bulunamadı"
    return result.returncode, (result.stdout + result.stderr).strip()


def main() -> int:
    arg_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg_parser.add_argument("--run-tests", action="store_true", help='pytest -m "not integration" çalıştır')
    args = arg_parser.parse_args()
    lines = [f"# Teslimat denetimi — {datetime.now():%Y-%m-%d %H:%M}", ""]
    critical = 0

    code, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if code != 0:
        print("HATA: Bu klasör bir git deposu değil veya git bulunamadı.", file=sys.stderr)
        return 2
    _, last_commit = _run(["git", "log", "-1", "--format=%h %ad %s", "--date=short"])
    _, status = _run(["git", "status", "--porcelain"])
    _, remotes = _run(["git", "remote", "-v"])
    _, ahead = _run(["git", "status", "-sb"])
    lines += ["## Git", "", f"- Branch: `{branch}`", f"- Son commit: `{last_commit or '—'}`",
              f"- Uzak depo: `{(remotes.splitlines() or ['tanımlı değil'])[0]}`",
              f"- Durum: `{ahead.splitlines()[0] if ahead else '—'}`",
              f"- Commit edilmemiş değişiklik: {len(status.splitlines())} dosya", ""]
    if status:
        lines += ["```", *status.splitlines()[:40], "```", ""]

    _, tracked_raw = _run(["git", "ls-files"])
    tracked = [p for p in tracked_raw.splitlines() if p]
    sizes = {p: Path(p).stat().st_size for p in tracked if Path(p).is_file()}
    findings = classify_tracked_files(tracked, sizes)
    for path in tracked:
        file = Path(path)
        if file.is_file() and sizes.get(path, 0) < 1024 * 1024 and file.suffix.lower() in (
            ".py", ".md", ".toml", ".txt", ".json", ".yml", ".yaml", ".ini", ".cfg", ".env", ".example", ""
        ):
            findings += scan_secrets(path, file.read_text(encoding="utf-8", errors="replace"))
    critical += sum(f.level == CRITICAL for f in findings)
    lines += [f"## Takip edilen dosyalar ({len(tracked)})", ""]
    lines += [f"- **{f.level}** `{f.path}` — {f.reason}" for f in findings] or ["- Sorun bulunmadı."]
    lines.append("")

    gitignore = Path(".gitignore")
    missing = missing_gitignore_entries(gitignore.read_text(encoding="utf-8") if gitignore.exists() else "")
    lines += ["## .gitignore", ""]
    lines += [f"- Eksik: `{entry}`" for entry in missing] or ["- Gerekli satırların hepsi var."]
    lines.append("")

    installed = {_normalize(d.metadata["Name"]): d.version for d in importlib.metadata.distributions()}
    lines += ["## Bağımlılıklar", "", f"- Python: `{sys.version.split()[0]}`"]
    for requirements_file in ("requirements.txt", "requirements-dev.txt"):
        path = Path(requirements_file)
        if not path.exists():
            lines.append(f"- `{requirements_file}` yok")
            continue
        mismatches = requirement_mismatches(path.read_text(encoding="utf-8").splitlines(), installed)
        lines += [f"- `{requirements_file}`: " + ("sabit sürümlerin hepsi kurulu sürümle aynı" if not mismatches
                  else f"{len(mismatches)} uyuşmazlık")]
        lines += [f"  - `{name}`: istenen {wanted}, kurulu {actual}" for name, wanted, actual in mismatches]
    for name in ("torch", "easyocr", "docling", "chromadb", "sentence-transformers", "streamlit", "ollama"):
        lines.append(f"- {name}: `{installed.get(_normalize(name), 'kurulu değil')}`")
    code, pip_check = _run([sys.executable, "-m", "pip", "check"])
    lines += ["", "### pip check", "", "```", pip_check or "(çıktı yok)", "```", ""]
    if code != 0:
        critical += 1

    if args.run_tests:
        code, output = _run([sys.executable, "-m", "pytest", "-m", "not integration", "-q", "-p", "no:cacheprovider"])
        summary = output.splitlines()[-1] if output else "(çıktı yok)"
        lines += ["## Birim testleri", "", f"`{summary}`", ""]
        if code != 0:
            critical += 1

    lines += ["## Özet", "", f"Kritik bulgu: **{critical}**"]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nRapor: {REPORT_PATH}")
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
