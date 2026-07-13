# Claude Multi Agent

Common-case multi-agent runtime for Claude Code users.

The project is designed for Ubuntu 22.04 users who already have their own
Claude Code / Router / LLM setup. This repository does not choose your model,
provider, router profile, or output-token settings. Your existing Claude
environment remains the source of truth.

## Quick Start: Ubuntu 22.04

Use the install skill first. It prepares this repository and the local dashboard.

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

Recommended source checkout:

```bash
git -c core.autocrlf=false clone https://github.com/fr407041/claude_multi_agent.git
```

GitHub zip downloads also work. Strict package verification is byte-for-byte;
if a corporate Git client or Windows checkout converts LF to CRLF,
`verify_install.py --strict` reports `CRLF_LINE_ENDING_CONVERSION` with
remediation instead of a vague hash error.

Start the dashboard:

```bash
bash agent_os_mvp/start-dashboard.sh
```

Open:

```text
http://127.0.0.1:15174/
```

Health check:

```bash
curl http://127.0.0.1:18010/health
```

Stop:

```bash
bash agent_os_mvp/stop-dashboard.sh
```

## Two Skills, Two Jobs

### 1. Install skill

Path:

```text
skills/install-multi-agent-runtime/
```

Use this for first-time setup:

- create `.env` when missing
- create `agent-runs/`, `results/`, and `logs/`
- install dashboard backend/frontend dependencies locally
- run doctor and install verification
- confirm the operation skill exists

It must not modify global Claude Code, Claude Code Router, model, provider,
token, shell, npm, or Python configuration.

### 2. Operation skill

Path:

```text
.claude/skills/research-task-orchestrator/
```

Use this after installation:

```text
Use the research-task-orchestrator skill to run: <your task>
```

It handles bounded task planning, agent meeting, worker dispatch, artifact
verification, watchdog checks, and dashboard reporting. It assumes installation
has already been completed.

## Dashboard Behavior

The dashboard is a common task observer. It is not specific to websites, PTT,
stocks, or any one validation case.

Completed runs show:

- `Review outputs` as the primary action
- `Generated outputs` with real files/folders, type, size, modified time, and
  safe inline previews
- verification evidence and limitations
- meeting discussion and task plan when recorded

The dashboard uses manual refresh by default so users can inspect a result
without the page flickering between stale and live states.

The frontend reads `/runtime-config.json` at startup to find the backend API.
`agent_os_mvp/start-dashboard.sh` and the Docker image both generate this file
from the selected backend port. If the backend cannot be reached, the dashboard
now shows `Dashboard cannot reach backend` with the exact API base and health
check URL instead of pretending there are no runs.

Watched artifact roots:

- `AI_COMPANY_RESULTS_ROOT` defaults to `./results/ai_company_task_harness`
- `MICRO_GATES_RUNS_ROOT` defaults to `./agent-test-runs`
- `/health` reports the exact roots the dashboard is reading.
- If an older run records a Windows host path, the dashboard normalizes it back
  to the mounted project root before checking whether an artifact exists.

Default local ports:

```env
DASHBOARD_BACKEND_PORT=18010
DASHBOARD_FRONTEND_PORT=15174
```

If ports conflict:

```bash
AGENT_OS_BACKEND_PORT=28010 \
AGENT_OS_FRONTEND_PORT=25174 \
AGENT_OS_PUBLIC_API_BASE_URL=http://127.0.0.1:28010 \
bash agent_os_mvp/start-dashboard.sh
```

## Verification

Common install verification:

```bash
python3 scripts/verify_install.py --strict --json
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/ai-company-release-readiness-strict-demo.json --mode mock
```

`/run-task` success is contract-aware. A wrapper, install check, or mock harness
exit code is not enough: when a task asks for exact JSON or exact text, the
runtime writes `task-contract.json` and only reports success if the model output
satisfies that task contract. Contract failures use
`TASK_OUTPUT_CONTRACT_FAILED`.

Managed workers and the local action executor also use a safe-read guard for
file context. `read_file` actions go through `scripts/safe_file_context.py`,
which checks file size first, then records bounded context metadata instead of
blindly reading whole files into model context. Action logs include
`size_bytes`, `included_chars`, `skipped_bytes`, `estimated_tokens`,
`source_estimated_tokens`, and `context_guard_action` (`full_read`,
`chunked_context`, or `blocked`). Files over `file_hard_limit_bytes` fail with
`INPUT_FILE_TOO_LARGE`; files over the soft limit are chunked and audited.

This is enforceable for CIM-managed workers and the local-model action
executor because those code paths route file reads through the wrapper. It is
not a hard sandbox for unrestricted Claude Code or arbitrary shell access. If a
model is granted full tools / `--dangerously-skip-permissions`, file-read policy
must be enforced by that tool layer or by a container/filesystem sandbox.

