"""Check every shipped skill's identity, declared contracts, example and agent references."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from loop_runtime.model import require

skills = ROOT / ".agents/skills"
count = 0
for skill in sorted(skills.iterdir()):
    if not skill.is_dir():
        continue
    text = (skill / "SKILL.md").read_text()
    require(text.startswith("---\n") and "name: " + skill.name + "\n" in text and "description: " in text, "invalid skill frontmatter")
    require(len(text.splitlines()) < 200, "use progressive disclosure")
    contract = json.loads((skill / "contract.json").read_text())
    require(set(contract) == {"responsibility", "inputs", "outputs", "commands", "forbidden", "example"}, "incomplete skill contract")
    require(all(contract[k] for k in contract), "empty skill contract")
    require((skill / contract["example"]).is_file(), "missing concrete example")
    json.loads((skill / contract["example"]).read_text())
    count += 1
for path in (ROOT / ".agents/agents").glob("*/AGENT.md"):
    text = path.read_text()
    require("Human" in text and "workflow" in text, "agent boundaries missing")
    for line in text.splitlines():
        if line.startswith("skill: "):
            require((skills / line[7:] / "SKILL.md").is_file(), "orphan agent skill reference")
require(count == 10, "unexpected skill count")
print(json.dumps({"result": "pass", "skills": count, "agents": 3}))
