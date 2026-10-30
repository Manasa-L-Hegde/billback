import os, base64, sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ.get("MODEL_API_KEY", ""), timeout=60.0, max_retries=2)

r = client.chat.completions.create(
    model="muse-spark-1.3",
    messages=[{"role": "user", "content": "Say hello in one short sentence."}],
)
print(r.choices[0].message.content)

# image test: python test_call.py samples/bill1.jpg
if len(sys.argv) > 1:
    b64 = base64.b64encode(open(sys.argv[1], "rb").read()).decode()
    r = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": "Extract every line item (name, qty, rate, amount) and the total as JSON."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
    )
    print(r.choices[0].message.content)
