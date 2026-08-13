---
name: developing-with-streamlit
description: "Use for ALL Streamlit work in this repo: creating or editing pages, widgets and layouts; debugging reruns, session state or caching; styling, theming and CSS; performance work; custom components. Also covers this project's own Streamlit conventions (the chat UI and Execution Dashboard). Triggers: streamlit, st., st.session_state, rerun, st.cache_resource, st.fragment, st.dialog, st.status, dashboard, app.py, main.py, chat.py, widget, layout, theme, CSS, styling, slow app, caching, custom component."
---

# Developing with Streamlit

This is a **routing skill**. It has two jobs:

1. Point you at Streamlit's own reference documentation, which ships inside the installed
   `streamlit` package — always matching the version this project actually resolves.
2. Record the Streamlit conventions specific to *this* repo.

Read section 1 for general Streamlit questions. Read section 2 before editing any file in
`ddd_harness_engineering/`.

---

## 1. Streamlit's shipped reference docs

The `streamlit` package vendors a large, well-maintained reference set (~25 topic files:
API reference, session state, performance, layouts, theming, dashboards, chat UI, custom
components, and more). It is **not** committed to this repo — it arrives with `uv sync`.

**Locate it (works on Windows, macOS and Linux — do not hardcode the path):**

```bash
uv run python -c "import streamlit, pathlib; print(pathlib.Path(streamlit.__file__).parent / '.agents' / 'skills' / 'developing-with-streamlit')"
```

That prints a directory containing:

- `SKILL.md` — Streamlit's own routing table, mapping task type to reference file
- `references/*.md` — the topic files (`session-state.md`, `performance.md`, `layouts.md`,
  `theme.md`, `dashboards.md`, `chat-ui.md`, `api-reference.md`, `custom-components-v2.md`, …)
- `assets/templates/` — runnable starter apps and theme `.toml` configs

**Workflow:** run the command above, read that directory's `SKILL.md` to pick the right
reference file, then read only that file. Do not read the whole `references/` tree — the point
of progressive disclosure is that you load one topic, not twenty-five.

> **Why a runtime lookup instead of a checked-in copy?** The venv layout differs by OS
> (`.venv/Lib/site-packages` on Windows vs `.venv/lib/python3.14/site-packages` elsewhere), so
> any hardcoded relative path is wrong on two thirds of the machines in the room. Resolving
> through `streamlit.__file__` is OS-independent and can never go stale against the installed
> version. If the command above fails, the environment is not set up — run `uv sync`.

---

## 2. This project's Streamlit conventions

This repo is a Streamlit front end wrapping a `deepagents` deep agent. Its distinguishing
feature is that the app **renders the agent's own internals** — reasoning, tool calls, subagent
hops and state updates — in a live Execution Dashboard.

**Orient yourself first.** Before editing, list `ddd_harness_engineering/` and read the module
you are about to change. Do not assume a function still lives where an older note says it does;
this codebase is actively edited during the workshop.

### Rules that matter here

- **Run it with `uv`.** `uv run streamlit run ddd_harness_engineering/main.py`. Never call a
  bare `python` or `streamlit` — they will miss the project venv.
- **Every widget interaction reruns the whole script, top to bottom.** Anything expensive or
  stateful must survive that. If you are about to construct an object per rerun, ask whether it
  belongs in `st.cache_resource` or in `st.session_state` instead.
- **`st.session_state` is the only thing that persists across reruns.** Conversation history and
  the execution-event log live there. When you add state, initialise it defensively
  (`if key not in st.session_state`) rather than assuming an ordering of reruns.
- **Streaming output goes through a placeholder or `st.write_stream`,** not a loop of `st.write`
  calls — otherwise each token appends a new element and the layout thrashes.
- **The execution trace is a feature, not debug output.** When you add a capability to the agent
  (a tool, a subagent, an MCP server), make sure it still shows up in the trace. A capability the
  dashboard cannot render is a capability participants cannot observe — and observing is the
  point of the exercise.
- **Never print secrets into the UI.** Settings come from `.env` via the `Settings` class in
  `ddd_harness_engineering/__init__.py`; `MICROSOFT_FOUNDRY_KEY` is a `SecretStr` precisely so it
  does not leak into a repr. Keep it that way — this app is screen-shared.

### Common tasks

| Task | Start here |
|---|---|
| Change what the dashboard shows | the trace/event rendering code in `ddd_harness_engineering/` |
| Add an approval dialog for a tool call | `st.dialog` + Streamlit's `references/session-state.md` |
| App feels slow / re-does work | Streamlit's `references/performance.md` (caching, fragments) |
| Restyle or re-theme | Streamlit's `references/theme.md` and `assets/templates/themes/` |
| Chat layout and message rendering | Streamlit's `references/chat-ui.md` |
