import os, json, math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

random.seed(42)

TRUTH_DIR = Path("samples/truth")
SAMPLES_DIR = Path("samples")
TRUTH_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

FONTS_DIR = Path("C:/Windows/Fonts")

def get_font(name, size):
    font_path = FONTS_DIR / name
    if font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            pass
    return ImageFont.load_default()

FONT_CONSOLA = "consola.ttf"
FONT_CONSOLA_B = "consolab.ttf"
FONT_ARIAL = "arial.ttf"
FONT_ARIAL_B = "arialbd.ttf"
FONT_HAND = "segoepr.ttf" if (FONTS_DIR / "segoepr.ttf").exists() else ("Inkfree.ttf" if (FONTS_DIR / "Inkfree.ttf").exists() else "comic.ttf")
FONT_HAND_B = "segoeprb.ttf" if (FONTS_DIR / "segoeprb.ttf").exists() else FONT_HAND

def apply_perspective_and_shadow(paper_img, angle=1.2):
    pw, ph = paper_img.size
    margin = 80
    bg_w = pw + margin * 2
    bg_h = ph + margin * 2

    # Background surface (wooden/desk tabletop color)
    bg = Image.new("RGB", (bg_w, bg_h), (218, 214, 206))
    
    # Draw soft subtle gradient/texture on bg
    bg_draw = ImageDraw.Draw(bg)
    for y in range(0, bg_h, 4):
        tint = int(10 * math.sin(y / 40.0))
        bg_draw.line([(0, y), (bg_w, y)], fill=(218 + tint, 214 + tint, 206 + tint))

    # Drop shadow
    shadow_mask = Image.new("L", (pw + 30, ph + 30), 0)
    sdraw = ImageDraw.Draw(shadow_mask)
    sdraw.rectangle([10, 10, pw + 20, ph + 20], fill=140)
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(14))
    
    # Shadow layer
    shadow_img = Image.new("RGBA", (bg_w, bg_h), (0, 0, 0, 0))
    shadow_img.paste((40, 40, 40, 130), (margin - 5, margin + 8), shadow_mask)
    
    # Rotate paper
    paper_rgba = paper_img.convert("RGBA")
    rotated_paper = paper_rgba.rotate(angle, resample=Image.BICUBIC, expand=True)
    rotated_shadow = shadow_img.rotate(angle, resample=Image.BICUBIC, expand=False)
    
    # Composite
    bg.paste(rotated_shadow, (0, 0), rotated_shadow)
    
    # Center rotated paper
    rw, rh = rotated_paper.size
    ox = (bg_w - rw) // 2
    oy = (bg_h - rh) // 2
    bg.paste(rotated_paper, (ox, oy), rotated_paper)
    return bg

