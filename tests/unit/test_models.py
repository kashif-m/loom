from loom.models import ClassificationResult, CompiledWorkflowStep, CompletionSemantics, StepTransitions


def test_classification_confidence_validation():
    ok = ClassificationResult(intent_group="x", confidence=0.5, outcome="supported")
    assert ok.confidence == 0.5


def test_compiled_workflow_step_defaults():
    step = CompiledWorkflowStep(
        step_id="s1",
        title="Step",
        owned_by="docs_ops",
        transitions=StepTransitions(on_success="completed"),
        completion=CompletionSemantics(type="all_outputs_present"),
    )
    assert step.spawn_strategy == "single_owner"
