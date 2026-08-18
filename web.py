from app import app


@app.after_request
def load_dashboard_modules(response):
    """Load isolated dashboard feature modules on rendered HTML pages only."""
    content_type = (response.content_type or "").lower()
    if response.status_code != 200 or "text/html" not in content_type:
        return response

    html = response.get_data(as_text=True)
    script_tags = [
        '<script src="/static/leaderboards.js"></script>',
        '<script src="/static/form-fixtures.js"></script>',
        '<script src="/static/standings-table.js"></script>',
        '<script src="/static/opponent-preview.js"></script>',
    ]
    for script_tag in script_tags:
        if script_tag not in html and "</body>" in html:
            html = html.replace("</body>", f"{script_tag}\n</body>", 1)

    response.set_data(html)
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response
