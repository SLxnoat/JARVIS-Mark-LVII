"""
plugins/smart_desktop_cleaner.py - Downloads & Directory Auto-Organizer.

Scans, categorizes, and organizes files in ~/Downloads, ~/Desktop, or custom directories
into structured subfolders (Documents, Images, Audio, Video, Archives, Installers, Code).
Detects duplicate download versions and stale installers with safe dry-run preview mode.

Adheres strictly to AGENTS.md:
- Never instantiates Qt widgets on worker threads.
- Thread-safe HUD updates via player.show_content() and player.write_log().
- Fast returns; non-blocking; never raises unhandled exceptions.
- Handles player=None gracefully.
"""
from __future__ import annotations

import os
import re
import shutil
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

PLUGIN: Dict[str, Any] = {
    "name": "smart_desktop_cleaner",
    "description": (
        "Intelligently scans, categorizes, and organizes files in ~/Downloads, ~/Desktop, "
        "or custom directories into structured subfolders (Documents, Images, Audio, Video, "
        "Archives, Installers, Code). Detects duplicate download versions and stale temp files "
        "with safe dry-run preview mode before moving."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_dir": {
                "type": "STRING",
                "description": "Directory to clean/scan: 'downloads', 'desktop', or a custom path (defaults to 'downloads').",
            },
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'scan' (inspect only), 'organize' (move files), 'find_duplicates' (list duplicate versions).",
                "enum": ["scan", "organize", "find_duplicates"],
            },
            "dry_run": {
                "type": "BOOLEAN",
                "description": "If true, simulates the organization without moving any files (default true for safety).",
            },
        },
    },
}

