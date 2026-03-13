from __future__ import annotations


class CollaborativeStepRunner:
    def __init__(self, step_runner):
        self.step_runner = step_runner

    def run(self, task, step, participants):
        outputs = []
        for p in participants:
            _, out = self.step_runner.run(task, step, p)
            outputs.append(out)

        merge = step.merge_strategy
        if merge == "first_valid_output":
            merged = next((o for o in outputs if o.get("ok")), outputs[0])
        elif merge == "consensus_summary":
            merged = {
                "summary": " | ".join(o.get("summary", "") for o in outputs),
                "complete": all(o.get("complete", False) for o in outputs),
            }
        elif merge == "explicit_human_choice":
            merged = {"summary": "human choice required", "complete": False, "candidates": outputs}
            return "blocked", merged
        else:
            merged = {
                "summary": "owner synthesis: " + "; ".join(o.get("summary", "") for o in outputs),
                "complete": any(o.get("complete", False) for o in outputs),
            }

        outcome = "success" if merged.get("complete", False) else "blocked"
        return outcome, merged
