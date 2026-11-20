#!/usr/bin/env python3
"""Archive public YesTrack resource listings; do not contact authors or use credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--output", type=Path, default=Path("analysis/public_resource_search.json"))
p.add_argument("--supplement", type=Path, default=Path("analysis/resources/yestrack_supplement.pdf"))
a = p.parse_args()
repo = "https://api.github.com/repos/ggbondrighthere24/YesTrack"
urls = {
    "repository": repo,
    "branches": repo + "/branches?per_page=100",
    "tags": repo + "/tags?per_page=100",
    "releases": repo + "/releases?per_page=100",
    "forks": repo + "/forks?per_page=100",
    "commits": repo + "/commits?per_page=100",
    "author_repositories": "https://api.github.com/users/ggbondrighthere24/repos?per_page=100",
    "issues": repo + "/issues?state=all&per_page=100",
    "issue_comments": repo + "/issues/comments?per_page=100",
    "pull_requests": repo + "/pulls?state=all&per_page=100",
    "author_gists": "https://api.github.com/users/ggbondrighthere24/gists?per_page=100",
    **{f"hf_{kind}": f"https://huggingface.co/api/{kind}?search=YesTrack&limit=100"
       for kind in ("models", "datasets", "spaces")},
}


def fetch(item):
    name, url = item
    try:
        with urlopen(Request(url, headers={"User-Agent": "YesTrack-reproduction-resource-audit"}), timeout=30) as r:
            return name, {"url": url, "status": r.status, "data": json.load(r)}
    except Exception as e:
        return name, {"url": url, "error": f"{type(e).__name__}: {e}"}


with ThreadPoolExecutor(max_workers=4) as pool:
    listings = dict(pool.map(fetch, urls.items()))
supp_url = ("https://media.springernature.com/original/springer-static/esm/"
            "chp%3A10.1007%2F978-3-032-37020-4_4/MediaObjects/699772_1_En_4_MOESM1_ESM.pdf")
a.supplement.parent.mkdir(parents=True, exist_ok=True)
with urlopen(Request(supp_url, headers={"User-Agent": "YesTrack-reproduction-resource-audit"}), timeout=45) as r:
    payload = r.read()
    supplement = {"chapter_url": "https://link.springer.com/chapter/10.1007/978-3-032-37020-4_4",
                  "url": supp_url, "status": r.status,
                  "content_type": r.headers.get("Content-Type"), "bytes": len(payload)}
if payload.startswith(b"%PDF-"):
    a.supplement.write_bytes(payload)
    supp_text = a.supplement.with_suffix(".txt")
    subprocess.run(["pdftotext", "-layout", str(a.supplement), str(supp_text)], check=True)
    text = supp_text.read_text()
    supplement.update(local_pdf=str(a.supplement), local_text=str(supp_text),
                      urls_in_extracted_text=sorted(set(re.findall(r"https?://\S+", text))))
else:
    response_path = a.supplement.with_suffix(".response.html")
    response_path.write_bytes(payload)
    if a.supplement.exists() and not a.supplement.read_bytes().startswith(b"%PDF-"):
        a.supplement.unlink()
    supplement.update(local_response=str(response_path),
                      download_state="HTML response, not a downloaded PDF; browser-source inspection recorded separately")
record = {
    "retrieved_utc": datetime.now(timezone.utc).isoformat(),
    "listings": listings,
    "supplement": supplement,
    "scope": "Public resource discovery only; no tracking implementation is reconstructed from pseudocode.",
}
a.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
summary = {name: (len(r["data"]) if isinstance(r.get("data"), list) else r.get("error", "metadata saved"))
           for name, r in listings.items()}
print(json.dumps({"output": str(a.output), "public_listing_counts": summary,
                  "supplement_bytes": record["supplement"]["bytes"]}, ensure_ascii=False, indent=2))
