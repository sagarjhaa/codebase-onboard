"""Generate dependency and architecture graphs."""

import re
from pathlib import Path
from collections import defaultdict, Counter
from .models import HotFile, ComplexityScore, FirstPRGuide


def generate_dependency_graph(files: list, analysis) -> str:
    """Generate a Mermaid dependency graph from import analysis."""
    # Build import graph
    imports_graph = defaultdict(set)
    file_map = {}

    for f in files:
        if not f.language or not f.imports:
            continue

        # Normalize file path to module name
        module = _path_to_module(f.relative_path)
        file_map[module] = f.relative_path

        for imp in f.imports:
            target = _extract_import_target(imp, f.language)
            if target and target != module:
                # Only include internal imports
                imports_graph[module].add(target)

    if not imports_graph:
        return ""

    # Filter to only internal modules (those that exist in the repo)
    known_modules = set(file_map.keys())
    internal_graph = {}
    for source, targets in imports_graph.items():
        internal_targets = set()
        for t in targets:
            # Check if any known module starts with or matches this import
            for km in known_modules:
                if km == t or km.startswith(t + "/") or km.startswith(t + "."):
                    internal_targets.add(km)
                    break
        if internal_targets:
            internal_graph[source] = internal_targets

    if not internal_graph:
        return ""

    # Limit to most-connected nodes for readability
    all_nodes = set()
    for s, targets in internal_graph.items():
        all_nodes.add(s)
        all_nodes.update(targets)

    if len(all_nodes) > 30:
        # Keep top 30 most connected nodes
        node_connections = Counter()
        for s, targets in internal_graph.items():
            node_connections[s] += len(targets)
            for t in targets:
                node_connections[t] += 1
        top_nodes = {n for n, _ in node_connections.most_common(30)}

        filtered_graph = {}
        for s, targets in internal_graph.items():
            if s in top_nodes:
                filtered_targets = targets & top_nodes
                if filtered_targets:
                    filtered_graph[s] = filtered_targets
        internal_graph = filtered_graph

    # Generate Mermaid diagram
    lines = ["```mermaid", "graph TD"]

    # Sanitize node names for mermaid
    node_ids = {}
    counter = 0
    for s, targets in internal_graph.items():
        if s not in node_ids:
            node_ids[s] = f"N{counter}"
            counter += 1
        for t in targets:
            if t not in node_ids:
                node_ids[t] = f"N{counter}"
                counter += 1

    # Add node labels
    for name, nid in node_ids.items():
        short_name = name.split("/")[-1] if "/" in name else name
        lines.append(f"    {nid}[{short_name}]")

    # Add edges
    for source, targets in internal_graph.items():
        for target in sorted(targets):
            lines.append(f"    {node_ids[source]} --> {node_ids[target]}")

    lines.append("```")
    return "\n".join(lines)


def calculate_complexity(analysis) -> ComplexityScore:
    """Calculate a complexity score for the codebase."""
    score = ComplexityScore()
    factors = []

    # Size score (0-25)
    total_lines = analysis.total_lines
    if total_lines < 1000:
        score.size_score = 5
    elif total_lines < 5000:
        score.size_score = 10
    elif total_lines < 20000:
        score.size_score = 15
    elif total_lines < 100000:
        score.size_score = 20
    else:
        score.size_score = 25
        factors.append(f"Large codebase ({total_lines:,} lines)")

    # Language diversity (0-20)
    num_langs = len(analysis.languages)
    score.language_diversity = min(num_langs * 4, 20)
    if num_langs > 3:
        factors.append(f"Multi-language ({num_langs} languages)")

    # Dependencies (0-25)
    num_deps = len(analysis.dependencies) + len(analysis.dev_dependencies)
    if num_deps < 10:
        score.dependency_count = 5
    elif num_deps < 30:
        score.dependency_count = 10
    elif num_deps < 100:
        score.dependency_count = 15
    elif num_deps < 300:
        score.dependency_count = 20
    else:
        score.dependency_count = 25
        factors.append(f"Heavy dependencies ({num_deps} packages)")

    # Architecture complexity (0-30)
    arch_score = 0
    if analysis.monorepo:
        arch_score += 10
        factors.append("Monorepo architecture")
    if analysis.docker:
        arch_score += 5
    if analysis.api_endpoints and len(analysis.api_endpoints) > 20:
        arch_score += 5
        factors.append(f"Large API surface ({len(analysis.api_endpoints)} endpoints)")
    if analysis.database_info.databases and len(analysis.database_info.databases) > 1:
        arch_score += 5
        factors.append(f"Multiple databases ({', '.join(analysis.database_info.databases)})")
    if len(analysis.frameworks) > 3:
        arch_score += 5
        factors.append(f"Multiple frameworks ({len(analysis.frameworks)})")
    score.architecture_complexity = min(arch_score, 30)

    # Overall
    score.overall = score.size_score + score.language_diversity + score.dependency_count + score.architecture_complexity

    if score.overall <= 20:
        score.label = "Simple"
    elif score.overall <= 40:
        score.label = "Moderate"
    elif score.overall <= 65:
        score.label = "Complex"
    else:
        score.label = "Very Complex"

    if not factors:
        if score.label == "Simple":
            factors.append("Small, focused codebase")
        else:
            factors.append("Standard complexity for this type of project")

    score.factors = factors
    return score


