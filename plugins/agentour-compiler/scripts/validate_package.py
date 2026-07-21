#!/usr/bin/env python3
"""Static preflight aligned with Agentour compiler contract v2026-07-14.1."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
import hashlib
import fnmatch

FORBIDDEN_UI = re.compile(r"\b(load skill|skill loaded|tool call|runtime boot|handler)\b", re.I)
SECRET_CONTENT = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
]
EXCLUDED = {"node_modules", ".output", ".eve", ".workflow-data", ".git", "__pycache__"}
ALLOWED_SMOKE = {"send", "expect_tool", "expect_contains", "expect_approval", "expect_question"}
LOCK_EXCLUDES = {"node_modules", ".output", ".eve", ".workflow-data", ".git",
                 "package.lock", "__pycache__"}


def generate_package_lock(root: pathlib.Path) -> dict:
    hashes = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if (not path.is_file() or any(part in LOCK_EXCLUDES for part in rel.parts)
                or fnmatch.fnmatch(path.name, ".agentour-*.log")):
            continue
        hashes[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    tree = hashlib.sha256()
    for rel, digest in sorted(hashes.items()):
        tree.update(rel.encode()); tree.update(b"\0"); tree.update(digest.encode()); tree.update(b"\n")
    lock = {"version": 1, "hash": tree.hexdigest(), "files": hashes,
            "generated_by": "agentourcore.lockfile/1"}
    (root / "package.lock").write_text(
        json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return lock


def files(root: pathlib.Path):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED for part in path.relative_to(root).parts):
            continue
        yield path


def validate_smoke(path: pathlib.Path) -> list[str]:
    problems = []
    current = None
    cases = []
    in_cases = False
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        text = raw.strip(); indent = len(raw) - len(raw.lstrip(" "))
        if text.startswith("schema_version:"):
            if text.partition(":")[2].strip() != "1": problems.append("Only smoke schema_version 1 is supported")
            continue
        if text == "cases:": in_cases = True; continue
        if not in_cases: problems.append(f"Smoke line {line_no}: expected cases:"); continue
        if indent == 2 and text.startswith("- "):
            current = {}; cases.append(current); text = text[2:]
        elif text.startswith("- "):
            problems.append(f"Smoke line {line_no}: nested lists are not supported"); continue
        if current is None or ":" not in text:
            problems.append(f"Smoke line {line_no}: invalid flat field"); continue
        key, _, value = text.partition(":"); key = key.strip()
        if key not in ALLOWED_SMOKE:
            problems.append(f"Smoke line {line_no}: unsupported field {key}")
        else:
            current[key] = value.strip()
    for i, case in enumerate(cases, 1):
        if not case.get("send"): problems.append(f"Smoke case #{i} missing send")
        if len(case) < 2: problems.append(f"Smoke case #{i} needs an expect_* assertion")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("package"); args = parser.parse_args()
    started = time.monotonic(); root = pathlib.Path(args.package).resolve()
    lock = generate_package_lock(root)
    critical: list[str] = []; warnings: list[str] = []; passed: list[str] = []
    required = ["agentour.json", "README.md", "RELEASE.md", "tests/smoke.yaml",
                "payload/package.json", "payload/pnpm-lock.yaml", "payload/agent/agent.ts",
                "payload/agent/instructions.md", "payload/agent/sandbox/sandbox.ts"]
    missing = [item for item in required if not (root / item).is_file()]
    critical.extend("Missing file: " + item for item in missing)

    try: manifest = json.loads((root / "agentour.json").read_text(encoding="utf-8"))
    except Exception as exc: manifest = {}; critical.append(f"Invalid agentour.json: {exc}")
    for key in ("id", "name", "version", "runtime", "capabilities", "description", "pricing"):
        if not manifest.get(key): critical.append(f"Manifest field is required: {key}")
    pricing = manifest.get("pricing") or {}
    if not isinstance(pricing.get("amount_credits"), int):
        critical.append("pricing.amount_credits must be an integer number of credits")
    if "amount_cents" in pricing:
        warnings.append("pricing.amount_cents is legacy; use amount_credits (credits, not RMB cents)")

    try:
        package_json = json.loads((root / "payload/package.json").read_text(encoding="utf-8"))
        if str((package_json.get("engines") or {}).get("node", "")) != ">=24":
            critical.append('payload/package.json must declare engines.node: ">=24"')
    except Exception as exc: critical.append(f"Invalid payload/package.json: {exc}")

    runtime_ui = manifest.get("runtime_ui") or {}; ui_caps = runtime_ui.get("capabilities") or {}
    for capability in manifest.get("capabilities") or []:
        item = ui_caps.get(capability)
        if not isinstance(item, dict): critical.append(f"Missing runtime_ui for capability: {capability}"); continue
        for field in ("display_name", "loading_message"):
            value = str(item.get(field, "")).strip()
            if not value: critical.append(f"runtime_ui.capabilities.{capability}.{field} is required")
            elif FORBIDDEN_UI.search(value): critical.append(f"Internal terminology in {capability}.{field}")
    for field in ("startup_message", "default_working_message"):
        value = str(runtime_ui.get(field, "")).strip()
        if not value: critical.append(f"runtime_ui.{field} is required")
        elif FORBIDDEN_UI.search(value): critical.append(f"Internal terminology in runtime_ui.{field}")

    scanned = 0
    for path in files(root):
        scanned += 1
        if path.stat().st_size > 2_000_000: continue
        try: text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError): continue
        rel = path.relative_to(root).as_posix()
        for pattern in SECRET_CONTENT:
            if pattern.search(text): critical.append(f"Possible credential content in {rel}"); break
        if rel == "agentour.json" and FORBIDDEN_UI.search(text): critical.append("agentour.json exposes internal terminology")
    smoke = root / "tests/smoke.yaml"
    if smoke.is_file(): critical.extend(validate_smoke(smoke))
    instructions = root / "payload/agent/instructions.md"
    content = instructions.read_text(encoding="utf-8") if instructions.is_file() else ""
    if "ask_question" not in content: warnings.append("Missing-input behavior should use Eve ask_question")
    if manifest.get("approval_required") and "审批" not in content and "approval" not in content.lower():
        critical.append("Approval is declared but instructions do not explain it")
    if re.search(r"等待审批.{0,20}(正在执行|运行中|思考中)", content):
        critical.append("Waiting for approval is incorrectly described as running")

    try:
        version = subprocess.check_output(["node", "--version"], text=True).strip().lstrip("v")
        if int(version.split(".", 1)[0]) < 24: warnings.append(f"Local Node {version} is too old for Eve; use Node 24")
    except Exception: warnings.append("Node.js not found; local build is unverified")

    if not critical: passed.extend(["Required files and manifest passed", "Upload-scope secret scan passed",
                                    f"Generated package.lock {lock['hash'][:16]}"])
    for title, values in (("Critical", critical), ("Warnings", warnings), ("Passed", passed)):
        if values:
            print(title + ":")
            for item in sorted(set(values)): print(f"- {item}")
    print(f"Scanned {scanned} uploadable files in {time.monotonic() - started:.2f}s; excluded {sorted(EXCLUDED)}")
    return 1 if critical else 0


if __name__ == "__main__": sys.exit(main())
