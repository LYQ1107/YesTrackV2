#!/usr/bin/env python3
"""Probe the official public share using its published extraction code."""
from __future__ import annotations

import argparse
from datetime import datetime
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request
from zoneinfo import ZoneInfo


def probe(cfg: dict) -> dict:
    base = "https://pan.baidu.com"
    short = cfg["official_release_url"].rsplit("/1", 1)[1]
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    headers = {"User-Agent": "Mozilla/5.0", "Referer": base + "/share/init?surl=" + short,
               "Origin": base}
    result = {"checked_at_asia_shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "official_share": cfg["official_release_url"], "listings": []}

    def request(path: str, params: dict | None = None, form: dict | None = None) -> str:
        url = path if path.startswith("https://") else base + path
        if params:
            url += "?" + urlencode(params)
        data = urlencode(form).encode() if form is not None else None
        with opener.open(Request(url, data=data, headers=headers), timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")

    request(cfg["official_release_url"])
    verified = json.loads(request("/share/verify", dict(surl=short, t=int(time.time()*1000),
        channel="chunlei", web=1, app_id=250528, clienttype=0),
        dict(pwd=cfg["official_release_code"], vcode="", vcode_str="")))
    result["verify_errno"] = verified.get("errno")
    if verified.get("errno") != 0:
        return dict(result, status="EXTRACTION_CODE_VERIFICATION_FAILED")
    page = request(cfg["official_release_url"])
    ids = {k.lower(): int(v) for k, v in re.findall(
        r'''["'](shareid|share_id|uk|share_uk)["']\s*:\s*["']?(\d+)''', page, re.I)}
    shareid = ids.get("shareid", ids.get("share_id"))
    uk = ids.get("share_uk") or ids.get("uk")
    if shareid is None or uk is None:
        return dict(result, status="VERIFIED_PAGE_HAS_NO_SHARE_METADATA")

    def listing(directory: str | None = None) -> list:
        params = dict(uk=uk, shareid=shareid, num=100, page=1, order="name", desc=0,
                      showempty=0, web=1, app_id=250528, clienttype=0)
        params.update(dict(root=1) if directory is None else dict(dir=directory))
        payload = json.loads(request("/share/list", params))
        items = payload.get("list", [])
        result["listings"].append({"path": directory or "<root>", "errno": payload.get("errno"),
            "items": [{k: row[k] for k in ("server_filename", "path", "isdir", "size") if k in row}
                      for row in items]})
        return items

    root = listing()
    files = [r for r in root if not int(r.get("isdir", 0))]
    for row in root:
        if int(row.get("isdir", 0)) and row.get("server_filename", "").lower() == "yestrack":
            files += [r for r in listing(row["path"]) if not int(r.get("isdir", 0))]
    archives = [r for r in files if r.get("server_filename", "").lower().endswith(".zip")]
    result["archive_count"] = len(archives)
    result["direct_download_link_available"] = any(bool(r.get("dlink")) for r in files)
    result["download_signature_available"] = bool(re.search(r'''["']sign["']\s*:\s*["']([^"']+)["']''', page))
    result["download_timestamp_available"] = bool(re.search(r'''["']timestamp["']\s*:\s*["']?(\d+)''', page))
    if archives and not result["direct_download_link_available"] and not (
            result["download_signature_available"] and result["download_timestamp_available"]):
        result["status"] = "PUBLIC_ARCHIVE_LISTED_ANONYMOUS_DOWNLOAD_UNAVAILABLE"
    else:
        result["status"] = "PUBLIC_SHARE_PROBED_REVIEW_DOWNLOAD_AVAILABILITY"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("analysis/config.json"))
    parser.add_argument("--output", type=Path, default=Path("analysis/release_probe.json"))
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    try:
        result = probe(cfg)
    except HTTPError as e:
        result = {"status": "PUBLIC_RELEASE_HTTP_ERROR", "http_status": e.code}
    except URLError as e:
        result = {"status": "PUBLIC_RELEASE_CONNECTION_ERROR", "reason": str(e.reason)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
