import os, json, re, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
META_KEY = os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY", "")
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=META_KEY, timeout=60.0, max_retries=2)
MODEL = "muse-spark-1.3"

VENDOR_SYSTEM_PROMPT = """You are roleplaying as a small wholesale shop owner / billing manager responding to a billing dispute from a customer.
Every reply must be strictly labeled as:
Sender: Simulated vendor

Behavior rules based on strategy and round:
- If strategy is 'partial_50': offer exactly 50% credit/refund (e.g., claiming handling costs, split difference, or standard store policy).
- If strategy is 'deny': dispute the claim or claim no error occurred, offer Rs 0.
- If strategy is 'accept': acknowledge the mistake politely and grant full credit note / refund for the exact claimed amount.
- If strategy is 'realistic':
    - Round 1: push back or offer partial credit (e.g., 50%).
    - Round 2 (when customer presents undeniable proof like delivery challan or contract rate): concede and agree to full credit note.

Return ONLY valid JSON:
{
  "sender": "Simulated vendor",
  "reply_text": "polite business email text",
  "offer_amount": number,
  "decision": "accept" | "partial" | "deny"
}"""

def _parse_json(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text)

def _scripted_vendor_reply(claimed_amount, round_num, strategy):
    if strategy == "accept":
        return {
            "sender": "Simulated vendor",
            "reply_text": f"Dear Customer,\n\nUpon checking our delivery records against the signed challan, we confirm the discrepancy and approve full credit note of Rs. {claimed_amount}.\n\nRegards,\nSimulated Vendor Accounts Team",
            "offer_amount": float(claimed_amount),
            "decision": "accept"
        }
    elif strategy == "partial_50":
        offer = round(float(claimed_amount) * 0.5, 2)
        return {
            "sender": "Simulated vendor",
            "reply_text": f"Dear Customer,\n\nWe reviewed your dispute regarding invoice discrepancy. Due to warehouse processing fees and stock allocation, we can only offer a 50% credit note of Rs. {offer}. Please let us know if this is acceptable.\n\nRegards,\nSimulated Vendor Accounts Team",
            "offer_amount": offer,
            "decision": "partial"
        }
    elif strategy == "deny":
        return {
            "sender": "Simulated vendor",
            "reply_text": f"Dear Customer,\n\nWe have reviewed our dispatch logs and confirm that all billed items were dispatched as per invoice. We cannot accept the overcharge claim of Rs. {claimed_amount} and must deny the dispute.\n\nRegards,\nSimulated Vendor Accounts Team",
            "offer_amount": 0.0,
            "decision": "deny"
        }
    else: # realistic
        if round_num == 1:
            offer = round(float(claimed_amount) * 0.5, 2)
            return {
                "sender": "Simulated vendor",
                "reply_text": f"Dear Customer,\n\nWe reviewed your dispute. We can offer a partial 50% credit of Rs. {offer} to resolve this quickly.\n\nRegards,\nSimulated Vendor Accounts Team",
                "offer_amount": offer,
                "decision": "partial"
            }
        else:
            return {
                "sender": "Simulated vendor",
                "reply_text": f"Dear Customer,\n\nHaving verified your signed delivery challan and agreement, we concede the billing discrepancy and grant full credit of Rs. {claimed_amount}.\n\nRegards,\nSimulated Vendor Accounts Team",
                "offer_amount": float(claimed_amount),
                "decision": "accept"
            }

def simulate_vendor_reply(dispute_text, claimed_amount, round_num=1, strategy="realistic", allow_fallback=True, force_cache=False):
    t0 = time.time()
    
    # 0. FORCED CACHE REPLAY (budget cap reached or scripted replay)
    if force_cache:
        fallback_res = _scripted_vendor_reply(claimed_amount, round_num, strategy)
        fallback_res["source"] = "cache"
        fallback_res["latency"] = round(time.time() - t0, 2)
        fallback_res["tokens"] = 0
        return fallback_res

    prompt = (
        f"Incoming dispute email from customer:\n\"\"\"\n{dispute_text}\n\"\"\"\n\n"
        f"Claimed overcharge amount: Rs. {claimed_amount}\n"
        f"Negotiation Round: {round_num}\n"
        f"Strategy directive: {strategy}\n\n"
        f"Draft the vendor's response and offer."
    )

    # 1. LIVE API Call (Default: cache/scripted is OFF unless API fails)
    try:
        r = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": VENDOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        data = _parse_json(r.choices[0].message.content)
        data["sender"] = "Simulated vendor"
        latency = round(time.time() - t0, 2)
        usage = getattr(r, "usage", None)
        data["source"] = "live"
        data["latency"] = latency
        data["tokens"] = usage.total_tokens if usage else 0
        return data
    except Exception as live_err:
        if allow_fallback:
            fallback_res = _scripted_vendor_reply(claimed_amount, round_num, strategy)
            fallback_res["source"] = "cache"
            fallback_res["latency"] = round(time.time() - t0, 2)
            fallback_res["tokens"] = 0
            fallback_res["fallback_reason"] = str(live_err)
            return fallback_res
        raise live_err

if __name__ == "__main__":
    reply = simulate_vendor_reply("You billed 12 bottles of Cooking Oil, but slip shows only 6 delivered. Overcharge: Rs. 780.", 780.0, strategy="partial_50")
    print(json.dumps(reply, indent=2))

