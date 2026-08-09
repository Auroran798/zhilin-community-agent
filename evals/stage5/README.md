# Stage 5 deterministic evaluation

`python evals/stage5/run.py` evaluates the offline Fake LLM delivery path. Metrics are calculated from executable cases; no remote LLM judge or paid API is used. The data intentionally focuses on regression checks, high-risk escalation and prompt-injection interception. It does not claim evaluation of a separately configured real LLM.
