"""Detect API endpoints across various frameworks."""

import re
from pathlib import Path
from ..models import APIEndpoint
from ..constants import MAX_FILE_READ_BYTES


def detect_api_endpoints(repo_path: Path, files: list) -> list:
    """Find API endpoint definitions across frameworks."""
    endpoints = []

    for f in files:
        if not f.language:
            continue

        # Skip our own detector files
        if "codebase_onboard" in f.relative_path or "codebase-onboard" in f.relative_path:
            continue

        # Focus on likely API files
        path_lower = f.relative_path.lower()
        is_likely_api = any(kw in path_lower for kw in [
            "route", "api", "controller", "handler", "endpoint", "view",
            "router", "server", "app", "urls"
        ])

        # Also check files that import routing frameworks
        has_route_import = any(kw in imp.lower() for imp in f.imports for kw in [
            "express", "fastify", "flask", "fastapi", "django", "router",
            "gin", "mux", "actix", "axum", "rails", "sinatra", "koa",
            "hono", "elysia"
        ])

        if not is_likely_api and not has_route_import:
            continue

        fpath = repo_path / f.relative_path
        try:
            content = fpath.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
        except Exception:
            continue

        # Detect based on language/framework
        if f.language == "Python":
            endpoints.extend(_detect_python_endpoints(content, f.relative_path))
        elif f.language in ("JavaScript", "TypeScript", "TypeScript (React)", "JavaScript (React)"):
            endpoints.extend(_detect_js_endpoints(content, f.relative_path))
        elif f.language == "Go":
            endpoints.extend(_detect_go_endpoints(content, f.relative_path))
        elif f.language == "Ruby":
            endpoints.extend(_detect_ruby_endpoints(content, f.relative_path))
        elif f.language == "Rust":
            endpoints.extend(_detect_rust_endpoints(content, f.relative_path))

    return endpoints


def _detect_python_endpoints(content: str, filepath: str) -> list:
    """Detect endpoints in Python (FastAPI, Flask, Django)."""
    endpoints = []

    # FastAPI: @app.get("/path") or @router.get("/path")
    for m in re.finditer(
        r'@(?:app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)',
        content, re.IGNORECASE
    ):
        method = m.group(1).upper()
        path = m.group(2)
        # Find handler name on next line
        pos = m.end()
        handler_match = re.search(r'(?:async\s+)?def\s+(\w+)', content[pos:pos+200])
        handler = handler_match.group(1) if handler_match else ""
        endpoints.append(APIEndpoint(
            method=method, path=path, file=filepath,
            handler=handler, framework="FastAPI"
        ))

    # Flask: @app.route("/path", methods=["GET"])
    for m in re.finditer(
        r'@(?:app|bp|blueprint)\.\s*route\s*\(\s*["\']([^"\']+)["\'](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?',
        content, re.IGNORECASE
    ):
        path = m.group(1)
        methods_str = m.group(2) if m.group(2) else "GET"
        methods = re.findall(r'["\'](\w+)["\']', methods_str) if m.group(2) else ["GET"]
        pos = m.end()
        handler_match = re.search(r'def\s+(\w+)', content[pos:pos+200])
        handler = handler_match.group(1) if handler_match else ""
        for method in methods:
            endpoints.append(APIEndpoint(
                method=method.upper(), path=path, file=filepath,
                handler=handler, framework="Flask"
            ))

    # Django URLs: path("api/...", view)
    for m in re.finditer(r'path\s*\(\s*["\']([^"\']*)["\']', content):
        path = "/" + m.group(1) if not m.group(1).startswith("/") else m.group(1)
        endpoints.append(APIEndpoint(
            method="*", path=path, file=filepath,
            framework="Django"
        ))

    return endpoints


