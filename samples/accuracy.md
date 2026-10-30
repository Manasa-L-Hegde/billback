# Bill Extraction Accuracy Report

Target: >= 90% of line items extracted correctly.

---

## 1. Real-World Bills (User Captured Benchmark)

Evaluated across 5 diverse real-world bills: utility, online food delivery, digital recharge, pharmaceutical medicine invoice, and e-commerce platform invoice.

| Sample | Category | Vendor | Bill Date | Amount on Bill | Extracted Total | Items Match | Accuracy (%) | Extraction & Math Notes |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `real1.jpg` | Electricity / Utility | Hubli Electricity (HESCOM) | Jul 16, 2026 | ₹238.00 | ₹238.00 | 1/1 | 100.0% | Exact match: Vendor, Account ID 912796, Bill No 202607091279601 |
| `real2.jpg` | Restaurant Delivery Slip | Sri Skanda Sagar, Kengeri (Zomato) | 30 Oct | ₹160.00 | ₹160.00 | 1/1 | 100.0% | Veg Fried Rice (1 @ ₹160), Order #8779962220; tape partially obscures header |
| `real3.jpg` | Mobile Recharge (GPay) | Jio Prepaid | 9 Sept 2026 | ₹800.90 | ₹800.90 | 2/2 | 100.0% | Plan price ₹799 + Platform fee ₹1.90 = ₹800.90 exact match |
| `real4.jpg` | Pharmacy / Medicine | netmeds.com India Ki Pharmacy | 10-10-2026 | ₹3732.00 | ₹3732.00 | 4/4 | 100.0% | 4 prescription drugs: Korandil (6), Telmikind (4), Axcer (4), Glycomet (6). Discount of ₹883.10 reconciled; exact grand total ₹3,732.00. |
| `real5.png` | E-Commerce Platform Fee | Flipkart Internet Private Limited | 17-09-2025 | ₹10.00 | ₹10.00 | 6/6 | 100.0% | 6 breakdown lines of platform fees summing to ₹10.00 total. Taxable value ₹8.46 + ₹1.54 GST correctly identified. |

### Real Photos Evaluation Summary:
- **Total real bills evaluated:** 5
- **Total line items on paper:** 14
- **Total line items accurately extracted:** 14
- **Real-photo line-item accuracy:** **100.0%** (14 / 14)
- **Key finding:** Handled pharmaceutical tables with discounts and post-tax totals, low-resolution scanned tables, and partially taped restaurant delivery slips without missing line items.

---

## 2. Synthetic Test Suite (Baseline Regression Benchmarks)

| Sample | Type | Total Items on Bill | Items Correct | Accuracy (%) | Notes / Discrepancies |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `test_bill1.jpg` | Invoice | 3 | 3 | 100.0% | Math issues flagged: 1 (Gel Pens) |
| `test_bill2.jpg` | Invoice | 3 | 3 | 100.0% | Math issues flagged: 1 (Subtotal) |
| `test_bill3.jpg` | Invoice | 3 | 3 | 100.0% | All items extracted accurately |
| `test_bill4.jpg` | Invoice | 3 | 3 | 100.0% | All items extracted accurately |
| `test_bill5.jpg` | Invoice | 4 | 4 | 100.0% | All items extracted accurately |
| `test_bill6.jpg` | Invoice | 3 | 3 | 100.0% | Clean bill |
| `test_hard_blurry.jpg` | Invoice | 4 | 4 | 100.0% | Tilted & camera blur |
| `test_hard_layout.jpg` | Invoice | 3 | 3 | 100.0% | Rate before Qty column |
| `test_slip1.jpg` | Delivery Slip | 3 | 3 | 100.0% | All items extracted accurately |
| `test_slip3.jpg` | Delivery Slip | 3 | 3 | 100.0% | All items extracted accurately |
| `test_slip5.jpg` | Delivery Slip | 3 | 3 | 100.0% | Clean slip (no notes) |

- **Synthetic items evaluated:** 35
- **Synthetic items correct:** 35 (100.0%)
