from __future__ import annotations

from loom.domainpacks.docs.verification import VerificationPipeline


class DocsWorkflowBindings:
    def __init__(self, git_adapter, gh_adapter):
        self.git = git_adapter
        self.gh = gh_adapter
        self.verification = VerificationPipeline()

    def run_validations(self, repo_root: str, puml_files: list[str] | None = None) -> dict:
        return self.verification.verify(repo_root=repo_root, puml_files=puml_files)

    def create_or_update_pr(self, title: str, body: str, base: str, head: str) -> dict:
        result = self.gh.pr_create(title=title, body=body, base=base, head=head)
        return {"ok": True, "result": result}

    def promote_pr(self, pr_number: int, approved: bool) -> dict:
        if not approved:
            return {"ok": False, "reason": "approval required"}
        result = self.gh.pr_merge(pr_number, method="squash")
        return {"ok": True, "result": result}
