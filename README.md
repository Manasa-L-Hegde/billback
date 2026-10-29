# BillBack

> Small shops and families pay bills where the real agreement lives in a voice note, the proof of delivery is a paper slip, and the bill is a photo. There's no ERP and no contract system. Overcharges slip through (wrong math, fees nobody agreed to, items billed twice or never delivered) because checking means cross-referencing three messy sources by hand, and disputing means writing and chasing emails. BillBack is an agent that reads all three, proves each overcharge with arithmetic, and carries the dispute through to recovery.

---

## Features
- **Multimodal Bill & Slip Extraction**: Extracts line items (name, quantity, rate, amount, total) from printed and handwritten invoices and delivery challans.
- **Arithmetic Verification**: Validates line-item math ($qty \times rate = amount$), subtotal consistency, and grand totals.
- **Cross-Source Audit Engine**: Cross-references invoices with delivery slips and agreed rate cards to catch unauthorized delivery fees, duplicate items, delivered vs. billed quantity discrepancies, and unapproved rate hikes.
- **Autonomous Dispute Generation**: Formulates clear dispute findings backed by exact mathematical proofs.

---

## Project Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Manasa-L-Hegde/billback.git
   cd billback
   ```

2. **Set up virtual environment & install dependencies**:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Linux/macOS:
   source .venv/bin/activate

   pip install openai fastapi uvicorn python-dotenv python-multipart pillow
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   MODEL_API_KEY=your_key_here
   ```

4. **Run Bill Extraction**:
   ```bash
   python extract.py samples/test_bill1.jpg
   python extract.py samples/test_slip3.jpg slip
   ```

5. **Run the Cross-Source Audit**:
   ```bash
   # Single bill math audit:
   python audit.py outputs/test_bill1.json -

   # Bill cross-referenced with delivery slip:
   python audit.py outputs/test_bill3.json outputs/test_slip3.json
   ```

6. **Run Autonomous Agent with Chat Agreements**:
   ```bash
   # Autonomous audit cross-referencing invoice with chat agreement screenshot:
   python agent.py samples/test_bill4.jpg - samples/test_chat1.jpg
   ```

7. **Run Full Test Suite & Evaluations**:
   ```bash
   # Evaluate extraction accuracy across test suite:
   python eval.py

   # Evaluate audit engine against planted discrepancy cases:
   python eval_audit.py
   ```

---

## Test Data & Benchmarks

All test documents and ground truth files are located in `samples/` and `samples/truth/`. Note: All sample invoices (`test_bill1.jpg` to `test_bill6.jpg`), delivery slips (`test_slip*.jpg`), and chat agreement screenshots (`test_chat1.jpg` to `test_chat3.jpg`) are synthetic **test data** generated with deliberate discrepancies for benchmarking.

- **Audit Discrepancy Evaluation (`eval_audit.py`)**:
  - Planted overcharge errors caught: **5 / 5 (100%)**
  - False alarms on clean bills: **0**
- **Extraction Benchmark**:
  - Clean synthetic baseline accuracy: tracked in `samples/accuracy.md`.
  - Real-photo accuracy: tracked separately under real-world lighting and camera conditions.