def find_hot_files(repo_path: Path, files: list) -> list:
    """Find the most imported and most changed files."""
    hot_files = []

    # Most imported files
    import_count = Counter()
    for f in files:
        if not f.language:
            continue
        for imp in f.imports:
            # Normalize import to potential file path
            target = _extract_import_target(imp, f.language)
            if target:
                import_count[target] += 1

    # Map import targets back to actual files
    file_modules = {}
    for f in files:
        if f.language:
            module = _path_to_module(f.relative_path)
            file_modules[module] = f.relative_path

    # Find files that are imported most
    for target, count in import_count.most_common(20):
        for module, fpath in file_modules.items():
            if module == target or module.endswith("/" + target) or target in module:
                hot_files.append(HotFile(
                    path=fpath, import_count=count,
                    reason=f"imported by {count} files"
                ))
                break

    # Most changed files (via git log)
    try:
        import subprocess
        result = subprocess.run(
            ["git", "log", "--format=format:", "--name-only", "-n", "200"],
            capture_output=True, text=True, cwd=str(repo_path), timeout=10
        )
        if result.returncode == 0:
            change_count = Counter()
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line:
                    change_count[line] += 1

            for fpath, count in change_count.most_common(10):
                # Check if already in hot_files
                existing = next((h for h in hot_files if h.path == fpath), None)
                if existing:
                    existing.change_count = count
                    existing.reason += f", changed {count} times in recent history"
                else:
                    hot_files.append(HotFile(
                        path=fpath, change_count=count,
                        reason=f"changed {count} times in recent history"
                    ))
    except Exception:
        pass

    # Sort by combined score
    hot_files.sort(key=lambda h: (h.import_count + h.change_count), reverse=True)
    return hot_files[:15]


