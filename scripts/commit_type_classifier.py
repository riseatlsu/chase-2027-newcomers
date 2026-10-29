"""
Commit type classification using GitHub Linguist and IANA MIME types.

Strategy:
- If a commit changes at least one source-code file, classify it as "code".
- Otherwise, classify it by non-code precedence:
  config > docs > assets > other

This strategy is intended to capture whether a newcomer's first contribution
involved direct source-code modification.
"""

import json
from typing import List, Dict, Tuple

# GitHub Linguist - mapping of extensions to language types
# Based on: https://github.com/github/linguist/blob/master/lib/linguist/languages.yml
LINGUIST_EXTENSIONS = {
    # Python ecosystem
    ".py": "code",
    ".pyx": "code",
    ".pyi": "code",
    ".ipynb": "code",  # Jupyter notebooks = code

    # C/C++/C#
    ".c": "code",
    ".h": "code",
    ".cc": "code",
    ".cpp": "code",
    ".cxx": "code",
    ".c++": "code",
    ".hpp": "code",
    ".hxx": "code",
    ".h++": "code",
    ".cs": "code",

    # Java/Kotlin
    ".java": "code",
    ".kt": "code",
    ".kts": "code",

    # JavaScript/TypeScript
    ".js": "code",
    ".mjs": "code",
    ".jsx": "code",
    ".ts": "code",
    ".tsx": "code",

    # Ruby
    ".rb": "code",
    ".erb": "code",

    # Go
    ".go": "code",

    # Rust
    ".rs": "code",

    # PHP
    ".php": "code",
    ".phtml": "code",

    # Swift
    ".swift": "code",

    # R language
    ".r": "code",
    ".R": "code",

    # Scala
    ".scala": "code",

    # Other compiled/interpreted languages
    ".el": "code",    # Emacs Lisp
    ".clj": "code",   # Clojure
    ".cljs": "code",  # ClojureScript
    ".erl": "code",   # Erlang
    ".ex": "code",    # Elixir
    ".exs": "code",   # Elixir Scripts
    ".hs": "code",    # Haskell
    ".lua": "code",
    ".pl": "code",    # Perl
    ".pm": "code",    # Perl Module
    ".ml": "code",    # OCaml
    ".fs": "code",    # F#
    ".fsx": "code",
    ".fsi": "code",
    ".dart": "code",
    ".groovy": "code",

    # Shell scripts
    ".sh": "code",
    ".bash": "code",
    ".zsh": "code",
    ".fish": "code",
    ".ps1": "code",   # PowerShell

    # Vim/Neovim
    ".vim": "code",

    # LISP dialects
    ".lisp": "code",
    ".scm": "code",   # Scheme

    # ROS-specific / full filenames
    "package.xml": "config",
    "cmakelists.txt": "config",
    ".launch": "config",
    ".urdf": "config",
    ".sdf": "config",
}

# IANA MIME types for documentation and configs
# Based on: https://www.iana.org/assignments/media-types/
IANA_MIME_TYPES = {
    # Text/Markup documentation
    ".md": "docs",
    ".markdown": "docs",
    ".rst": "docs",
    ".asciidoc": "docs",
    ".adoc": "docs",
    ".org": "docs",   # Emacs org-mode
    ".tex": "docs",
    ".latex": "docs",

    # Office documents
    ".doc": "docs",
    ".docx": "docs",
    ".odt": "docs",   # OpenDocument Text
    ".pdf": "docs",
    ".txt": "docs",

    # Web markup (can be docs or code depending on context)
    ".html": "code",  # Often code
    ".htm": "code",
    ".xml": "config",  # Often config
    ".xhtml": "code",

    # Configuration files (application/*)
    ".json": "config",
    ".yaml": "config",
    ".yml": "config",
    ".toml": "config",
    ".ini": "config",
    ".cfg": "config",
    ".conf": "config",
    ".config": "config",
    ".properties": "config",
    ".gradle": "config",
    ".cmake": "config",
    ".editorconfig": "config",
    ".gitignore": "config",
    ".gitattributes": "config",
    ".env": "config",
    ".envrc": "config",

    # Build/packaging configs
    "dockerfile": "config",
    "makefile": "config",
    ".dockerfile": "config",
    ".pom": "config",
    ".dockerignore": "config",

    # Image files
    ".png": "assets",
    ".jpg": "assets",
    ".jpeg": "assets",
    ".gif": "assets",
    ".svg": "assets",
    ".ico": "assets",
    ".webp": "assets",

    # Compressed/archive
    ".zip": "assets",
    ".tar": "assets",
    ".gz": "assets",
    ".bz2": "assets",
    ".7z": "assets",

    # Audio
    ".mp3": "assets",
    ".wav": "assets",
    ".flac": "assets",
    ".m4a": "assets",

    # Video
    ".mp4": "assets",
    ".avi": "assets",
    ".mov": "assets",
    ".mkv": "assets",
    ".webm": "assets",
}