If you reuse an existing Docker image and only mount the latest repo, you must
also mount the repo runtime override:

```text
./agent-test-runtime/run_task.sh:/app/runtime/run_task.sh:ro
```

Otherwise the container may keep executing the baked image runtime. Verify the
no-rebuild path before trusting `/run-task`:

```bash
API_BASE=http://127.0.0.1:18080 bash scripts/run-task-contract-smoke.sh
```

On PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-task-contract-smoke.ps1 -ApiBase http://127.0.0.1:18080
```

If this reports `STALE_IMAGE_RUNTIME`, the latest repo is mounted but the
container is not executing the mounted runtime override. Use
`docker-compose.agent-test.yml`, add the runtime override mount to `docker run`,
or rebuild the image.

Common generated-output live demo:

```bash
bash scripts/run-shopping-site-common-demo.sh live
```

This asks the installed agent environment to hold the normal bounded meeting,
generate a small static output package, and verify the generated files. The
default demo is a shopping-site package because it is easy for humans to review:
`shopping-site/index.html`, `shopping-site/styles.css`,
`shopping-site/app.js`, and `shopping-site/README.md`. The architecture is not
shopping-specific; it is a common "generated outputs + verification evidence"
demo profile.

Deterministic common demo:

```bash
bash scripts/run-shopping-site-common-demo.sh mock
```

Mock mode does not prove model quality. It proves the installed repo, generated
output verifier, result format, and dashboard display can complete on a clean
machine without depending on a live provider.

GitHub repository scoring demo:

```bash
bash scripts/run-github-repo-scoring-demo.sh mock
bash scripts/run-github-repo-scoring-demo.sh live
```

The default target is `openhands/openhands`. Override it without editing the
repo:

```bash
GITHUB_REPO_SCORING_TARGET=openhands/openhands \
GITHUB_REPO_SCORING_REF=main \
bash scripts/run-github-repo-scoring-demo.sh live
```

Normal live defaults are intentionally usable rather than ultra-conservative:

```bash
export CCR_MAX_OUTPUT_TOKENS="${CCR_MAX_OUTPUT_TOKENS:-4096}"
export CLAUDE_CHILD_TIMEOUT_SEC="${CLAUDE_CHILD_TIMEOUT_SEC:-300}"
export AI_COMPANY_LIVE_REQUEST_TIMEOUT_SEC="${AI_COMPANY_LIVE_REQUEST_TIMEOUT_SEC:-300}"
export AI_COMPANY_MAX_PARALLEL_WORKERS="${AI_COMPANY_MAX_PARALLEL_WORKERS:-2}"
```

`CCR_MAX_OUTPUT_TOKENS` controls the maximum LLM response length for each
worker call. It does not control how much repository input is read; input is
bounded separately by the safe-read context guard.

If the local model host is overloaded or intermittently refusing connections,
drop to troubleshooting mode without editing the repo:

```bash
AI_COMPANY_MAX_PARALLEL_WORKERS=1 \
AI_COMPANY_MAX_TOTAL_JOBS=5 \
bash scripts/run-github-repo-scoring-demo.sh live
```

This case prepares an every-file repository inventory, `file_context_manifest`,
bounded snippets, and inventory shards before dispatching the skill workflow.
The agent scores architecture, maintainability, testing, documentation,
security, and developer experience, then writes concrete improvement
recommendations under `repo-score/`.

The important contract is coverage, not prompt stuffing: every file must appear
in the inventory/context manifest, while large or unsupported files are handled
through safe-read metadata, skipped bytes, and bounded chunks to avoid token
overflow.

The generated `summary.md` must be a clean user-readable artifact. Raw provider
JSON envelopes, `chat.completion` payloads, or reasoning dumps are verifier
failures and must be repaired before a live run is accepted.

Dashboard verification:

```bash
bash agent_os_mvp/smoke-dashboard.sh
```

## Fab Agent POC: Persona Is User-Owned, Capability Is CIM-Owned

This POC proves a common governance pattern:

- Fab users create a simple Role Card: `name`, `role`, `background`, and
  `style`.
- Fab users choose a CIM-approved role such as `planner`, `builder`, or
  `reviewer`; they do not configure skills, MCP, hooks, tools, or output paths.
- CIM developers own skills, MCP groups, hooks, tool actions, and output path
  boundaries.
- Runtime evidence, not agent self-reporting, decides whether the boundary was
  enforced.

### Common path: create a Role Card

List available roles:

```bash
python3 scripts/list_roles.py
```

Create a Role Card interactively:

```bash
python3 scripts/create_role_card.py
```

Or create one with a single command:

```bash
python3 scripts/create_role_card.py \
  --name Mina \
  --role builder \
  --background "Frontend builder focused on clean, reviewable UI." \
  --style concise
