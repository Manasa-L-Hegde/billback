import os, sys, json, base64, re, mimetypes
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ.get("MODEL_API_KEY", ""))
MODEL = "muse-spark-1.3"

SYSTEM_PROMPT = """You are reading a business agreement from a chat screenshot or message transcript between a buyer and vendor (may be in English or Hinglish).
Return ONLY valid JSON, with no other text or explanation:
{
  "agreed_rates": {"<item_name_lowercase>": number},
  "free_delivery": true | false | null,
  "source_quote": str
}
Rules:
- item names must be lowercase strings.
- rates must be plain numbers (e.g. 55 or 55.0), without currency symbols.
- free_delivery: true if free delivery was explicitly agreed/mentioned, false if delivery fee agreed, null if not mentioned.
- source_quote: the exact sentence or excerpt where the prices and delivery terms were agreed.
- NEVER guess or invent any rates. If unclear or not stated, omit the item or use null."""

def _image_part(path):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}

def _parse_json(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text)

def extract_agreement(path_or_text):
    path = Path(path_or_text) if isinstance(path_or_text, (str, Path)) else None
    is_file = path and path.exists() and path.is_file()
    
    if is_file and path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
        content = [
            {"type": "text", "text": SYSTEM_PROMPT},
            _image_part(str(path))
        ]
    else:
        text_content = path.read_text(encoding="utf-8") if is_file else str(path_or_text)
        content = [
            {"type": "text", "text": f"{SYSTEM_PROMPT}\n\nTranscript:\n{text_content}"}
        ]

    for attempt in range(2):
        r = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[{"role": "user", "content": content}]
        )
        try:
            return _parse_json(r.choices[0].message.content)
        except json.JSONDecodeError:
            if attempt == 1:
                raise

if __name__ == "__main__":
    if len(sys.argv) > 1:
        res = extract_agreement(sys.argv[1])
        print(json.dumps(res, indent=2, ensure_ascii=False))

