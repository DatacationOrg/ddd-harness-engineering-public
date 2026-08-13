# The Harness Scorecard

**Anyone can call a model. Engineering the harness around it is the job.**

Twelve components sit between a text generator and an agent you would let near production data.
Each one is a decision that creates capability, or risk, or — usually — both. This scorecard is the
list, with tick-boxes concrete enough to actually check.

**How to use it during the event.** Tick boxes as you finish each station. A box is honest only if
you can *show* it — in the Execution Dashboard, in the code, or in a test. "I think so" is not a tick.
Expect to leave the day with gaps; the gaps are the useful part.

**How to use it after.** This outlives the event. Point it at the next agent you or your team
ships — yours or someone else's — and read it as a review checklist. Most of these boxes are
unticked in most production agents, and the ones teams discover too late cluster in Group D.

The tick-boxes are drawn from Anthropic's *Building Effective Agents*, *Effective Context
Engineering for AI Agents* and *Effective Harnesses for Long-Running Agents*, plus the *12-Factor
Agents* manifesto. Links at the bottom.

---

## Group A — Think

### 1. Model
*Decides: capability ceiling, reasoning effort, cost, latency, streaming, structured output.*
> Covered at **S1 · Model, Prompt & Context**.

- [ ] I can name the exact model ID my agent runs on without opening a config file — and say why it and not the cheaper one next to it.
- [ ] I have run the same prompt at two reasoning efforts and compared the step count, the latency and the answer. I did not just assume more effort is better.
- [ ] Streaming is on for the user-facing path and off for the structured-output path — or I can say why they are the same.
- [ ] Every model call that must return a shape uses structured output, not a "reply in JSON" instruction plus a parser and a prayer.

### 2. Prompt
*Decides: behaviour. The "Goldilocks zone" — specific enough to steer, loose enough to generalise.*
> Covered at **S1 · Model, Prompt & Context**.

- [ ] My system prompt is organised into distinct sections with Markdown headings or XML tags, not one wall of prose.
- [ ] I have deliberately broken it in both directions — absurdly vague, then absurdly rigid — and watched two *different* failure modes. I found the Goldilocks zone rather than asserting it.
- [ ] There is no line in the prompt that exists only to patch one bad transcript. Hardcoded if-this-then-that logic is a bug report, not a prompt.
- [ ] The prompt is a named constant in version control, so a prompt change shows up in a diff and can be reverted like any other change.

### 3. Context engineering
*Decides: the scaling constraint. The smallest set of high-signal tokens that maximise the chance of the outcome.*
> Covered at **S1 · Model, Prompt & Context**, and revisited at every station after it.

- [ ] I know roughly how many tokens my agent spends *before the user types anything* — system prompt plus tool schemas plus skill descriptions.
- [ ] Nothing is in the context window "just in case". Every file, tool result and memory in there got fetched because a step needed it (just-in-time retrieval, lightweight identifiers over eager loading).
- [ ] I have a named answer for what happens at turn 50 — compaction, notes persisted outside the context window, or delegation to a subagent — and I have watched it fire at least once.
- [ ] Large tool outputs are truncated or paginated at the tool boundary. The model is never handed 200KB and asked to be sensible about it.

---

## Group B — Act

### 4. Tools
*Decides: the action surface. Bloated, overlapping tool sets are the single most common failure mode.*
> Covered at **S2 · Tools & Environment**.

- [ ] Every tool docstring is written for a model, not a human: it says *when to reach for this tool*, not just what it does.
- [ ] No two of my tools overlap. If a colleague can't definitively say which tool applies to a given task, neither can the model.
- [ ] Every error path returns one short, actionable sentence the model can recover from — not a stack trace, not a bare `None`, not silence. I have triggered at least one and read what the *model* saw.
- [ ] Parameters are descriptive and unambiguous (`path: str`, not `arg1`), and each tool is self-contained: calling it needs no knowledge that lives only in my head.

### 5. Skills
*Decides: procedural knowledge, progressively disclosed. Free until invoked.*
> Covered at **S5 · Skills**.

- [ ] The `description` in my `SKILL.md` frontmatter says *when* to use the skill, and the agent triggered it without me naming it in chat.
- [ ] The skill encodes procedure — the house convention, the order of operations — not a capability that should have been a tool.
- [ ] Only the frontmatter is loaded until the skill is invoked. I can state the token cost of having the skill installed and not using it (it should be small).
- [ ] `allowed_tools` scopes what the skill may reach, and I know which one wins when a skill contradicts the system prompt — because I wrote a contradicting skill and tested it.

### 6. MCP
*Decides: interop. Someone else's tools, on a standard protocol, without writing an integration.*
> Covered at **S6 · MCP**.

- [ ] I can list every tool each connected server contributes, by name, without reconnecting to check.
- [ ] The list handed to the model is filtered to the task — strictly shorter than the server's full list — and I can say what I dropped and why.
- [ ] Untrusted MCP servers sit behind the same approval gate as shell execution. Connecting one does not quietly widen the blast radius.
- [ ] I have attached an oversized server and watched tool selection degrade, so I recognise that failure before it reaches production.