def _extract_filename(file_obj) -> str:
    """
    Normalize filename extraction from either:
    - dicts like {"filename": "..."}
    - raw strings
    """
    if isinstance(file_obj, dict):
        return str(file_obj.get("filename", "")).strip().lower()
    return str(file_obj).strip().lower()


def _extract_extension(filename: str) -> str:
    """
    Extract the last-dot extension from a filename.
    Returns None if there is no extension.
    """
    if "." not in filename:
        return None
    return "." + filename.split(".")[-1]


def _categorize_file(filename: str) -> str:
    """
    Categorize one file into:
    - code
    - docs
    - config
    - assets
    - other
    """
    ext = _extract_extension(filename)

    # Check full filename in IANA first
    if filename in IANA_MIME_TYPES:
        return IANA_MIME_TYPES[filename]

    # Check extension in IANA
    if ext and ext in IANA_MIME_TYPES:
        return IANA_MIME_TYPES[ext]

    # Check full filename in Linguist map
    if filename in LINGUIST_EXTENSIONS:
        return LINGUIST_EXTENSIONS[filename]

    # Check extension in Linguist map
    if ext and ext in LINGUIST_EXTENSIONS:
        return LINGUIST_EXTENSIONS[ext]

    return "other"


def classify_from_files_v2(files: List) -> Tuple[str, Dict]:
    """
    Classify commit type based on file extensions using GitHub Linguist + IANA MIME types.

    Current strategy:
    - If the commit contains at least one source-code file, classify as "code".
    - Otherwise, apply non-code precedence:
      config > docs > assets > other

    Returns: (classification, details_dict)
      - classification: "code", "docs", "config", "assets", or "other"
      - details_dict: breakdown of file counts by type and rule used
    """
    if not files:
        return "other", {"reason": "no files"}

    file_counts = {
        "code": 0,
        "docs": 0,
        "config": 0,
        "assets": 0,
        "other": 0,
    }

    categorized_files = []

    for f in files:
        filename = _extract_filename(f)
        category = _categorize_file(filename)

        file_counts[category] += 1
        categorized_files.append({
            "filename": filename,
            "category": category,
        })

    # Main decision rule:
    # any-code => code
    # otherwise: config > docs > assets > other
    if file_counts["code"] > 0:
        primary = "code"
        decision_rule = "any_code_file"
    elif file_counts["config"] > 0:
        primary = "config"
        decision_rule = "non_code_precedence_config"
    elif file_counts["docs"] > 0:
        primary = "docs"
        decision_rule = "non_code_precedence_docs"
    elif file_counts["assets"] > 0:
        primary = "assets"
        decision_rule = "non_code_precedence_assets"
    else:
        primary = "other"
        decision_rule = "fallback_other"

    details = {
        "file_counts": file_counts,
        "total_files": len(files),
        "primary_category": primary,
        "decision_rule": decision_rule,
        "categorized_files": categorized_files[:20],  # keep debug output bounded
    }

    return primary, details


if __name__ == "__main__":
    # Test case 1: Code commit
    code_files = [
        {"filename": "src/main.py"},
        {"filename": "src/utils.py"},
        {"filename": "README.md"},
    ]

    result, details = classify_from_files_v2(code_files)
    print(f"Test 1 (Code): {result}")
    print(f"  Details: {json.dumps(details, indent=2)}\n")

    # Test case 2: Config commit
    config_files = [
        "package.xml",
        "CMakeLists.txt",
        ".gitignore",
        "setup.cfg",
    ]

    result, details = classify_from_files_v2(config_files)
    print(f"Test 2 (Config): {result}")
    print(f"  Details: {json.dumps(details, indent=2)}\n")

    # Test case 3: Documentation commit
    doc_files = [
        "README.md",
        "CONTRIBUTING.md",
        "docs/guide.rst",
        "docs/api.md",
    ]

    result, details = classify_from_files_v2(doc_files)
    print(f"Test 3 (Docs): {result}")
    print(f"  Details: {json.dumps(details, indent=2)}\n")

    # Test case 4: Mixed commit with code present
    mixed_files = [
        "src/module.py",
        "README.md",
        "config.yaml",
        "image.png",
    ]

    result, details = classify_from_files_v2(mixed_files)
    print(f"Test 4 (Mixed with code): {result}")
    print(f"  Details: {json.dumps(details, indent=2)}\n")

    # Test case 5: Mixed non-code commit
    mixed_non_code_files = [
        "README.md",
        "docs/install.md",
        "config.yaml",
        "image.png",
    ]

    result, details = classify_from_files_v2(mixed_non_code_files)
    print(f"Test 5 (Mixed non-code): {result}")
    print(f"  Details: {json.dumps(details, indent=2)}\n")