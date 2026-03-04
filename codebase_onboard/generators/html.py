"""Generate a beautiful standalone HTML onboarding page."""

from .markdown import generate_markdown

try:
    from markdown_it import MarkdownIt
    HAS_MARKDOWN_IT = True
except ImportError:
    HAS_MARKDOWN_IT = False


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Onboarding Guide: {name}</title>
<style>
:root {{
    --bg: #0d1117;
    --card-bg: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --accent: #58a6ff;
    --accent-green: #3fb950;
    --accent-orange: #d29922;
    --accent-red: #f85149;
    --code-bg: #1f2937;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem;
}}
h1 {{ color: var(--accent); font-size: 2rem; margin: 2rem 0 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
h2 {{ color: var(--accent-green); font-size: 1.5rem; margin: 2.5rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }}
h3 {{ color: var(--text); font-size: 1.15rem; margin: 1.5rem 0 0.5rem; }}
p {{ margin: 0.5rem 0; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
blockquote {{
    border-left: 3px solid var(--accent);
    padding: 0.5rem 1rem;
    margin: 1rem 0;
    background: var(--card-bg);
    border-radius: 0 8px 8px 0;
    color: var(--text-muted);
}}
code {{
    background: var(--code-bg);
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.9em;
    font-family: 'SF Mono', 'Fira Code', monospace;
}}
pre {{
    background: var(--code-bg);
    padding: 1rem;
    border-radius: 8px;
    overflow-x: auto;
    margin: 1rem 0;
    border: 1px solid var(--border);
}}
pre code {{ background: none; padding: 0; }}
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    border-radius: 8px;
    overflow: hidden;
}}
th, td {{
    padding: 0.6rem 1rem;
    border: 1px solid var(--border);
    text-align: left;
}}
th {{ background: var(--card-bg); font-weight: 600; }}
tr:nth-child(even) {{ background: var(--card-bg); }}
ul, ol {{ padding-left: 1.5rem; margin: 0.5rem 0; }}
li {{ margin: 0.3rem 0; }}
hr {{ border: none; border-top: 1px solid var(--border); margin: 2rem 0; }}
.nav {{
    position: fixed;
    top: 0;
    left: 0;
    width: 250px;
    height: 100vh;
    background: var(--card-bg);
    border-right: 1px solid var(--border);
    padding: 1rem;
    overflow-y: auto;
    z-index: 100;
}}
.nav h3 {{ color: var(--accent); font-size: 0.9rem; margin-bottom: 0.5rem; }}
.nav a {{
    display: block;
    padding: 0.3rem 0.5rem;
    color: var(--text-muted);
    font-size: 0.85rem;
    border-radius: 4px;
    transition: all 0.2s;
}}
.nav a:hover {{ background: var(--bg); color: var(--text); text-decoration: none; }}
.nav a.active {{ color: var(--accent); background: var(--bg); }}
.badge {{
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
}}
.badge-green {{ background: rgba(63,185,80,0.2); color: var(--accent-green); }}
.badge-yellow {{ background: rgba(210,153,34,0.2); color: var(--accent-orange); }}
.badge-red {{ background: rgba(248,81,73,0.2); color: var(--accent-red); }}
@media (max-width: 768px) {{
    .nav {{ display: none; }}
    body {{ padding: 1rem; }}
}}
@media (min-width: 769px) {{
    body {{ margin-left: 270px; }}
}}
.header-badge {{
    display: inline-block;
    margin-left: 0.5rem;
    font-size: 0.7em;
    vertical-align: middle;
}}
</style>
</head>
<body>
<nav class="nav" id="sidebar">
    <h3>📋 Navigation</h3>
    {nav_links}
</nav>
<main>
{content}
</main>
<script>
// Highlight active nav link on scroll
const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
        if (entry.isIntersecting) {{
            document.querySelectorAll('.nav a').forEach(a => a.classList.remove('active'));
            const id = entry.target.id;
            const link = document.querySelector(`.nav a[href="#${{id}}"]`);
            if (link) link.classList.add('active');
        }}
    }});
}}, {{ threshold: 0.3 }});
document.querySelectorAll('h2[id]').forEach(h2 => observer.observe(h2));
</script>
</body>
</html>"""


def generate_html(analysis) -> str:
    """Generate a beautiful standalone HTML onboarding page."""
    md_content = generate_markdown(analysis)

    # Convert markdown to HTML
    if HAS_MARKDOWN_IT:
        md = MarkdownIt("commonmark", {"html": True})
        md.enable("table")
        html_content = md.render(md_content)
    else:
        # Basic markdown to HTML fallback
        html_content = _basic_md_to_html(md_content)

    # Add IDs to h2 elements and build nav
    import re
    nav_links = []
    h2_count = 0

    def add_h2_id(match):
        nonlocal h2_count
        h2_count += 1
        text = re.sub(r'<[^>]+>', '', match.group(1))
        slug = re.sub(r'[^\w\s-]', '', text).strip().lower().replace(' ', '-')
        nav_links.append(f'<a href="#{slug}">{text}</a>')
        return f'<h2 id="{slug}">{match.group(1)}</h2>'

    html_content = re.sub(r'<h2>(.*?)</h2>', add_h2_id, html_content)

    return HTML_TEMPLATE.format(
        name=analysis.name,
        nav_links="\n    ".join(nav_links),
        content=html_content
    )


def _basic_md_to_html(md: str) -> str:
    """Very basic markdown to HTML conversion as fallback."""
    import re
    lines = md.split("\n")
    html = []
    in_code = False
    in_table = False
    in_list = False

    for line in lines:
        # Code blocks
        if line.strip().startswith("```"):
            if in_code:
                html.append("</code></pre>")
                in_code = False
            else:
                lang = line.strip()[3:]
                html.append(f"<pre><code class='{lang}'>")
                in_code = True
            continue

        if in_code:
            html.append(line.replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # Headers
        if line.startswith("# "):
            html.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("---"):
            html.append("<hr>")
        elif line.startswith("> "):
            html.append(f"<blockquote><p>{line[2:]}</p></blockquote>")
        elif line.startswith("- "):
            if not in_list:
                html.append("<ul>")
                in_list = True
            content = line[2:]
            # Bold
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            # Code
            content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)
            html.append(f"<li>{content}</li>")
        elif line.startswith("|"):
            if not in_table:
                html.append("<table>")
                in_table = True
            if "---" in line:
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            tag = "th" if not any("---" in c for c in cells) and in_table and html[-1] == "<table>" else "td"
            row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            html.append(f"<tr>{row}</tr>")
        else:
            if in_list:
                html.append("</ul>")
                in_list = False
            if in_table and not line.startswith("|"):
                html.append("</table>")
                in_table = False
            if line.strip():
                content = line
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
                content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)
                html.append(f"<p>{content}</p>")

    if in_list:
        html.append("</ul>")
    if in_table:
        html.append("</table>")

    return "\n".join(html)