```

This creates:

```text
fab_agents/mina/role-card.yaml
```

Validate it:

```bash
python3 scripts/validate_role_card.py fab_agents/mina/role-card.yaml
```

Resolve it into CIM-managed runtime policy:

```bash
python3 scripts/resolve_role_card.py fab_agents/mina/role-card.yaml --out results/fab_agent_resolved
```

Role Card fields are intentionally small:

```yaml
name: Mina
role: builder
style: concise
background: |
  Frontend builder focused on clean, reviewable UI.
```

Role Cards cannot define `skills`, `mcp_servers`, `hooks`, `allowed_tools`,
`commands`, or `capability`. Those are owned by CIM role presets.

### CIM developer path: manage capabilities

CIM role presets live in:

```text
configs/cim_roles/
```

Each role maps to an existing capability in:

```text
configs/cim_capabilities/
```

List raw CIM capabilities:

```bash
python3 scripts/list_cim_capabilities.py
```

Validate a Fab agent:

```bash
python3 scripts/validate_fab_agent.py fab_agents/examples/fab_product_planner
```

Resolve the effective runtime policy:

```bash
python3 scripts/resolve_fab_agent.py fab_agents/examples/fab_frontend_builder --out results/fab_agent_resolved
```

Run the capability-boundary POC:

```bash
python3 scripts/run_fab_agent_poc.py --case shopping-site --mode live
```

The POC uses website generation as a human-reviewable fixture. The generic
contract is: agents discuss, produce a generated output package, record
effective capability policy, record allowed/blocked actions, run deterministic
verification, and show the evidence in the dashboard.

Deterministic mode is available for clean-machine checks:

```bash
python3 scripts/run_fab_agent_poc.py --case shopping-site --mode mock
```

The dashboard reads these runs from:

```env
FAB_AGENT_POC_RESULTS_ROOT=./results/fab_agent_poc
```

Backend unit tests:

```bash
cd agent_os_mvp/backend
python3 -m unittest discover -s tests -v
```

Frontend build:

```bash
cd agent_os_mvp/frontend
npm run build
```

## Advanced: Docker Compose

Docker Compose is only for maintainers, CI, or isolated reproduction. It is not
the common user install path.

```bash
cd agent_os_mvp
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:15174/
```

## Repository Contents

- `skills/install-multi-agent-runtime/`: install and doctor skill
- `.claude/skills/research-task-orchestrator/`: runtime operation skill
- `agent_os_mvp/`: dashboard backend/frontend package
- `configs/cim_roles/`: user-facing role presets that map to CIM capabilities
- `fab_agents/templates/`: copyable Role Card examples
- `scripts/verify_install.py`: repository verification
- `scripts/run_ai_company_task_harness.py`: mock/live task harness
- `scripts/run-agent-micro-gates.ps1`: precise live micro-gate runner
- `scripts/list_roles.py`: list simple user-facing roles
- `scripts/create_role_card.py`: create a Role Card without editing JSON
- `scripts/validate_role_card.py`: reject Role Card attempts to self-assign skills/MCP/hooks/tools
- `scripts/resolve_role_card.py`: materialize Role Card into effective runtime policy
- `scripts/list_cim_capabilities.py`: list CIM-approved capability choices
- `scripts/validate_fab_agent.py`: reject Fab agent attempts to self-assign skills/MCP/hooks/tools
- `scripts/resolve_fab_agent.py`: generate effective policy, Claude settings, MCP config, and audit log
- `scripts/run_fab_agent_poc.py`: common capability-boundary POC runner
- `scripts/verify_agent_micro_gate.py`: deterministic micro-gate verifier
- `scripts/run-shopping-site-common-demo.sh`: common live generated-output demo
- `scripts/verify_generated_output_package.py`: generated output package verifier

## Legacy Stress Tests

`scripts/run-agent-micro-gates.ps1` still exists for strict PTT Stock crawler
stress testing. It depends on an external website and on the model reliably
creating crawler artifacts, so it is useful for hardening but no longer the
common install/live demo acceptance path. Missing artifacts in those gates are
reported as model artifact reliability failures, not as a dashboard install
failure. Files that exist but fail semantic checks, such as a too-short parsed
article body, are classified as `ARTIFACT_CONTENT_TOO_SHORT` under
`ARTIFACT_CONTRACT_FAILED`.

## Safety

Do not commit API keys, passwords, Docker images, model weights, runtime logs,
SQLite databases, `.venv`, `node_modules`, or generated result caches.
