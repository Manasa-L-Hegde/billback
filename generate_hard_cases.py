import os, json, math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONTS_DIR = Path("C:/Windows/Fonts")
SAMPLES_DIR = Path("samples")
TRUTH_DIR = Path("samples/truth")
SAMPLES_DIR.mkdir(exist_ok=True)
TRUTH_DIR.mkdir(exist_ok=True)

def get_font(name, size):
    p = FONTS_DIR / name
    if p.exists():
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            pass
    return ImageFont.load_default()

f_consolab = get_font("consolab.ttf", 20)
f_consola = get_font("consola.ttf", 17)
f_arialb = get_font("arialbd.ttf", 20)
f_arial = get_font("arial.ttf", 17)
f_title = get_font("arialbd.ttf", 26)

# 1. Update test_slip5.jpg (Remove giveaway note: list quantities ONLY)
def render_clean_slip5():
    W, H = 700, 750
    paper = Image.new("RGB", (W, H), (250, 250, 245))
    draw = ImageDraw.Draw(paper)
    
    draw.text((W // 2, 50), "CITY WHOLESALE MART", fill=(40, 40, 40), font=f_title, anchor="mt")
    draw.text((W // 2, 90), "DELIVERY CHALLAN", fill=(40, 40, 40), font=f_arialb, anchor="mt")
    draw.line([(50, 125), (W - 50, 125)], fill=(120, 120, 120), width=2)
    
    draw.text((60, 145), "Date: 2026-10-25", fill=(40, 40, 40), font=f_arialb)
    draw.text((W - 60, 145), "Challan No: CH-9021", fill=(40, 40, 40), font=f_arialb, anchor="ra")
    draw.line([(50, 180), (W - 50, 180)], fill=(120, 120, 120), width=1)
    
    # Header
    draw.text((60, 205), "Delivered Item", fill=(40, 40, 40), font=f_arialb)
    draw.text((450, 205), "Quantity", fill=(40, 40, 40), font=f_arialb, anchor="ma")
    draw.text((W - 80, 205), "Unit", fill=(40, 40, 40), font=f_arialb, anchor="ma")
    draw.line([(50, 235), (W - 50, 235)], fill=(120, 120, 120), width=2)
    
    items = [
        ("Cooking Oil 1L", 6, "bottle"),
        ("Sugar 5kg", 2, "bag"),
        ("Tea Powder 500g", 3, "pack")
    ]
    y = 260
    for name, qty, unit in items:
        draw.text((60, y), name, fill=(40, 40, 40), font=f_arial)
        draw.text((450, y), str(qty), fill=(40, 40, 40), font=f_arial, anchor="ma")
        draw.text((W - 80, y), unit, fill=(40, 40, 40), font=f_arial, anchor="ma")
        y += 45
        
    draw.line([(50, y + 20), (W - 50, y + 20)], fill=(120, 120, 120), width=1)
    draw.text((60, y + 45), "Received in good condition.", fill=(100, 100, 100), font=f_arial)
    draw.text((W - 120, y + 100), "Receiver Sign: [Verified]", fill=(40, 40, 40), font=f_arialb, anchor="mt")
    
    # Save image & update truth JSON
    paper.save(SAMPLES_DIR / "test_slip5.jpg", "JPEG", quality=90)
    truth5 = {
        "vendor": "City Wholesale Mart",
        "date": "2026-10-25",
        "items": [
            {"name": "Cooking Oil 1L", "qty": 6, "unit": "bottle"},
            {"name": "Sugar 5kg", "qty": 2, "unit": "bag"},
            {"name": "Tea Powder 500g", "qty": 3, "unit": "pack"}
        ],
        "delivery_charge": 0.0,
        "confidence": 0.95,
        "notes": "Received in good condition."
    }
    (TRUTH_DIR / "test_slip5.json").write_text(json.dumps(truth5, indent=2), encoding="utf-8")
    print("Updated clean test_slip5.jpg (no giveaway note)")

render_clean_slip5()

# 2. Hard Case A: Rotated (-4.5 deg) and Blurry Bill (test_hard_blurry.jpg)
def render_blurry_rotated():
    W, H = 700, 850
    paper = Image.new("RGB", (W, H), (248, 245, 238))
    draw = ImageDraw.Draw(paper)
    
    draw.text((W // 2, 40), "NATIONAL STATIONERY MART", fill=(45, 45, 45), font=f_title, anchor="mt")
    draw.text((W // 2, 80), "CASH BILL / ESTIMATE", fill=(70, 70, 70), font=f_arial, anchor="mt")
    draw.line([(40, 115), (W - 40, 115)], fill=(130, 130, 130), width=2)
    
    draw.text((50, 130), "Inv: NSM-4412", fill=(45, 45, 45), font=f_arialb)
    draw.text((W - 50, 130), "Date: 2026-10-28", fill=(45, 45, 45), font=f_arialb, anchor="ra")
    draw.line([(40, 160), (W - 40, 160)], fill=(130, 130, 130), width=1)
    
    draw.text((50, 180), "Item", fill=(45, 45, 45), font=f_arialb)
    draw.text((360, 180), "Qty", fill=(45, 45, 45), font=f_arialb, anchor="ma")
    draw.text((450, 180), "Rate", fill=(45, 45, 45), font=f_arialb, anchor="ra")
    draw.text((W - 50, 180), "Amount", fill=(45, 45, 45), font=f_arialb, anchor="ra")
    draw.line([(40, 210), (W - 40, 210)], fill=(130, 130, 130), width=2)
    
    items = [
        ("Whiteboard Markers (Set of 4)", 5, 180.0, 900.0),
        ("Correction Tape", 10, 45.0, 450.0),
        ("Heavy Duty Stapler", 2, 350.0, 700.0),
        ("Staple Pins 24/6", 8, 25.0, 200.0)
    ]
    y = 230
    for name, qty, rate, amt in items:
        draw.text((50, y), name, fill=(50, 50, 50), font=f_arial)
        draw.text((360, y), str(qty), fill=(50, 50, 50), font=f_arial, anchor="ma")
        draw.text((450, y), f"{rate:.2f}", fill=(50, 50, 50), font=f_arial, anchor="ra")
        draw.text((W - 50, y), f"{amt:.2f}", fill=(50, 50, 50), font=f_arial, anchor="ra")
        y += 40
        
    y += 20
    draw.line([(40, y), (W - 40, y)], fill=(130, 130, 130), width=1)
    y += 20
    draw.text((450, y), "Subtotal:", fill=(45, 45, 45), font=f_arialb, anchor="ra")
    draw.text((W - 50, y), "2250.00", fill=(45, 45, 45), font=f_arial, anchor="ra")
    y += 35
    draw.text((450, y), "Tax (12%):", fill=(45, 45, 45), font=f_arialb, anchor="ra")
    draw.text((W - 50, y), "270.00", fill=(45, 45, 45), font=f_arial, anchor="ra")
    y += 35
    draw.text((450, y), "Grand Total:", fill=(45, 45, 45), font=f_title, anchor="ra")
    draw.text((W - 50, y), "2520.00", fill=(45, 45, 45), font=f_title, anchor="ra")
    
    # Apply motion/camera blur (radius=1.3)
    blurry_paper = paper.filter(ImageFilter.GaussianBlur(1.3))
    
    # Rotate by -4.5 degrees with background desk
    bg = Image.new("RGB", (W + 120, H + 120), (205, 200, 192))
    rot_paper = blurry_paper.rotate(-4.5, resample=Image.BICUBIC, expand=True)
    ox = (bg.width - rot_paper.width) // 2
    oy = (bg.height - rot_paper.height) // 2
    bg.paste(rot_paper, (ox, oy))
    
    out_img = SAMPLES_DIR / "test_hard_blurry.jpg"
    bg.save(out_img, "JPEG", quality=85)
    
    truth_blurry = {
        "vendor": "National Stationery Mart",
        "date": "2026-10-28",
        "invoice_no": "NSM-4412",
        "items": [
            {"name": "Whiteboard Markers (Set of 4)", "qty": 5, "unit": None, "rate": 180.0, "amount": 900.0},
            {"name": "Correction Tape", "qty": 10, "unit": None, "rate": 45.0, "amount": 450.0},
            {"name": "Heavy Duty Stapler", "qty": 2, "unit": None, "rate": 350.0, "amount": 700.0},
            {"name": "Staple Pins 24/6", "qty": 8, "unit": None, "rate": 25.0, "amount": 200.0}
        ],
        "subtotal": 2250.0,
        "tax_total": 270.0,
        "delivery_charge": 0.0,
        "grand_total": 2520.0,
        "confidence": 0.85,
        "notes": "Rotated (-4.5 deg) with slight camera blur test"
    }
    (TRUTH_DIR / "test_hard_blurry.json").write_text(json.dumps(truth_blurry, indent=2), encoding="utf-8")
    print(f"Generated {out_img}")

render_blurry_rotated()

# 3. Hard Case B: Different Layout (Rate BEFORE Qty, 2-column header box)
def render_diff_layout():
    W, H = 760, 900
    paper = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(paper)
    
    # Modern corporate sidebar / top bar
    draw.rectangle([0, 0, W, 8], fill=(37, 99, 235)) # Blue accent top bar
    
    # Left: Vendor Info
    draw.text((50, 40), "GLOBAL LOGISTICS & HARDWARE", fill=(17, 24, 39), font=f_title)
    draw.text((50, 75), "Industrial Area Phase 2, Bangalore", fill=(107, 114, 128), font=f_arial)
    
    # Right Box: Invoice Meta (2-column layout)
    draw.rectangle([W - 280, 35, W - 50, 115], outline=(209, 213, 219), width=1, fill=(249, 250, 251))
    draw.text((W - 265, 45), "INVOICE #:", fill=(75, 85, 99), font=f_arialb)
    draw.text((W - 70, 45), "GLH-709", fill=(17, 24, 39), font=f_arialb, anchor="ra")
    draw.text((W - 265, 80), "DATE:", fill=(75, 85, 99), font=f_arialb)
    draw.text((W - 70, 80), "2026-10-29", fill=(17, 24, 39), font=f_arialb, anchor="ra")
    
    draw.line([(50, 140), (W - 50, 140)], fill=(229, 231, 235), width=2)
    
    # Table with unusual column order: [Description | Unit Price (Rate) | Quantity | Unit | Total Amount]
    draw.rectangle([50, 160, W - 50, 195], fill=(243, 244, 246))
    draw.text((65, 172), "Description", fill=(55, 65, 81), font=f_arialb)
    draw.text((410, 172), "Rate (INR)", fill=(55, 65, 81), font=f_arialb, anchor="ra")
    draw.text((490, 172), "Qty", fill=(55, 65, 81), font=f_arialb, anchor="ma")
    draw.text((560, 172), "Unit", fill=(55, 65, 81), font=f_arialb, anchor="ma")
    draw.text((W - 65, 172), "Total (INR)", fill=(55, 65, 81), font=f_arialb, anchor="ra")
    
    items = [
        ("Industrial Safety Helmets", 320.0, 15, "pcs", 4800.0),
        ("Safety Goggles Anti-Fog", 85.0, 20, "pcs", 1700.0),
        ("Leather Work Gloves", 110.0, 25, "pair", 2750.0)
    ]
    y = 215
    for name, rate, qty, unit, amt in items:
        draw.text((65, y), name, fill=(31, 41, 55), font=f_arial)
        draw.text((410, y), f"{rate:.2f}", fill=(31, 41, 55), font=f_arial, anchor="ra")
        draw.text((490, y), str(qty), fill=(31, 41, 55), font=f_arial, anchor="ma")
        draw.text((560, y), unit, fill=(31, 41, 55), font=f_arial, anchor="ma")
        draw.text((W - 65, y), f"{amt:.2f}", fill=(31, 41, 55), font=f_arial, anchor="ra")
        y += 45
        draw.line([(50, y - 10), (W - 50, y - 10)], fill=(243, 244, 246), width=1)
        
    y += 20
    draw.text((490, y), "Subtotal:", fill=(75, 85, 99), font=f_arialb, anchor="ra")
    draw.text((W - 65, y), "9250.00", fill=(17, 24, 39), font=f_arial, anchor="ra")
    y += 35
    draw.text((490, y), "Tax (18% GST):", fill=(75, 85, 99), font=f_arialb, anchor="ra")
    draw.text((W - 65, y), "1665.00", fill=(17, 24, 39), font=f_arial, anchor="ra")
    y += 35
    draw.text((490, y), "Grand Total:", fill=(17, 24, 39), font=f_title, anchor="ra")
    draw.text((W - 65, y), "10915.00", fill=(17, 24, 39), font=f_title, anchor="ra")
    
    out_img = SAMPLES_DIR / "test_hard_layout.jpg"
    paper.save(out_img, "JPEG", quality=92)
    
    truth_layout = {
        "vendor": "Global Logistics & Hardware",
        "date": "2026-10-29",
        "invoice_no": "GLH-709",
        "items": [
            {"name": "Industrial Safety Helmets", "qty": 15, "unit": "pcs", "rate": 320.0, "amount": 4800.0},
            {"name": "Safety Goggles Anti-Fog", "qty": 20, "unit": "pcs", "rate": 85.0, "amount": 1700.0},
            {"name": "Leather Work Gloves", "qty": 25, "unit": "pair", "rate": 110.0, "amount": 2750.0}
        ],
        "subtotal": 9250.0,
        "tax_total": 1665.0,
        "delivery_charge": 0.0,
        "grand_total": 10915.0,
        "confidence": 0.95,
        "notes": "Different layout test: Rate before Qty column, modern 2-col header"
    }
    (TRUTH_DIR / "test_hard_layout.json").write_text(json.dumps(truth_layout, indent=2), encoding="utf-8")
    print(f"Generated {out_img}")

render_diff_layout()