### 7. Environment / sandbox
*Decides: where actions actually land. The `backend`. Blast radius.*
> Covered at **S2 · Tools & Environment** and **S4 · The interpreter**.

- [ ] I can state the blast radius in one sentence: exactly which paths the agent can write, and what happens when it reaches past them.
- [ ] I have tried to escape — `../../.env`, an absolute path, a symlink — and been refused, and the refusal is visible in the trace.
- [ ] Everything destructive lands somewhere disposable. I can regenerate the whole environment with one command, which is what makes it safe to be reckless on purpose.
- [ ] If the backend grants shell execution, I have added at least one of: command allowlist, timeout, output cap, approval gate. Reading the library's own warning counts as a prompt, not as a guardrail.

---

## Group C — Persist & Delegate

### 8. Memory & state
*Decides: what survives a turn. Prerequisite for pause/resume.*
> Covered at **S7 · Human in the loop** (and its organiser pre-work).

- [ ] I can name what survives a turn and what does not, and the answer came from reading the code rather than from hoping.
- [ ] There is a checkpointer and a stable thread id, so a conversation *resumes* rather than *replays*.
- [ ] I have killed the process mid-run and restarted it, and work continued from the last checkpoint instead of from zero.
- [ ] State lives in one place. The UI reads the agent's state rather than keeping a parallel copy that can silently drift out of sync.

### 9. Orchestration & subagents
*Decides: control flow. Small focused agents over one monolith; clean context per subtask.*
> Covered at **S3 · Subagents & Orchestration**.

- [ ] Each subagent's `description` is specific enough that the main agent picks the right one without me naming it.
- [ ] At least one tool is given to a subagent *only*, and I have confirmed it is absent from the main agent's toolset. Least privilege made structural, not prompted.
- [ ] A subagent returns a distilled summary — hundreds to low thousands of tokens — not its raw working transcript. That's the context-engineering win, not just tidiness.
- [ ] I can point at the trace and show the hop into the subagent's own namespace and back out again.

---

## Group D — Be Trusted

### 10. Guardrails & permissions
*Decides: least privilege, allowlists, injection defence, blast-radius limits.*
> Covered at **every station** — safety is the repeating beat, not the closing lecture.

- [ ] Capability the agent must not have is *absent*, not merely discouraged in the prompt. A prompt is a preference; a missing tool is a guarantee.
- [ ] Tool output is treated as data, never as instruction. Untrusted content is wrapped in explicit delimiters, and I have run a planted prompt injection through and watched behaviour not change.
- [ ] There is an allowlist somewhere — domains, commands, or paths — and I can recite what is on it from memory.
- [ ] I have genuinely attacked my own agent and written down what worked *before* I fixed it. A station isn't done when the code compiles; it's done when you have broken it and then stopped yourself from breaking it.

### 11. Human in the loop
*Decides: approve / edit / reject. "Contact humans with tool calls."*
> Covered at **S7 · Human in the loop**.

- [ ] The set of tools that pause for approval is explicit, and I can list it without looking.
- [ ] All three responses work and produce visibly different outcomes: approve, **edit the arguments**, reject with feedback. The middle one is the one nobody expects.
- [ ] The approval UI shows the actual call and its actual arguments — not "the agent would like to do something".
- [ ] The pause is real: state survives a UI refresh, because the graph genuinely stopped rather than a dialog appearing in front of work that already happened.

### 12. Observability & evals
*Decides: whether you can prove any of the above. The component teams skip and regret.*
> Covered at **S8 · Observability & evals**, and used at every station before it.

- [ ] I can walk one full trace end to end and narrate every step out loud. Any step I cannot explain is a bug I haven't found yet.
- [ ] Every tool call in the trace shows its arguments *and* its result, not just its name.
- [ ] At least three evals run in CI: one capability (it does the thing), one guardrail (it refuses the thing), one injection (it ignores the planted instruction). Evals in CI, not vibes.
- [ ] Deliberately breaking a guardrail turns exactly one of those evals red — and I have checked that this week, not the week the tests were written.

---

## What to do with this

**Score it honestly, twice.** Once at the showcase, on the agent you built today. Then again, next
week, on whatever agent your team already has in production. The second run is the one that pays for
the day.

**Read the pattern, not the total.** A 40/44 is not the goal and the number means nothing on its
own. What means something is *where* the gaps cluster:

- Gaps in **Group A (Think)** usually mean the agent works and nobody knows why. It will stop working and nobody will know why then either.
- Gaps in **Group B (Act)** are the ones that show up as "the model is dumb". Usually the model is fine and the tool descriptions are ambiguous.
- Gaps in **Group C (Persist & Delegate)** are what make long tasks impossible rather than merely slow.
- Gaps in **Group D (Be Trusted)** are the ones that decide whether this ever leaves your laptop. They are also the cheapest to close *before* launch and the most expensive after.

**Two questions to take to your next agent review**, both of which this scorecard exists to make
answerable:

1. What is the worst thing this agent can do, and what structurally stops it?
2. If someone changes the prompt next month, what turns red?

---

## References

- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — Anthropic
- [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic
- [12-Factor Agents](https://www.humanlayer.dev/blog/12-factor-agents) — HumanLayer
