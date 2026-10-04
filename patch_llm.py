import re

with open("core/llm_client.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace `requests.post(` with `_post(`
code = code.replace("requests.post(", "_req_post(")

# Add _req_post definition near the top
inject = """
def _req_post(url, **kwargs):
    import os
    headers = kwargs.get("headers", {})
    if "api.groq.com" in url and os.environ.get("GROQ_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['GROQ_API_KEY']}"
    elif "openrouter.ai" in url and os.environ.get("OPENROUTER_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENROUTER_API_KEY']}"
    kwargs["headers"] = headers
    return requests.post(url, **kwargs)
"""

code = code.replace("import requests", "import requests\n" + inject)

with open("core/llm_client.py", "w", encoding="utf-8") as f:
    f.write(code)
