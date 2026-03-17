"""PydanticAI tool definitions for Loom MVP.

Tools are defined as functions decorated with @tool.
They receive the RunContext with AgentContext as deps.
"""
from pydantic_ai import RunContext, Tool

from src.agents.pydantic_ai.agent import AgentContext


async def file_read(ctx: RunContext[AgentContext], path: str) -> str:
    """Read a file from the filesystem.
    
    Args:
        path: Path to the file to read
        
    Returns:
        File contents as string
    """
    try:
        with open(path) as f:
            content = f.read()
        return f"File contents of {path}:\n{content[:2000]}"  # Limit to 2000 chars
    except Exception as e:
        return f"Error reading file {path}: {e}"


async def file_write(ctx: RunContext[AgentContext], path: str, content: str) -> str:
    """Write content to a file.
    
    Args:
        path: Path to write to
        content: Content to write
        
    Returns:
        Success message
    """
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing to {path}: {e}"


async def code_search(ctx: RunContext[AgentContext], query: str, path: str = ".") -> str:
    """Search for code patterns in the codebase.
    
    Args:
        query: Search pattern (regex or text)
        path: Directory to search in
        
    Returns:
        Search results
    """
    import os
    import re
    
    results = []
    try:
        for root, dirs, files in os.walk(path):
            # Skip common non-code directories
            dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', '__pycache__', '.venv']]
            
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.tsx', '.json', '.md')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path) as f:
                            content = f.read()
                            if re.search(query, content, re.IGNORECASE):
                                # Find the matching line
                                for i, line in enumerate(content.split('\n'), 1):
                                    if re.search(query, line, re.IGNORECASE):
                                        results.append(f"{file_path}:{i}: {line.strip()}")
                                        if len(results) >= 10:  # Limit results
                                            break
                    except:
                        continue
                        
        if results:
            return "Search results:\n" + "\n".join(results[:20])
        else:
            return f"No matches found for '{query}'"
    except Exception as e:
        return f"Search error: {e}"


async def task_query(ctx: RunContext[AgentContext], query: str) -> str:
    """Query information about the current task or related tasks.
    
    Args:
        query: What to query about the task
        
    Returns:
        Task information
    """
    task = await ctx.deps.task_store.get_task(ctx.deps.task_id)
    if not task:
        return "Task not found"
    
    history = await ctx.deps.task_store.get_task_history(ctx.deps.task_id)
    history_text = "\n".join([
        f"  {h.from_state or 'start'} -> {h.to_state} ({h.agent_id})"
        for h in history[-5:]  # Last 5 transitions
    ])
    
    return f"""Task Information:
ID: {task.task_id}
Description: {task.description}
Status: {task.status}
Current State: {task.current_state}
Team: {task.team_id}

Recent History:
{history_text}
"""


async def git_status(ctx: RunContext[AgentContext]) -> str:
    """Get git repository status.
    
    Returns:
        Git status output
    """
    import subprocess
    
    try:
        result = subprocess.run(
            ['git', 'status', '--short'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            if result.stdout:
                return f"Git status:\n{result.stdout}"
            else:
                return "Working directory clean"
        else:
            return f"Git error: {result.stderr}"
    except Exception as e:
        return f"Error running git status: {e}"


async def notify_team(ctx: RunContext[AgentContext], message: str) -> str:
    """Send a notification to the team.
    
    Args:
        message: Message to send
        
    Returns:
        Confirmation
    """
    # In MVP, this just logs the notification
    # In production, this would integrate with Slack/Teams/etc
    print(f"[NOTIFICATION to {ctx.deps.agent_config.team_id}]: {message}")
    return f"Notification sent to team {ctx.deps.agent_config.team_id}"


# Tool registry
all_tools = {
    "file_read": file_read,
    "file_write": file_write,
    "code_search": code_search,
    "task_query": task_query,
    "git_status": git_status,
    "notify": notify_team,
}
