# Deterministic offline planner comparison

Dataset: Boston; requests: 200.
Sources: {'synthetic': 200}. Same candidates for each paired request.
No LLM, paid API, or live Maps calls were used.

| Mode | Nonempty plan | Full stop count | Feasible nonempty | Feasible full | Violation/unknown/no plan | Unknown hours | Avg stops |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive_scripted | 100.0% | 99.0% | 6.5% | 6.5% | 93.5% | 29.0% | 3.99 |
| constraint_aware_rules | 94.0% | 33.0% | 94.0% | 33.0% | 6.0% | 0.0% | 2.42 |

Rates use all requests as the denominator; failures are never dropped.
A full stop count alone does not mean a feasible plan. Unknown hours are unverified.

- Generated requests are not real-user outcomes.
- Feasibility uses estimates and historical hours, not live truth.
- Greedy planning is not globally optimal; partial plans are reported.
- Rule planner enforces these same constraints by construction; this is an integration benchmark, not an independent quality study.

Input/code fingerprint: `5c284dd2569bec0e301c64255c7e51dd14dbb27af750a7788765ab814f9a2a12`
