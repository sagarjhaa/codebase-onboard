"""Generate rich terminal output."""

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree
    from rich.columns import Columns
    from rich.text import Text
    from rich.markdown import Markdown
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_terminal(analysis, console=None):
    """Print a rich formatted analysis to the terminal."""
    if not HAS_RICH:
        # Fallback: just print markdown
        from .markdown import generate_markdown
        print(generate_markdown(analysis))
        return

    c = console or Console()
    a = analysis

    # Header
    complexity_colors = {"Simple": "green", "Moderate": "yellow", "Complex": "dark_orange", "Very Complex": "red"}
    complexity_color = complexity_colors.get(a.complexity.label, "white") if a.complexity else "white"

    c.print()
    c.print(Panel.fit(
        f"[bold cyan]🚀 Codebase Onboarding: {a.name}[/bold cyan]\n"
        f"[dim]{a.url or a.path}[/dim]\n"
        f"[{complexity_color}]Complexity: {a.complexity.label} ({a.complexity.overall}/100)[/{complexity_color}]"
        if a.complexity else
        f"[bold cyan]🚀 Codebase Onboarding: {a.name}[/bold cyan]\n"
        f"[dim]{a.url or a.path}[/dim]",
        border_style="cyan"
    ))

    # Quick Stats Table
    stats = Table(title="📋 Quick Overview", show_header=True, border_style="dim")
    stats.add_column("Metric", style="bold")
    stats.add_column("Value", style="cyan")

    stats.add_row("Primary Language", a.primary_language or "N/A")
    if a.frameworks:
        stats.add_row("Frameworks", ", ".join(a.frameworks))
    stats.add_row("Files", f"{a.total_files:,}")
    stats.add_row("Lines of Code", f"{a.total_lines:,}")
    if a.license_type:
        stats.add_row("License", a.license_type)
    if a.package_manager:
        stats.add_row("Package Manager", a.package_manager)
    if a.database_info and a.database_info.databases:
        stats.add_row("Database", ", ".join(a.database_info.databases))
    if a.api_endpoints:
        stats.add_row("API Endpoints", str(len(a.api_endpoints)))
    if a.test_coverage:
        stats.add_row("Test Coverage", f"{a.test_coverage.coverage_estimate.title()} ({a.test_coverage.test_count} test files)")

    c.print(stats)
    c.print()

    # Language breakdown
    if a.languages:
        lang_table = Table(title="🛠 Languages", border_style="dim")
        lang_table.add_column("Language", style="bold")
        lang_table.add_column("Lines")
        lang_table.add_column("Percentage")
        lang_table.add_column("Bar")

        total = sum(a.languages.values())
        for lang, count in a.languages.items():
            pct = (count / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            lang_table.add_row(lang, f"{count:,}", f"{pct:.1f}%", f"[green]{bar}[/green]")

        c.print(lang_table)
        c.print()

    # Architecture highlights
    if a.architecture_hints:
        c.print(Panel(
            "\n".join(f"• {h}" for h in a.architecture_hints),
            title="🏗 Architecture",
            border_style="green"
        ))
        c.print()

    # API Endpoints
    if a.api_endpoints:
        ep_table = Table(title=f"🌐 API Endpoints ({len(a.api_endpoints)})", border_style="dim")
        ep_table.add_column("Method", style="bold magenta")
        ep_table.add_column("Path", style="cyan")
        ep_table.add_column("File")
        ep_table.add_column("Framework", style="dim")

        for ep in a.api_endpoints[:20]:
            ep_table.add_row(ep.method, ep.path, ep.file, ep.framework)

        c.print(ep_table)
        if len(a.api_endpoints) > 20:
            c.print(f"  [dim]... and {len(a.api_endpoints) - 20} more endpoints[/dim]")
        c.print()

    # Database
    if a.database_info and (a.database_info.databases or a.database_info.orms):
        db = a.database_info
        db_info = []
        if db.databases:
            db_info.append(f"Databases: {', '.join(db.databases)}")
        if db.orms:
            db_info.append(f"ORM: {', '.join(db.orms)}")
        if db.has_migrations:
            db_info.append(f"Migrations: {db.migration_tool}")
        if db.models:
            db_info.append(f"Models: {', '.join(db.models[:10])}")

        c.print(Panel("\n".join(db_info), title="🗄️ Database", border_style="blue"))
        c.print()

    # Auth
    if a.auth_info and a.auth_info.patterns:
        auth_info = []
        for p in a.auth_info.patterns:
            auth_info.append(f"• {p}")
        if a.auth_info.providers:
            auth_info.append(f"OAuth Providers: {', '.join(a.auth_info.providers)}")
        c.print(Panel("\n".join(auth_info), title="🔐 Authentication", border_style="yellow"))
        c.print()

    # Entry Points
    if a.entry_points:
        c.print("[bold]🚪 Entry Points[/bold]")
        for ep in a.entry_points:
            c.print(f"  [cyan]→ {ep.relative_path}[/cyan]")
            if ep.functions:
                c.print(f"    Functions: {', '.join(ep.functions[:8])}")
        c.print()

    # Hot Files
    if a.hot_files:
        c.print("[bold]🔥 Hot Files[/bold]")
        for hf in a.hot_files[:8]:
            c.print(f"  [yellow]→ {hf.path}[/yellow] — {hf.reason}")
        c.print()

    # Environment Variables
    if a.env_vars:
        env_count = len(a.env_vars)
        c.print(f"[bold]🔐 Environment Variables ({env_count})[/bold]")
        for item in a.env_vars[:10]:
            if isinstance(item, tuple):
                name, files = item
                c.print(f"  [dim]${name}[/dim] ← {', '.join(files[:2])}")
            else:
                c.print(f"  [dim]${item}[/dim]")
        if env_count > 10:
            c.print(f"  [dim]... and {env_count - 10} more[/dim]")
        c.print()

    # CI/CD
    if a.cicd_info and a.cicd_info.provider:
        ci = a.cicd_info
        features = []
        if ci.has_test: features.append("[green]✅ Tests[/green]")
        if ci.has_lint: features.append("[green]✅ Lint[/green]")
        if ci.has_build: features.append("[green]✅ Build[/green]")
        if ci.has_deploy: features.append("[green]✅ Deploy[/green]")
        c.print(f"[bold]🔄 CI/CD: {ci.provider}[/bold] — {' '.join(features)}")
        c.print()

    # Gotchas
    if a.gotchas:
        c.print(Panel(
            "\n".join(f"⚠️  {g}" for g in a.gotchas),
            title="⚠️ Gotchas",
            border_style="yellow"
        ))
        c.print()

    # First PR Guide
    if a.first_pr and a.first_pr.suggested_areas:
        c.print("[bold]🎯 Your First PR[/bold]")
        for area in a.first_pr.suggested_areas:
            c.print(f"  {area}")
        c.print()

    # Complexity breakdown
    if a.complexity and a.complexity.factors:
        c.print(f"[bold]📊 Complexity: [{complexity_color}]{a.complexity.label}[/{complexity_color}] ({a.complexity.overall}/100)[/bold]")
        for f in a.complexity.factors:
            c.print(f"  • {f}")
        c.print()

    c.print("[dim]Generated by Codebase Onboarding Agent v1.0[/dim]")
    c.print()
