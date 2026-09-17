#!/usr/bin/env python3
"""Export the parts of the AgentGateway config that are safe to publish.

Reads the gateway admin API, keeps only the resource kinds below, and refuses to
write anything that still contains a plaintext credential. Run it on the gateway
host, where the admin API listens on 127.0.0.1:15000.

    ./scripts/export-public-gateway-config.py --out /tmp/out

The output is meant for the public netcat-ai/public repository. Credentials stay
in the gateway's own .env file and must appear here only as `$VAR` references.
Internal addresses (tailnet host names and private/CGNAT IPs) are replaced with
placeholders before writing; see redact().
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

# Resource kinds that are publishable, and the file each one lands in.
PUBLISHABLE = {
    "llm.provider": "providers.json",
    "llm.model": "models.json",
    "llm.virtualModel": "virtual-models.json",
    "modelCatalog": "model-catalog.json",
}

# Kinds that are never exported, with the reason shown in the summary.
NEVER_EXPORT = {
    "llm.apiKey": "holds user credentials",
    "llm.policy": "CORS allow-list names internal origins",
}

SECRET_FIELD = re.compile(r"key|token|secret|password|passwd|credential", re.I)
SECRET_VALUE = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|nc_ai_[A-Za-z0-9_\-]{8,}|hskey-[A-Za-z0-9_\-]{8,})")

# Internal addressing: tailnet host names and private/CGNAT IPv4 literals are
# replaced, because the repository states that addresses and network topology
# are not published. Loopback (127.0.0.0/8) is kept: it documents the local hop
# between the gateway and CLIProxyAPI and is not reachable from outside.
INTERNAL_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]*\.v4\.chat\b", re.I)
INTERNAL_IPV4 = re.compile(
    r"\b(?:"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"
    r")\b"
)


def redact(text):
    """Replace internal host names and addresses with readable placeholders."""
    return INTERNAL_IPV4.sub("<internal-ip>", INTERNAL_HOST.sub("<internal-host>", text))


def redact_value(value):
    """Redact every string inside a JSON value, leaving numbers and booleans alone."""
    return json.loads(redact(json.dumps(value, ensure_ascii=False)))


def walk(value, path="", out=None):
    """Yield (path, leaf) for every leaf value."""
    out = [] if out is None else out
    if isinstance(value, dict):
        for k, v in value.items():
            walk(v, f"{path}/{k}", out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk(v, f"{path}/{i}", out)
    else:
        out.append((path, value))
    return out


def check_resource(resource):
    """Return a list of reasons this resource must not be published."""
    problems = []
    for path, leaf in walk(resource.get("value")):
        if not isinstance(leaf, str):
            continue
        field = path.rsplit("/", 1)[-1]
        if SECRET_FIELD.search(field) and not leaf.startswith("$"):
            problems.append(f"{resource['kind']}/{resource['id']}: {path} holds a plaintext credential")
        elif SECRET_VALUE.search(leaf):
            problems.append(f"{resource['kind']}/{resource['id']}: {path} looks like a raw secret")
    if resource["kind"] not in PUBLISHABLE:
        problems.append(f"{resource['kind']}/{resource['id']}: kind is not on the publish allow-list")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gateway", default="http://127.0.0.1:15000", help="admin API base URL")
    ap.add_argument("--out", required=True, type=pathlib.Path, help="output directory")
    ap.add_argument("--check-only", action="store_true", help="report problems without writing files")
    args = ap.parse_args()

    url = args.gateway.rstrip("/") + "/api/config/resources"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            resources = json.load(resp)["resources"]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
        print(f"failed to read {url}: {exc}", file=sys.stderr)
        return 2

    problems, buckets, skipped = [], {}, {}
    for resource in resources:
        kind = resource.get("kind", "")
        if kind in NEVER_EXPORT:
            skipped.setdefault(kind, []).append(resource.get("id", "?"))
            continue
        found = check_resource(resource)
        if found:
            problems.extend(found)
            continue
        buckets.setdefault(kind, []).append(
            {"kind": kind, "id": resource["id"], "value": redact_value(resource["value"])}
        )

    if problems:
        print("refusing to export — plaintext credentials or unknown kinds found:", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        return 1

    total = sum(len(v) for v in buckets.values())
    print(f"publishable resources: {total}")
    for kind, items in sorted(buckets.items()):
        print(f"  {kind:<18} {len(items):>3} -> {PUBLISHABLE[kind]}")
    for kind, ids in sorted(skipped.items()):
        print(f"excluded {kind}: {len(ids)} resource(s) — {NEVER_EXPORT[kind]}")

    if args.check_only:
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for kind, items in sorted(buckets.items()):
        path = args.out / PUBLISHABLE[kind]
        text = json.dumps({"resources": items}, ensure_ascii=False, indent=2) + "\n"
        leftover = [m.group(0) for m in INTERNAL_HOST.finditer(text) if not m.group(0) == "<internal-host>"]
        leftover += INTERNAL_IPV4.findall(text)
        if leftover:
            print(f"refusing to write {path}: internal address survived redaction: {leftover[:5]}", file=sys.stderr)
            return 1
        path.write_text(text)
        print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
