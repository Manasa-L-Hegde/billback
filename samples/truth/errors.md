# Deliberate Planted Test Errors

This document details the synthetic errors planted in each test invoice for auditing and regression validation.

| Test File | Type | Error Category | Description & Audit Ground Truth |
| :--- | :--- | :--- | :--- |
| `test_bill1.jpg` | Printed Receipt | **1. Qty × Rate ≠ Line Amount** | Item **"Gel Pens Blue (Pack)"**: 4 packs @ ₹120.00 should equal **₹480.00**, but invoice prints **₹580.00** (₹100 overcharge on line math). |
| `test_bill2.jpg` | Handwritten Bill | **2. Line items do not add up to Subtotal** | Line items: Cement (₹3800) + Steel Wire (₹900) + PVC Pipe (₹1100) = **₹5800.00**. However, the printed subtotal states **₹6200.00** (₹400 unjustified addition). |
| `test_bill3.jpg` | Printed Invoice | **3. Delivery charge added without slip authorization** | Invoice charges **₹350.00** delivery fee. Matching delivery slip (`test_slip3.jpg` / `test_slip1.jpg`) confirms delivery terms: **Free Delivery / Included in order**. |
| `test_bill4.jpg` | Handwritten Bill | **4. Rate higher than agreed rate** | Item **"Sona Masoori Rice"** (50 kg): Billed at **₹62.00/kg** (Total ₹3100.00). **Agreed contract rate is ₹55.00/kg**. Discrepancy: ₹7.00/kg × 50 kg = **₹350.00 overcharge**. |
| `test_bill5.jpg` | Printed Receipt | **5. Item billed twice (Duplicate item)** | Item **"Cooking Oil 1L"** (6 bottles @ ₹130 = ₹780) appears twice on the bill. Matching delivery slip (`test_slip5.jpg`) confirms only 6 bottles were delivered. Duplicate overcharge: **₹780.00**. |
| `test_bill6.jpg` | Printed Invoice | **6. Fully correct bill** | No calculation, rate, duplicate, or delivery errors. 3 cables/hubs/mice correctly tallied with 18% tax and ₹80 delivery fee = ₹4092.00. |

---

### Contract / Agreement Master Rates (for Case 4)
- **Vendor:** Kaveri Grain Stores
- **Sona Masoori Rice:** ₹55.00 / kg *(Billed at ₹62.00 / kg)*
- **Toor Dal:** ₹140.00 / kg
- **Wheat Flour:** ₹42.00 / kg

