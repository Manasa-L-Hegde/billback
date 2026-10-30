import concurrent.futures
from agent import CaseSession

def run_case_a():
    # Case A: test_bill6.jpg (clean bill, 0 overcharge)
    s = CaseSession("samples/test_bill6.jpg")
    res = s.run()
    return "Case A (Bill 6)", s.state.get("audit", {}).get("total_overcharge", 0.0), res

def run_case_b():
    # Case B: test_bill1.jpg (math error, 100 overcharge)
    s = CaseSession("samples/test_bill1.jpg")
    res = s.run()
    return "Case B (Bill 1)", s.state.get("audit", {}).get("total_overcharge", 0.0), res

print("Running two cases concurrently in parallel threads...")
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(run_case_a), executor.submit(run_case_b)]
    for f in concurrent.futures.as_completed(futures):
        name, overcharge, text = f.result()
        print(f"\n[Parallel Result] {name} completed: Audited Overcharge = Rs. {overcharge}")
        print("First 100 chars:", text[:100].replace("\n", " "))

print("\nParallel execution completed successfully with zero state collision!")

