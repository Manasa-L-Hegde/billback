import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path("C:/Windows/Fonts")
SAMPLES_DIR = Path("samples")
SAMPLES_DIR.mkdir(exist_ok=True)

def get_font(name, size):
    p = FONTS_DIR / name
    if p.exists():
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            pass
    return ImageFont.load_default()

f_header = get_font("segoeui.ttf", 22)
f_sub = get_font("segoeui.ttf", 15)
f_msg = get_font("segoeui.ttf", 18)
f_time = get_font("segoeui.ttf", 13)

def render_chat(messages, title="Vendor Direct Message", filename="test_chat1.jpg"):
    W, H = 540, 680
    img = Image.new("RGB", (W, H), (242, 244, 247))
    draw = ImageDraw.Draw(img)

    # Top app bar (neutral, clean)
    draw.rectangle([0, 0, W, 75], fill=(255, 255, 255))
    draw.line([(0, 75), (W, 75)], fill=(225, 228, 232), width=1)
    
    # Avatar circle
    draw.ellipse([20, 16, 62, 58], fill=(99, 102, 241))
    draw.text((41, 37), title[0].upper(), fill=(255, 255, 255), font=f_header, anchor="mm")
    
    # Title & status
    draw.text((75, 23), title, fill=(30, 41, 59), font=f_header)
    draw.text((75, 48), "Online", fill=(16, 185, 129), font=f_sub)

    # Date badge
    draw.rectangle([W // 2 - 50, 90, W // 2 + 50, 115], fill=(225, 229, 235))
    draw.text((W // 2, 102), "TODAY", fill=(100, 116, 139), font=f_time, anchor="mm")

    y = 135
    for msg in messages:
        sender = msg["sender"] # "user" (outgoing) or "vendor" (incoming)
        text = msg["text"]
        time_str = msg.get("time", "10:15 AM")

        # Estimate bubble size
        lines = []
        words = text.split()
        cur_line = []
        for w in words:
            cur_line.append(w)
            bbox = draw.textbbox((0, 0), " ".join(cur_line), font=f_msg)
            if bbox[2] - bbox[0] > 320:
                cur_line.pop()
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        bubble_w = max(draw.textbbox((0, 0), l, font=f_msg)[2] for l in lines) + 36
        bubble_w = max(bubble_w, 120)
        bubble_h = len(lines) * 26 + 32

        if sender == "user":
            bx = W - 20 - bubble_w
            bubble_color = (79, 70, 229) # Indigo
            txt_color = (255, 255, 255)
            time_color = (224, 231, 255)
        else:
            bx = 20
            bubble_color = (255, 255, 255) # Clean White
            txt_color = (30, 41, 59)
            time_color = (148, 163, 184)

        # Bubble rounded rect
        draw.rounded_rectangle([bx, y, bx + bubble_w, y + bubble_h], radius=14, fill=bubble_color)
        
        # Text
        ty = y + 10
        for l in lines:
            draw.text((bx + 16, ty), l, fill=txt_color, font=f_msg)
            ty += 24
        
        # Timestamp
        draw.text((bx + bubble_w - 14, y + bubble_h - 14), time_str, fill=time_color, font=f_time, anchor="rb")
        y += bubble_h + 16

    out_path = SAMPLES_DIR / filename
    img.save(out_path, "JPEG", quality=92)
    print(f"Generated chat screenshot: {out_path}")

# Chat 1: Direct English confirmation for Rice
render_chat([
    {"sender": "user", "text": "Hi, need Sona Masoori Rice 50kg bag. What is your rate?", "time": "10:12 AM"},
    {"sender": "vendor", "text": "Best price for 50kg bag is Rs 55 per kg.", "time": "10:14 AM"},
    {"sender": "user", "text": "Agreed at Rs 55/kg. Please dispatch today.", "time": "10:15 AM"},
    {"sender": "vendor", "text": "Confirmed, dispatching at 55/kg.", "time": "10:16 AM"}
], title="Kaveri Grain Stores", filename="test_chat1.jpg")

# Chat 2: Hinglish confirmation for Rice and Toor Dal with free delivery
render_chat([
    {"sender": "user", "text": "Bhai Sona Masoori Rice ka rate kya fix hua tha?", "time": "11:02 AM"},
    {"sender": "vendor", "text": "Bhai Rice 55 per kg aur Toor Dal 140 per kg fix hua hai. Delivery free rahega.", "time": "11:04 AM"},
    {"sender": "user", "text": "Theek hai bhai, 50kg rice bhej do.", "time": "11:05 AM"},
    {"sender": "vendor", "text": "Pakka, free delivery ke sath nikal diya hai.", "time": "11:06 AM"}
], title="Kaveri Grain Stores", filename="test_chat2.jpg")

# Chat 3: Fresh Produce confirmation with Free Delivery
render_chat([
    {"sender": "user", "text": "Please confirm rate for Tomatoes, Onions and Potatoes.", "time": "09:30 AM"},
    {"sender": "vendor", "text": "Tomatoes at 35, Onions at 40, Potatoes at 30/kg. Free delivery on this order.", "time": "09:32 AM"},
    {"sender": "user", "text": "Confirmed at these rates, thank you.", "time": "09:33 AM"}
], title="Apex Fresh Produce", filename="test_chat3.jpg")

