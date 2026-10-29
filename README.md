# Billback

Billback is an AI-powered bill audit tool that extracts line items from receipts/bills, compares them against agreed prices or delivery notes, and detects overcharges.

## Features
- Receipt & bill item extraction (name, quantity, rate, amount, total)
- Delivery slip and verbal agreement cross-referencing
- Overcharge and discrepancy detection

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

   pip install openai fastapi uvicorn python-dotenv python-multipart
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   MODEL_API_KEY=your_key_here
   ```

4. **Run API Test**:
   ```bash
   python test_call.py
   # Or with an image:
   python test_call.py samples/bill1.jpg
   ```

## Test Data
Sample bills, slips, and audio notes for testing are located in `samples/`. Note: All sample documents containing test cases or simulated discrepancies are **test data**.