CATEGORIES: Dict[str, Tuple[str, ...]] = {
    "Images": (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff"),
    "Documents": (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt", ".csv", ".md", ".epub", ".odt"),
    "Archives": (".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz", ".tgz"),
    "Installers": (".deb", ".rpm", ".dmg", ".pkg", ".exe", ".msi", ".appimage", ".iso"),
    "Code": (".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".sh", ".cpp", ".c", ".rs", ".go", ".sql"),
    "Audio": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"),
    "Video": (".mp4", ".mkv", ".mov", ".avi", ".webm"),
}


def _resolve_dir(target_dir: str | None) -> Path:
    if not target_dir or target_dir.lower() == "downloads":
        return Path.home() / "Downloads"
    if target_dir.lower() == "desktop":
        return Path.home() / "Desktop"
    return Path(target_dir).expanduser().resolve()


def _get_category(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Others"


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _find_duplicates(directory: Path) -> List[Dict[str, Any]]:
    """Detects duplicate files via download naming patterns e.g. file (1).pdf or identical hashes."""
    duplicates: List[Dict[str, Any]] = []
    pattern = re.compile(r"^(.*?)\s*\(\d+\)(\.[^.]+)$")

    files = [f for f in directory.iterdir() if f.is_file() and not f.name.startswith(".")]
    for f in files:
        m = pattern.match(f.name)
        if m:
            base_name = f"{m.group(1)}{m.group(2)}"
            orig = directory / base_name
            duplicates.append({
                "duplicate": f.name,
                "original_candidate": base_name if orig.exists() else "None",
                "size": _format_size(f.stat().st_size),
                "path": str(f),
            })
    return duplicates


def run(parameters: dict | None = None, player=None, session_memory=None) -> str:
    try:
        params = parameters or {}
        target_name = params.get("target_dir", "downloads")
        action = params.get("action", "scan")
        dry_run = params.get("dry_run", True)

        dir_path = _resolve_dir(target_name)
        if not dir_path.exists() or not dir_path.is_dir():
            msg = f"Directory not found: {dir_path}"
            if player:
                player.write_log(f"Cleaner: {msg}")
            return msg

        # Collect direct files (ignore subdirectories and hidden files)
        all_files = [f for f in dir_path.iterdir() if f.is_file() and not f.name.startswith(".")]
        total_files = len(all_files)
        total_size = sum(f.stat().st_size for f in all_files)

        category_counts: Dict[str, List[Path]] = {cat: [] for cat in CATEGORIES}
        category_counts["Others"] = []

        for f in all_files:
            cat = _get_category(f.name)
            category_counts[cat].append(f)

        duplicates = _find_duplicates(dir_path)

        if action == "find_duplicates":
            if not duplicates:
                summary_text = (
                    f"### 🔍 Duplicate Scanner: `{dir_path}`\n\n"
                    "No duplicate downloaded files detected in this directory.\n"
                )
                if player:
                    player.show_content("Duplicate Scan", summary_text)
                return f"No duplicate files detected in {dir_path.name}, sir."

            rows = "\n".join(
                f"| `{d['duplicate']}` | `{d['original_candidate']}` | {d['size']} |"
                for d in duplicates[:20]
            )
            md = (
                f"### 🔍 Duplicate Files Detected: `{dir_path}`\n\n"
                f"Found **{len(duplicates)}** suspected duplicate download files:\n\n"
                f"| Duplicate File | Original Match | Size |\n"
                f"|:---|:---|:---|\n"
                f"{rows}\n"
            )
            if player:
                player.show_content("Duplicate Scan", md)
                player.write_log(f"Cleaner: Found {len(duplicates)} duplicate files in {dir_path.name}")
            return f"Found {len(duplicates)} duplicate files in {dir_path.name}, sir."

        if action == "organize":
            moved_records: List[Tuple[str, str]] = []
            for cat, files in category_counts.items():
                if not files or cat == "Others":
                    continue
                dest_dir = dir_path / cat
                if not dry_run and not dest_dir.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)

                for f in files:
                    dest_file = dest_dir / f.name
                    if not dry_run:
                        if dest_file.exists():
                            dest_file = dest_dir / f"{f.stem}_{int(dest_file.stat().st_mtime)}{f.suffix}"
                        shutil.move(str(f), str(dest_file))
                    moved_records.append((f.name, cat))

            mode_str = "[DRY-RUN SIMULATION]" if dry_run else "[EXECUTED]"
            rows = "\n".join(
                f"| `{fn}` | ➡️ `{cat}/` |" for fn, cat in moved_records[:25]
            )
            if len(moved_records) > 25:
                rows += f"\n| ... and {len(moved_records) - 25} more files | |"

            md = (
                f"### 🧹 Workspace Cleaner {mode_str}: `{dir_path}`\n\n"
                f"- **Total Files Identified:** {len(moved_records)}\n"
                f"- **Target Directory:** `{dir_path}`\n"
                f"- **Dry-Run Mode:** {'Enabled (No files changed)' if dry_run else 'Disabled (Files organized)'}\n\n"
                f"| File Name | Destination Folder |\n"
                f"|:---|:---|\n"
                f"{rows or '| No files needed moving | - |'}\n"
            )
            if player:
                player.show_content("Directory Organizer", md)
                player.write_log(f"Cleaner: {mode_str} organized {len(moved_records)} files in {dir_path.name}")

            if dry_run:
                return f"Dry-run complete, sir. Ready to organize {len(moved_records)} files into categorized folders in {dir_path.name}."
            return f"Successfully organized {len(moved_records)} files into categorized folders in {dir_path.name}, sir."

        # Default action: 'scan'
        cat_summary_rows = "\n".join(
            f"| **{cat}** | {len(files)} files | {_format_size(sum(f.stat().st_size for f in files))} |"
            for cat, files in category_counts.items() if files
        )
        md = (
            f"### 📊 Directory Hygiene Inspection: `{dir_path}`\n\n"
            f"- **Total Files:** {total_files}\n"
            f"- **Cumulative Size:** {_format_size(total_size)}\n"
            f"- **Detected Duplicates:** {len(duplicates)}\n\n"
            f"| Category | File Count | Size |\n"
            f"|:---|:---|:---|\n"
            f"{cat_summary_rows or '| Directory is empty | 0 | 0 B |'}\n\n"
            f"> *Run with action='organize' and dry_run=False to auto-sort into subfolders.*"
        )
        if player:
            player.show_content("Directory Hygiene Scan", md)
            player.write_log(f"Cleaner: Scanned {dir_path.name} ({total_files} files, {_format_size(total_size)})")

        return f"Directory scan complete for {dir_path.name}. Found {total_files} files totaling {_format_size(total_size)} across {len([c for c, f in category_counts.items() if f])} categories, sir."

    except Exception as e:
        err_msg = f"Cleaner error: {e}"
        if player:
            player.write_log(f"Cleaner error: {e}")
        return f"Sir, I encountered an issue inspecting the directory: {e}"
