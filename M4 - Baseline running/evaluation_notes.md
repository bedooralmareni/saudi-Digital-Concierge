# M4 - Baseline running

## Saudi Digital Concierge
Saudi Digital Concierge is a research project investigating whether a multi-agent Large Language Model (LLM) architecture can improve travel planning compared with an equivalent single-agent LLM architecture.

### 1. Success: Which matters most: accuracy, speed, or user experience?

Accuracy and constraint satisfaction are our highest priorities because the system must recommend suitable hotels, attractions, and events based on user requirements. User experience comes second, followed by response speed.

### 2.Task suite: Which typical tasks and edge cases? How many are enough?

Our task suite includes four typical tasks: hotel recommendations, attraction discovery, event recommendations, and complete itinerary planning.

Edge cases include limited budgets, conflicting constraints, missing information, and requests with multiple complex requirements.

We will evaluate *60 diverse scenarios: 40 typical tasks and 20 edge cases*, covering both normal and challenging situations to assess the system's performance and robustness.

### 3.Metrics: Rule-based checks or LLM judges? Process or outcome?

| Metric | Evaluation method | Process or outcome |
|---|---|---|
| Constraint satisfaction | Rule-based checks | Outcome |
| Itinerary consistency | Rule-based checks | Outcome |
| Itinerary completeness | Rule-based checks | Outcome |
| Recommendation relevance | LLM judges | Outcome |
| Tool usage | Rule-based checks and LLM judges | Process |
| Execution steps | Rule-based checks and LLM judges | Process |
| Errors | Rule-based checks | Process |


### 4.Baselines: Compare to what? A plain model call, a single agent, the last version?

We will use *Single-Agent systems as our baselines* and *Multi-Agent systems as our experimental treatments*.

### 5.Iteration: When do evals run? How do we catch things getting worse?

We will run evaluations after each major system update, including changes to prompts, tools, retrieval, or architecture. During development, we will use *60 development scenarios* to identify errors and improve performance, then *20 validation scenarios* to compare versions and detect regressions. We will track constraint satisfaction, recommendation relevance, itinerary completeness, consistency, tool errors, execution time, and API cost. If performance drops, we will review failed scenarios and traces, fix the issue, and rerun evaluations. After finalizing the configuration, we will test all four systems on the same *20 held-out final scenarios*, with three runs per configuration under controlled settings.