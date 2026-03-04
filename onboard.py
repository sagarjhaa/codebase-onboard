#!/usr/bin/env python3
"""
Codebase Onboarding Agent
=========================
Analyzes a GitHub repository and generates a comprehensive onboarding guide
for new developers. Designed to be genuinely useful on Day 1 at a new job.

Usage:
    python3 onboard.py https://github.com/org/repo
    python3 onboard.py /path/to/local/repo
    python3 onboard.py https://github.com/org/repo --output guide.md
    python3 onboard.py https://github.com/org/repo --ai  # Use LLM for enhanced analysis
"""

import os
import sys
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Optional

try:
    import click
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.markdown import Markdown
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    click = None

try:
    from pathspec import PathSpec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LANGUAGE_EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript (React)",
    ".jsx": "JavaScript (React)", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".kt": "Kotlin", ".swift": "Swift", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".cpp": "C++", ".h": "C/C++ Header", ".cs": "C#",
    ".scala": "Scala", ".clj": "Clojure", ".ex": "Elixir", ".erl": "Erlang",
    ".hs": "Haskell", ".lua": "Lua", ".r": "R", ".R": "R",
    ".dart": "Dart", ".vue": "Vue", ".svelte": "Svelte",
    ".sh": "Shell", ".bash": "Bash", ".zsh": "Zsh",
    ".sql": "SQL", ".graphql": "GraphQL", ".proto": "Protocol Buffers",
}

CONFIG_FILES = {
    "package.json": "Node.js project manifest",
    "package-lock.json": "npm lock file",
    "yarn.lock": "Yarn lock file",
    "pnpm-lock.yaml": "pnpm lock file",
    "tsconfig.json": "TypeScript configuration",
    "pyproject.toml": "Python project config (PEP 518)",
    "setup.py": "Python package setup (legacy)",
    "setup.cfg": "Python package config",
    "requirements.txt": "Python dependencies",
    "Pipfile": "Pipenv dependencies",
    "poetry.lock": "Poetry lock file",
    "Cargo.toml": "Rust project manifest",
    "Cargo.lock": "Rust lock file",
    "go.mod": "Go module definition",
    "go.sum": "Go dependency checksums",
    "Gemfile": "Ruby dependencies",
    "Gemfile.lock": "Ruby lock file",
    "build.gradle": "Gradle build (Java/Kotlin)",
    "build.gradle.kts": "Gradle Kotlin DSL build",
    "pom.xml": "Maven build (Java)",
    "Makefile": "Make build system",
    "CMakeLists.txt": "CMake build system",
    "docker-compose.yml": "Docker Compose services",
    "docker-compose.yaml": "Docker Compose services",
    "Dockerfile": "Docker container definition",
    ".dockerignore": "Docker ignore patterns",
    ".env.example": "Environment variable template",
    ".env.sample": "Environment variable template",
    "webpack.config.js": "Webpack bundler config",
    "vite.config.ts": "Vite bundler config",
    "vite.config.js": "Vite bundler config",
    "next.config.js": "Next.js config",
    "next.config.mjs": "Next.js config",
    "nuxt.config.ts": "Nuxt.js config",
    ".eslintrc.json": "ESLint config",
    ".eslintrc.js": "ESLint config",
    ".prettierrc": "Prettier config",
    "jest.config.js": "Jest test config",
    "jest.config.ts": "Jest test config",
    "vitest.config.ts": "Vitest config",
    "pytest.ini": "Pytest config",
    "tox.ini": "Tox test config",
    ".github/workflows": "GitHub Actions CI/CD",
    ".gitlab-ci.yml": "GitLab CI/CD config",
    "Jenkinsfile": "Jenkins pipeline",
    ".circleci/config.yml": "CircleCI config",
    "terraform.tf": "Terraform infrastructure",
    "main.tf": "Terraform main config",
    "serverless.yml": "Serverless Framework config",
    "fly.toml": "Fly.io deployment config",
    "vercel.json": "Vercel deployment config",
    "netlify.toml": "Netlify deployment config",
    "railway.json": "Railway deployment config",
    "render.yaml": "Render deployment config",
    "Procfile": "Heroku/process manager config",
    ".pre-commit-config.yaml": "Pre-commit hooks",
    "renovate.json": "Renovate dependency updates",
    ".dependabot": "Dependabot config",
    "CODEOWNERS": "Code ownership rules",
    "CONTRIBUTING.md": "Contribution guidelines",
    "ARCHITECTURE.md": "Architecture documentation",
}

ENTRY_POINT_PATTERNS = [
    "main.py", "app.py", "server.py", "index.py", "cli.py", "manage.py", "__main__.py",
    "index.js", "index.ts", "app.js", "app.ts", "server.js", "server.ts",
    "main.js", "main.ts", "src/index.js", "src/index.ts", "src/main.ts",
    "src/App.tsx", "src/App.jsx", "src/app.tsx", "src/app.jsx",
    "main.go", "cmd/main.go", "main.rs", "src/main.rs", "src/lib.rs",
    "Program.cs", "Startup.cs",
]

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".tox", ".pytest_cache",
    ".mypy_cache", "venv", ".venv", "env", ".env", "dist", "build",
    ".next", ".nuxt", "out", "target", ".cargo", "vendor",
    ".idea", ".vscode", ".DS_Store", "coverage", ".coverage",
    "htmlcov", "eggs", "*.egg-info", ".eggs", "bower_components",
}

MAX_FILE_READ_BYTES = 50_000  # 50KB per file
MAX_FILES_TO_ANALYZE = 500


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    path: str
    relative_path: str
    extension: str
    language: str
    size: int
    line_count: int
    is_entry_point: bool = False
    is_config: bool = False
    config_description: str = ""
    imports: list = field(default_factory=list)
    exports: list = field(default_factory=list)
    classes: list = field(default_factory=list)
    functions: list = field(default_factory=list)
    todos: list = field(default_factory=list)
    summary: str = ""


@dataclass
class RepoAnalysis:
    name: str
    path: str
    url: str
    readme_content: str = ""
    license_type: str = ""
    primary_language: str = ""
    languages: dict = field(default_factory=dict)
    framework: str = ""
    frameworks: list = field(default_factory=list)
    package_manager: str = ""
    files: list = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    config_files: list = field(default_factory=list)
    entry_points: list = field(default_factory=list)
    directory_structure: str = ""
    dependencies: dict = field(default_factory=dict)
    dev_dependencies: dict = field(default_factory=dict)
    scripts: dict = field(default_factory=dict)
    ci_cd: list = field(default_factory=list)
    docker: bool = False
    monorepo: bool = False
    test_framework: str = ""
    patterns: list = field(default_factory=list)
    gotchas: list = field(default_factory=list)
    env_vars: list = field(default_factory=list)
    architecture_hints: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core analyzer
