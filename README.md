# DDD — Harness Engineering

Streamlit harness for deepagents with assignment-driven implementation modules.

- **[SCORECARD.md](SCORECARD.md)** — the 12 components of an agent, as a checklist you keep afterwards
- **[docs/modules/](docs/modules/README.md)** — base-to-solution module branch flow and per-module assignment READMEs
- **[CLAUDE.md](CLAUDE.md)** — architecture and implementation conventions

---

## Setup

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/):

**Windows (PowerShell)**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS and Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal and verify the installation:

```bash
uv --version
```

Then set up and run the project:

```bash
git clone https://github.com/DatacationOrg/ddd-harness-engineering-public.git
cd ddd-harness-engineering-public

uv sync                                          # install everything
cp .env.example .env                             # PowerShell: Copy-Item .env.example .env
                                                 # then paste in the key you were given
uv run python scripts/seed_sandbox.py --reset    # generate the agent's sandbox
uv run streamlit run ddd_harness_engineering/main.py
```

Then ask it something in the collapsible chat drawer on the right. The **Activity** workspace shows
agent actions, arguments, results, and approval decisions.

```bash
uv run pytest        # no API key required
```

---

## Sandbox

`scripts/seed_sandbox.py` generates `sandbox/northwind-freight/`.

Use it as the only runtime workspace for assignments.

---

## How a station works

Every module follows this sequence:

| Beat | |
|---|---|
| **Ship** | Apply the guided change manually, or brief your coding agent. Get it working. |
| **Break** | Feed it garbage, oversized input, malicious input. Try to escape the sandbox. |
| **Guard** | Add the constraint that makes your break impossible. |
| **Observe** | Find the whole story in the execution trace. |
| **Log** | Tick the scorecard. Write one line on what surprised you. |

---

## Safety

- **Never commit `.env`.** It is gitignored. Never paste your key into chat and never screen-share it.
- Point the agent at `sandbox/` and nothing else. Station 2 is where you make that a hard boundary
  rather than a good intention.
- Station 4 enables shell execution. Keep command guardrails enabled.
