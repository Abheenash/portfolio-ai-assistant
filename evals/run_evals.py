#!/usr/bin/env python3
"""Run the eval cases against a deployed endpoint and write a Markdown report.

    python3 evals/run_evals.py https://<api-id>.execute-api.us-east-1.amazonaws.com/chat

Each case is a real request (a fraction of a cent each). A case passes if the reply
contains at least one `must_contain_any` string and none of `must_not_contain`
(case-insensitive). The report is committed so behaviour is tracked over time.
"""
import datetime as dt
import json
import sys
import time
import urllib.request

ORIGIN = "https://abheenash.com"


def ask(endpoint, message):
    # `endpoint` is an operator-supplied argument to this script, not user input,
    # but a typo'd file: URL would silently read the filesystem instead of failing,
    # so refuse anything that is not https up front.
    if not endpoint.lower().startswith("https://"):
        raise SystemExit(f"endpoint must be https://, got: {endpoint[:60]}")
    req = urllib.request.Request(  # noqa: S310 — scheme checked above
        endpoint, data=json.dumps({"message": message, "history": []}).encode(),
        headers={"Content-Type": "application/json", "Origin": ORIGIN}, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310 — scheme checked above
        body = json.loads(r.read())
    return body.get("reply", ""), (time.time() - t0) * 1000


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    endpoint = sys.argv[1]
    with open("evals/cases.json") as fh:
        cases = json.load(fh)
    rows, passed = [], 0
    for c in cases:
        reply, ms = ask(endpoint, c["message"])
        low = reply.lower()
        ok_any = any(s.lower() in low for s in c["must_contain_any"]) if c["must_contain_any"] else True
        ok_none = not any(s.lower() in low for s in c["must_not_contain"])
        ok = ok_any and ok_none
        passed += ok
        rows.append((c, reply, ms, ok, ok_any, ok_none))
        print(f"{'PASS' if ok else 'FAIL'}  {c['id']:28s} {ms:6.0f} ms")
        time.sleep(0.5)  # stay under the API's 3 rps throttle

    # UTC, so a run just before midnight local time doesn't label itself
    # with yesterday's date in the committed results file.
    today = dt.datetime.now(dt.UTC).date().isoformat()
    out = [f"# Eval results — {today}", "", f"Endpoint: `{endpoint}`  ", f"**{passed}/{len(cases)} passed**", "",
           "| id | kind | result | latency | reply (truncated) |", "|---|---|---|---|---|"]
    for c, reply, ms, ok, ok_any, _ok_none in rows:
        why = "" if ok else (" (missing expected phrase)" if not ok_any else " (contained forbidden phrase)")
        out.append(f"| {c['id']} | {c['kind']} | {'✅' if ok else '❌'}{why} | {ms:.0f} ms | {reply[:160].replace('|', '/').replace(chr(10), ' ')} |")
    path = f"evals/results-{today}.md"
    with open(path, "w") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"\n{passed}/{len(cases)} passed — wrote {path}")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
