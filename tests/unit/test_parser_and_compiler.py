from loom.compiler.llm_compiler import DeterministicLLMCompiler
from loom.compiler.markdown_parser import WorkflowMarkdownParser


def sample_md() -> str:
    return """
## Title
Sample
## Purpose
Do things
## Trigger
when requested
## Required Inputs
- x
## Steps
1. First step
- id: first
- owned_by: docs_ops
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
errors
## Rules
- no direct merge
"""


def test_parse_and_compile():
    parser = WorkflowMarkdownParser()
    doc = parser.parse(sample_md())
    ir = DeterministicLLMCompiler().compile("wf", 1, doc)
    assert ir.workflow_id == "wf"
    assert ir.steps[0].step_id == "first"
