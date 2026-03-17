"""Core exceptions for Loom MVP."""


class LoomException(Exception):
    """Base exception for all Loom errors."""
    pass


class StaleTaskVersionError(LoomException):
    """Raised when task version mismatch during state transition."""
    pass


class WorkflowMatchError(LoomException):
    """Raised when no workflow matches a task."""
    pass


class MemoryAccessDeniedError(LoomException):
    """Raised when agent tries to access unauthorized memory tier."""
    pass


class EscalationRequiredError(LoomException):
    """Raised when task needs human escalation."""
    pass


class AgentToolError(LoomException):
    """Raised when agent tool execution fails."""
    pass


class OpenFangConnectionError(LoomException):
    """Raised when OpenFang tool registry is unreachable."""
    pass