# Invoices data definitions
DATA_BILLS = [
    {
        "id": "test_bill1",
        "style": "printed_receipt",
        "angle": -1.5,
        "truth": {
            "vendor": "Metro Supplies",
            "date": "2026-10-15",
            "invoice_no": "INV-1021",
            "items": [
                {"name": "Printer Paper A4", "qty": 5, "unit": "ream", "rate": 350.0, "amount": 1750.0},
                {"name": "Gel Pens Blue (Pack)", "qty": 4, "unit": "pack", "rate": 120.0, "amount": 580.0},
                {"name": "Sticky Notes", "qty": 3, "unit": "pad", "rate": 60.0, "amount": 180.0}
            ],
            "subtotal": 2510.0,
            "tax_total": 125.5,
            "delivery_charge": 0.0,
            "grand_total": 2635.5,
            "confidence": 0.95,
            "notes": "Error planted: Gel Pens Blue 4 x 120 = 480, but billed 580.0"
        }
    },
    {
        "id": "test_bill2",
        "style": "handwritten",
        "angle": 1.8,
        "truth": {
            "vendor": "Sri Lakshmi Hardware",
            "date": "2026-10-18",
            "invoice_no": "SL-408",
            "items": [
                {"name": "Cement Bag 50kg", "qty": 10, "unit": "bag", "rate": 380.0, "amount": 3800.0},
                {"name": "Steel Wire Roll", "qty": 2, "unit": "roll", "rate": 450.0, "amount": 900.0},
                {"name": "PVC Pipe 10ft", "qty": 5, "unit": "piece", "rate": 220.0, "amount": 1100.0}
            ],
            "subtotal": 6200.0,
            "tax_total": 0.0,
            "delivery_charge": 200.0,
            "grand_total": 6400.0,
            "confidence": 0.9,
            "notes": "Error planted: Line items sum to 5800.0, but subtotal billed is 6200.0"
        }
    },
    {
        "id": "test_bill3",
        "style": "printed_invoice",
        "angle": -0.8,
        "truth": {
            "vendor": "Apex Fresh Produce",
            "date": "2026-10-20",
            "invoice_no": "APX-8832",
            "items": [
                {"name": "Tomatoes", "qty": 20, "unit": "kg", "rate": 35.0, "amount": 700.0},
                {"name": "Onions", "qty": 30, "unit": "kg", "rate": 40.0, "amount": 1200.0},
                {"name": "Potatoes", "qty": 25, "unit": "kg", "rate": 30.0, "amount": 750.0}
            ],
            "subtotal": 2650.0,
            "tax_total": 0.0,
            "delivery_charge": 350.0,
            "grand_total": 3000.0,
            "confidence": 0.95,
            "notes": "Error planted: Delivery charge of 350.0 added, not in delivery slip (slip has free delivery)"
        }
    },
    {
        "id": "test_bill4",
        "style": "handwritten",
        "angle": 1.2,
        "truth": {
            "vendor": "Kaveri Grain Stores",
            "date": "2026-10-22",
            "invoice_no": "CB-512",
            "items": [
                {"name": "Sona Masoori Rice", "qty": 50, "unit": "kg", "rate": 62.0, "amount": 3100.0},
                {"name": "Toor Dal", "qty": 10, "unit": "kg", "rate": 140.0, "amount": 1400.0},
                {"name": "Wheat Flour", "qty": 20, "unit": "kg", "rate": 42.0, "amount": 840.0}
            ],
            "subtotal": 5340.0,
            "tax_total": 0.0,
            "delivery_charge": 100.0,
            "grand_total": 5440.0,
            "confidence": 0.9,
            "notes": "Error planted: Rice billed at 62.0/kg, higher than agreed rate of 55.0/kg"
        }
    },
    {
        "id": "test_bill5",
        "style": "printed_receipt",
        "angle": -1.1,
        "truth": {
            "vendor": "City Wholesale Mart",
            "date": "2026-10-25",
            "invoice_no": "CWM-9021",
            "items": [
                {"name": "Cooking Oil 1L", "qty": 6, "unit": "bottle", "rate": 130.0, "amount": 780.0},
                {"name": "Sugar 5kg", "qty": 2, "unit": "bag", "rate": 210.0, "amount": 420.0},
                {"name": "Cooking Oil 1L", "qty": 6, "unit": "bottle", "rate": 130.0, "amount": 780.0},
                {"name": "Tea Powder 500g", "qty": 3, "unit": "pack", "rate": 160.0, "amount": 480.0}
            ],
            "subtotal": 2460.0,
            "tax_total": 123.0,
            "delivery_charge": 0.0,
            "grand_total": 2583.0,
            "confidence": 0.95,
            "notes": "Error planted: Cooking Oil 1L is billed twice (duplicate item)"
        }
    },
    {
        "id": "test_bill6",
        "style": "printed_invoice",
        "angle": 0.7,
        "truth": {
            "vendor": "TechZone Electronics",
            "date": "2026-10-27",
            "invoice_no": "TZ-1409",
            "items": [
                {"name": "HDMI Cable 2m", "qty": 3, "unit": "piece", "rate": 250.0, "amount": 750.0},
                {"name": "USB-C Hub 6-in-1", "qty": 1, "unit": "piece", "rate": 1450.0, "amount": 1450.0},
                {"name": "Wireless Mouse", "qty": 2, "unit": "piece", "rate": 600.0, "amount": 1200.0}
            ],
            "subtotal": 3400.0,
            "tax_total": 612.0,
            "delivery_charge": 80.0,
            "grand_total": 4092.0,
            "confidence": 0.98,
            "notes": "Fully correct bill without errors"
        }
    }
]

DATA_SLIPS = [
    {
        "id": "test_slip3",
        "for_bill": "test_bill3",
        "style": "printed_invoice",
        "angle": 1.1,
        "truth": {
            "vendor": "Apex Fresh Produce",
            "date": "2026-10-20",
            "items": [
                {"name": "Tomatoes", "qty": 20, "unit": "kg"},
                {"name": "Onions", "qty": 30, "unit": "kg"},
                {"name": "Potatoes", "qty": 25, "unit": "kg"}
            ],
            "confidence": 0.95,
            "notes": "Delivery Slip #DS-8832. Free Delivery agreed."
        }
    },
    {
        "id": "test_slip5",
        "for_bill": "test_bill5",
        "style": "printed_receipt",
        "angle": -1.4,
        "truth": {
            "vendor": "City Wholesale Mart",
            "date": "2026-10-25",
            "items": [
                {"name": "Cooking Oil 1L", "qty": 6, "unit": "bottle"},
                {"name": "Sugar 5kg", "qty": 2, "unit": "bag"},
                {"name": "Tea Powder 500g", "qty": 3, "unit": "pack"}
            ],
            "confidence": 0.95,
            "notes": "Challan #CH-9021. Cooking Oil received only once (6 bottles)."
        }
    }
]

