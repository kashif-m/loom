from __future__ import annotations


class ContextAssembler:
    def assemble(self, task, step, memory_slice, domain_context):
        return {
            "task": task.model_dump(),
            "step": step.model_dump(),
            "memory": memory_slice,
            "domain": domain_context,
        }
