from loom.integrations.openclaw_adapter_runtime import OpenClawRuntimeAdapter
from loom.security.policy_guard import CommandSafetyPolicy


def test_openclaw_signature_verification():
    adapter = OpenClawRuntimeAdapter("secret")
    sig = adapter.sign("hello", "session-1")
    assert adapter.verify("hello", "session-1", sig)
    assert not adapter.verify("tampered", "session-1", sig)


def test_command_safety_policy():
    policy = CommandSafetyPolicy()
    policy.validate(["git", "status"])
    try:
        policy.validate(["bash", "-lc", "whoami"])
        raise AssertionError("should reject")
    except PermissionError:
        pass
