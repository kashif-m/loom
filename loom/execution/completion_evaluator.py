from __future__ import annotations


class CompletionEvaluator:
    def evaluate(self, completion, outputs: list[dict], context: dict) -> bool:
        ctype = completion.type
        if ctype == "all_outputs_present":
            return bool(outputs) and all(o.get("ok", True) for o in outputs)
        if ctype == "predicate":
            predicate = completion.predicate or ""
            return predicate.lower() in str(outputs).lower()
        if ctype == "approval_received":
            return context.get("approved", False)
        if ctype == "all_participants_complete":
            return all(o.get("complete", False) for o in outputs)
        if ctype == "any_participant_complete":
            return any(o.get("complete", False) for o in outputs)
        return False
