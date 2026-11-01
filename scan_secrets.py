import subprocess
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def scan_secrets():
    print("=" * 80)
    print(" BILLBACK REPOSITORY & GIT HISTORY SECRETS AUDIT ")
    print("=" * 80)

    # 1. Check if .env was ever committed in git history
    print("\n[Check 1] Checking if .env was EVER committed in Git history...")
    res_env = subprocess.run(
        ["git", "log", "--all", "--full-history", "--", ".env"],
        capture_output=True, text=True, errors="ignore"
    )
    if res_env.stdout.strip():
        print("  [CRITICAL LEAK] .env was committed in git history!")
        print(res_env.stdout.strip())
        env_leaked = True
    else:
        print("  [CONFIRMED] .env was NEVER committed in Git history.")
        env_leaked = False

    # Check .gitignore
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        if ".env" in content:
            print("  [CONFIRMED] .gitignore contains .env entry.")
        else:
            print("  [WARNING] .gitignore does not explicitly mention .env!")

    # 2. Scan entire git history diffs
    print("\n[Check 2] Scanning all commits in git history (git log -p) for secret patterns...")
    res_log = subprocess.run(
        ["git", "log", "-p", "--all"],
        capture_output=True, text=True, errors="ignore"
    )
    full_git_log = res_log.stdout

    patterns = {
        "OpenAI / Meta API Key": r"sk-[a-zA-Z0-9_\-]{20,}",
        "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
        "GitHub Token": r"(?:ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{40,})",
        "Gmail App Password (16-char code)": r"\b[a-z]{4}\s[a-z]{4}\s[a-z]{4}\s[a-z]{4}\b",
        "Bearer Token": r"Bearer\s+[A-Za-z0-9_\-\.]{25,}",
        "Hardcoded Password Assignment": r"(?:api[_\-]?key|auth[_\-]?token|app[_\-]?password)\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]"
    }

    findings = []

    for name, pat in patterns.items():
        matches = re.findall(pat, full_git_log, re.IGNORECASE)
        # Filter false positives like dummy example placeholders or descriptions
        real_matches = []
        for m in matches:
            m_str = m if isinstance(m, str) else str(m)
            if any(fake in m_str.lower() for fake in ["example", "your_api_key", "placeholder", "dummy", "fake"]):
                continue
            real_matches.append(m_str)
        if real_matches:
            findings.append((name, len(real_matches), real_matches))

    # Scan for email addresses in commit history
    print("\n[Check 3] Scanning for personal emails in commit history...")
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    all_emails = set(re.findall(email_pattern, full_git_log))
    filtered_emails = [e for e in all_emails if not any(ign in e.lower() for ign in ["example.com", "users.noreply.github.com", "netmeds.com", "reliance"])]

    # Check working directory files (excluding .git and .venv)
    print("\n[Check 4] Scanning current working directory files (excluding .git and .venv)...")
    for p in Path(".").rglob("*"):
        if any(ign in p.parts for ign in [".git", ".venv", "__pycache__", ".pytest_cache"]):
            continue
        if p.is_file() and p.name != ".env" and p.suffix not in [".jpg", ".jpeg", ".png", ".wav", ".db"]:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                for name, pat in patterns.items():
                    m = re.findall(pat, txt, re.IGNORECASE)
                    for match in m:
                        m_str = match if isinstance(match, str) else str(match)
                        if any(fake in m_str.lower() for fake in ["example", "your_api_key", "placeholder", "dummy"]):
                            continue
                        findings.append((f"{name} in {p}", 1, [m_str]))
            except Exception:
                pass

    print("-" * 80)
    print("AUDIT FINDINGS SUMMARY:")
    print(f"  .env Committed in History : {'NO (Clean)' if not env_leaked else 'YES (LEAKED!)'}")
    print(f"  Hardcoded Keys / Tokens   : {len(findings)} found")
    if findings:
        print("  [!] POTENTIAL SECRETS DETECTED:")
        for name, count, samples in findings:
            print(f"      - {name}: {count} instance(s)")
    else:
        print("  [+] No API keys, passwords, or tokens found in git history or workspace.")

    print(f"\n  Email addresses in commits/files ({len(filtered_emails)} found):")
    for em in sorted(filtered_emails):
        print(f"      - {em}")
    print("=" * 80)

if __name__ == "__main__":
    scan_secrets()
