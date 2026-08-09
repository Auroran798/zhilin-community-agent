import json
from pathlib import Path
report=json.loads(Path("evals/agent/reports/latest.json").read_text(encoding="utf-8"))
Path("evals/agent/reports/latest.md").write_text("# Stage 3 Agent Evaluation\n\n```json\n"+json.dumps(report,ensure_ascii=False,indent=2)+"\n```\n",encoding="utf-8")
print("exported evals/agent/reports/latest.md")
