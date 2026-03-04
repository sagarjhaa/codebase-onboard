"""Core codebase analysis engine."""

import os
import re
import json
import subprocess
from pathlib import Path
from collections import Counter, defaultdict

from .models import FileInfo, RepoAnalysis
from .constants import (
    LANGUAGE_EXTENSIONS, CONFIG_FILES, ENTRY_POINT_PATTERNS,
    IGNORE_DIRS, MAX_FILE_READ_BYTES, MAX_FILES_TO_ANALYZE,
)
from .detectors.test_coverage import detect_test_coverage
from .detectors.cicd import detect_cicd
from .detectors.docker import detect_docker
from .detectors.api_endpoints import detect_api_endpoints
from .detectors.database import detect_database
from .detectors.auth import detect_auth
from .detectors.env_vars import detect_env_vars
from .graph import (
    generate_dependency_graph, calculate_complexity,
    find_hot_files, generate_first_pr_guide, extract_key_concepts,
)

try:
    from pathspec import PathSpec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False


class CodebaseAnalyzer:
    """Analyzes a codebase and extracts structural information."""

    def __init__(self, repo_path: str, console=None, depth: str = "standard",
                 focus: str = None):
        self.repo_path = Path(repo_path)
        self.console = console
        self.depth = depth  # "shallow", "standard", "deep"
        self.focus = focus  # Optional subdirectory to focus on
        self.analysis = RepoAnalysis(
            name=self.repo_path.name,
            path=str(self.repo_path),
        )
        self._gitignore_spec = self._load_gitignore()

        # If focusing on a subdirectory
        if self.focus:
            focus_path = self.repo_path / self.focus
            if focus_path.is_dir():
                self._log(f"Focusing analysis on: {self.focus}/")

    def _load_gitignore(self):
        gitignore_path = self.repo_path / ".gitignore"
        if gitignore_path.exists() and HAS_PATHSPEC:
            try:
                with open(gitignore_path) as f:
                    return PathSpec.from_lines("gitwildmatch", f)
            except Exception:
                pass
        return None

    def _should_ignore(self, path: Path) -> bool:
        parts = path.relative_to(self.repo_path).parts
        for part in parts:
            if part in IGNORE_DIRS or (part.startswith(".") and part != ".github"):
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
        if self.console:
            self.console.print(f"  [dim]{msg}[/dim]")

    def _update_progress(self, progress, task, advance=1):
        if progress:
            progress.update(task, advance=advance)

    def analyze(self, progress=None, task=None) -> RepoAnalysis:
        """Run the full analysis pipeline."""
        steps = [
            ("Reading README & license", self._read_readme),
            ("Scanning file structure", self._scan_files),
            ("Detecting frameworks", self._detect_frameworks),
            ("Parsing configurations", self._parse_configs),
            ("Finding entry points", self._find_entry_points),
            ("Building directory tree", self._build_directory_tree),
            ("Detecting patterns", self._detect_patterns),
            ("Finding gotchas", self._find_gotchas),
        ]

        # Standard + deep analysis steps
        if self.depth != "shallow":
            steps.extend([
                ("Analyzing test coverage", self._analyze_test_coverage),
                ("Detecting CI/CD", self._analyze_cicd),
                ("Analyzing Docker setup", self._analyze_docker),
                ("Finding API endpoints", self._find_api_endpoints),
                ("Detecting databases", self._analyze_database),
                ("Analyzing auth patterns", self._analyze_auth),
                ("Extracting env variables", self._extract_env_vars),
                ("Analyzing architecture", self._analyze_architecture),
            ])

        # Deep analysis only
        if self.depth == "deep":
            steps.extend([
                ("Generating dependency graph", self._generate_dep_graph),
                ("Finding hot files", self._find_hot_files),
                ("Generating first PR guide", self._generate_first_pr),
                ("Extracting key concepts", self._extract_concepts),
            ])

        # Always calculate complexity
        steps.append(("Calculating complexity", self._calc_complexity))

        for desc, fn in steps:
            self._log(desc + "...")
            fn()
            self._update_progress(progress, task)

        return self.analysis

    def _read_readme(self):
        for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
            readme_path = self.repo_path / name
            if readme_path.exists():
                try:
                    self.analysis.readme_content = readme_path.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
                except Exception:
                    pass
                break

        for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]:
            license_path = self.repo_path / name
            if license_path.exists():
                try:
                    content = license_path.read_text(errors="replace")[:2000]
                    for lic_type in ["MIT", "Apache", "GPL", "BSD", "ISC", "MPL", "LGPL", "AGPL"]:
                        if lic_type in content:
                            self.analysis.license_type = lic_type if lic_type not in ("Apache",) else "Apache 2.0"
                            break
                    else:
                        self.analysis.license_type = "Custom"
                except Exception:
                    pass
                break

    def _scan_files(self):
        language_lines = Counter()
        file_count = 0
        scan_root = self.repo_path / self.focus if self.focus else self.repo_path

        for root, dirs, filenames in os.walk(scan_root):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not self._should_ignore(root_path / d)]

            for fname in filenames:
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

                if size > 5_000_000:
                    continue

                line_count = 0
                if lang or ext in (".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini"):
                    try:
                        with open(fpath, "r", errors="replace") as f:
                            line_count = sum(1 for _ in f)
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
        try:
            content = fpath.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
        except Exception:
            return

        for line in content.split("\n"):
            stripped = line.strip()

            # Imports
            if fi.language == "Python":
                if stripped.startswith("import ") or stripped.startswith("from "):
                    fi.imports.append(stripped)
                # Decorators
                if stripped.startswith("@"):
                    fi.decorators.append(stripped[:100])
            elif fi.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
                if stripped.startswith("import ") or "require(" in stripped:
                    fi.imports.append(stripped)
            elif fi.language == "Go":
                if stripped.startswith("import"):
                    fi.imports.append(stripped)
            elif fi.language == "Rust":
                if stripped.startswith("use "):
                    fi.imports.append(stripped)
            elif fi.language == "Ruby":
                if stripped.startswith("require") or stripped.startswith("gem"):
                    fi.imports.append(stripped)

            # Classes
            if fi.language == "Python":
                m = re.match(r"^class\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))
            elif fi.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
                m = re.match(r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))
                # TypeScript interfaces and types
                m = re.match(r"^(?:export\s+)?(?:interface|type)\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))
            elif fi.language == "Rust":
                m = re.match(r"^(?:pub\s+)?struct\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))
                m = re.match(r"^(?:pub\s+)?enum\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))
                m = re.match(r"^(?:pub\s+)?trait\s+(\w+)", stripped)
                if m:
                    fi.classes.append(m.group(1))
            elif fi.language == "Go":
                m = re.match(r"^type\s+(\w+)\s+struct", stripped)
                if m:
                    fi.classes.append(m.group(1))

            # Functions
            if fi.language == "Python":
                m = re.match(r"^def\s+(\w+)", stripped)
                if m:
                    fi.functions.append(m.group(1))
            elif fi.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
                m = re.match(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", stripped)
                if m:
                    fi.functions.append(m.group(1))
                m = re.match(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?[\(\<]", stripped)
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

            # TODOs
            for marker in ("TODO", "FIXME", "HACK", "XXX", "BUG"):
                if marker in line.upper():
                    fi.todos.append(stripped[:150])
                    break

    def _detect_frameworks(self):
        file_names = {f.relative_path for f in self.analysis.files}
        file_basenames = {Path(f.relative_path).name for f in self.analysis.files}
        frameworks = []

        # JS/TS frameworks
        if any(n.startswith("next.config") for n in file_basenames):
            frameworks.append("Next.js")
        if any(n.startswith("nuxt.config") for n in file_basenames):
            frameworks.append("Nuxt.js")
        if any(f.relative_path.endswith(".svelte") for f in self.analysis.files):
            frameworks.append("Svelte")
        if any(f.relative_path.endswith(".vue") for f in self.analysis.files):
            frameworks.append("Vue.js")
        if any("from 'react'" in i or 'from "react"' in i for f in self.analysis.files for i in f.imports):
            frameworks.append("React")
        if any("@angular" in i for f in self.analysis.files for i in f.imports):
            frameworks.append("Angular")

        deps_str = str(self._get_all_deps())
        for pkg, name in [("express", "Express.js"), ("fastify", "Fastify"),
                          ("hono", "Hono"), ("koa", "Koa"), ("elysia", "Elysia")]:
            if pkg in deps_str:
                frameworks.append(name)

        # Python frameworks
        for f in self.analysis.files:
            for imp in f.imports:
                imp_lower = imp.lower()
                if "flask" in imp_lower and "Flask" not in frameworks:
                    frameworks.append("Flask")
                if "django" in imp_lower and "Django" not in frameworks:
                    frameworks.append("Django")
                if "fastapi" in imp_lower and "FastAPI" not in frameworks:
                    frameworks.append("FastAPI")
        if "manage.py" in file_basenames and "Django" not in frameworks:
            frameworks.append("Django")

        # Go frameworks
        for f in self.analysis.files:
            for imp in f.imports:
                if "gin-gonic" in imp and "Gin" not in frameworks:
                    frameworks.append("Gin (Go)")
                if "gorilla/mux" in imp:
                    frameworks.append("Gorilla Mux (Go)")
                if "go-chi/chi" in imp:
                    frameworks.append("Chi (Go)")
                if "labstack/echo" in imp:
                    frameworks.append("Echo (Go)")

        # Rust frameworks
        for f in self.analysis.files:
            for imp in f.imports:
                if "actix" in imp:
                    frameworks.append("Actix (Rust)")
                if "axum" in imp:
                    frameworks.append("Axum (Rust)")
                if "rocket" in imp:
                    frameworks.append("Rocket (Rust)")

        # Infrastructure
        if "Dockerfile" in file_basenames:
            self.analysis.docker = True
            frameworks.append("Docker")
        if any("docker-compose" in f or f in ("compose.yml", "compose.yaml") for f in file_basenames):
            frameworks.append("Docker Compose")
        if any(f.endswith(".tf") for f in file_names):
            frameworks.append("Terraform")
        if "fly.toml" in file_basenames:
            frameworks.append("Fly.io")

        # Testing
        if "jest.config.js" in file_basenames or "jest.config.ts" in file_basenames:
            self.analysis.test_framework = "Jest"
        if "vitest.config.ts" in file_basenames or "vitest.config.js" in file_basenames:
            self.analysis.test_framework = "Vitest"
        if "pytest.ini" in file_basenames or "conftest.py" in file_basenames:
            self.analysis.test_framework = "pytest"

        # CI/CD (basic detection for the overview)
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
        pm_map = [
            ("package-lock.json", "npm"), ("yarn.lock", "yarn"), ("pnpm-lock.yaml", "pnpm"),
            ("bun.lockb", "bun"), ("poetry.lock", "poetry"), ("Pipfile.lock", "pipenv"),
            ("requirements.txt", "pip"), ("go.mod", "go modules"), ("Cargo.lock", "cargo"),
            ("Gemfile.lock", "bundler"),
        ]
        for fname, pm in pm_map:
            if fname in file_basenames:
                self.analysis.package_manager = pm
                break

        # Monorepo
        if any(f in file_basenames for f in ["lerna.json", "pnpm-workspace.yaml", "nx.json", "turbo.json"]):
            self.analysis.monorepo = True
        if (self.repo_path / "packages").is_dir():
            self.analysis.monorepo = True

        self.analysis.frameworks = list(dict.fromkeys(frameworks))

    def _get_all_deps(self) -> dict:
        return {**self.analysis.dependencies, **self.analysis.dev_dependencies}

    def _parse_configs(self):
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
                if "name" in data and data["name"] != self.analysis.name:
                    self.analysis.architecture_hints.append(f"npm package name: `{data['name']}`")
            except Exception:
                pass

        # pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(errors="replace")
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
                # Extract inline deps from dependencies = [...]
                m = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if m:
                    for dep in re.findall(r'"([^"]+)"', m.group(1)):
                        name = re.split(r'[>=<!\[]', dep)[0].strip()
                        if name:
                            self.analysis.dependencies[name] = dep
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
                    if line and not line.startswith("//") and not line.startswith("module") and not line.startswith("go ") and line not in ("require (", ")"):
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
                in_dev_deps = False
                for line in content.split("\n"):
                    if "[dependencies]" in line and "dev" not in line:
                        in_deps = True
                        in_dev_deps = False
                        continue
                    if "[dev-dependencies]" in line:
                        in_dev_deps = True
                        in_deps = False
                        continue
                    if line.startswith("[") and line != "[dependencies]":
                        in_deps = False
                        in_dev_deps = False
                    if "=" in line:
                        parts = line.split("=", 1)
                        name = parts[0].strip()
                        val = parts[1].strip().strip('"')
                        if in_deps and name:
                            self.analysis.dependencies[name] = val
                        elif in_dev_deps and name:
                            self.analysis.dev_dependencies[name] = val
            except Exception:
                pass

    def _find_entry_points(self):
        file_paths = {f.relative_path: f for f in self.analysis.files}
        for pattern in ENTRY_POINT_PATTERNS:
            if pattern in file_paths:
                file_paths[pattern].is_entry_point = True
                self.analysis.entry_points.append(file_paths[pattern])

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
                annotation = ""
                rel = str(entry.relative_to(self.repo_path))
                if entry.name in CONFIG_FILES:
                    annotation = f"  ← {CONFIG_FILES[entry.name]}"
                elif rel in CONFIG_FILES:
                    annotation = f"  ← {CONFIG_FILES[rel]}"

                lines.append(f"{prefix}{connector}{entry.name}{indicator}{annotation}")

                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(entry, prefix + extension, depth + 1)

        _walk(self.repo_path, "", 1)
        self.analysis.directory_structure = "\n".join(lines[:200])
        if len(lines) > 200:
            self.analysis.directory_structure += f"\n... ({len(lines) - 200} more entries)"

    def _detect_patterns(self):
        patterns = []
        dir_names = set()
        for f in self.analysis.files:
            parts = Path(f.relative_path).parts
            for p in parts[:-1]:
                dir_names.add(p.lower())

        pattern_rules = [
            ({"models", "views", "controllers"}, "**MVC Architecture**: Models, Views, and Controllers pattern detected."),
            ({"models", "views", "templates"}, "**MVT Architecture**: Models, Views, and Templates (Django-style) pattern detected."),
            ({"components",}, "**Component-Based Architecture**: Dedicated `components/` directory for reusable UI components."),
            ({"services",}, "**Service Layer**: Dedicated `services/` directory for business logic separation."),
            ({"domain", "infrastructure"}, "**Clean/Hexagonal Architecture**: Domain-driven design with separated layers."),
            ({"routes",}, "**Route-Based Structure**: Dedicated `routes/` directory for endpoint definitions."),
            ({"middleware",}, "**Middleware Pattern**: Middleware directory for request/response processing."),
            ({"hooks",}, "**Custom Hooks**: React custom hooks directory for shared stateful logic."),
            ({"store",}, "**Centralized State Management**: Store directory for global state management."),
            ({"utils", "helpers"}, "**Utility Layer**: Shared utility/helper functions directory."),
            ({"lib",}, "**Library Code**: Shared library code in `lib/` directory."),
            ({"pages",}, "**File-Based Routing**: Pages directory suggests file-based routing (Next.js/Nuxt)."),
        ]

        for required_dirs, desc in pattern_rules:
            if required_dirs & dir_names:
                patterns.append(desc)

        # Test patterns
        test_files = [f for f in self.analysis.files if "test" in f.relative_path.lower() or "spec" in f.relative_path.lower()]
        if test_files:
            colocated = any("__tests__" in f.relative_path or ".test." in f.relative_path or ".spec." in f.relative_path for f in test_files)
            separated = any(f.relative_path.startswith(("test/", "tests/", "test\\", "tests\\")) for f in test_files)
            if colocated:
                patterns.append("**Colocated Tests**: Test files alongside source (`.test.` / `__tests__/` pattern).")
            if separated:
                patterns.append("**Separated Tests**: Dedicated `test/` or `tests/` directory.")

        # TypeScript config
        tsconfig = self.repo_path / "tsconfig.json"
        if tsconfig.exists():
            try:
                data = json.loads(tsconfig.read_text(errors="replace"))
                strict = data.get("compilerOptions", {}).get("strict", False)
                if strict:
                    patterns.append("**TypeScript Strict Mode**: Enabled for strong type safety.")
            except Exception:
                pass

        self.analysis.patterns = patterns

    def _find_gotchas(self):
        gotchas = []
        all_todos = [(f.relative_path, todo) for f in self.analysis.files for todo in f.todos]
        if all_todos:
            gotchas.append(f"**{len(all_todos)} TODO/FIXME/HACK comments** found — review for known issues and tech debt.")

        large_files = sorted(
            [f for f in self.analysis.files if f.line_count > 500 and f.language],
            key=lambda f: f.line_count, reverse=True
        )[:5]
        if large_files:
            file_list = ", ".join(f"`{f.relative_path}` ({f.line_count} lines)" for f in large_files)
            gotchas.append(f"**Large source files**: {file_list}")

        test_files = [f for f in self.analysis.files if "test" in f.relative_path.lower() or "spec" in f.relative_path.lower()]
        if not test_files:
            gotchas.append("**No test files detected.** This codebase may lack automated testing.")

        if not self.analysis.ci_cd:
            gotchas.append("**No CI/CD configuration found.** Builds and deployments may be manual.")

        if not self.analysis.license_type:
            gotchas.append("**No LICENSE file found.**")

        if len(self.analysis.languages) > 3:
            langs = ", ".join(list(self.analysis.languages.keys())[:5])
            gotchas.append(f"**Multi-language codebase** ({langs}) — expect different tooling across components.")

        self.analysis.gotchas = gotchas

    # -- V2 analysis methods --

    def _analyze_test_coverage(self):
        self.analysis.test_coverage = detect_test_coverage(self.repo_path, self.analysis.files)

    def _analyze_cicd(self):
        self.analysis.cicd_info = detect_cicd(self.repo_path, self.analysis.files)

    def _analyze_docker(self):
        self.analysis.docker_info = detect_docker(self.repo_path, self.analysis.files)

    def _find_api_endpoints(self):
        self.analysis.api_endpoints = detect_api_endpoints(self.repo_path, self.analysis.files)

    def _analyze_database(self):
        all_deps = {**self.analysis.dependencies, **self.analysis.dev_dependencies}
        self.analysis.database_info = detect_database(self.repo_path, self.analysis.files, all_deps)

    def _analyze_auth(self):
        all_deps = {**self.analysis.dependencies, **self.analysis.dev_dependencies}
        self.analysis.auth_info = detect_auth(self.repo_path, self.analysis.files, all_deps)

    def _extract_env_vars(self):
        env_result = detect_env_vars(self.repo_path, self.analysis.files)
        # Store as list of (name, files) tuples
        self.analysis.env_vars = env_result

    def _analyze_architecture(self):
        hints = list(self.analysis.architecture_hints)

        dir_counts = Counter()
        for f in self.analysis.files:
            parts = Path(f.relative_path).parts
            if len(parts) > 1:
                dir_counts[parts[0]] += 1

        top_dirs = dir_counts.most_common(10)
        if top_dirs:
            hints.append("**Top-level directories:** " +
                         ", ".join(f"`{d}/` ({c} files)" for d, c in top_dirs))

        api_files = [f for f in self.analysis.files if any(x in f.relative_path.lower() for x in ("route", "endpoint", "api", "controller", "handler", "resolver"))]
        if api_files:
            hints.append(f"**API layer:** {len(api_files)} files related to API routing/handlers.")

        db_indicators = [f for f in self.analysis.files if any(x in f.relative_path.lower() for x in ("model", "schema", "migration", "entity", "repository"))]
        if db_indicators:
            hints.append(f"**Data layer:** {len(db_indicators)} files related to data models/schemas.")

        if self.analysis.monorepo:
            for pkg_dir in ["packages", "apps", "libs", "modules"]:
                pkgs_path = self.repo_path / pkg_dir
                if pkgs_path.is_dir():
                    pkgs = [p.name for p in pkgs_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
                    if pkgs:
                        hints.append(f"**Monorepo {pkg_dir}:** {', '.join(pkgs[:10])}")

        self.analysis.architecture_hints = hints

    def _generate_dep_graph(self):
        self.analysis.dependency_graph = generate_dependency_graph(
            self.analysis.files, self.analysis
        )

    def _find_hot_files(self):
        self.analysis.hot_files = find_hot_files(self.repo_path, self.analysis.files)

    def _generate_first_pr(self):
        self.analysis.first_pr = generate_first_pr_guide(
            self.repo_path, self.analysis.files, self.analysis
        )

    def _extract_concepts(self):
        self.analysis.key_concepts = extract_key_concepts(
            self.analysis.files, self.repo_path
        )

    def _calc_complexity(self):
        self.analysis.complexity = calculate_complexity(self.analysis)
