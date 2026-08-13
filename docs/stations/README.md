# The workshop modules

This folder documents assignment flow and implementation checkpoints.

| | Station | Component |
|---|---|---|
| **S1** | [Model, prompt & context](s1.md) | Model · Prompt · Context engineering |
| **S2** | [Tools & the environment](s2.md) | Tools · Environment · Guardrails |
| **S7** | [Human in the loop](s7.md) | Human in the loop · Memory & state |

## Optional extensions

| Station | Extension |
|---|---|
| [S3](s3.md) | Web research in a subagent, with prompt-injection defences |
| [S5](s5.md) | A Northwind filing skill |
| [S4](s4.md) | Local interpreter and shipment-data profiling |
| [S6](s6.md) | MCP tool filtering |
| [S8](s8.md) | Evals for capability, boundary, and injection behaviour |

[The capstone library](../capstones.md) is follow-up work for a longer event.

---

## How a station works

Use this sequence for every module.

| Beat | |
|---|---|
| **Ship** | Apply the guided change manually, or brief your coding agent. Get it working. |
| **Break** | Feed it garbage, oversized input, malicious input. Try to escape. |
| **Guard** | Add the constraint that makes your break impossible. |
| **Observe** | Find the whole story in the execution trace. |
| **Log** | Tick [the scorecard](../../SCORECARD.md). |

## Using your coding agent

Each core module has a manual route and coding-agent route.
Read [CLAUDE.md](../../CLAUDE.md) for implementation conventions.

## If you get stuck

Follow the module progression guide first:

- [docs/modules/README.md](../modules/README.md)

Reference solutions are cumulative by branch:

```bash
git checkout s0   # starter branch (S1 unsolved)
git checkout s1   # module 1 complete
git checkout s2   # module 2 complete (built on s1)
git checkout s3   # module 3 complete (built on s2)
```

To inspect only what changed between modules:

```bash
git diff s1..s2
git diff s2..s3
```

Each module should start in a not-implemented starter state (UI + code scaffold),
then move from red tests to green tests using the steps in the module README.
