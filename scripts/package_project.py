"""Build a clean deployment archive from an explicit source-file allowlist."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def package_project():
    destination = ROOT / "dist" / "FinModel_AI_ready_base.zip"
    destination.parent.mkdir(exist_ok=True)
    files = [ROOT / name for name in (
        "app.py", "streamlit_app.py", "requirements.txt", "requirements-dev.txt",
        "README.md", "DEPLOYMENT.md", "start_mac.sh", ".gitignore",
        ".streamlit/config.toml", "static/release.txt", "data/README.md", "exports/.gitkeep",
    )]
    for directory in ("finmodel_agents", "tests", "scripts"):
        files.extend(sorted((ROOT / directory).glob("*.py")))
    with ZipFile(destination,"w",ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path,path.relative_to(ROOT))
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert "streamlit_app.py" in archive.namelist()
        assert not any("cache/" in name or ".venv/" in name or "secrets" in name for name in archive.namelist())
    print(destination)
    return destination


if __name__ == "__main__":
    package_project()
