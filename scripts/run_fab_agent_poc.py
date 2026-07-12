#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fab_agent_policy import ROOT, audit_action, load_audit_entries, resolve_fab_agent, utc_now, write_json
from verify_generated_output_package import verify_package


EXAMPLE_AGENTS = [
    ROOT / "fab_agents" / "examples" / "fab_product_planner",
    ROOT / "fab_agents" / "examples" / "fab_frontend_builder",
    ROOT / "fab_agents" / "examples" / "fab_artifact_reviewer",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_id() -> str:
    return "run-fab-agent-poc-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def deterministic_shopping_site(worktree: Path) -> None:
    write_text(
        worktree / "shopping-site/index.html",
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>POC Shopping Site</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header><h1>POC Shopping Site</h1><p>Static generated storefront for review.</p></header>
  <main>
    <section class="product-grid">
      <article class="product-card"><h2>Notebook</h2><p class="price" data-price="12">12</p><button class="add-to-cart" data-name="Notebook" data-price="12">Add to cart</button></article>
      <article class="product-card"><h2>Pen Set</h2><p class="price" data-price="8">8</p><button class="add-to-cart" data-name="Pen Set" data-price="8">Add to cart</button></article>
      <article class="product-card"><h2>Desk Lamp</h2><p class="price" data-price="28">28</p><button class="add-to-cart" data-name="Desk Lamp" data-price="28">Add to cart</button></article>
      <article class="product-card"><h2>Cable Kit</h2><p class="price" data-price="16">16</p><button class="add-to-cart" data-name="Cable Kit" data-price="16">Add to cart</button></article>
    </section>
    <aside class="cart">
      <h2>Cart</h2>
      <p>Items: <span id="cart-count">0</span></p>
      <p>Total: $<span id="cart-total">0</span></p>
      <ul id="cart-items"></ul>
      <button id="checkout">Checkout demo only - no real payment</button>
      <p id="checkout-message"></p>
    </aside>
  </main>
  <script src="app.js"></script>
</body>
</html>
""",
    )
    write_text(
        worktree / "shopping-site/styles.css",
        """body{font-family:Arial,sans-serif;margin:0;background:#f6f7fb;color:#20242c}header{padding:2rem;background:#172033;color:white}.product-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;padding:1rem}.product-card,.cart{background:white;border-radius:14px;padding:1rem;box-shadow:0 10px 30px #0001}.add-to-cart,#checkout{border:0;border-radius:10px;padding:.7rem 1rem;background:#2563eb;color:white;cursor:pointer}.cart{margin:1rem}.price::before{content:'$'}@media(max-width:640px){main{display:block}}""",
    )
    write_text(
        worktree / "shopping-site/app.js",
        """const cartItems=[];const countEl=document.getElementById('cart-count');const totalEl=document.getElementById('cart-total');const listEl=document.getElementById('cart-items');function renderCart(){countEl.textContent=String(cartItems.length);const total=cartItems.reduce((sum,item)=>sum+item.price,0);totalEl.textContent=String(total);listEl.innerHTML='';cartItems.forEach(item=>{const li=document.createElement('li');li.textContent=`${item.name} - $${item.price}`;listEl.appendChild(li);});}document.querySelectorAll('.add-to-cart').forEach(button=>{button.addEventListener('click',()=>{cartItems.push({name:button.dataset.name,price:Number(button.dataset.price)});renderCart();});});document.getElementById('checkout').addEventListener('click',()=>{document.getElementById('checkout-message').textContent='Checkout is a demo stub only; no real payment is processed.';});renderCart();""",
    )
    write_text(
        worktree / "shopping-site/README.md",
        """# POC Shopping Site

Open `index.html` in a browser to review the generated static storefront.

Files included:
- `index.html`
- `styles.css`
- `app.js`
- `README.md`

This is a static demo. The checkout button is a stub and no real payment is processed.
""",
    )


def run_live_harness(run_dir: Path) -> dict[str, Any]:
    evidence_dir = run_dir / "live-harness"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_ai_company_task_harness.py"),
        str(ROOT / "docs" / "ai_specs" / "shopping-site-common-demo.json"),
        "--mode",
        "live",
        "--out-root",
        str(ROOT / "results" / "ai_company_task_harness"),
    ]
    started = utc_now()
    env = os.environ.copy()
    if not env.get("CCR_MESSAGES_URL"):
        base = (env.get("CCR_BASE_URL") or env.get("ANTHROPIC_BASE_URL") or "").rstrip("/")
        if base:
            env["CCR_MESSAGES_URL"] = base + "/v1/messages"
    if env.get("CCR_MESSAGES_URL") and not env.get("ANTHROPIC_BASE_URL"):
        env["ANTHROPIC_BASE_URL"] = env["CCR_MESSAGES_URL"].split("/v1/messages", 1)[0].rstrip("/")
    completed = subprocess.run(command, cwd=str(ROOT), env=env, text=True, capture_output=True, timeout=1800)
    finished = utc_now()
    write_text(evidence_dir / "command.txt", " ".join(command))
    write_text(evidence_dir / "stdout.log", completed.stdout)
    write_text(evidence_dir / "stderr.log", completed.stderr)
    payload = {
        "command": command,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "exit_code": completed.returncode,
        "stdout_path": str(evidence_dir / "stdout.log"),
        "stderr_path": str(evidence_dir / "stderr.log"),
    }
    parsed: dict[str, Any] = {}
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = {}
    payload["parsed"] = parsed
    write_json(evidence_dir / "live-harness-result.json", payload)
    return payload


def copy_live_outputs(live_result: dict[str, Any], worktree: Path) -> bool:
    run_dir_value = live_result.get("parsed", {}).get("run_dir")
    if not run_dir_value:
        return False
    source = Path(str(run_dir_value)) / "worktree" / "shopping-site"
    if not source.exists():
        return False
    target = worktree / "shopping-site"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return True


def build_meeting(run_dir: Path, resolved_agents: list[dict[str, Any]]) -> dict[str, Any]:
    meeting = {
        "summary": "Fab agents discussed the website POC under CIM-managed capability boundaries.",
        "live_meeting_used": False,
        "discussion_log": [
            {
                "round": 1,
                "role": "fab_product_planner",
                "summary": "Define a simple product grid, clear cart state, and visible checkout limitation.",
                "proposed_actions": ["Planner writes memo only", "Builder creates static package", "Reviewer verifies outputs"],
                "decision_state": "recorded",
            },
            {
                "round": 1,
                "role": "fab_frontend_builder",
                "summary": "Implement dependency-free HTML, CSS, and JavaScript inside allowed worktree paths.",
                "proposed_actions": ["Create index.html", "Create styles.css", "Create app.js", "Create README.md"],
                "decision_state": "recorded",
            },
            {
                "round": 1,
                "role": "fab_artifact_reviewer",
                "summary": "Review verifier evidence and blocked tool attempts without modifying deliverables.",
                "proposed_actions": ["Run deterministic verifier", "Inspect audit logs"],
                "decision_state": "recorded",
            },
        ],
        "task_assignments": [
            {
                "task_id": item["effective"]["agent_id"],
                "owner_role": item["effective"]["display_name"],
                "agent_profile": item["effective"]["capability"],
                "scope": item["effective"].get("allowed_actions", []),
                "fallback_plan": "Blocked actions are recorded and do not count as successful task completion.",
            }
            for item in resolved_agents
        ],
    }
    write_json(run_dir / "ai_company" / "meeting_decision.json", meeting)
    return meeting


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Fab agent capability-boundary POC.")
    parser.add_argument("--case", default="shopping-site", choices=["shopping-site"])
    parser.add_argument("--mode", default="live", choices=["mock", "live"])
    parser.add_argument("--out-root", default=str(ROOT / "results" / "fab_agent_poc"))
    args = parser.parse_args()

    run_dir = Path(args.out_root) / run_id()
    worktree = run_dir / "worktree"
    agents_dir = run_dir / "agents"
    ai_dir = run_dir / "ai_company"
    worktree.mkdir(parents=True, exist_ok=True)
    ai_dir.mkdir(parents=True, exist_ok=True)

    resolved_agents: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []
    for agent_dir in EXAMPLE_AGENTS:
        resolved = resolve_fab_agent(agent_dir, agents_dir)
        if resolved.get("passed"):
            resolved_agents.append(resolved)
        else:
            validation_errors.append(resolved)

    meeting = build_meeting(run_dir, resolved_agents)

    audit_entries: list[dict[str, Any]] = []
    by_id = {item["effective"]["agent_id"]: item for item in resolved_agents}
    planner = by_id.get("fab_product_planner")
    builder = by_id.get("fab_frontend_builder")
    reviewer = by_id.get("fab_artifact_reviewer")

    if planner:
        planner_dir = Path(planner["output_dir"])
        audit_entries.append(audit_action(planner_dir, planner["effective"], "write_agent_artifact", "agents/fab_product_planner/planning-memo.md", "planner memo allowed"))
        write_text(planner_dir / "planning-memo.md", "Product grid, cart count, total update, and checkout limitation are required.\n")
        audit_entries.append(audit_action(planner_dir, planner["effective"], "write_project_file", "worktree/shopping-site/app.js", "negative enforcement A: readonly agent attempted project write"))

    live_result: dict[str, Any] | None = None
    live_outputs_copied = False
    if args.mode == "live":
        live_result = run_live_harness(run_dir)
        if int(live_result.get("exit_code", 1)) == 0:
            live_outputs_copied = copy_live_outputs(live_result, worktree)
    else:
        deterministic_shopping_site(worktree)

    if builder:
        builder_dir = Path(builder["output_dir"])
        for rel in [
            "worktree/shopping-site/index.html",
            "worktree/shopping-site/styles.css",
            "worktree/shopping-site/app.js",
            "worktree/shopping-site/README.md",
        ]:
            audit_entries.append(audit_action(builder_dir, builder["effective"], "write_project_file", rel, "builder output allowed"))

    verifier = verify_package(worktree, "shopping-site")
    write_json(ai_dir / "artifact_verify_report.json", verifier)

    if reviewer:
        reviewer_dir = Path(reviewer["output_dir"])
        audit_entries.append(audit_action(reviewer_dir, reviewer["effective"], "run_verifier", "ai_company/artifact_verify_report.json", "reviewer verifier read allowed"))
        audit_entries.append(audit_action(reviewer_dir, reviewer["effective"], "edit_project_file", "worktree/shopping-site/index.html", "negative enforcement C: reviewer attempted edit"))

    all_audit_entries: list[dict[str, Any]] = []
    for item in resolved_agents:
        all_audit_entries.extend(load_audit_entries(Path(item["output_dir"])))

    blocked_attempts = [item for item in all_audit_entries if item.get("blocked")]
    effective_policies = [item["effective"] for item in resolved_agents]
    enforcement_passed = not validation_errors and len(blocked_attempts) >= 2
    live_generation_passed = args.mode == "mock" or bool(live_result and live_result.get("exit_code") == 0 and live_outputs_copied)
    overall_status = "pass" if enforcement_passed and verifier["all_passed"] and live_generation_passed else "fail"
    failure_category = ""
    if validation_errors:
        failure_category = "FAB_AGENT_POLICY_VIOLATION"
    elif not enforcement_passed:
        failure_category = "CIM_ENFORCEMENT_EVIDENCE_MISSING"
    elif not live_generation_passed:
        failure_category = "LIVE_WEBSITE_GENERATION_FAILED"
    elif not verifier["all_passed"]:
        failure_category = verifier.get("failure_category") or "ARTIFACT_CONTRACT_FAILED"

    summary = {
        "schema_version": "fab-agent-poc.v1",
        "run_id": run_dir.name,
        "run_type": "fab_agent_poc",
        "mode": args.mode,
        "case": args.case,
        "started_at_utc": datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc).isoformat(),
        "finished_at_utc": utc_now(),
        "overall_status": overall_status,
        "failure_category": failure_category,
        "run_dir": str(run_dir),
        "worktree": str(worktree),
        "meeting": meeting,
        "effective_policies": effective_policies,
        "validation_errors": validation_errors,
        "audit_entries": all_audit_entries,
        "blocked_attempts": blocked_attempts,
        "verifier": verifier,
        "live_result": live_result,
        "acceptance": {
            "resolved_three_fab_agents": len(resolved_agents) == 3,
            "blocked_readonly_project_write": any(item.get("agent_id") == "fab_product_planner" and item.get("blocked") for item in blocked_attempts),
            "blocked_reviewer_project_edit": any(item.get("agent_id") == "fab_artifact_reviewer" and item.get("blocked") for item in blocked_attempts),
            "shopping_site_verified": bool(verifier["all_passed"]),
            "live_generation_passed": live_generation_passed,
        },
    }
    write_json(ai_dir / "fab_poc_summary.json", summary)
    write_json(run_dir / "fab_poc_summary.json", summary)
    write_json(
        ai_dir / "final_run_verdict.json",
        {
            "overall_status": overall_status,
            "failure_category": failure_category,
            "root_failed_job": "" if overall_status == "pass" else "fab_agent_poc",
            "failed_checks": [key for key, passed in summary["acceptance"].items() if not passed],
            "source": "fab_agent_poc",
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
