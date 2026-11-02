import os, sys, json, base64, re, mimetypes, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
META_KEY = os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY", "")
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=META_KEY, timeout=60.0, max_retries=2)
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

def extract_agreement(path_or_text, allow_cache_fallback=True, force_cache=False):
    path = Path(path_or_text) if isinstance(path_or_text, (str, Path)) else None
    is_file = path and path.exists() and path.is_file()
    stem = path.stem if is_file else None
    cache_path = Path("outputs") / f"{stem}.json" if stem else None
    t0 = time.time()

    # 0. FORCED CACHE REPLAY (budget cap reached or explicitly requested)
    if force_cache and cache_path and cache_path.exists():
        try:
            cached_data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_data["_source"] = "cache"
            cached_data["_latency"] = round(time.time() - t0, 2)
            cached_data["_tokens"] = 0
            return cached_data
        except Exception:
            pass

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

    # 1. LIVE API Call (Default: cache is OFF unless API fails)
    try:
        r = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[{"role": "user", "content": content}]
        )
        data = _parse_json(r.choices[0].message.content)
        latency = round(time.time() - t0, 2)
        usage = getattr(r, "usage", None)
        total_toks = usage.total_tokens if usage else 0

        data["_source"] = "live"
        data["_latency"] = latency
        data["_tokens"] = total_toks

        if cache_path:
            try:
                Path("outputs").mkdir(exist_ok=True)
                cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return data
    except Exception as live_err:
        # 2. CACHE FALLBACK (Only if API failed / unreachable)
        if allow_cache_fallback and cache_path and cache_path.exists():
            try:
                cached_data = json.loads(cache_path.read_text(encoding="utf-8"))
                cached_data["_source"] = "cache"
                cached_data["_latency"] = round(time.time() - t0, 2)
                cached_data["_tokens"] = 0
                cached_data["_fallback_reason"] = str(live_err)
                return cached_data
            except Exception:
                pass
        raise live_err

if __name__ == "__main__":
    if len(sys.argv) > 1:
        res = extract_agreement(sys.argv[1])
        print(json.dumps(res, indent=2, ensure_ascii=False))

