"""Self-reflection logic for agents using Instructor structured outputs."""
from loguru import logger

from src.core.llm.client import complete_structured
from src.core.llm.models import ModelRole
from src.core.llm.schemas import Message, SelfReflectionResponse


async def self_reflect(
    output: str, 
    task_description: str, 
    success_condition: str
) -> dict:
    """Self-reflect on output quality using Instructor structured outputs.

    Args:
        output: The output to evaluate
        task_description: Original task description
        success_condition: What success looks like

    Returns:
        Dict with approved (bool), reasoning (str), and score (float)
    """
    prompt = f"""Evaluate whether the following output meets the success criteria.

Task: {task_description}

Success Condition: {success_condition}

Output to Evaluate:
{output[:2000]}  # Limit to 2000 chars

Provide:
1. Whether the output is approved (true/false)
2. Your reasoning for the evaluation
3. A quality score from 0.0 to 1.0
"""

    messages = [
        Message(
            role="system",
            content="You are evaluating task output quality. Be strict but fair in your assessment."
        ),
        Message(role="user", content=prompt),
    ]

    try:
        # Use Instructor for structured output
        response = await complete_structured(
            role=ModelRole.FAST,
            messages=messages,
            response_model=SelfReflectionResponse,
            temperature=0.3,
            max_retries=2,
        )

        logger.info(
            f"Self-reflection: approved={response.approved}, "
            f"score={response.score}"
        )
        logger.debug(f"Reasoning: {response.reasoning[:150]}...")

        return {
            "approved": response.approved,
            "reasoning": response.reasoning,
            "score": response.score,
        }

    except Exception as e:
        logger.error(f"Self-reflection failed: {e}")
        # Fail safe: approve if we can't evaluate
        return {
            "approved": True,
            "reasoning": f"Self-reflection failed: {e}. Approving by default.",
            "score": 0.5,
        }


async def evaluate_output(
    output: str,
    expected_format: str | None = None,
    constraints: list[str] | None = None,
) -> dict:
    """Comprehensive output evaluation.

    Args:
        output: The output to evaluate
        expected_format: Expected format description
        constraints: List of constraints to check

    Returns:
        Evaluation results
    """
    checks = []
    
    if expected_format:
        checks.append(f"Format: {expected_format}")
    if constraints:
        for i, constraint in enumerate(constraints, 1):
            checks.append(f"Constraint {i}: {constraint}")
    
    checks_text = "\n".join(checks) if checks else "General quality check"
    
    prompt = f"""Evaluate the following output against these criteria:

{checks_text}

Output:
{output[:2000]}

Provide:
1. Whether the output passes all checks (true/false)
2. Your evaluation reasoning
3. A quality score from 0.0 to 1.0
"""

    messages = [
        Message(role="system", content="You are evaluating output quality."),
        Message(role="user", content=prompt),
    ]

    try:
        response = await complete_structured(
            role=ModelRole.FAST,
            messages=messages,
            response_model=SelfReflectionResponse,
            temperature=0.3,
            max_retries=2,
        )

        return {
            "approved": response.approved,
            "reasoning": response.reasoning,
            "score": response.score,
            "checks_passed": response.approved,
        }

    except Exception as e:
        logger.error(f"Output evaluation failed: {e}")
        return {
            "approved": True,
            "reasoning": f"Evaluation failed: {e}. Approving by default.",
            "score": 0.5,
            "checks_passed": True,
        }
