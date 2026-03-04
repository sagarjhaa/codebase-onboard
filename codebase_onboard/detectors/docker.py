"""Detect Docker configuration and services."""

import re
from pathlib import Path
from ..models import DockerInfo
from ..constants import MAX_FILE_READ_BYTES


def detect_docker(repo_path: Path, files: list) -> DockerInfo:
    """Analyze Docker configuration."""
    info = DockerInfo()
    file_basenames = {Path(f.relative_path).name for f in files}
    file_paths = {f.relative_path for f in files}

    # Dockerfile analysis
    dockerfile_paths = [f.relative_path for f in files if Path(f.relative_path).name.startswith("Dockerfile")]
    if dockerfile_paths:
        info.has_dockerfile = True
        for df_path in dockerfile_paths:
            _parse_dockerfile(repo_path / df_path, info)

    # Docker Compose analysis
    compose_files = [f for f in files if "docker-compose" in f.relative_path or f.relative_path == "compose.yml" or f.relative_path == "compose.yaml"]
    if compose_files:
        info.has_compose = True
        for cf in compose_files:
            _parse_compose(repo_path / cf.relative_path, info)

    return info


def _parse_dockerfile(path: Path, info: DockerInfo):
    """Parse a Dockerfile for base images, exposed ports, etc."""
    try:
        content = path.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
    except Exception:
        return

    # Base images
    for m in re.finditer(r'^FROM\s+(\S+)', content, re.MULTILINE):
        image = m.group(1)
        if image not in info.base_images:
            info.base_images.append(image)

    # Exposed ports
    for m in re.finditer(r'^EXPOSE\s+(\d+)', content, re.MULTILINE):
        port = m.group(1)
        if port not in info.exposed_ports:
            info.exposed_ports.append(port)


def _parse_compose(path: Path, info: DockerInfo):
    """Parse docker-compose.yml for services."""
    try:
        content = path.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
    except Exception:
        return

    # Extract services (YAML parsing without pyyaml)
    in_services = False
    current_service = None
    indent_level = 0

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Detect services block
        if line.startswith("services:"):
            in_services = True
            continue

        if in_services:
            # Top-level key (not under services anymore)
            if not line.startswith(" ") and not line.startswith("\t") and ":" in line:
                in_services = False
                current_service = None
                continue

            # Service name (2-space indent)
            indent = len(line) - len(line.lstrip())
            if indent == 2 and ":" in stripped:
                service_name = stripped.split(":")[0].strip()
                current_service = service_name
                if service_name not in info.services:
                    info.services.append(service_name)
                info.compose_services[service_name] = {}
                continue

            if current_service and indent >= 4:
                # Service properties
                if stripped.startswith("image:"):
                    image = stripped.split(":", 1)[1].strip()
                    info.compose_services[current_service]["image"] = image
                elif stripped.startswith("ports:"):
                    info.compose_services[current_service]["ports"] = []
                elif stripped.startswith("- ") and "ports" in info.compose_services.get(current_service, {}):
                    port = stripped[2:].strip().strip('"').strip("'")
                    if ":" in port:
                        info.compose_services[current_service].setdefault("ports", []).append(port)
                elif stripped.startswith("volumes:"):
                    pass
                elif stripped.startswith("environment:"):
                    pass

    # Extract volumes from the compose file
    for m in re.finditer(r'^\s+-\s+([^:]+):([^\s]+)', content, re.MULTILINE):
        vol = f"{m.group(1).strip()} → {m.group(2).strip()}"
        if vol not in info.volumes and not vol.startswith("-"):
            info.volumes.append(vol)
