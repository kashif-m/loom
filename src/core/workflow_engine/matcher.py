"""Workflow matcher for Loom MVP using Instructor for structured outputs."""
import os

from loguru import logger

from src.core.llm.client import complete_structured
from src.core.llm.models import ModelRole
from src.core.llm.schemas import Message, WorkflowMatchResponse
from src.core.workflow_engine.registry import get_registry
from src.core.workflow_engine.schemas import WorkflowDefinition, WorkflowMatchResult, WorkflowStatus


# Confidence threshold for LLM matching
MATCH_CONFIDENCE_THRESHOLD = float(os.getenv("MATCH_CONFIDENCE_THRESHOLD", "0.6"))


async def match_workflow(description: str, level: str | None = None) -> WorkflowMatchResult | None:
    """Match a task description to a workflow using Instructor structured outputs.

    Two-stage matching:
    1. Deterministic tag matching (exact matches)
    2. LLM fallback matching with Instructor (structured outputs)
    
    Args:
        description: Task description
        level: Optional workflow level filter (org, team, agentic)
        
    Returns:
        WorkflowMatchResult or None if no match found
    """
    registry = get_registry()

    # Stage 1: Tag matching (exact matches)
    all_workflows = [
        w for w in registry.get_all()
        if w.status == WorkflowStatus.ACTIVE
    ]
    
    if level:
        all_workflows = [w for w in all_workflows if w.level.value == level]
    
    if not all_workflows:
        logger.warning("No active workflows found")
        return None

    # Check for exact tag matches first
    description_lower = description.lower()
    for workflow in all_workflows:
        for tag in workflow.tags:
            if tag in description_lower:
                logger.info(f"Tag match found: {tag} in workflow {workflow.id}")
                return WorkflowMatchResult(
                    workflow=workflow,
                    confidence=0.9,
                    match_type="tag"
                )

    # Stage 2: LLM matching with Instructor
    logger.debug("No tag match found, trying LLM matching with Instructor")

    # Build workflow descriptions
    workflow_descriptions = []
    for i, wf in enumerate(all_workflows, 1):
        workflow_descriptions.append(
            f"{i}. ID: {wf.id}\n"
            f"   Purpose: {wf.trigger}\n"
            f"   Tags: {', '.join(wf.tags)}\n"
            f"   States: {' -> '.join(wf.states)}"
        )

    # Build prompt
    prompt = f"""Given the following task description, select the most appropriate workflow.

Task Description:
{description}

Available Workflows:
{chr(10).join(workflow_descriptions)}

Select the best workflow by its index number (1-{len(all_workflows)}), or 0 if none are appropriate.
Provide a confidence score (0.0-1.0) and reasoning for your selection.
"""

    messages = [
        Message(
            role="system", 
            content="You are a workflow matching assistant. Analyze the task and select the best workflow match."
        ),
        Message(role="user", content=prompt),
    ]

    try:
        # Use Instructor for structured output
        response = await complete_structured(
            role=ModelRole.FAST,
            messages=messages,
            response_model=WorkflowMatchResponse,
            temperature=0.3,
            max_retries=3,
        )

        logger.info(
            f"Instructor matched workflow #{response.selection} "
            f"with confidence {response.confidence}"
        )
        logger.debug(f"Reasoning: {response.reasoning[:200]}...")

        # Check selection bounds
        if response.selection == 0:
            logger.info("No workflow selected (selection=0)")
            return None

        if response.selection < 1 or response.selection > len(all_workflows):
            logger.warning(f"Invalid workflow selection: {response.selection}")
            return None

        # Check confidence threshold
        if response.confidence < MATCH_CONFIDENCE_THRESHOLD:
            logger.info(
                f"LLM confidence {response.confidence} below threshold "
                f"{MATCH_CONFIDENCE_THRESHOLD}"
            )
            return None

        selected_workflow = all_workflows[response.selection - 1]

        logger.info(
            f"Matched workflow: {selected_workflow.id} (v{selected_workflow.version}) "
            f"with confidence {response.confidence}"
        )

        return WorkflowMatchResult(
            workflow=selected_workflow,
            confidence=response.confidence,
            match_type="llm"
        )

    except Exception as e:
        logger.error(f"LLM matching failed: {e}")
        return None
