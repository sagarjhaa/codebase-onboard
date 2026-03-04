"""Detect CI/CD configuration and pipeline details."""

import re
from pathlib import Path
from ..models import CICDInfo
from ..constants import MAX_FILE_READ_BYTES

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def detect_cicd(repo_path: Path, files: list) -> CICDInfo:
    """Analyze CI/CD configuration."""
    info = CICDInfo()
    file_basenames = {Path(f.relative_path).name for f in files}

    # GitHub Actions
    gh_workflows = repo_path / ".github" / "workflows"
    if gh_workflows.exists() and gh_workflows.is_dir():
        info.provider = "GitHub Actions"
        for wf in sorted(gh_workflows.iterdir()):
            if wf.suffix in (".yml", ".yaml"):
                info.config_files.append(f".github/workflows/{wf.name}")
                _parse_github_workflow(wf, info)

    # GitLab CI
    gitlab_ci = repo_path / ".gitlab-ci.yml"
    if gitlab_ci.exists():
        info.provider = info.provider or "GitLab CI"
        info.config_files.append(".gitlab-ci.yml")
        _parse_yaml_pipeline(gitlab_ci, info)

    # CircleCI
    circleci = repo_path / ".circleci" / "config.yml"
    if circleci.exists():
        info.provider = info.provider or "CircleCI"
        info.config_files.append(".circleci/config.yml")
        _parse_yaml_pipeline(circleci, info)

    # Jenkins
    if "Jenkinsfile" in file_basenames:
        info.provider = info.provider or "Jenkins"
        info.config_files.append("Jenkinsfile")
        _parse_jenkinsfile(repo_path / "Jenkinsfile", info)

    # Travis CI
    if ".travis.yml" in file_basenames:
        info.provider = info.provider or "Travis CI"
        info.config_files.append(".travis.yml")
        _parse_yaml_pipeline(repo_path / ".travis.yml", info)

    # Azure Pipelines
    if "azure-pipelines.yml" in file_basenames:
        info.provider = info.provider or "Azure Pipelines"
        info.config_files.append("azure-pipelines.yml")

    # Buildkite
    buildkite = repo_path / ".buildkite" / "pipeline.yml"
    if buildkite.exists():
        info.provider = info.provider or "Buildkite"
        info.config_files.append(".buildkite/pipeline.yml")

    return info


def _parse_github_workflow(path: Path, info: CICDInfo):
    """Parse a GitHub Actions workflow file."""
    try:
        content = path.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
    except Exception:
        return

    name = path.stem
    pipeline_desc = f"**{name}**"

    # Extract trigger events
    triggers = []
    for m in re.finditer(r'on:\s*\n((?:\s+.+\n)*)', content):
        block = m.group(1)
        for event in re.findall(r'^\s+(\w+):', block, re.MULTILINE):
            triggers.append(event)
    if not triggers:
        for m in re.finditer(r'on:\s*\[([^\]]+)\]', content):
            triggers = [t.strip() for t in m.group(1).split(",")]

    if triggers:
        pipeline_desc += f" (triggers: {', '.join(triggers[:4])})"

    # Detect what it does
    content_lower = content.lower()
    if any(kw in content_lower for kw in ["npm test", "pytest", "cargo test", "go test", "jest", "vitest"]):
        info.has_test = True
    if any(kw in content_lower for kw in ["deploy", "publish", "release", "aws", "gcloud", "azure"]):
        info.has_deploy = True
    if any(kw in content_lower for kw in ["lint", "eslint", "flake8", "ruff", "clippy", "golangci"]):
        info.has_lint = True
    if any(kw in content_lower for kw in ["build", "compile", "cargo build", "go build", "npm run build"]):
        info.has_build = True

    # Extract job names
    jobs = re.findall(r'^\s{2}(\w[\w-]*):', content, re.MULTILINE)
    if jobs:
        # Filter out common non-job keys
        non_jobs = {"on", "name", "env", "permissions", "concurrency", "defaults"}
        jobs = [j for j in jobs if j not in non_jobs]
        if jobs:
            pipeline_desc += f" → jobs: {', '.join(jobs[:5])}"

    # Detect environments
    for m in re.finditer(r'environment:\s*(\w+)', content):
        env = m.group(1)
        if env not in info.environments:
            info.environments.append(env)

    info.pipelines.append(pipeline_desc)


def _parse_yaml_pipeline(path: Path, info: CICDInfo):
    """Parse a generic YAML CI/CD pipeline."""
    try:
        content = path.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
    except Exception:
        return

    content_lower = content.lower()
    if any(kw in content_lower for kw in ["test", "pytest", "jest", "spec"]):
        info.has_test = True
    if any(kw in content_lower for kw in ["deploy", "publish", "release"]):
        info.has_deploy = True
    if any(kw in content_lower for kw in ["lint", "eslint", "flake8", "ruff"]):
        info.has_lint = True
    if any(kw in content_lower for kw in ["build", "compile"]):
        info.has_build = True

    # Extract stage/job names
    stages = re.findall(r'^\s*-\s*(\w+)\s*$', content, re.MULTILINE)
    if stages:
        info.pipelines.append(f"Stages: {', '.join(stages[:8])}")


def _parse_jenkinsfile(path: Path, info: CICDInfo):
    """Parse a Jenkinsfile."""
    try:
        content = path.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
    except Exception:
        return

    content_lower = content.lower()
    if "test" in content_lower:
        info.has_test = True
    if "deploy" in content_lower:
        info.has_deploy = True

    stages = re.findall(r"stage\(['\"](.+?)['\"]\)", content)
    if stages:
        info.pipelines.append(f"Stages: {', '.join(stages[:8])}")
