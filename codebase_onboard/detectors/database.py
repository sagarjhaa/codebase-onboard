"""Detect database usage, ORMs, and migration patterns."""

import re
from pathlib import Path
from ..models import DatabaseInfo
from ..constants import DB_PACKAGES, MAX_FILE_READ_BYTES


def detect_database(repo_path: Path, files: list, dependencies: dict) -> DatabaseInfo:
    """Analyze database usage patterns."""
    info = DatabaseInfo()

    # Check dependencies for known DB packages
    all_deps_str = " ".join(dependencies.keys()).lower()

    for pkg, (orm_name, db_name) in DB_PACKAGES.items():
        if pkg.lower() in all_deps_str:
            if orm_name not in info.orms:
                info.orms.append(orm_name)
            for db in db_name.split("/"):
                if db.strip() not in info.databases:
                    info.databases.append(db.strip())

    # Check imports in source files
    for f in files:
        if not f.language:
            continue
        for imp in f.imports:
            imp_lower = imp.lower()
            for pkg, (orm_name, db_name) in DB_PACKAGES.items():
                if pkg.lower() in imp_lower:
                    if orm_name not in info.orms:
                        info.orms.append(orm_name)
                    for db in db_name.split("/"):
                        if db.strip() not in info.databases:
                            info.databases.append(db.strip())

    # Check for database connection strings in common config files
    config_patterns = [
        "config", "database", "db", "settings", ".env.example", ".env.sample"
    ]
    for f in files:
        if not any(p in f.relative_path.lower() for p in config_patterns):
            continue
        try:
            content = Path(f.path).read_text(errors="replace")[:MAX_FILE_READ_BYTES]
        except Exception:
            continue

        # PostgreSQL
        if re.search(r'postgres(?:ql)?://', content, re.IGNORECASE):
            if "PostgreSQL" not in info.databases:
                info.databases.append("PostgreSQL")
            info.connection_files.append(f.relative_path)
        # MySQL
        if re.search(r'mysql://', content, re.IGNORECASE):
            if "MySQL" not in info.databases:
                info.databases.append("MySQL")
            info.connection_files.append(f.relative_path)
        # MongoDB
        if re.search(r'mongodb(?:\+srv)?://', content, re.IGNORECASE):
            if "MongoDB" not in info.databases:
                info.databases.append("MongoDB")
            info.connection_files.append(f.relative_path)
        # Redis
        if re.search(r'redis://', content, re.IGNORECASE):
            if "Redis" not in info.databases:
                info.databases.append("Redis")
            info.connection_files.append(f.relative_path)
        # SQLite
        if re.search(r'sqlite(?:3)?://', content, re.IGNORECASE) or "sqlite" in content.lower():
            if "SQLite" not in info.databases:
                info.databases.append("SQLite")

    # Detect migrations
    migration_dirs = ["migrations", "migrate", "db/migrate", "alembic",
                      "prisma/migrations", "drizzle", "src/migrations"]
    for mdir in migration_dirs:
        if (repo_path / mdir).is_dir():
            info.has_migrations = True
            if "alembic" in mdir:
                info.migration_tool = "Alembic"
            elif "prisma" in mdir:
                info.migration_tool = "Prisma Migrate"
            elif "drizzle" in mdir:
                info.migration_tool = "Drizzle Kit"
            elif "db/migrate" in mdir:
                info.migration_tool = "Rails Migrations"
            else:
                info.migration_tool = "Custom"
            break

    # Check for Django migrations
    for f in files:
        if "/migrations/" in f.relative_path and f.relative_path.endswith(".py"):
            info.has_migrations = True
            info.migration_tool = "Django Migrations"
            break

    # Check for Prisma schema
    prisma_schema = repo_path / "prisma" / "schema.prisma"
    if prisma_schema.exists():
        try:
            content = prisma_schema.read_text(errors="replace")
            # Extract model names
            for m in re.finditer(r'model\s+(\w+)\s*\{', content):
                info.models.append(m.group(1))
            # Detect DB provider
            provider_match = re.search(r'provider\s*=\s*"(\w+)"', content)
            if provider_match:
                provider = provider_match.group(1)
                db_map = {"postgresql": "PostgreSQL", "mysql": "MySQL",
                          "sqlite": "SQLite", "mongodb": "MongoDB"}
                db = db_map.get(provider, provider)
                if db not in info.databases:
                    info.databases.append(db)
            if "Prisma" not in info.orms:
                info.orms.append("Prisma")
        except Exception:
            pass

    # Extract model names from source files
    model_patterns = [
        (r'class\s+(\w+)\s*\(.*(?:Model|Base|Entity|Document)', "Python"),
        (r'@Entity\(\)\s*(?:export\s+)?class\s+(\w+)', "TypeScript"),
    ]
    for f in files:
        if not f.language:
            continue
        for cls in f.classes:
            cls_lower = cls.lower()
            if any(kw in cls_lower for kw in ["model", "entity", "schema"]):
                if cls not in info.models and not cls.startswith("_"):
                    info.models.append(cls)

    # Deduplicate
    info.databases = list(dict.fromkeys(info.databases))
    info.orms = list(dict.fromkeys(info.orms))
    info.connection_files = list(dict.fromkeys(info.connection_files))

    return info
