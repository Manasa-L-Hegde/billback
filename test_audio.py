import os, wave, struct, math, base64, json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

# Generate a small 3-second 440Hz sine wave WAV file
wav_path = "samples/test_audio.wav"
sample_rate = 16000
duration = 3.0  # seconds
num_samples = int(sample_rate * duration)

with wave.open(wav_path, "w") as wav_file:
    wav_file.setnchannels(1)  # mono
    wav_file.setsampwidth(2)  # 16-bit
    wav_file.setframerate(sample_rate)
    for i in range(num_samples):
        val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
        wav_file.writeframes(struct.pack("<h", val))

print(f"Generated {wav_path} ({os.path.getsize(wav_path)} bytes)")

b64_audio = base64.b64encode(open(wav_path, "rb").read()).decode()

# Format 1: standard OpenAI input_audio
print("\n--- Testing format 1: input_audio ---")
try:
    r = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Listen to this audio note and extract any agreed prices."},
                {"type": "input_audio", "input_audio": {"data": b64_audio, "format": "wav"}}
            ]
        }]
    )
    print("Success with input_audio:", r.choices[0].message.content)
except Exception as e:
    print("Error with input_audio:", type(e).__name__, str(e))

# Format 2: audio_url with data URL
print("\n--- Testing format 2: audio_url ---")
try:
    r = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Listen to this audio note and extract any agreed prices."},
                {"type": "audio_url", "audio_url": {"url": f"data:audio/wav;base64,{b64_audio}"}}
            ]
        }]
    )
    print("Success with audio_url:", r.choices[0].message.content)
except Exception as e:
    print("Error with audio_url:", type(e).__name__, str(e))

# Format 3: image_url format with audio mime
print("\n--- Testing format 3: image_url schema with audio/wav mime ---")
try:
    r = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Listen to this audio note and extract any agreed prices."},
                {"type": "image_url", "image_url": {"url": f"data:audio/wav;base64,{b64_audio}"}}
            ]
        }]
    )
    print("Success with image_url audio:", r.choices[0].message.content)
except Exception as e:
    print("Error with image_url audio:", type(e).__name__, str(e))

