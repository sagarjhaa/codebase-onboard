"""Detect authentication and authorization patterns."""

import re
from pathlib import Path
from ..models import AuthInfo
from ..constants import AUTH_PACKAGES, MAX_FILE_READ_BYTES


def detect_auth(repo_path: Path, files: list, dependencies: dict) -> AuthInfo:
    """Analyze authentication patterns."""
    info = AuthInfo()

    all_deps = set(k.lower() for k in dependencies.keys())

    # Check dependencies
    for pkg, desc in AUTH_PACKAGES.items():
        if pkg.lower() in all_deps:
            info.patterns.append(desc)

    # Check imports and source code
    for f in files:
        if not f.language:
            continue

        # Check file names for auth-related files
        path_lower = f.relative_path.lower()
        if any(kw in path_lower for kw in ["auth", "login", "session", "passport",
                                            "guard", "permission", "middleware/auth"]):
            info.auth_files.append(f.relative_path)

        # Check imports
        for imp in f.imports:
            imp_lower = imp.lower()
            for pkg, desc in AUTH_PACKAGES.items():
                if pkg.lower() in imp_lower and desc not in info.patterns:
                    info.patterns.append(desc)

    # Scan auth files for specific patterns
    for auth_file in info.auth_files[:10]:
        fpath = repo_path / auth_file
        try:
            content = fpath.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
        except Exception:
            continue

        content_lower = content.lower()

        # JWT detection
        if any(kw in content_lower for kw in ["jwt", "jsonwebtoken", "bearer"]):
            if "JWT Authentication" not in info.patterns:
                info.patterns.append("JWT Authentication")

        # OAuth detection
        if any(kw in content_lower for kw in ["oauth", "authorization_code", "client_credentials"]):
            if "OAuth2" not in info.patterns:
                info.patterns.append("OAuth2")

        # Session-based auth
        if any(kw in content_lower for kw in ["session", "cookie", "express-session"]):
            if "Session-based Auth" not in info.patterns:
                info.patterns.append("Session-based Auth")

        # API key auth
        if any(kw in content_lower for kw in ["api_key", "apikey", "x-api-key"]):
            if "API Key Auth" not in info.patterns:
                info.patterns.append("API Key Auth")

        # Social/OAuth providers
        providers = {
            "google": "Google", "github": "GitHub", "facebook": "Facebook",
            "apple": "Apple", "twitter": "Twitter", "microsoft": "Microsoft",
            "discord": "Discord", "slack": "Slack"
        }
        for key, provider in providers.items():
            if key in content_lower and provider not in info.providers:
                info.providers.append(provider)

        # RBAC detection
        if any(kw in content_lower for kw in ["role", "permission", "rbac", "authorize",
                                               "can(", "ability", "policy"]):
            info.has_rbac = True

        # Auth middleware
        if any(kw in content_lower for kw in ["middleware", "guard", "interceptor",
                                               "before_action", "before_request"]):
            info.has_middleware = True

    # Deduplicate
    info.patterns = list(dict.fromkeys(info.patterns))
    info.auth_files = list(dict.fromkeys(info.auth_files))
    info.providers = list(dict.fromkeys(info.providers))

    return info
