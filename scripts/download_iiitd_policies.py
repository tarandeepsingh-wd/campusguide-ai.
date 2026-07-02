from __future__ import annotations

import json
import re
import ssl
from html import unescape
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "iiitd_policies"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

POLICIES = [
    {
        "title": "B.Tech Ordinances",
        "filename": "iiitd-btech-ordinances-2017.pdf",
        "url": "https://iiitd.ac.in/sites/default/files/docs/education/BTech-Ordinances.pdf",
        "source_page": "https://www.iiitd.ac.in/academics/resources",
    },
    {
        "title": "B.Tech Regulations",
        "filename": "iiitd-btech-regulations-2025-october.pdf",
        "url": "https://iiitd.ac.in/sites/default/files/docs/education/2025/2025-October-UG%20Regulations.pdf",
        "source_page": "https://www.iiitd.ac.in/academics/resources",
    },
    {
        "title": "B.Tech CSD Specific Regulations",
        "filename": "iiitd-btech-csd-regulations-2024-may.pdf",
        "url": "https://iiitd.ac.in/sites/default/files/docs/education/2024/2024-May-BTech%28CSD%29-Regulations.pdf",
        "source_page": "https://www.iiitd.ac.in/academics/resources",
    },
    {
        "title": "Penalty for Forged Documents or Misbehavior",
        "filename": "iiitd-penalty-forged-documents-misbehavior-2025.pdf",
        "url": "https://www.iiitd.ac.in/sites/default/files/docs/forms/2025/Penalty%20for%20Submission%20of%20any%20Forged%20Documents%20or%20Misbehaviour%20by%20students%20in%20any%20form.pdf",
        "source_page": "https://www.iiitd.ac.in/academics/resources",
    },
    {
        "title": "Evaluation Policy",
        "filename": "iiitd-evaluation-policy.txt",
        "url": "https://www.iiitd.ac.in/academics/resources/evaluation",
        "source_page": "https://www.iiitd.ac.in/academics/resources",
        "start_marker": "Evaluation Policy",
    },
    {
        "title": "Academic Dishonesty Policy",
        "filename": "iiitd-academic-dishonesty-policy.txt",
        "url": "https://www.iiitd.ac.in/academics/resources/acad-dishonesty",
        "source_page": "https://www.iiitd.ac.in/academics/resources",
        "start_marker": "Academic Dishonesty in Courses",
    },
]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for policy in POLICIES:
        target = OUTPUT_DIR / policy["filename"]
        print(f"Downloading {policy['title']} -> {target.name}")
        content = _download(policy["url"])
        if target.suffix.lower() == ".txt":
            text = _html_to_text(content.decode("utf-8", errors="ignore"))
            text = _trim_to_policy_content(text, policy.get("start_marker"))
            target.write_text(text, encoding="utf-8")
        else:
            target.write_bytes(content)
        manifest.append({**policy, "local_path": str(target.relative_to(ROOT))})

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {MANIFEST_PATH}")


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "CampusGuideAI/0.1"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except (ssl.SSLCertVerificationError, URLError) as exc:
        if isinstance(exc, URLError) and "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        # Some bundled Python runtimes do not include the local issuer chain.
        context = ssl._create_unverified_context()
        with urlopen(request, timeout=30, context=context) as response:
            return response.read()


def _html_to_text(html: str) -> str:
    main = re.search(r"<h[12][^>]*>.*?</footer>", html, flags=re.IGNORECASE | re.DOTALL)
    text = main.group(0) if main else html
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _trim_to_policy_content(text: str, start_marker: str | None) -> str:
    if not start_marker:
        return text
    start = text.find(start_marker)
    if start == -1:
        return text
    trimmed = text[start:]
    copyright_at = trimmed.find("Copyright")
    if copyright_at != -1:
        trimmed = trimmed[:copyright_at]
    return trimmed.strip() + "\n"


if __name__ == "__main__":
    main()
