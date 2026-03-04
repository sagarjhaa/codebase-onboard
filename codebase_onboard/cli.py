"""CLI interface for Codebase Onboarding Agent."""

import os
import sys
import shutil
import subprocess
import tempfile
import hashlib
from pathlib import Path

import click

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


CACHE_DIR = Path.home() / ".cache" / "codebase-onboard"
BANNER = """
╔══════════════════════════════════════════════╗
║  🚀 Codebase Onboarding Agent v1.0          ║
║  Understand any codebase in minutes          ║
╚══════════════════════════════════════════════╝
"""


def _get_cache_path(url: str) -> Path:
    """Get a deterministic cache path for a repository URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    # Extract repo name from URL
    name = url.rstrip("/").split("/")[-1].replace(".git", "")
    return CACHE_DIR / f"{name}_{url_hash}"


def _clone_repo(url: str, target: Path, console=None, shallow: bool = True) -> Path:
    """Clone a repository, using cache if available."""
    if target.exists():
        if console and HAS_RICH:
            console.print(f"  [green]✓[/green] Using cached clone: {target}")
        # Pull latest
        try:
            subprocess.run(
                ["git", "pull", "--ff-only"],
                capture_output=True, text=True, cwd=str(target), timeout=30
            )
        except Exception:
            pass
        return target

    target.parent.mkdir(parents=True, exist_ok=True)

    if console and HAS_RICH:
        console.print(f"  [dim]Cloning {url}...[/dim]")

    cmd = ["git", "clone"]
    if shallow:
        cmd.extend(["--depth", "1"])
    cmd.extend([url, str(target)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Clone timed out (120s)")

    return target


@click.command()
@click.argument("repo")
@click.option("--output", "-o", help="Output file path (auto-detects format from extension)")
@click.option("--format", "-f", "fmt", type=click.Choice(["markdown", "html", "json", "terminal"]),
              default=None, help="Output format (default: markdown, or auto-detect from -o extension)")
@click.option("--ai", is_flag=True, help="Enable AI-powered insights (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)")
@click.option("--depth", type=click.Choice(["shallow", "standard", "deep"]), default="deep",
              help="Analysis depth (default: deep)")
@click.option("--focus", help="Focus analysis on a specific directory")
@click.option("--no-cache", is_flag=True, help="Don't use cached repository clones")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output")
def cli(repo, output, fmt, ai, depth, focus, no_cache, quiet):
    """🚀 Analyze a codebase and generate an onboarding guide.

    REPO can be a GitHub URL, git URL, or local directory path.

    Examples:

        onboard https://github.com/expressjs/express

        onboard ./my-project --format html -o guide.html

        onboard https://github.com/org/repo --ai --depth deep

        onboard /path/to/repo --focus src/api --format terminal
    """
    console = Console() if HAS_RICH and not quiet else None
    temp_dir = None

    try:
        if console:
            console.print(BANNER, style="cyan")

        # Determine if URL or local path
        is_url = repo.startswith(("http://", "https://", "git@", "ssh://"))

        if is_url:
            if no_cache:
                temp_dir = tempfile.mkdtemp(prefix="onboard_")
                repo_path = str(_clone_repo(repo, Path(temp_dir) / "repo", console))
            else:
                cache_path = _get_cache_path(repo)
                repo_path = str(_clone_repo(repo, cache_path, console))
        elif os.path.isdir(repo):
            repo_path = os.path.abspath(repo)
        else:
            click.echo(f"Error: '{repo}' is not a valid directory or URL", err=True)
            sys.exit(1)

        # Auto-detect format from output extension
        if fmt is None:
            if output:
                ext = Path(output).suffix.lower()
                fmt = {".html": "html", ".htm": "html", ".json": "json"}.get(ext, "markdown")
            else:
                fmt = "terminal" if (console and not output) else "markdown"

        # Run analysis
        from .analyzer import CodebaseAnalyzer

        # For URLs, derive a nice name
        repo_display_name = None
        if is_url:
            # Extract "org/repo" or just "repo" from URL
            parts = repo.rstrip("/").rstrip(".git").split("/")
            repo_display_name = parts[-1] if parts else None

        if console:
            total_steps = {"shallow": 8, "standard": 17, "deep": 21}
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(complete_style="green"),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing codebase...", total=total_steps.get(depth, 17))
                analyzer = CodebaseAnalyzer(repo_path, console=None, depth=depth, focus=focus)
                analysis = analyzer.analyze(progress=progress, task=task)
                analysis.url = repo if is_url else ""
                if repo_display_name:
                    analysis.name = repo_display_name
        else:
            analyzer = CodebaseAnalyzer(repo_path, depth=depth, focus=focus)
            analysis = analyzer.analyze()
            analysis.url = repo if is_url else ""
            if repo_display_name:
                analysis.name = repo_display_name

        # AI enhancement
        if ai:
            if console:
                console.print("\n[bold]🤖 Generating AI insights...[/bold]")
            from .ai_enhancer import enhance_with_ai
            analysis.ai_insights = enhance_with_ai(analysis)

        # Generate output
        if fmt == "json":
            from .generators.json_output import generate_json
            result = generate_json(analysis)
        elif fmt == "html":
            from .generators.html import generate_html
            result = generate_html(analysis)
        elif fmt == "terminal":
            from .generators.terminal import print_terminal
            print_terminal(analysis, console)
            result = None
        else:  # markdown
            from .generators.markdown import generate_markdown
            result = generate_markdown(analysis)

        # Output
        if result:
            if output:
                Path(output).write_text(result)
                if console:
                    console.print(f"\n[bold green]✅ Guide written to {output}[/bold green]")
                    console.print(f"[dim]{analysis.total_files} files analyzed, {analysis.total_lines:,} lines of code[/dim]")
            else:
                if fmt != "terminal":
                    print(result)
        elif fmt == "terminal" and console:
            console.print(f"[dim]{analysis.total_files} files analyzed, {analysis.total_lines:,} lines of code[/dim]")

    except KeyboardInterrupt:
        click.echo("\nAborted.", err=True)
        sys.exit(1)
    except Exception as e:
        if console:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    cli()
