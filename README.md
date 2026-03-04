# 🚀 Developer Productivity Research + Codebase Onboarding Agent

## What's Here

### Research: The Developer Productivity Crisis
**[RESEARCH.md](./RESEARCH.md)** — A deep analysis of the six biggest unsolved problems in developer productivity:

1. **Context Switching Tax** — 23 minutes to regain focus after each interruption
2. **Meeting Overload** — 31 hours/month in unproductive meetings
3. **Documentation Rot** — $85B/year cost of bad documentation
4. **Onboarding Hell** — 6+ months to full productivity for new engineers
5. **Dependency Hell** — 84% of codebases have known vulnerabilities
6. **The IDE Gap** — What Cursor/Copilot got right, got wrong, and what's next

With real data, research citations, and actionable opportunity analysis.

### Prototype: Codebase Onboarding Agent
**[onboard.py](./onboard.py)** — A Python tool that analyzes any GitHub repository and generates a comprehensive onboarding guide for new developers.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Analyze a GitHub repo
python3 onboard.py https://github.com/expressjs/express

# Analyze a local repo
python3 onboard.py /path/to/repo

# Save to file
python3 onboard.py https://github.com/org/repo --output guide.md

# Enhanced with AI (requires OPENAI_API_KEY)
python3 onboard.py https://github.com/org/repo --ai

# JSON output (raw analysis)
python3 onboard.py https://github.com/org/repo --json
```

## What the Onboarding Agent Generates

- 📋 **Quick Overview** — What this project is
- 🛠 **Tech Stack** — Languages, frameworks, tools with line counts
- 📂 **Directory Structure** — Annotated tree view
- 🏗 **Architecture Overview** — How the pieces fit together
- 🚪 **Entry Points** — Where execution begins
- 📄 **Key Files** — Configuration files and important source files
- ⚡ **Setup Guide** — How to get running locally (auto-detected)
- 🔄 **Common Patterns** — Architectural patterns and conventions in use
- 📦 **Dependencies** — Categorized dependency overview
- 🧪 **Testing** — Test framework, file locations, how to run
- 🔄 **CI/CD** — Pipeline configuration
- 🔐 **Environment Variables** — All env vars referenced in code
- ⚠️ **Gotchas** — Potential issues (no tests, large files, missing configs)
- 🎯 **Next Steps** — What to do on your first day

## Requirements

- Python 3.8+
- Git (for cloning remote repos)
- Optional: `OPENAI_API_KEY` for AI-enhanced analysis

## Architecture

The tool has two main components:

1. **`CodebaseAnalyzer`** — Walks the repository, parses configs, extracts code structure, detects patterns
2. **`OnboardingGuideGenerator`** — Takes the analysis and renders a comprehensive Markdown guide

Supports: Python, JavaScript, TypeScript, Go, Rust, Java, and 20+ other languages.

## License

MIT