def render_invoice_image(bill_data):
    style = bill_data["style"]
    truth = bill_data["truth"]
    
    W, H = 720, 960
    paper_color = (252, 250, 246) if style != "handwritten" else (255, 253, 242)
    paper = Image.new("RGB", (W, H), paper_color)
    draw = ImageDraw.Draw(paper)
    
    # Fonts
    if style == "printed_receipt":
        f_title = get_font(FONT_CONSOLA_B, 26)
        f_bold = get_font(FONT_CONSOLA_B, 18)
        f_regular = get_font(FONT_CONSOLA, 17)
        text_color = (35, 35, 35)
        line_color = (80, 80, 80)
    elif style == "handwritten":
        f_title = get_font(FONT_HAND_B, 28)
        f_bold = get_font(FONT_HAND_B, 20)
        f_regular = get_font(FONT_HAND, 18)
        text_color = (25, 40, 95)  # blue pen ink
        line_color = (70, 90, 140)
    else: # printed_invoice
        f_title = get_font(FONT_ARIAL_B, 28)
        f_bold = get_font(FONT_ARIAL_B, 18)
        f_regular = get_font(FONT_ARIAL, 17)
        text_color = (30, 30, 30)
        line_color = (120, 120, 120)

    # Header
    y = 50
    draw.text((W // 2, y), truth["vendor"].upper(), fill=text_color, font=f_title, anchor="mt")
    y += 45
    sub_title = "TAX INVOICE / CASH BILL"
    draw.text((W // 2, y), sub_title, fill=text_color, font=f_regular, anchor="mt")
    y += 35
    
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=2)
    y += 15
    
    # Meta info
    draw.text((60, y), f"Invoice No: {truth['invoice_no']}", fill=text_color, font=f_bold)
    draw.text((W - 60, y), f"Date: {truth['date']}", fill=text_color, font=f_bold, anchor="ra")
    y += 35
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=1)
    y += 15

    # Table Header
    draw.text((60, y), "Item / Description", fill=text_color, font=f_bold)
    draw.text((360, y), "Qty", fill=text_color, font=f_bold, anchor="ma")
    draw.text((450, y), "Unit", fill=text_color, font=f_bold, anchor="ma")
    draw.text((540, y), "Rate", fill=text_color, font=f_bold, anchor="ra")
    draw.text((W - 60, y), "Amount", fill=text_color, font=f_bold, anchor="ra")
    y += 30
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=2)
    y += 15

    # Items
    for it in truth["items"]:
        draw.text((60, y), it["name"], fill=text_color, font=f_regular)
        draw.text((360, y), str(it["qty"]), fill=text_color, font=f_regular, anchor="ma")
        draw.text((450, y), str(it["unit"]), fill=text_color, font=f_regular, anchor="ma")
        draw.text((540, y), f"{it['rate']:.2f}", fill=text_color, font=f_regular, anchor="ra")
        draw.text((W - 60, y), f"{it['amount']:.2f}", fill=text_color, font=f_regular, anchor="ra")
        y += 35
    
    y = max(y + 20, 520)
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=1)
    y += 20

    # Totals block
    right_label_x = 480
    right_val_x = W - 60

    if truth.get("subtotal") is not None:
        draw.text((right_label_x, y), "Subtotal:", fill=text_color, font=f_bold, anchor="ra")
        draw.text((right_val_x, y), f"{truth['subtotal']:.2f}", fill=text_color, font=f_regular, anchor="ra")
        y += 30

    if truth.get("tax_total") is not None and truth["tax_total"] > 0:
        draw.text((right_label_x, y), "Tax / GST:", fill=text_color, font=f_bold, anchor="ra")
        draw.text((right_val_x, y), f"{truth['tax_total']:.2f}", fill=text_color, font=f_regular, anchor="ra")
        y += 30

    if truth.get("delivery_charge") is not None and truth["delivery_charge"] > 0:
        draw.text((right_label_x, y), "Delivery Charge:", fill=text_color, font=f_bold, anchor="ra")
        draw.text((right_val_x, y), f"{truth['delivery_charge']:.2f}", fill=text_color, font=f_regular, anchor="ra")
        y += 30

    draw.line([(right_label_x - 60, y), (W - 50, y)], fill=line_color, width=2)
    y += 15
    draw.text((right_label_x, y), "Grand Total:", fill=text_color, font=f_title, anchor="ra")
    draw.text((right_val_x, y), f"{truth['grand_total']:.2f}", fill=text_color, font=f_title, anchor="ra")
    y += 50
    draw.line([(right_label_x - 60, y), (W - 50, y)], fill=line_color, width=2)
    
    # Footer
    y = H - 90
    if style == "handwritten":
        draw.text((W - 120, y), "Authorized Signatory", fill=text_color, font=f_regular, anchor="mt")
    else:
        draw.text((W // 2, y), "Thank you for your business!", fill=text_color, font=f_regular, anchor="mt")

    # Add realistic tilt, perspective and shadow
    final_img = apply_perspective_and_shadow(paper, angle=bill_data["angle"])
    return final_img

def render_slip_image(slip_data):
    style = slip_data["style"]
    truth = slip_data["truth"]
    
    W, H = 700, 800
    paper_color = (250, 250, 245)
    paper = Image.new("RGB", (W, H), paper_color)
    draw = ImageDraw.Draw(paper)
    
    if style == "printed_receipt":
        f_title = get_font(FONT_CONSOLA_B, 24)
        f_bold = get_font(FONT_CONSOLA_B, 18)
        f_regular = get_font(FONT_CONSOLA, 17)
        text_color = (40, 40, 40)
        line_color = (90, 90, 90)
    else:
        f_title = get_font(FONT_ARIAL_B, 26)
        f_bold = get_font(FONT_ARIAL_B, 18)
        f_regular = get_font(FONT_ARIAL, 17)
        text_color = (30, 30, 30)
        line_color = (120, 120, 120)

    y = 50
    draw.text((W // 2, y), truth["vendor"].upper(), fill=text_color, font=f_title, anchor="mt")
    y += 40
    draw.text((W // 2, y), "DELIVERY CHALLAN / GOODS RECEIPT SLIP", fill=text_color, font=f_bold, anchor="mt")
    y += 35
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=2)
    y += 15

    draw.text((60, y), f"Date: {truth['date']}", fill=text_color, font=f_bold)
    y += 35
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=1)
    y += 20

    # Table Header
    draw.text((60, y), "Delivered Item", fill=text_color, font=f_bold)
    draw.text((450, y), "Quantity", fill=text_color, font=f_bold, anchor="ma")
    draw.text((W - 80, y), "Unit", fill=text_color, font=f_bold, anchor="ma")
    y += 30
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=2)
    y += 20

    for it in truth["items"]:
        draw.text((60, y), it["name"], fill=text_color, font=f_regular)
        draw.text((450, y), str(it["qty"]), fill=text_color, font=f_regular, anchor="ma")
        draw.text((W - 80, y), str(it["unit"]), fill=text_color, font=f_regular, anchor="ma")
        y += 40

    y += 30
    draw.line([(50, y), (W - 50, y)], fill=line_color, width=1)
    y += 20
    draw.text((60, y), f"Note: {truth['notes']}", fill=text_color, font=f_regular)
    y += 60
    draw.text((W - 140, y), "Receiver's Sign: [Verified]", fill=text_color, font=f_bold, anchor="mt")

    final_img = apply_perspective_and_shadow(paper, angle=slip_data["angle"])
    return final_img

# Generate all bills
for b in DATA_BILLS:
    img = render_invoice_image(b)
    img_path = SAMPLES_DIR / f"{b['id']}.jpg"
    img.save(img_path, "JPEG", quality=90)
    
    # Save truth JSON
    truth_path = TRUTH_DIR / f"{b['id']}.json"
    truth_path.write_text(json.dumps(b["truth"], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated {img_path} and {truth_path}")

# Generate slips
for s in DATA_SLIPS:
    img = render_slip_image(s)
    img_path = SAMPLES_DIR / f"{s['id']}.jpg"
    img.save(img_path, "JPEG", quality=90)
    
    truth_path = TRUTH_DIR / f"{s['id']}.json"
    truth_path.write_text(json.dumps(s["truth"], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated {img_path} and {truth_path}")

# Also generate test_slip1.jpg as an alias/match for convenience
slip3_img = Image.open(SAMPLES_DIR / "test_slip3.jpg")
slip3_img.save(SAMPLES_DIR / "test_slip1.jpg", "JPEG", quality=90)
truth_slip1 = json.loads((TRUTH_DIR / "test_slip3.json").read_text(encoding="utf-8"))
(TRUTH_DIR / "test_slip1.json").write_text(json.dumps(truth_slip1, indent=2), encoding="utf-8")
print("Generated samples/test_slip1.jpg")

print("All sample images and ground truths generated successfully.")

