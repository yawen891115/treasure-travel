"""Check that your Claude API key works (billable; check provider pricing first).

python scripts/check_llm.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

from src import config  # noqa: E402

load_dotenv(config.ROOT / ".env")
if not os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-"):
    sys.exit("ANTHROPIC_API_KEY is missing in .env (it should start with sk-ant-). See guide 8.2.")

import anthropic  # noqa: E402

model = os.environ.get("LLM_MODEL")
if not model:
    sys.exit("Set LLM_MODEL to a model ID available in your Anthropic account.")
client = anthropic.Anthropic()
resp = client.messages.create(
    model=model,
    max_tokens=300,
    messages=[{"role": "user", "content": "In one sentence: what is a good rainy-day activity?"}],
)
text = " ".join(b.text for b in resp.content if b.type == "text")  # skip "thinking" blocks
print(f"model: {model}")
print(f"reply: {text}")
print(f"tokens: in={resp.usage.input_tokens} out={resp.usage.output_tokens}")
