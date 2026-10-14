# M4 - Baseline running

## Saudi Digital Concierge
Saudi Digital Concierge is a research project investigating whether a multi-agent Large Language Model (LLM) architecture can improve travel planning compared with an equivalent single-agent LLM architecture.

### 1. Success: Which matters most: accuracy, speed, or user experience?

Our priority is *accuracy and constraint satisfaction*, followed by recommendation relevance and user experience. The system should provide reliable recommendations that match user budgets, dates, and preferences.

Speed and cost are secondary, but we will monitor them to ensure efficient performance.

### 2.Task suite: Which typical tasks and edge cases? How many are enough?

We will evaluate *100 scenarios: 70 typical tasks and 30 edge cases*.

- *Typical Tasks:* Hotel recommendations, attraction discovery, event recommendations, and itinerary planning.
- *Edge Cases:* Limited budgets, conflicting constraints, missing information, and multiple complex requirements.

The scenarios will cover different Saudi cities and both Arabic and English requests.

| Dataset | Scenarios | Purpose |
|---|---:|---|
| Development | 60 | Testing and improvement |
| Validation | 20 | Performance monitoring and model selection |
| Final Test | 20 | Unbiased final evaluation |

### 3.Metrics: Rule-based checks or LLM judges? Process or outcome?

We will use *both rule-based checks and LLM judges* to evaluate outcomes and execution processes.

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

We will use *Single-Agent systems as baselines* and *Multi-Agent systems as treatments*, using two LLMs: Qwen and OpenAI.

| Model | Baseline | Treatment |
|---|---|---|
| Qwen | Qwen Single-Agent | Qwen Multi-Agent |
| OpenAI | OpenAI Single-Agent | OpenAI Multi-Agent |

All configurations will use the same knowledge base, equivalent tools, scenarios, and evaluation metrics to ensure a fair comparison.

### 5.Iteration: When do evals run? How do we catch things getting worse?

We will run evaluations after major updates to prompts, tools, retrieval methods, or agent architecture.

- *Development (60):* Identify errors and improve the systems.
- *Validation (20):* Compare versions and detect performance regressions.
- *Final Test (20):* Evaluate all four configurations using three runs per scenario.

We will detect regressions by monitoring evaluation scores, tool errors, execution time, and cost. If performance decreases, we will analyze failed scenarios and execution traces before making improvements.

The final test set will remain separate from development to ensure a fair evaluation.
