"""Data models for codebase analysis."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileInfo:
    """Information about a single file in the repository."""
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
    decorators: list = field(default_factory=list)
    summary: str = ""


@dataclass
class TestCoverage:
    """Test coverage analysis results."""
    test_files: list = field(default_factory=list)
    test_count: int = 0
    test_frameworks: list = field(default_factory=list)
    coverage_estimate: str = ""  # "high", "medium", "low", "none"
    test_dirs: list = field(default_factory=list)
    has_coverage_config: bool = False
    source_to_test_ratio: float = 0.0


@dataclass
class CICDInfo:
    """CI/CD configuration details."""
    provider: str = ""
    config_files: list = field(default_factory=list)
    pipelines: list = field(default_factory=list)
    has_deploy: bool = False
    has_test: bool = False
    has_lint: bool = False
    has_build: bool = False
    environments: list = field(default_factory=list)


@dataclass
class DockerInfo:
    """Docker configuration details."""
    has_dockerfile: bool = False
    has_compose: bool = False
    services: list = field(default_factory=list)
    base_images: list = field(default_factory=list)
    exposed_ports: list = field(default_factory=list)
    volumes: list = field(default_factory=list)
    compose_services: dict = field(default_factory=dict)


@dataclass
class APIEndpoint:
    """A detected API endpoint."""
    method: str  # GET, POST, PUT, DELETE, etc.
    path: str
    file: str
    line: int = 0
    handler: str = ""
    framework: str = ""


@dataclass
class DatabaseInfo:
    """Database usage information."""
    databases: list = field(default_factory=list)  # ["PostgreSQL", "Redis", ...]
    orms: list = field(default_factory=list)  # ["SQLAlchemy", "Prisma", ...]
    has_migrations: bool = False
    migration_tool: str = ""
    models: list = field(default_factory=list)  # model/entity names
    connection_files: list = field(default_factory=list)


@dataclass
class AuthInfo:
    """Authentication pattern information."""
    patterns: list = field(default_factory=list)  # ["JWT", "OAuth2", "Session"]
    auth_files: list = field(default_factory=list)
    providers: list = field(default_factory=list)  # ["Google", "GitHub", ...]
    has_rbac: bool = False
    has_middleware: bool = False


@dataclass
class ComplexityScore:
    """Codebase complexity assessment."""
    overall: int = 0  # 1-100
    size_score: int = 0
    language_diversity: int = 0
    dependency_count: int = 0
    architecture_complexity: int = 0
    label: str = ""  # "Simple", "Moderate", "Complex", "Very Complex"
    factors: list = field(default_factory=list)


@dataclass
class HotFile:
    """A frequently modified or imported file."""
    path: str
    import_count: int = 0
    change_count: int = 0
    reason: str = ""  # "most imported", "most changed"


@dataclass
class FirstPRGuide:
    """Guide for making a first pull request."""
    suggested_areas: list = field(default_factory=list)
    good_first_files: list = field(default_factory=list)
    conventions: list = field(default_factory=list)
    branch_pattern: str = ""
    pr_template: str = ""


@dataclass
class RepoAnalysis:
    """Complete analysis of a repository."""
    name: str
    path: str
    url: str = ""
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
    # New v2 fields
    test_coverage: TestCoverage = field(default_factory=TestCoverage)
    cicd_info: CICDInfo = field(default_factory=CICDInfo)
    docker_info: DockerInfo = field(default_factory=DockerInfo)
    api_endpoints: list = field(default_factory=list)
    database_info: DatabaseInfo = field(default_factory=DatabaseInfo)
    auth_info: AuthInfo = field(default_factory=AuthInfo)
    complexity: ComplexityScore = field(default_factory=ComplexityScore)
    hot_files: list = field(default_factory=list)
    first_pr: FirstPRGuide = field(default_factory=FirstPRGuide)
    key_concepts: list = field(default_factory=list)
    dependency_graph: str = ""  # Mermaid diagram
    ai_insights: str = ""
