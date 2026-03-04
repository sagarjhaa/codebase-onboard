"""Detect test coverage and testing patterns."""

import re
from pathlib import Path
from collections import Counter
from ..models import TestCoverage
from ..constants import MAX_FILE_READ_BYTES


def detect_test_coverage(repo_path: Path, files: list) -> TestCoverage:
    """Analyze test coverage and testing patterns."""
    tc = TestCoverage()

    # Find test files
    test_patterns = [
        r'test[_/]', r'_test\.', r'\.test\.', r'\.spec\.', r'__tests__',
        r'tests[/\\]', r'spec[/\\]', r'_spec\.'
    ]

    source_files = []
    for f in files:
        if not f.language:
            continue
        is_test = any(re.search(p, f.relative_path.lower()) for p in test_patterns)
        if is_test:
            tc.test_files.append(f.relative_path)
        else:
            source_files.append(f)

    tc.test_count = len(tc.test_files)

    # Detect test frameworks
    frameworks = set()
    file_basenames = {Path(f.relative_path).name for f in files}
    file_content_cache = {}

    # Config-based detection
    framework_configs = {
        "jest.config.js": "Jest", "jest.config.ts": "Jest", "jest.config.mjs": "Jest",
        "vitest.config.ts": "Vitest", "vitest.config.js": "Vitest",
        "pytest.ini": "pytest", "conftest.py": "pytest",
        ".nycrc": "NYC/Istanbul", ".nycrc.json": "NYC/Istanbul",
        "karma.conf.js": "Karma", "cypress.config.ts": "Cypress",
        "cypress.config.js": "Cypress", "playwright.config.ts": "Playwright",
        ".mocharc.yml": "Mocha", ".mocharc.json": "Mocha",
    }
    for config, fw in framework_configs.items():
        if config in file_basenames:
            frameworks.add(fw)

    # Check pyproject.toml for pytest
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
            if "[tool.pytest" in content:
                frameworks.add("pytest")
            if "coverage" in content.lower():
                tc.has_coverage_config = True
        except Exception:
            pass

    # Check package.json for test frameworks
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text(errors="replace"))
            all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "jest" in all_deps:
                frameworks.add("Jest")
            if "vitest" in all_deps:
                frameworks.add("Vitest")
            if "mocha" in all_deps:
                frameworks.add("Mocha")
            if "cypress" in all_deps:
                frameworks.add("Cypress")
            if "playwright" in all_deps or "@playwright/test" in all_deps:
                frameworks.add("Playwright")
            if "nyc" in all_deps or "c8" in all_deps or "istanbul" in all_deps:
                tc.has_coverage_config = True
        except Exception:
            pass

    # Import-based detection in test files
    for tf in tc.test_files[:20]:  # Sample first 20
        fpath = repo_path / tf
        if not fpath.exists():
            continue
        try:
            content = fpath.read_text(errors="replace")[:5000]
            file_content_cache[tf] = content
            if "import pytest" in content or "from pytest" in content:
                frameworks.add("pytest")
            if "import unittest" in content:
                frameworks.add("unittest")
            if "from django.test" in content:
                frameworks.add("Django TestCase")
            if "describe(" in content and ("it(" in content or "test(" in content):
                if "vitest" in content.lower():
                    frameworks.add("Vitest")
                elif "jest" not in str(frameworks).lower():
                    frameworks.add("Jest/Mocha")
            if "testing.T" in content:
                frameworks.add("Go testing")
            if "#[test]" in content or "#[cfg(test)]" in content:
                frameworks.add("Rust testing")
            if "RSpec" in content or "describe" in content and ".rb" in tf:
                frameworks.add("RSpec")
        except Exception:
            pass

    tc.test_frameworks = sorted(frameworks)

    # Estimate coverage
    if source_files:
        tc.source_to_test_ratio = len(tc.test_files) / len(source_files) if source_files else 0

    if tc.test_count == 0:
        tc.coverage_estimate = "none"
    elif tc.source_to_test_ratio >= 0.5:
        tc.coverage_estimate = "high"
    elif tc.source_to_test_ratio >= 0.2:
        tc.coverage_estimate = "medium"
    else:
        tc.coverage_estimate = "low"

    # Find test directories
    test_dirs = Counter()
    for tf in tc.test_files:
        parts = Path(tf).parts
        if len(parts) > 1:
            test_dirs[parts[0]] += 1
        else:
            test_dirs["(root)"] += 1
    tc.test_dirs = [(d, c) for d, c in test_dirs.most_common(10)]

    return tc
