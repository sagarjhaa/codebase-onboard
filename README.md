# 🚀 Codebase Onboarding Agent

**Understand any codebase in minutes, not months.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

New engineers take **6.2 months** to reach full productivity. Every context switch costs **23 minutes** of focus. Bad documentation costs the industry **$85B/year**.

This tool fixes the first step: **understanding the codebase.**

Point it at any repository — GitHub URL or local path — and get a comprehensive onboarding guide with architecture analysis, API endpoints, database schemas, auth patterns, dependency graphs, and a "Your First PR" guide. In seconds.

## Quick Start

```bash
# Install
pip install -e .

# Analyze any GitHub repo
onboard https://github.com/expressjs/express

# Analyze a local repo
onboard ./my-project

# Generate a beautiful HTML page
onboard https://github.com/org/repo -o guide.html

# AI-enhanced insights (optional)
export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
onboard https://github.com/org/repo --ai

# JSON output for programmatic use
onboard ./my-project --format json -o analysis.json
```

## What It Analyzes

| Feature | What It Does |
|---------|-------------|
| 📋 **Quick Overview** | Language breakdown, framework detection, complexity score |
| 🏗 **Architecture** | Patterns (MVC, microservices, monorepo), file distribution |
| 🌐 **API Endpoints** | Detects REST routes in Express, FastAPI, Flask, Django, Gin, Axum, Rails, Next.js |
| 🗄️ **Database** | Which DB (Postgres, MongoDB, Redis...), ORM, migrations, models |
| 🔐 **Authentication** | JWT, OAuth2, session-based, RBAC, social providers |
| 🧪 **Testing** | Framework detection, coverage estimate, test-to-source ratio |
| 🔄 **CI/CD** | GitHub Actions, GitLab CI, CircleCI, Jenkins pipeline analysis |
| 🐳 **Docker** | Dockerfile parsing, compose services, exposed ports |
| 🔗 **Dependency Graph** | Mermaid diagram of internal module dependencies |
| 🔥 **Hot Files** | Most imported and most frequently changed files |
| 🔐 **Environment Variables** | Every env var referenced across ALL files with locations |
| 📦 **Dependencies** | Categorized dependency overview (web, DB, auth, testing...) |
| 🎯 **First PR Guide** | Where to make your first contribution, conventions to follow |
| 💡 **Key Concepts** | Domain-specific terminology extracted from the codebase |
| 📊 **Complexity Score** | 1-100 score with breakdown (size, languages, deps, architecture) |
| ⚠️ **Gotchas** | Missing tests, large files, no CI/CD, multi-language warnings |

## Output Formats

| Format | Flag | Best For |
|--------|------|----------|
| **Terminal** | `--format terminal` (default) | Quick exploration with rich formatting |
| **Markdown** | `--format markdown` or `-o guide.md` | Documentation, README, wiki |
| **HTML** | `-o guide.html` | Beautiful standalone page with navigation sidebar |
| **JSON** | `--format json` | Programmatic use, dashboards, automation |

## CLI Options

```
Usage: onboard [OPTIONS] REPO

Options:
  -o, --output TEXT          Output file (auto-detects format from extension)
  -f, --format [markdown|html|json|terminal]
                             Output format
  --ai                       Enable AI-powered insights (needs API key)
  --depth [shallow|standard|deep]
                             Analysis depth (default: deep)
  --focus TEXT               Focus on a specific directory
  --no-cache                 Don't use cached repository clones
  -q, --quiet                Suppress progress output
  --help                     Show this message
```

## Language & Framework Support

**Languages:** Python, JavaScript, TypeScript, Go, Rust, Ruby, Java, Kotlin, Swift, C/C++, C#, Scala, Elixir, Dart, PHP, and more.

**Frameworks detected:**
- **Backend:** Express, FastAPI, Flask, Django, Gin, Axum, Actix, Rails, Fastify, Hono, Koa
- **Frontend:** React, Next.js, Vue, Nuxt, Svelte, Angular
- **Infrastructure:** Docker, Terraform, Serverless, Fly.io, Vercel, Netlify
- **Testing:** Jest, Vitest, pytest, Mocha, Cypress, Playwright, RSpec, Go testing, Rust testing
- **Databases:** PostgreSQL, MySQL, MongoDB, Redis, SQLite, Elasticsearch via 20+ ORMs

## AI Enhancement (Optional)

With `--ai`, the tool sends a structured summary to Claude or GPT to generate:

- **Architecture Summary** — What the codebase does in plain English
- **Learning Path** — Recommended order to explore the code
- **Design Decisions** — Notable architectural choices and reasoning
- **Common Tasks Q&A** — How to add features, endpoints, tests
- **Architecture Diagram** — Auto-generated Mermaid diagram

Works with either `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. The tool works great without AI — AI just makes it better.

## Example Outputs

See the [`examples/`](examples/) directory for real outputs:
- [Flask](examples/flask.md) — Classic Python web framework
- [FastAPI](examples/fastapi.md) — Modern Python API framework

## Why This Exists

Based on [research into developer productivity](RESEARCH.md):

> - **6.2 months** average time to full productivity for new engineers (Jellyfish, 2023)
> - **23 minutes** to regain focus after each context switch (Gloria Mark, UC Irvine)
> - **$85B/year** cost of bad documentation in US software industry (Stripe, 2018)
> - **Only 12%** of employees say their org does a great job of onboarding (Gallup)
> - **40%** of new hires who receive poor onboarding leave within a year (Digitate)

The biggest untapped opportunity in developer productivity is **onboarding** — and it starts with understanding the codebase.

## Architecture

```
codebase_onboard/
├── cli.py              # Click-based CLI with progress bars
├── analyzer.py         # Core analysis engine (orchestrates detectors)
├── models.py           # Data models for all analysis results
├── constants.py        # Language, config, and framework mappings
├── graph.py            # Dependency graphs, complexity scoring, hot files
├── ai_enhancer.py      # Claude/OpenAI integration for AI insights
├── detectors/          # Modular detection engines
│   ├── test_coverage.py    # Test framework & coverage detection
│   ├── cicd.py             # CI/CD pipeline analysis
│   ├── docker.py           # Docker & Compose parsing
│   ├── api_endpoints.py    # REST endpoint detection (6 languages)
│   ├── database.py         # DB, ORM, migration detection
│   ├── auth.py             # Auth pattern & provider detection
│   └── env_vars.py         # Environment variable extraction
└── generators/         # Output format generators
    ├── markdown.py         # Comprehensive Markdown guide
    ├── html.py             # Standalone HTML with dark theme & nav
    ├── json_output.py      # Structured JSON for programmatic use
    └── terminal.py         # Rich terminal output with tables & panels
```

## Alternatives

| Tool | Approach | Limitations |
|------|----------|------------|
| **GitHub Copilot** | AI Q&A on code | No structured guide, no offline, per-file focus |
| **Sourcegraph** | Code search & navigation | Enterprise-focused, no guide generation |
| **Code tours** (VS Code) | Manual walkthrough creation | Requires manual curation, goes stale |
| **README** | Static documentation | Written once, never updated, incomplete |
| **This tool** | **Automated analysis → structured guide** | Static snapshot (re-run for updates) |

## Contributing

```bash
git clone https://github.com/sagarjhaa/codebase-onboard
cd codebase-onboard
python -m venv venv && source venv/bin/activate
pip install -e ".[all]"
onboard . --format terminal  # test on itself!
```

## License

MIT