# ---------------------------------------------------------------------------

class CodebaseAnalyzer:
    """Analyzes a codebase and extracts structural information."""

    def __init__(self, repo_path: str, console=None):
        self.repo_path = Path(repo_path)
        self.console = console
        self.analysis = RepoAnalysis(
            name=self.repo_path.name,
            path=str(self.repo_path),
            url=""
        )
        self._gitignore_spec = self._load_gitignore()

    def _load_gitignore(self) -> Optional[object]:
        """Load .gitignore patterns for filtering."""
        gitignore_path = self.repo_path / ".gitignore"
        if gitignore_path.exists() and HAS_PATHSPEC:
            try:
                with open(gitignore_path) as f:
                    return PathSpec.from_lines("gitwildmatch", f)
            except Exception:
                pass
        return None

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        parts = path.relative_to(self.repo_path).parts
        for part in parts:
            if part in IGNORE_DIRS or part.startswith("."):
                # Allow .github directory
                if part == ".github":
                    continue
                return True
        if self._gitignore_spec:
            try:
                rel = str(path.relative_to(self.repo_path))
                if self._gitignore_spec.match_file(rel):
                    return True
            except Exception:
                pass
        return False

    def _log(self, msg: str):
        if self.console and HAS_RICH:
            self.console.print(f"  [dim]{msg}[/dim]")

    def analyze(self) -> RepoAnalysis:
        """Run full analysis pipeline."""
        self._log("Reading README...")
        self._read_readme()
        self._log("Scanning file structure...")
        self._scan_files()
        self._log("Detecting frameworks and tools...")
        self._detect_frameworks()
        self._log("Parsing config files...")
        self._parse_configs()
        self._log("Analyzing entry points...")
        self._find_entry_points()
        self._log("Building directory tree...")
        self._build_directory_tree()
        self._log("Detecting patterns...")
        self._detect_patterns()
        self._log("Finding potential gotchas...")
        self._find_gotchas()
        self._log("Extracting environment variables...")
        self._extract_env_vars()
        self._log("Analyzing architecture...")
        self._analyze_architecture()
        return self.analysis

    def _read_readme(self):
        """Read the main README file."""
        for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
            readme_path = self.repo_path / name
            if readme_path.exists():
                try:
                    content = readme_path.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
                    self.analysis.readme_content = content
                except Exception:
                    pass
                break

        # Check license
        for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]:
            license_path = self.repo_path / name
            if license_path.exists():
                try:
                    content = license_path.read_text(errors="replace")[:2000]
                    if "MIT" in content:
                        self.analysis.license_type = "MIT"
                    elif "Apache" in content:
                        self.analysis.license_type = "Apache 2.0"
                    elif "GPL" in content:
                        self.analysis.license_type = "GPL"
                    elif "BSD" in content:
                        self.analysis.license_type = "BSD"
                    elif "ISC" in content:
                        self.analysis.license_type = "ISC"
                    else:
                        self.analysis.license_type = "Custom"
                except Exception:
                    pass
                break

    def _scan_files(self):
        """Walk the repository and catalog all relevant files."""
        language_lines = Counter()
        file_count = 0

        for root, dirs, files in os.walk(self.repo_path):
            root_path = Path(root)
            # Filter dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(root_path / d)]

            for fname in files:
                if file_count >= MAX_FILES_TO_ANALYZE:
                    break

                fpath = root_path / fname
                if self._should_ignore(fpath):
                    continue

                rel_path = str(fpath.relative_to(self.repo_path))
                ext = fpath.suffix.lower()
                lang = LANGUAGE_EXTENSIONS.get(ext, "")

                try:
                    size = fpath.stat().st_size
                except OSError:
                    continue

                if size > 5_000_000:  # Skip files > 5MB
                    continue

                line_count = 0
                if lang or ext in (".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini"):
                    try:
                        with open(fpath, "r", errors="replace") as f:
                            lines = f.readlines()
                            line_count = len(lines)
                    except Exception:
                        pass

                is_config = fname in CONFIG_FILES or rel_path in CONFIG_FILES
                config_desc = CONFIG_FILES.get(fname, CONFIG_FILES.get(rel_path, ""))

                fi = FileInfo(
                    path=str(fpath),
                    relative_path=rel_path,
                    extension=ext,
                    language=lang,
                    size=size,
                    line_count=line_count,
                    is_config=is_config,
                    config_description=config_desc,
                )

                if lang:
                    language_lines[lang] += line_count
                    self._extract_code_info(fi, fpath)

                self.analysis.files.append(fi)
                if is_config:
                    self.analysis.config_files.append(fi)
                file_count += 1

        self.analysis.total_files = file_count
        self.analysis.total_lines = sum(f.line_count for f in self.analysis.files)
        self.analysis.languages = dict(language_lines.most_common())
        if language_lines:
            self.analysis.primary_language = language_lines.most_common(1)[0][0]

    def _extract_code_info(self, fi: FileInfo, fpath: Path):
        """Extract imports, classes, functions, and TODOs from a source file."""
        try:
            content = fpath.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
        except Exception:
            return

        lines = content.split("\n")

        for line in lines:
            stripped = line.strip()

            # Imports
            if fi.language == "Python":
                if stripped.startswith("import ") or stripped.startswith("from "):
                    fi.imports.append(stripped)
            elif fi.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
                if stripped.startswith("import ") or "require(" in stripped:
                    fi.imports.append(stripped)
            elif fi.language == "Go":
                if stripped.startswith("import"):
                    fi.imports.append(stripped)

            # Classes
            if fi.language == "Python":
                m = re.match(r"^class\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))
            elif fi.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
                m = re.match(r"^(?:export\s+)?class\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))

            # Functions (top-level)
            if fi.language == "Python":
                m = re.match(r"^def\s+(\w+)", stripped)
                if m:
                    fi.functions.append(m.group(1))
            elif fi.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
                m = re.match(r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)", stripped)
                if m:
                    fi.functions.append(m.group(1))
                # Arrow functions
                m = re.match(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(", stripped)
                if m:
                    fi.functions.append(m.group(1))
            elif fi.language == "Go":
                m = re.match(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", stripped)
                if m:
                    fi.functions.append(m.group(1))
            elif fi.language == "Rust":
                m = re.match(r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", stripped)
                if m:
                    fi.functions.append(m.group(1))

            # Exports
            if fi.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
                if stripped.startswith("export "):
                    fi.exports.append(stripped[:100])
                elif stripped.startswith("module.exports"):
                    fi.exports.append(stripped[:100])

            # TODOs/FIXMEs
            for marker in ("TODO", "FIXME", "HACK", "XXX", "BUG"):
                if marker in line.upper():
                    fi.todos.append(stripped[:150])
                    break

    def _detect_frameworks(self):
        """Detect frameworks, libraries, and build tools in use."""
        file_names = {f.relative_path for f in self.analysis.files}
        file_basenames = {Path(f.relative_path).name for f in self.analysis.files}

        frameworks = []

        # JavaScript/TypeScript frameworks
        if "next.config.js" in file_basenames or "next.config.mjs" in file_basenames or "next.config.ts" in file_basenames:
            frameworks.append("Next.js")
        if "nuxt.config.ts" in file_basenames or "nuxt.config.js" in file_basenames:
            frameworks.append("Nuxt.js")
        if any(f.relative_path.endswith(".svelte") for f in self.analysis.files):
            frameworks.append("Svelte")
        if any(f.relative_path.endswith(".vue") for f in self.analysis.files):
            frameworks.append("Vue.js")
        if any("from 'react'" in (i) or 'from "react"' in (i) for f in self.analysis.files for i in f.imports):
            frameworks.append("React")
        if any("@angular" in i for f in self.analysis.files for i in f.imports):
            frameworks.append("Angular")
        if "express" in str(self._get_dependencies()):
            frameworks.append("Express.js")
        if "fastify" in str(self._get_dependencies()):
            frameworks.append("Fastify")

        # Python frameworks
        if any("flask" in i.lower() for f in self.analysis.files for i in f.imports):
            frameworks.append("Flask")
        if any("django" in i.lower() for f in self.analysis.files for i in f.imports):
            frameworks.append("Django")
        if any("fastapi" in i.lower() for f in self.analysis.files for i in f.imports):
            frameworks.append("FastAPI")
        if "manage.py" in file_basenames:
            frameworks.append("Django")

        # Go frameworks
        if any("gin-gonic" in i for f in self.analysis.files for i in f.imports):
            frameworks.append("Gin (Go)")
        if any("gorilla/mux" in i for f in self.analysis.files for i in f.imports):
            frameworks.append("Gorilla Mux (Go)")

        # Rust frameworks
        if any("actix" in i for f in self.analysis.files for i in f.imports):
            frameworks.append("Actix (Rust)")
        if any("axum" in i for f in self.analysis.files for i in f.imports):
            frameworks.append("Axum (Rust)")

        # Infrastructure
        if "Dockerfile" in file_basenames:
            self.analysis.docker = True
            frameworks.append("Docker")
        if any("docker-compose" in f for f in file_basenames):
            frameworks.append("Docker Compose")
        if any(f.endswith(".tf") for f in file_names):
            frameworks.append("Terraform")
        if "serverless.yml" in file_basenames or "serverless.yaml" in file_basenames:
            frameworks.append("Serverless Framework")
        if "fly.toml" in file_basenames:
            frameworks.append("Fly.io")

        # Testing
        if "jest.config.js" in file_basenames or "jest.config.ts" in file_basenames:
            self.analysis.test_framework = "Jest"
        if "vitest.config.ts" in file_basenames or "vitest.config.js" in file_basenames:
            self.analysis.test_framework = "Vitest"
        if "pytest.ini" in file_basenames or "conftest.py" in file_basenames:
            self.analysis.test_framework = "pytest"
        if "tox.ini" in file_basenames:
            frameworks.append("tox")

        # CI/CD
        gh_workflows = self.repo_path / ".github" / "workflows"
        if gh_workflows.exists():
            for wf in gh_workflows.iterdir():
                if wf.suffix in (".yml", ".yaml"):
                    self.analysis.ci_cd.append(f"GitHub Actions: {wf.name}")
        if ".gitlab-ci.yml" in file_basenames:
            self.analysis.ci_cd.append("GitLab CI")
        if "Jenkinsfile" in file_basenames:
            self.analysis.ci_cd.append("Jenkins")

        # Package manager
        if "package-lock.json" in file_basenames:
            self.analysis.package_manager = "npm"
        elif "yarn.lock" in file_basenames:
            self.analysis.package_manager = "yarn"
        elif "pnpm-lock.yaml" in file_basenames:
            self.analysis.package_manager = "pnpm"
        elif "poetry.lock" in file_basenames:
            self.analysis.package_manager = "poetry"
        elif "Pipfile.lock" in file_basenames:
            self.analysis.package_manager = "pipenv"
        elif "requirements.txt" in file_basenames:
            self.analysis.package_manager = "pip"
        elif "go.mod" in file_basenames:
            self.analysis.package_manager = "go modules"
        elif "Cargo.lock" in file_basenames:
            self.analysis.package_manager = "cargo"

        # Monorepo detection
        if any(f in file_basenames for f in ["lerna.json", "pnpm-workspace.yaml", "nx.json"]):
            self.analysis.monorepo = True
        if (self.repo_path / "packages").is_dir():
            self.analysis.monorepo = True

        # Deduplicate
        self.analysis.frameworks = list(dict.fromkeys(frameworks))

    def _get_dependencies(self) -> dict:
        """Helper to read dependencies from package files."""
        if self.analysis.dependencies:
            return self.analysis.dependencies
        return {}

    def _parse_configs(self):
        """Parse key configuration files for dependencies and scripts."""
        # package.json
        pkg_json = self.repo_path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(errors="replace"))
                self.analysis.dependencies = data.get("dependencies", {})
                self.analysis.dev_dependencies = data.get("devDependencies", {})
                self.analysis.scripts = data.get("scripts", {})
                if "description" in data:
                    self.analysis.architecture_hints.append(f"Package description: {data['description']}")
            except Exception:
                pass

        # pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(errors="replace")
                # Simple TOML parsing for dependencies
                in_deps = False
                for line in content.split("\n"):
                    if "[project.dependencies]" in line or "[tool.poetry.dependencies]" in line:
                        in_deps = True
                        continue
                    if in_deps and line.startswith("["):
                        in_deps = False
                    if in_deps and "=" in line:
                        parts = line.split("=", 1)
                        self.analysis.dependencies[parts[0].strip()] = parts[1].strip().strip('"')
                # Extract scripts
                in_scripts = False
                for line in content.split("\n"):
                    if "[project.scripts]" in line or "[tool.poetry.scripts]" in line:
                        in_scripts = True
                        continue
                    if in_scripts and line.startswith("["):
                        in_scripts = False
                    if in_scripts and "=" in line:
                        parts = line.split("=", 1)
                        self.analysis.scripts[parts[0].strip()] = parts[1].strip().strip('"')
            except Exception:
                pass

        # requirements.txt
        reqs = self.repo_path / "requirements.txt"
        if reqs.exists() and not self.analysis.dependencies:
            try:
                for line in reqs.read_text(errors="replace").split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        name = re.split(r"[>=<!\[]", line)[0].strip()
                        if name:
                            self.analysis.dependencies[name] = line
            except Exception:
                pass

        # go.mod
        gomod = self.repo_path / "go.mod"
        if gomod.exists():
            try:
                content = gomod.read_text(errors="replace")
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("//") and not line.startswith("module") and not line.startswith("go ") and not line in ("require (", ")"):
                        parts = line.split()
                        if len(parts) >= 2:
                            self.analysis.dependencies[parts[0]] = parts[1]
            except Exception:
                pass

        # Cargo.toml
        cargo = self.repo_path / "Cargo.toml"
        if cargo.exists():
            try:
                content = cargo.read_text(errors="replace")
                in_deps = False
                for line in content.split("\n"):
                    if "[dependencies]" in line:
                        in_deps = True
                        continue
                    if in_deps and line.startswith("["):
                        in_deps = False
                    if in_deps and "=" in line:
                        parts = line.split("=", 1)
                        self.analysis.dependencies[parts[0].strip()] = parts[1].strip().strip('"')
            except Exception:
                pass

    def _find_entry_points(self):
        """Identify main entry points of the application."""
        file_paths = {f.relative_path: f for f in self.analysis.files}

        for pattern in ENTRY_POINT_PATTERNS:
            if pattern in file_paths:
                file_paths[pattern].is_entry_point = True
                self.analysis.entry_points.append(file_paths[pattern])

        # Check package.json "main" and "bin"
        pkg_json = self.repo_path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(errors="replace"))
                for key in ("main", "module", "bin"):
                    val = data.get(key, "")
                    if isinstance(val, str) and val in file_paths:
                        file_paths[val].is_entry_point = True
                        if file_paths[val] not in self.analysis.entry_points:
                            self.analysis.entry_points.append(file_paths[val])
                    elif isinstance(val, dict):
                        for v in val.values():
                            if v in file_paths and file_paths[v] not in self.analysis.entry_points:
                                file_paths[v].is_entry_point = True
                                self.analysis.entry_points.append(file_paths[v])
            except Exception:
                pass

    def _build_directory_tree(self, max_depth=3):
        """Build a visual directory tree."""
        lines = [f"{self.analysis.name}/"]

        def _walk(dir_path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return
            try:
                entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return

            entries = [e for e in entries if not self._should_ignore(e)]

            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                indicator = "/" if entry.is_dir() else ""

                # Add annotations for known config files
                annotation = ""
                rel = str(entry.relative_to(self.repo_path))
                basename = entry.name
                if basename in CONFIG_FILES:
                    annotation = f"  ← {CONFIG_FILES[basename]}"
                elif rel in CONFIG_FILES:
                    annotation = f"  ← {CONFIG_FILES[rel]}"

                lines.append(f"{prefix}{connector}{entry.name}{indicator}{annotation}")

                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(entry, prefix + extension, depth + 1)

        _walk(self.repo_path, "", 1)
        self.analysis.directory_structure = "\n".join(lines[:200])  # Cap at 200 lines
        if len(lines) > 200:
            self.analysis.directory_structure += f"\n... ({len(lines) - 200} more entries)"

    def _detect_patterns(self):
        """Detect common architectural and coding patterns."""
        patterns = []
        file_paths = {f.relative_path for f in self.analysis.files}
        dir_names = set()
        for f in self.analysis.files:
            parts = Path(f.relative_path).parts
            for p in parts[:-1]:
                dir_names.add(p.lower())

        # MVC / MVT
        if {"models", "views", "controllers"} & dir_names or {"models", "views", "templates"} & dir_names:
            patterns.append("**MVC/MVT Architecture**: Separate models, views, and controllers/templates directories detected.")

        # Component-based (React, Vue)
        if "components" in dir_names:
            patterns.append("**Component-Based Architecture**: Dedicated `components/` directory for reusable UI components.")

        # Microservices / multi-service
        if "services" in dir_names or self.analysis.monorepo:
            patterns.append("**Service-Oriented**: Multiple services or packages, suggesting a microservices or monorepo architecture.")

        # Clean architecture / domain-driven
        if {"domain", "infrastructure", "application"} & dir_names:
            patterns.append("**Clean/Hexagonal Architecture**: Domain-driven design with separated domain, application, and infrastructure layers.")

        # API routes
        if "routes" in dir_names or "api" in dir_names:
            patterns.append("**Route-Based API Structure**: Dedicated `routes/` or `api/` directories for endpoint definitions.")

        # Middleware
        if "middleware" in dir_names or "middlewares" in dir_names:
            patterns.append("**Middleware Pattern**: Middleware directory found, typical of Express.js, Django, or similar frameworks.")

        # Hooks (React)
        if "hooks" in dir_names:
            patterns.append("**Custom Hooks**: React custom hooks directory for shared stateful logic.")

        # State management
        if "store" in dir_names or "stores" in dir_names or "redux" in dir_names:
            patterns.append("**Centralized State Management**: Store/Redux directory found for global state management.")

        # Testing patterns
        test_files = [f for f in self.analysis.files if "test" in f.relative_path.lower() or "spec" in f.relative_path.lower()]
        if test_files:
            colocated = any("__tests__" in f.relative_path or ".test." in f.relative_path or ".spec." in f.relative_path for f in test_files)
            separated = any(f.relative_path.startswith("test") or f.relative_path.startswith("tests") for f in test_files)
            if colocated:
                patterns.append("**Colocated Tests**: Test files live alongside source files (`.test.` / `__tests__/` pattern).")
            if separated:
                patterns.append("**Separated Tests**: Dedicated `test/` or `tests/` directory for test files.")
            patterns.append(f"**Test Coverage**: {len(test_files)} test file(s) found.")

        # Environment configuration
        env_files = [f for f in self.analysis.files if f.relative_path.startswith(".env") or "env" in Path(f.relative_path).name.lower()]
        if env_files:
            patterns.append("**Environment Configuration**: `.env` files found for environment-specific config.")

        # Database migrations
        if "migrations" in dir_names or "migrate" in dir_names:
            patterns.append("**Database Migrations**: Migration files found, indicating structured database schema management.")

        # TypeScript strict mode
        tsconfig = self.repo_path / "tsconfig.json"
        if tsconfig.exists():
            try:
                data = json.loads(tsconfig.read_text(errors="replace"))
                strict = data.get("compilerOptions", {}).get("strict", False)
                if strict:
                    patterns.append("**TypeScript Strict Mode**: Enabled — expect strong type safety.")
                else:
                    patterns.append("**TypeScript Non-Strict**: Strict mode is off — may have looser type checking.")
            except Exception:
                pass

        self.analysis.patterns = patterns

    def _find_gotchas(self):
        """Identify potential gotchas and common issues."""
        gotchas = []

        # TODOs and FIXMEs
        all_todos = []
        for f in self.analysis.files:
            for todo in f.todos:
                all_todos.append((f.relative_path, todo))
        if all_todos:
            gotchas.append(f"**{len(all_todos)} TODO/FIXME/HACK comments** found across the codebase. Review these for known issues and technical debt.")

        # Large files
        large_files = [f for f in self.analysis.files if f.line_count > 500 and f.language]
        if large_files:
            largest = sorted(large_files, key=lambda f: f.line_count, reverse=True)[:5]
            file_list = ", ".join(f"`{f.relative_path}` ({f.line_count} lines)" for f in largest)
            gotchas.append(f"**Large source files** that may be hard to navigate: {file_list}")

        # No tests
        test_files = [f for f in self.analysis.files if "test" in f.relative_path.lower() or "spec" in f.relative_path.lower()]
        if not test_files:
            gotchas.append("**No test files detected.** This codebase may lack automated testing.")

        # No CI/CD
        if not self.analysis.ci_cd:
            gotchas.append("**No CI/CD configuration found.** Builds and deployments may be manual.")

        # No .env.example
        has_env = any(".env" in f.relative_path and not f.relative_path.endswith(".example") and not f.relative_path.endswith(".sample") for f in self.analysis.files)
        has_env_example = any(f.relative_path.endswith(".env.example") or f.relative_path.endswith(".env.sample") for f in self.analysis.files)
        if has_env and not has_env_example:
            gotchas.append("**`.env` file exists but no `.env.example`** — new developers may not know which environment variables are required.")

        # No license
        if not self.analysis.license_type:
            gotchas.append("**No LICENSE file found.** This may be intentional (proprietary) or an oversight.")

        # Monorepo without workspace config
        if self.analysis.monorepo and not any(f.relative_path in ("lerna.json", "pnpm-workspace.yaml", "nx.json") for f in self.analysis.files):
            gotchas.append("**Monorepo structure detected but no workspace management tool** (lerna, nx, pnpm workspaces). Dependency management may be manual.")

        # Mixed languages
        if len(self.analysis.languages) > 3:
            langs = ", ".join(list(self.analysis.languages.keys())[:5])
            gotchas.append(f"**Multi-language codebase** ({langs}). Expect different tooling and conventions across components.")

        # Docker without compose
        has_dockerfile = any(f.relative_path == "Dockerfile" for f in self.analysis.files)
        has_compose = any("docker-compose" in f.relative_path for f in self.analysis.files)
        if has_dockerfile and not has_compose:
            gotchas.append("**Dockerfile exists but no docker-compose.yml.** You may need to manually wire up services for local development.")

        self.analysis.gotchas = gotchas

    def _extract_env_vars(self):
        """Extract environment variable names from the codebase."""
        env_vars = set()

        # From .env.example / .env.sample
        for f in self.analysis.files:
            if f.relative_path.endswith((".env.example", ".env.sample", ".env.template")):
                try:
                    content = Path(f.path).read_text(errors="replace")
                    for line in content.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            var_name = line.split("=")[0].strip()
                            env_vars.add(var_name)
                except Exception:
                    pass

        # From source code (process.env.X, os.environ, os.getenv)
        for f in self.analysis.files:
            if not f.language:
                continue
            try:
                content = Path(f.path).read_text(errors="replace")[:MAX_FILE_READ_BYTES]
                # JavaScript/TypeScript: process.env.VAR_NAME
                for m in re.finditer(r"process\.env\.(\w+)", content):
                    env_vars.add(m.group(1))
                # Python: os.environ["VAR"] or os.getenv("VAR")
                for m in re.finditer(r'os\.(?:environ\[|getenv\()["\'](\w+)', content):
                    env_vars.add(m.group(1))
                # Generic: env("VAR") or ENV["VAR"]
                for m in re.finditer(r'(?:env|ENV)\(?["\'](\w+)', content):
                    env_vars.add(m.group(1))
            except Exception:
                pass

        self.analysis.env_vars = sorted(env_vars)

    def _analyze_architecture(self):
        """Generate high-level architecture insights."""
        hints = list(self.analysis.architecture_hints)

        # Count files by top-level directory
        dir_counts = Counter()
        for f in self.analysis.files:
            parts = Path(f.relative_path).parts
            if len(parts) > 1:
                dir_counts[parts[0]] += 1

        top_dirs = dir_counts.most_common(10)
        if top_dirs:
            hints.append("**Top-level directory distribution:** " +
                         ", ".join(f"`{d}/` ({c} files)" for d, c in top_dirs))

        # Identify API layers
        api_files = [f for f in self.analysis.files if any(x in f.relative_path.lower() for x in ("route", "endpoint", "api", "controller", "handler", "resolver"))]
        if api_files:
            hints.append(f"**API layer:** {len(api_files)} files related to API routing/handlers found.")

        # Database / ORM
        db_indicators = [f for f in self.analysis.files if any(x in f.relative_path.lower() for x in ("model", "schema", "migration", "entity", "repository", "dao"))]
        if db_indicators:
            hints.append(f"**Data layer:** {len(db_indicators)} files related to data models/schemas/migrations.")

        # Identify services/modules
        if self.analysis.monorepo:
            packages_dir = self.repo_path / "packages"
            if packages_dir.is_dir():
                pkgs = [p.name for p in packages_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
                if pkgs:
                    hints.append(f"**Monorepo packages:** {', '.join(pkgs[:10])}")

        self.analysis.architecture_hints = hints


# ---------------------------------------------------------------------------
# Guide generator
# ---------------------------------------------------------------------------

class OnboardingGuideGenerator:
    """Generates a markdown onboarding guide from analysis results."""

    def __init__(self, analysis: RepoAnalysis, use_ai: bool = False):
        self.a = analysis
        self.use_ai = use_ai and HAS_OPENAI and os.getenv("OPENAI_API_KEY")

    def generate(self) -> str:
        """Generate the full onboarding guide."""
        sections = [
            self._header(),
            self._quick_overview(),
            self._tech_stack(),
            self._directory_structure(),
            self._architecture_overview(),
            self._entry_points(),
            self._key_files(),
            self._setup_guide(),
            self._common_patterns(),
            self._dependency_overview(),
            self._testing(),
            self._ci_cd(),
            self._environment_variables(),
            self._gotchas(),
            self._next_steps(),
        ]

        guide = "\n\n---\n\n".join(s for s in sections if s)

        if self.use_ai:
            guide = self._enhance_with_ai(guide)

        return guide

    def _header(self) -> str:
        name = self.a.name
        return f"""# 🚀 Onboarding Guide: {name}

*Auto-generated by Codebase Onboarding Agent*
*Generated on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}*

> This guide was generated by analyzing the repository structure, configuration files,
> source code, and dependencies. It should give you a solid starting point for understanding
> this codebase. Always verify with your team for the latest conventions and practices."""

    def _quick_overview(self) -> str:
        lines = ["## 📋 Quick Overview", ""]

        if self.a.readme_content:
            # Extract first paragraph or first 500 chars of README
            paragraphs = self.a.readme_content.split("\n\n")
            # Skip title lines
            desc_paras = [p for p in paragraphs if not p.strip().startswith("#")]
            if desc_paras:
                first = desc_paras[0].strip()[:500]
                lines.append(f"> {first}")
                lines.append("")

        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| **Primary Language** | {self.a.primary_language or 'N/A'} |")
        if self.a.frameworks:
            lines.append(f"| **Frameworks** | {', '.join(self.a.frameworks)} |")
        lines.append(f"| **Total Files** | {self.a.total_files:,} |")
        lines.append(f"| **Total Lines** | {self.a.total_lines:,} |")
        if self.a.license_type:
            lines.append(f"| **License** | {self.a.license_type} |")
        if self.a.package_manager:
            lines.append(f"| **Package Manager** | {self.a.package_manager} |")
        if self.a.test_framework:
            lines.append(f"| **Test Framework** | {self.a.test_framework} |")
        if self.a.monorepo:
            lines.append(f"| **Monorepo** | Yes |")

        return "\n".join(lines)

    def _tech_stack(self) -> str:
        if not self.a.languages:
            return ""

        lines = ["## 🛠 Tech Stack", "", "### Languages (by lines of code)"]
        total_lines = sum(self.a.languages.values())
        for lang, count in self.a.languages.items():
            pct = (count / total_lines * 100) if total_lines > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            lines.append(f"- **{lang}**: {count:,} lines ({pct:.1f}%) `{bar}`")

        if self.a.frameworks:
            lines.append("")
            lines.append("### Frameworks & Tools")
            for fw in self.a.frameworks:
                lines.append(f"- {fw}")

        return "\n".join(lines)

    def _directory_structure(self) -> str:
        if not self.a.directory_structure:
            return ""

        return f"""## 📂 Directory Structure

```
{self.a.directory_structure}
```"""

    def _architecture_overview(self) -> str:
        if not self.a.architecture_hints and not self.a.patterns:
            return ""

        lines = ["## 🏗 Architecture Overview", ""]

        for hint in self.a.architecture_hints:
            lines.append(f"- {hint}")

        return "\n".join(lines)

    def _entry_points(self) -> str:
        if not self.a.entry_points:
            return ""

        lines = ["## 🚪 Entry Points", "",
                  "These are the main entry points where execution begins:", ""]

        for ep in self.a.entry_points:
            lines.append(f"### `{ep.relative_path}`")
            if ep.functions:
                lines.append(f"- **Key functions:** {', '.join(ep.functions[:10])}")
            if ep.classes:
                lines.append(f"- **Key classes:** {', '.join(ep.classes[:10])}")
            if ep.imports:
                key_imports = [i for i in ep.imports if not any(x in i for x in ("os", "sys", "re", "json", "typing"))][:5]
                if key_imports:
                    lines.append(f"- **Notable imports:** {', '.join(f'`{i[:80]}`' for i in key_imports)}")
            lines.append("")

        return "\n".join(lines)

    def _key_files(self) -> str:
        lines = ["## 📄 Key Files", ""]

        # Config files
        if self.a.config_files:
            lines.append("### Configuration Files")
            lines.append("")
            for cf in self.a.config_files[:20]:
                desc = cf.config_description or "Configuration file"
                lines.append(f"- **`{cf.relative_path}`** — {desc}")
            lines.append("")

        # Largest source files (often the most important)
        source_files = sorted(
            [f for f in self.a.files if f.language and f.line_count > 0],
            key=lambda f: f.line_count, reverse=True
        )[:15]

        if source_files:
            lines.append("### Important Source Files (by size)")
            lines.append("")
            for sf in source_files:
                details = []
                if sf.classes:
                    details.append(f"classes: {', '.join(sf.classes[:3])}")
                if sf.functions:
                    fn_list = sf.functions[:5]
                    details.append(f"functions: {', '.join(fn_list)}")
                detail_str = f" — {'; '.join(details)}" if details else ""
                lines.append(f"- **`{sf.relative_path}`** ({sf.line_count} lines, {sf.language}){detail_str}")

        return "\n".join(lines)

    def _setup_guide(self) -> str:
        lines = ["## ⚡ Getting Started (Dev Environment Setup)", ""]

        # Prerequisites
        prereqs = []
        if self.a.primary_language == "Python":
            prereqs.append("Python 3.8+")
        if self.a.primary_language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
            prereqs.append("Node.js 18+ (LTS recommended)")
        if self.a.primary_language == "Go":
            prereqs.append("Go 1.21+")
        if self.a.primary_language == "Rust":
            prereqs.append("Rust (latest stable via rustup)")
        if self.a.docker:
            prereqs.append("Docker & Docker Compose")

        if prereqs:
            lines.append("### Prerequisites")
            for p in prereqs:
                lines.append(f"- {p}")
            lines.append("")

        # Installation steps
        lines.append("### Installation")
        lines.append("")
        lines.append("```bash")
        lines.append(f"# Clone the repository")
        if self.a.url:
            lines.append(f"git clone {self.a.url}")
            lines.append(f"cd {self.a.name}")
        else:
            lines.append(f"cd {self.a.name}")
        lines.append("")

        # Package installation
        if self.a.package_manager == "npm":
            lines.append("# Install dependencies")
            lines.append("npm install")
        elif self.a.package_manager == "yarn":
            lines.append("# Install dependencies")
            lines.append("yarn install")
        elif self.a.package_manager == "pnpm":
            lines.append("# Install dependencies")
            lines.append("pnpm install")
        elif self.a.package_manager == "pip":
            lines.append("# Create virtual environment")
            lines.append("python3 -m venv venv")
            lines.append("source venv/bin/activate")
            lines.append("")
            lines.append("# Install dependencies")
            lines.append("pip install -r requirements.txt")
        elif self.a.package_manager == "poetry":
            lines.append("# Install dependencies")
            lines.append("poetry install")
        elif self.a.package_manager == "pipenv":
            lines.append("# Install dependencies")
            lines.append("pipenv install --dev")
        elif self.a.package_manager == "go modules":
            lines.append("# Download dependencies")
            lines.append("go mod download")
        elif self.a.package_manager == "cargo":
            lines.append("# Build the project")
            lines.append("cargo build")

        # Environment setup
        if self.a.env_vars:
            lines.append("")
            lines.append("# Set up environment variables")
            has_example = any(f.relative_path.endswith((".env.example", ".env.sample")) for f in self.a.files)
            if has_example:
                lines.append("cp .env.example .env")
                lines.append("# Edit .env with your local values")
            else:
                lines.append("# Create a .env file with required variables (see Environment Variables section below)")

        lines.append("```")
        lines.append("")

        # Available scripts
        if self.a.scripts:
            lines.append("### Available Scripts")
            lines.append("")
            runner = self.a.package_manager if self.a.package_manager in ("npm", "yarn", "pnpm") else ""
            for name, cmd in list(self.a.scripts.items())[:15]:
                prefix = f"{runner} run " if runner else ""
                lines.append(f"- **`{prefix}{name}`** — `{cmd}`")

        # Docker
        if self.a.docker:
            lines.append("")
            lines.append("### Docker")
            lines.append("")
            lines.append("```bash")
            has_compose = any("docker-compose" in f.relative_path for f in self.a.files)
            if has_compose:
                lines.append("# Start all services")
                lines.append("docker-compose up -d")
                lines.append("")
                lines.append("# View logs")
                lines.append("docker-compose logs -f")
            else:
                lines.append("# Build the image")
                lines.append(f"docker build -t {self.a.name} .")
                lines.append("")
                lines.append("# Run the container")
                lines.append(f"docker run -p 8080:8080 {self.a.name}")
            lines.append("```")

        return "\n".join(lines)

    def _common_patterns(self) -> str:
        if not self.a.patterns:
            return ""

        lines = ["## 🔄 Common Patterns & Conventions", ""]
        for pattern in self.a.patterns:
            lines.append(f"- {pattern}")

        return "\n".join(lines)

    def _dependency_overview(self) -> str:
        if not self.a.dependencies:
            return ""

        lines = ["## 📦 Dependencies", ""]

        # Categorize dependencies
        deps = self.a.dependencies
        if len(deps) > 30:
            lines.append(f"This project has **{len(deps)} dependencies**. Here are the most notable:")
            lines.append("")

        # Try to identify key categories
        categories = defaultdict(list)
        for name, version in deps.items():
            name_lower = name.lower()
            if any(x in name_lower for x in ("express", "fastify", "koa", "hapi", "flask", "django", "fastapi", "gin", "axum", "actix")):
                categories["Web Framework"].append((name, version))
            elif any(x in name_lower for x in ("react", "vue", "svelte", "angular", "next", "nuxt")):
                categories["Frontend Framework"].append((name, version))
            elif any(x in name_lower for x in ("prisma", "sequelize", "typeorm", "mongoose", "sqlalchemy", "knex", "drizzle")):
                categories["Database/ORM"].append((name, version))
            elif any(x in name_lower for x in ("jest", "mocha", "pytest", "vitest", "chai", "supertest", "testing")):
                categories["Testing"].append((name, version))
            elif any(x in name_lower for x in ("eslint", "prettier", "typescript", "babel", "webpack", "vite", "rollup")):
                categories["Build/Lint Tools"].append((name, version))
            elif any(x in name_lower for x in ("aws", "azure", "gcp", "firebase", "supabase", "redis", "kafka", "rabbitmq")):
                categories["Cloud/Infrastructure"].append((name, version))
            elif any(x in name_lower for x in ("auth", "jwt", "passport", "oauth", "bcrypt", "helmet")):
                categories["Auth/Security"].append((name, version))
            else:
                categories["Other"].append((name, version))

        for cat, items in categories.items():
            if cat == "Other" and len(items) > 20:
                lines.append(f"### {cat} ({len(items)} packages)")
                for name, ver in items[:10]:
                    lines.append(f"- `{name}` {ver}")
                lines.append(f"- *... and {len(items) - 10} more*")
            elif items:
                lines.append(f"### {cat}")
                for name, ver in items:
                    lines.append(f"- `{name}` {ver}")
            lines.append("")

        return "\n".join(lines)

    def _testing(self) -> str:
        test_files = [f for f in self.a.files if "test" in f.relative_path.lower() or "spec" in f.relative_path.lower()]
        if not test_files and not self.a.test_framework:
            return ""

        lines = ["## 🧪 Testing", ""]

        if self.a.test_framework:
            lines.append(f"**Test framework:** {self.a.test_framework}")
            lines.append("")

        if test_files:
            lines.append(f"**{len(test_files)} test file(s) found.**")
            lines.append("")

            # Show test file locations
            test_dirs = Counter()
            for f in test_files:
                parts = Path(f.relative_path).parts
                if len(parts) > 1:
                    test_dirs[parts[0]] += 1
                else:
                    test_dirs["(root)"] += 1

            lines.append("Test file distribution:")
            for dir_name, count in test_dirs.most_common(5):
                lines.append(f"- `{dir_name}/`: {count} test files")

        # Running tests
        lines.append("")
        lines.append("### Running Tests")
        lines.append("")
        lines.append("```bash")
        if self.a.test_framework == "Jest":
            lines.append("npm test")
            lines.append("# or for watch mode:")
            lines.append("npx jest --watch")
        elif self.a.test_framework == "Vitest":
            lines.append("npx vitest")
            lines.append("# or for watch mode:")
            lines.append("npx vitest --watch")
        elif self.a.test_framework == "pytest":
            lines.append("pytest")
            lines.append("# with coverage:")
            lines.append("pytest --cov")
        elif "test" in self.a.scripts:
            runner = self.a.package_manager if self.a.package_manager in ("npm", "yarn", "pnpm") else "npm"
            lines.append(f"{runner} test")
        else:
            lines.append("# Check package.json scripts or Makefile for test commands")
        lines.append("```")

        return "\n".join(lines)

    def _ci_cd(self) -> str:
        if not self.a.ci_cd:
            return ""

        lines = ["## 🔄 CI/CD", ""]
        for ci in self.a.ci_cd:
            lines.append(f"- {ci}")

        return "\n".join(lines)

    def _environment_variables(self) -> str:
        if not self.a.env_vars:
            return ""

        lines = ["## 🔐 Environment Variables", "",
                  "The following environment variables are referenced in the codebase:", ""]

        for var in self.a.env_vars:
            lines.append(f"- `{var}`")

        lines.append("")
        lines.append("*Check `.env.example` or ask your team for the correct values.*")

        return "\n".join(lines)

    def _gotchas(self) -> str:
        if not self.a.gotchas:
            return ""

        lines = ["## ⚠️ Gotchas & Potential Issues", ""]
        for g in self.a.gotchas:
            lines.append(f"- {g}")

        # Add TODOs summary
        all_todos = []
        for f in self.a.files:
            for todo in f.todos:
                all_todos.append((f.relative_path, todo))

        if all_todos:
            lines.append("")
            lines.append("### Notable TODOs/FIXMEs")
            lines.append("")
            for path, todo in all_todos[:15]:
                lines.append(f"- `{path}`: {todo[:120]}")
            if len(all_todos) > 15:
                lines.append(f"- *... and {len(all_todos) - 15} more*")

        return "\n".join(lines)

    def _next_steps(self) -> str:
        lines = ["## 🎯 Suggested Next Steps", "",
                  "1. **Read the README** thoroughly — it's your primary orientation document",
                  "2. **Set up the dev environment** using the steps above",
                  "3. **Run the tests** to verify your setup works"]

        if self.a.entry_points:
            ep_list = ", ".join(f"`{ep.relative_path}`" for ep in self.a.entry_points[:3])
            lines.append(f"4. **Start with the entry points**: {ep_list}")

        lines.append(f"5. **Explore the directory structure** — focus on the top-level organization")

        if self.a.ci_cd:
            lines.append(f"6. **Review CI/CD pipelines** to understand the deployment process")

        lines.extend([
            "",
            "### Questions to Ask Your Team",
            "",
            "- What's the branching strategy? (trunk-based, gitflow, etc.)",
            "- What's the PR review process?",
            "- Are there any known issues or ongoing refactors I should know about?",
            "- Who owns which parts of the codebase? (Check CODEOWNERS if it exists)",
            "- What's the deployment process and cadence?",
            "- Are there any services or systems not in this repo that I should know about?",
        ])

        return "\n".join(lines)

    def _enhance_with_ai(self, guide: str) -> str:
        """Use OpenAI to enhance the guide with deeper insights."""
        try:
            client = openai.OpenAI()

            # Send the README + key file summaries for deeper analysis
            context = f"README:\n{self.a.readme_content[:3000]}\n\n"
            context += f"Primary language: {self.a.primary_language}\n"
            context += f"Frameworks: {', '.join(self.a.frameworks)}\n"

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a senior software engineer creating an onboarding guide. Based on the analysis below, add a section called '## 🤖 AI-Enhanced Insights' with deeper observations about the architecture, potential learning curve, and recommendations for a new developer. Be specific and actionable. Keep it to 300 words."},
                    {"role": "user", "content": context + "\n\nCurrent guide:\n" + guide[:5000]}
                ],
                max_tokens=1000,
                temperature=0.7,
            )

            ai_section = response.choices[0].message.content
            guide += f"\n\n---\n\n{ai_section}"
        except Exception as e:
            guide += f"\n\n---\n\n*AI enhancement failed: {e}*"

        return guide


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def clone_repo(url: str, target_dir: str, console=None) -> str:
    """Clone a git repository and return the path."""
    if console and HAS_RICH:
        console.print(f"  [dim]Cloning {url}...[/dim]")

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, target_dir],
            capture_output=True, text=True, check=True, timeout=120
        )
        return target_dir
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to clone repository: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Clone timed out (120s limit)")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Codebase Onboarding Agent — Generate onboarding guides from repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 onboard.py https://github.com/expressjs/express
  python3 onboard.py /path/to/local/repo
  python3 onboard.py https://github.com/org/repo --output guide.md
  python3 onboard.py https://github.com/org/repo --ai
        """
    )
    parser.add_argument("repo", help="GitHub URL or local path to a repository")
    parser.add_argument("--output", "-o", help="Output file path (default: prints to stdout)")
    parser.add_argument("--ai", action="store_true", help="Use OpenAI to enhance the guide (requires OPENAI_API_KEY)")
    parser.add_argument("--json", action="store_true", help="Output raw analysis as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    console = Console() if HAS_RICH and not args.quiet else None
    temp_dir = None

    try:
        if console:
            console.print(Panel.fit(
                "[bold green]🚀 Codebase Onboarding Agent[/bold green]\n"
                f"[dim]Analyzing: {args.repo}[/dim]",
                border_style="green"
            ))

        # Determine if URL or local path
        repo_path = args.repo
        is_url = repo_path.startswith("http://") or repo_path.startswith("https://") or repo_path.startswith("git@")

        if is_url:
            temp_dir = tempfile.mkdtemp(prefix="onboard_")
            repo_path = clone_repo(args.repo, os.path.join(temp_dir, "repo"), console)
        elif not os.path.isdir(repo_path):
            print(f"Error: {repo_path} is not a valid directory or URL", file=sys.stderr)
            sys.exit(1)

        # Analyze
        if console:
            console.print("\n[bold]Analyzing codebase...[/bold]")

        analyzer = CodebaseAnalyzer(repo_path, console)
        analysis = analyzer.analyze()
        analysis.url = args.repo if is_url else ""

        if args.json:
            # Output raw analysis
            import dataclasses

            def serialize(obj):
                if dataclasses.is_dataclass(obj):
                    return dataclasses.asdict(obj)
                return str(obj)

            print(json.dumps(dataclasses.asdict(analysis), indent=2, default=str))
        else:
            # Generate guide
            if console:
                console.print("\n[bold]Generating onboarding guide...[/bold]")

            generator = OnboardingGuideGenerator(analysis, use_ai=args.ai)
            guide = generator.generate()

            if args.output:
                Path(args.output).write_text(guide)
                if console:
                    console.print(f"\n[bold green]✅ Guide written to {args.output}[/bold green]")
                    console.print(f"[dim]{analysis.total_files} files analyzed, {analysis.total_lines:,} lines of code[/dim]")
            else:
                print(guide)

    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if console:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
