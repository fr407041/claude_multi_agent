# Skills

This repository separates install-time skills from runtime operation skills.

- `skills/install-multi-agent-runtime/`: first-time setup, doctor checks, local directory initialization, and mock verification guidance.
- `.claude/skills/research-task-orchestrator/`: runtime operation skill used by Claude/backend agents to run bounded multi-agent tasks.

Do not use the install skill as a backend runtime skill. Do not use the runtime operation skill to explain or mutate global Claude/Router/model setup.
