"""Detect environment variables across all files."""

import re
from pathlib import Path
from ..constants import MAX_FILE_READ_BYTES


def detect_env_vars(repo_path: Path, files: list) -> list:
    """Extract environment variable names from the entire codebase."""
    env_vars = {}  # name -> set of files where found

    # From .env.example / .env.sample / .env.template
    for f in files:
        if f.relative_path.endswith((".env.example", ".env.sample", ".env.template",
                                     ".env.development", ".env.production", ".env.local")):
            try:
                content = Path(f.path).read_text(errors="replace")
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        var_name = line.split("=")[0].strip()
                        if var_name and re.match(r'^[A-Z][A-Z0-9_]*$', var_name):
                            env_vars.setdefault(var_name, set()).add(f.relative_path)
            except Exception:
                pass

    # From source code
    for f in files:
        if not f.language:
            continue
        try:
            content = Path(f.path).read_text(errors="replace")[:MAX_FILE_READ_BYTES]
        except Exception:
            continue

        found = set()

        # JavaScript/TypeScript: process.env.VAR_NAME
        for m in re.finditer(r'process\.env\.([A-Z][A-Z0-9_]+)', content):
            found.add(m.group(1))

        # JavaScript/TypeScript: process.env["VAR_NAME"] or process.env['VAR_NAME']
        for m in re.finditer(r'process\.env\[["\']([A-Z][A-Z0-9_]+)', content):
            found.add(m.group(1))

        # Python: os.environ["VAR"] or os.getenv("VAR") or os.environ.get("VAR")
        for m in re.finditer(r'os\.(?:environ(?:\[|\.get\()|getenv\()["\']([A-Z][A-Z0-9_]+)', content):
            found.add(m.group(1))

        # Go: os.Getenv("VAR")
        for m in re.finditer(r'os\.Getenv\(["\']([A-Z][A-Z0-9_]+)', content):
            found.add(m.group(1))

        # Rust: std::env::var("VAR") or env::var("VAR")
        for m in re.finditer(r'env::var\(["\']([A-Z][A-Z0-9_]+)', content):
            found.add(m.group(1))

        # Ruby: ENV["VAR"] or ENV.fetch("VAR")
        for m in re.finditer(r'ENV(?:\[|\.fetch\()["\']([A-Z][A-Z0-9_]+)', content):
            found.add(m.group(1))

        # Docker/docker-compose: ${VAR} or $VAR
        if f.relative_path.lower().endswith((".yml", ".yaml")) or "docker" in f.relative_path.lower():
            for m in re.finditer(r'\$\{?([A-Z][A-Z0-9_]+)', content):
                found.add(m.group(1))

        # GitHub Actions: ${{ env.VAR }} or ${{ secrets.VAR }}
        if ".github" in f.relative_path:
            for m in re.finditer(r'\$\{\{\s*(?:env|secrets)\.([A-Z][A-Z0-9_]+)', content):
                found.add(m.group(1))

        # Generic: env("VAR") or config("VAR")
        for m in re.finditer(r'(?:env|config)\(["\']([A-Z][A-Z0-9_]+)', content):
            found.add(m.group(1))

        for var in found:
            # Filter out common non-env-var matches
            if var in ("NODE_ENV", "PATH", "HOME", "USER", "SHELL", "TERM", "LANG"):
                env_vars.setdefault(var, set()).add(f.relative_path)
            elif len(var) >= 3 and not var.startswith("__"):
                env_vars.setdefault(var, set()).add(f.relative_path)

    # Sort by frequency then alphabetically
    sorted_vars = sorted(env_vars.items(), key=lambda x: (-len(x[1]), x[0]))
    return [(name, sorted(files_set)) for name, files_set in sorted_vars]