def _detect_js_endpoints(content: str, filepath: str) -> list:
    """Detect endpoints in JavaScript/TypeScript (Express, Fastify, Next.js API routes, Hono)."""
    endpoints = []

    # Express/Fastify: app.get("/path", handler) or router.get("/path", handler)
    for m in re.finditer(
        r'(?:app|router|server|fastify)\.(get|post|put|delete|patch|all|options|head)\s*\(\s*["\']([^"\']+)',
        content, re.IGNORECASE
    ):
        method = m.group(1).upper()
        path = m.group(2)
        endpoints.append(APIEndpoint(
            method=method, path=path, file=filepath,
            framework="Express/Fastify"
        ))

    # Hono: app.get("/path", handler)
    if "Hono" in content or "hono" in content:
        for m in re.finditer(
            r'(?:app|api)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)',
            content
        ):
            endpoints.append(APIEndpoint(
                method=m.group(1).upper(), path=m.group(2), file=filepath,
                framework="Hono"
            ))

    # Next.js API routes (file-based routing)
    if "/api/" in filepath or "\\api\\" in filepath:
        # Check for HTTP method exports
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            if re.search(rf'export\s+(?:async\s+)?function\s+{method}\b', content):
                # Derive route from file path
                route = "/" + filepath.replace("\\", "/")
                route = re.sub(r'(?:src/)?(?:app|pages)', '', route)
                route = re.sub(r'/route\.\w+$', '', route)
                route = re.sub(r'/\[(\w+)\]', r'/:\1', route)
                endpoints.append(APIEndpoint(
                    method=method, path=route, file=filepath,
                    framework="Next.js"
                ))

    return endpoints


def _detect_go_endpoints(content: str, filepath: str) -> list:
    """Detect endpoints in Go (net/http, Gin, Gorilla Mux, Chi)."""
    endpoints = []

    # Gin: r.GET("/path", handler)
    for m in re.finditer(
        r'(?:r|router|group|api|v\d+)\.(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(\s*["\']([^"\']+)',
        content
    ):
        endpoints.append(APIEndpoint(
            method=m.group(1), path=m.group(2), file=filepath,
            framework="Gin"
        ))

    # Chi/Gorilla Mux: r.Get("/path", handler)
    for m in re.finditer(
        r'(?:r|router|mux)\.(Get|Post|Put|Delete|Patch|Handle|HandleFunc)\s*\(\s*["\']([^"\']+)',
        content
    ):
        method = m.group(1).upper()
        if method in ("HANDLE", "HANDLEFUNC"):
            method = "*"
        endpoints.append(APIEndpoint(
            method=method, path=m.group(2), file=filepath,
            framework="Chi/Mux"
        ))

    # net/http: http.HandleFunc("/path", handler)
    for m in re.finditer(r'http\.HandleFunc\s*\(\s*["\']([^"\']+)', content):
        endpoints.append(APIEndpoint(
            method="*", path=m.group(1), file=filepath,
            framework="net/http"
        ))

    return endpoints


def _detect_ruby_endpoints(content: str, filepath: str) -> list:
    """Detect endpoints in Ruby (Rails, Sinatra)."""
    endpoints = []

    # Rails routes: get "/path", to: "controller#action"
    for m in re.finditer(
        r'(get|post|put|patch|delete)\s+["\']([^"\']+)',
        content, re.IGNORECASE
    ):
        endpoints.append(APIEndpoint(
            method=m.group(1).upper(), path=m.group(2), file=filepath,
            framework="Rails/Sinatra"
        ))

    # Rails resources
    for m in re.finditer(r'resources?\s+:(\w+)', content):
        resource = m.group(1)
        endpoints.append(APIEndpoint(
            method="CRUD", path=f"/{resource}", file=filepath,
            framework="Rails"
        ))

    return endpoints


def _detect_rust_endpoints(content: str, filepath: str) -> list:
    """Detect endpoints in Rust (Actix, Axum, Rocket)."""
    endpoints = []

    # Actix: #[get("/path")] or web::get().to(handler)
    for m in re.finditer(r'#\[(get|post|put|delete|patch)\s*\(\s*"([^"]+)"', content):
        endpoints.append(APIEndpoint(
            method=m.group(1).upper(), path=m.group(2), file=filepath,
            framework="Actix"
        ))

    # Axum: .route("/path", get(handler))
    for m in re.finditer(r'\.route\s*\(\s*"([^"]+)"\s*,\s*(get|post|put|delete|patch)', content):
        endpoints.append(APIEndpoint(
            method=m.group(2).upper(), path=m.group(1), file=filepath,
            framework="Axum"
        ))

    # Rocket: #[get("/path")]
    for m in re.finditer(r'#\[(get|post|put|delete|patch)\s*\(\s*"([^"]+)"', content):
        endpoints.append(APIEndpoint(
            method=m.group(1).upper(), path=m.group(2), file=filepath,
            framework="Rocket"
        ))

    return endpoints
