"""AI-powered enhancement for onboarding guides."""

import os
import json
from .models import RepoAnalysis


def enhance_with_ai(analysis: RepoAnalysis) -> str:
    """Use AI to generate deeper insights about the codebase."""

    # Build context for the AI
    context = _build_context(analysis)

    # Try Anthropic (Claude) first, then OpenAI
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return _call_anthropic(context, api_key)

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return _call_openai(context, api_key)

    return "*AI enhancement requires ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable.*"


def _build_context(a: RepoAnalysis) -> str:
    """Build a concise context string for the AI."""
    parts = []

    # README (truncated)
    if a.readme_content:
        parts.append(f"## README (first 2000 chars)\n{a.readme_content[:2000]}")

    # Basic info
    parts.append(f"""## Codebase Stats
- Name: {a.name}
- Primary Language: {a.primary_language}
- Frameworks: {', '.join(a.frameworks)}
- Total Files: {a.total_files}
- Total Lines: {a.total_lines:,}
- Package Manager: {a.package_manager}
- Monorepo: {a.monorepo}
- Complexity: {a.complexity.label} ({a.complexity.overall}/100)""")

    # Architecture
    if a.architecture_hints:
        parts.append("## Architecture\n" + "\n".join(f"- {h}" for h in a.architecture_hints))

    # Patterns
    if a.patterns:
        parts.append("## Patterns\n" + "\n".join(f"- {p}" for p in a.patterns))

    # API endpoints summary
    if a.api_endpoints:
        ep_summary = [f"- {ep.method} {ep.path} ({ep.framework})" for ep in a.api_endpoints[:20]]
        parts.append(f"## API Endpoints ({len(a.api_endpoints)} total)\n" + "\n".join(ep_summary))

    # Database
    if a.database_info and a.database_info.databases:
        parts.append(f"## Database\n- DBs: {', '.join(a.database_info.databases)}\n- ORMs: {', '.join(a.database_info.orms)}")

    # Auth
    if a.auth_info and a.auth_info.patterns:
        parts.append(f"## Auth\n" + "\n".join(f"- {p}" for p in a.auth_info.patterns))

    # Entry points
    if a.entry_points:
        ep_info = []
        for ep in a.entry_points[:5]:
            ep_info.append(f"- {ep.relative_path}: functions={ep.functions[:5]}, classes={ep.classes[:5]}")
        parts.append("## Entry Points\n" + "\n".join(ep_info))

    # Key dependencies
    if a.dependencies:
        deps = list(a.dependencies.keys())[:20]
        parts.append(f"## Key Dependencies\n{', '.join(deps)}")

    return "\n\n".join(parts)


SYSTEM_PROMPT = """You are a senior software architect creating an onboarding guide for new developers.
Based on the codebase analysis below, generate insights in these sections:

1. **Architecture Summary** (2-3 sentences): What does this codebase do and how is it structured?
2. **Learning Path**: Recommended order to explore the codebase (5-7 steps)
3. **Key Design Decisions**: Notable architectural choices and likely reasoning (3-5 items)
4. **Common Tasks Q&A**: Answer these questions based on the code structure:
   - "How do I add a new API endpoint?"
   - "How do I add a new feature?"
   - "Where do I add tests?"
   - "How does authentication work?"
5. **Potential Pitfalls**: What might trip up a new developer (3-5 items)
6. **Architecture Diagram**: A simple Mermaid diagram showing the high-level architecture

Be specific and actionable. Reference actual file paths and patterns from the analysis.
Use markdown formatting. Keep the total response under 800 words."""


def _call_anthropic(context: str, api_key: str) -> str:
    """Call Claude API for insights."""
    try:
        import httpx
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": f"{SYSTEM_PROMPT}\n\n---\n\n{context}"}
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]
    except ImportError:
        # Try with urllib
        return _call_anthropic_urllib(context, api_key)
    except Exception as e:
        return f"*AI enhancement failed (Anthropic): {e}*"


def _call_anthropic_urllib(context: str, api_key: str) -> str:
    """Fallback using urllib."""
    import urllib.request
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [
                {"role": "user", "content": f"{SYSTEM_PROMPT}\n\n---\n\n{context}"}
            ],
        }).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception as e:
        return f"*AI enhancement failed: {e}*"


def _call_openai(context: str, api_key: str) -> str:
    """Call OpenAI API for insights."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            max_tokens=2000,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except ImportError:
        return "*OpenAI package not installed. Run: pip install openai*"
    except Exception as e:
        return f"*AI enhancement failed (OpenAI): {e}*"
