import json

with open("config/api_keys.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

cfg["llm_provider"] = "openai"
cfg["llm_url"] = "https://api.groq.com/openai"
cfg["llm_model"] = "llama-3.3-70b-versatile"

with open("config/api_keys.json", "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