def generate_first_pr_guide(repo_path: Path, files: list, analysis) -> FirstPRGuide:
    """Generate guidance for a developer's first PR."""
    guide = FirstPRGuide()

    # Suggested areas for first contribution
    areas = []

    # Tests are always a good first PR
    test_files = [f for f in files if "test" in f.relative_path.lower() or "spec" in f.relative_path.lower()]
    if test_files:
        areas.append("📝 **Add or improve tests** — Great way to learn the codebase while adding value")
    else:
        areas.append("🧪 **Add the first tests** — This codebase lacks tests, which is a high-impact first contribution")

    # Documentation
    areas.append("📖 **Improve documentation** — Fix typos, add examples, clarify confusing sections")

    # TODOs/FIXMEs
    todo_count = sum(len(f.todos) for f in files)
    if todo_count > 0:
        areas.append(f"🔧 **Address TODO/FIXME comments** — There are {todo_count} across the codebase")

    # Type safety
    has_ts = any(f.language and "TypeScript" in f.language for f in files)
    has_js = any(f.language == "JavaScript" for f in files)
    if has_js and not has_ts:
        areas.append("🏷️ **Add TypeScript types** — If the project accepts TS, adding types to JS files is a safe improvement")

    # Linting/formatting
    if not any(f.relative_path in (".eslintrc.json", ".eslintrc.js", ".prettierrc",
                                    "pyproject.toml", "ruff.toml", ".flake8")
               for f in files):
        areas.append("🧹 **Add linting/formatting config** — Improves code consistency")

    guide.suggested_areas = areas

    # Find good first files (small, well-contained)
    source_files = [f for f in files if f.language and 50 < f.line_count < 200]
    source_files.sort(key=lambda f: f.line_count)
    guide.good_first_files = [f.relative_path for f in source_files[:10]]

    # Detect conventions
    conventions = []

    # Check for PR template
    pr_template = repo_path / ".github" / "pull_request_template.md"
    if pr_template.exists():
        guide.pr_template = ".github/pull_request_template.md"
        conventions.append("📋 PR template exists — follow the format")

    # Check for CONTRIBUTING.md
    contributing = repo_path / "CONTRIBUTING.md"
    if contributing.exists():
        conventions.append("📖 Read CONTRIBUTING.md before submitting")

    # Check for pre-commit hooks
    if (repo_path / ".pre-commit-config.yaml").exists():
        conventions.append("🪝 Pre-commit hooks are configured — install with `pre-commit install`")

    # Check for lint-staged
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text(errors="replace"))
            if "lint-staged" in data or "lint-staged" in data.get("devDependencies", {}):
                conventions.append("🧹 lint-staged runs on commit — your code will be auto-formatted")
            if "husky" in data.get("devDependencies", {}):
                conventions.append("🐕 Husky git hooks are set up — commits may trigger checks")
        except Exception:
            pass

    # Branch naming
    try:
        import subprocess
        result = subprocess.run(
            ["git", "branch", "-r", "--format=%(refname:short)"],
            capture_output=True, text=True, cwd=str(repo_path), timeout=5
        )
        if result.returncode == 0:
            branches = result.stdout.strip().split("\n")
            # Detect common patterns
            patterns = Counter()
            for b in branches:
                b = b.replace("origin/", "")
                if "/" in b:
                    prefix = b.split("/")[0]
                    patterns[prefix] += 1
            if patterns:
                common = patterns.most_common(3)
                prefixes = [p for p, c in common if c > 1]
                if prefixes:
                    guide.branch_pattern = f"Common prefixes: {', '.join(f'`{p}/`' for p in prefixes)}"
    except Exception:
        pass

    if not guide.branch_pattern:
        conventions.append("🌿 No consistent branch naming pattern detected — ask your team")
    else:
        conventions.append(f"🌿 Branch naming: {guide.branch_pattern}")

    guide.conventions = conventions
    return guide


def extract_key_concepts(files: list, repo_path: Path) -> list:
    """Extract domain-specific terminology and key concepts."""
    # Collect class names, exported types, and constants
    terms = Counter()
    seen_files = {}

    for f in files:
        if not f.language:
            continue

        # Class names are usually key domain concepts
        for cls in f.classes:
            if len(cls) > 2 and not cls.startswith("_"):
                # Split CamelCase
                words = re.findall(r'[A-Z][a-z]+|[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)', cls)
                if words:
                    terms[cls] += 1
                    seen_files[cls] = f.relative_path

        # Exported functions/types
        for func in f.functions:
            if len(func) > 4 and not func.startswith("_") and func[0].isupper():
                terms[func] += 1
                seen_files[func] = f.relative_path

    # Get top concepts
    concepts = []
    for term, count in terms.most_common(20):
        if count >= 1:
            concepts.append({
                "term": term,
                "file": seen_files.get(term, ""),
                "frequency": count
            })

    return concepts


def _path_to_module(path: str) -> str:
    """Convert a file path to a module-like identifier."""
    module = path.replace("\\", "/")
    # Remove extension
    for ext in [".tsx", ".jsx", ".ts", ".js", ".py", ".go", ".rs", ".rb", ".java"]:
        if module.endswith(ext):
            module = module[:-len(ext)]
            break
    # Remove index suffix
    if module.endswith("/index"):
        module = module[:-6]
    return module


def _extract_import_target(imp: str, language: str) -> str:
    """Extract the target module from an import statement."""
    if language == "Python":
        m = re.match(r'from\s+(\S+)\s+import', imp)
        if m:
            return m.group(1).replace(".", "/")
        m = re.match(r'import\s+(\S+)', imp)
        if m:
            return m.group(1).replace(".", "/")

    elif language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
        m = re.search(r'from\s+["\']([^"\']+)["\']', imp)
        if m:
            target = m.group(1)
            # Only track relative imports
            if target.startswith("."):
                return target.lstrip("./")
            return ""
        m = re.search(r'require\(["\']([^"\']+)["\']\)', imp)
        if m:
            target = m.group(1)
            if target.startswith("."):
                return target.lstrip("./")
            return ""

    elif language == "Go":
        m = re.search(r'"([^"]+)"', imp)
        if m:
            return m.group(1)

    return ""
