"""Assemble the Windows x64 portable (no-Docker) submission package."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / "Desktop" / "智邻管家_北京物业智能体_免Docker最终提交版"
PYTHON_HOME = Path(sys.base_prefix)
SITE_PACKAGES = Path(sys.prefix) / "Lib/site-packages"

SOURCE_DIRECTORIES = (
    ".github", "agent", "alembic", "api", "data", "data_pipeline", "docs",
    "domain", "evals", "harness", "mcp_server", "rag", "requirements",
    "scripts", "skills", "tests", "web",
)
SOURCE_FILES = (
    ".dockerignore", ".env.example", ".gitignore", "alembic.ini", "CHANGELOG.md",
    "docker-compose.yml", "docker-compose.public-real.yml", "Dockerfile",
    "Dockerfile.offline", "Makefile", "pyproject.toml", "README.md",
    "RELEASE_NOTES.md", "THIRD_PARTY_NOTICES.md", "VERSION",
    "智邻管家物业社区管理智能体项目实施提纲（完善版）.md",
)
SKIP_PARTS = {
    ".git", ".venv", ".venv313", ".pytest_cache", ".ruff_cache",
    "__pycache__", "htmlcov", "tmp", "tmp_pdf_review", "zhilin_community_agent.egg-info",
}

SCRIPT_FILES = (
    "START_HERE.md",
    "一键启动-Windows.bat",
    "一键启动-Windows.ps1",
    "停止服务-Windows.bat",
    "停止服务-Windows.ps1",
    "运行检查-Windows.bat",
    "运行检查.ps1",
    "免Docker运行操作说明.txt",
)


def ignored(path: Path) -> bool:
    parts=path.relative_to(ROOT).parts
    if any(part in SKIP_PARTS for part in parts): return True
    lowered={part.lower() for part in parts}
    if path.suffix.lower() in {".pyc",".pyo",".db",".sqlite",".sqlite3"}: return True
    if "data" in lowered and "knowledge" in lowered and ({"chroma","chroma_beijing_v1","files"}&lowered): return True
    if len(parts)>=3 and parts[0]=="data" and parts[1]=="public_real" and parts[2] in {"raw","processed","normalized"}: return True
    if parts and parts[0]=="artifacts": return True
    return False


def copy_tree(source: Path,destination: Path) -> None:
    for path in source.rglob("*"):
        if ignored(path): continue
        relative=path.relative_to(source);target=destination/relative
        if path.is_dir(): target.mkdir(parents=True,exist_ok=True)
        elif path.is_file(): target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)


def ensure_empty_target(target: Path) -> None:
    target.mkdir(parents=True,exist_ok=True)
    if list(target.iterdir()): raise SystemExit(f"Target must be empty before staging: {target}")


def copy_runtime(target: Path) -> dict:
    runtime = target / "runtime"
    shutil.copytree(
        PYTHON_HOME,
        runtime,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "Doc", "Tools", "tcltest"),
    )
    destination = runtime / "Lib/site-packages"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        SITE_PACKAGES,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", ".git", ".pytest_cache",
            "playwright", "pytest*", "_pytest", "coverage", "coverage-*", "pytest_cov", "pytest_cov-*",
            "bandit", "bandit-*", "pip_audit", "pip_audit-*", "cyclonedx", "cyclonedx_*",
        ),
    )
    for path in runtime.rglob("__pycache__"):
        if path.is_dir(): shutil.rmtree(path)
    for path in runtime.rglob("*.pyc"):
        path.unlink(missing_ok=True)
    streamlit_agent_assets=destination/"streamlit/.agents"
    if streamlit_agent_assets.exists(): shutil.rmtree(streamlit_agent_assets)
    # Editable installs and host-specific activation files must never refer to
    # the development workspace from the recipient's machine.
    for path in destination.glob("*.pth"):
        if "pywin32" not in path.name.lower():
            path.unlink()
    for pattern in ("__editable__*", "zhilin_community_agent-*.dist-info"):
        for path in destination.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    # Packaging/install tooling is unnecessary at runtime and reduces the
    # exposed command surface. The application imports directly from source/.
    for pattern in ("pip", "pip-*.dist-info", "setuptools", "setuptools-*.dist-info", "pkg_resources"):
        for path in destination.glob(pattern):
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink()
    for folder in (runtime / "Scripts", runtime / "Include", runtime / "share", runtime / "etc"):
        if folder.exists():
            shutil.rmtree(folder)
    files=[p for p in runtime.rglob("*") if p.is_file()]
    return {
        "python_version": sys.version.split()[0],
        "python_architecture": "x64" if sys.maxsize > 2**32 else "x86",
        "file_count": len(files),
        "bytes": sum(path.stat().st_size for path in files),
    }


def sanitize_machine_paths(value):
    """Remove developer-machine paths without changing measured results."""
    if isinstance(value,dict): return {key:sanitize_machine_paths(item) for key,item in value.items()}
    if isinstance(value,list): return [sanitize_machine_paths(item) for item in value]
    if not isinstance(value,str): return value
    replacements=(
        (str(ROOT),"<workspace>"),
        (str(ROOT).replace("\\","/"),"<workspace>"),
        (str(Path.home()),"<user-home>"),
        (str(Path.home()).replace("\\","/"),"<user-home>"),
    )
    for source,replacement in replacements: value=value.replace(source,replacement)
    value=re.sub(r"[A-Za-z]:[\\/](?:Users|WINDOWS)[\\/][^\r\n\"']+", "<local-path>", value)
    return value


def sanitize_evidence(folder: Path) -> None:
    for path in folder.glob("*.json"):
        try: payload=json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError): continue
        path.write_text(json.dumps(sanitize_machine_paths(payload),ensure_ascii=False,indent=2),encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--target",type=Path,default=DEFAULT_TARGET)
    args=parser.parse_args()
    target=args.target.resolve()
    ensure_empty_target(target)

    source_target=target/"source"
    source_target.mkdir()
    for directory in SOURCE_DIRECTORIES:
        copy_tree(ROOT/directory,source_target/directory)
    for file_name in SOURCE_FILES:
        shutil.copy2(ROOT/file_name,source_target/file_name)

    runtime_manifest=copy_runtime(target)
    (target/"runtime_data").mkdir()
    (target/"runtime_data/README.txt").write_text(
        "此目录在首次启动后保存 SQLite 数据库、Chroma 索引、日志和 PID；业务内容仅为 DEMO_SYNTHETIC。\n",
        encoding="utf-8-sig",
    )
    (target/"runtime/portable_runtime_manifest.json").write_text(
        json.dumps({**runtime_manifest,"supported_os":"Windows 10/11 x64","built_for":"智邻管家免Docker提交版"},ensure_ascii=False,indent=2),
        encoding="utf-8",
    )

    for file_name in SCRIPT_FILES:
        source=ROOT/"submission_nondocker"/file_name
        destination=target/file_name
        if source.suffix.lower() in {".ps1",".txt"}:
            destination.write_text(source.read_text(encoding="utf-8"),encoding="utf-8-sig")
        else:
            shutil.copy2(source,destination)

    documents=target/"documents";documents.mkdir()
    docker_documents=Path.home()/"Desktop"/"智邻管家_北京物业智能体_最终提交版"/"documents"
    if not docker_documents.exists():
        raise SystemExit(f"Docker submission documents not found: {docker_documents}")
    shutil.copytree(docker_documents,documents,dirs_exist_ok=True)

    evidence=target/"evidence";evidence.mkdir()
    docker_evidence=Path.home()/"Desktop"/"智邻管家_北京物业智能体_最终提交版"/"evidence"
    shutil.copytree(docker_evidence,evidence,dirs_exist_ok=True)
    sanitize_evidence(evidence)
    addendum_pdf=ROOT/"docs/102_nondocker_delivery_addendum.pdf"
    if addendum_pdf.exists(): shutil.copy2(addendum_pdf,documents/"免Docker便携交付补充说明.pdf")
    print(target)


if __name__=="__main__":
    main()
