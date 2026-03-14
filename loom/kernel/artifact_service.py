from __future__ import annotations

from typing import Any

from loom.models import (
    AuditResult,
    GroundingReference,
    PackageArtifact,
    PRContext,
    RepoTargetMapping,
)


class ArtifactService:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert_package(self, artifact: PackageArtifact) -> None:
        self.repositories.packages.upsert(
            artifact.package_id,
            artifact.model_dump(mode="json"),
            status=artifact.status.value,
        )

    def get_package(self, package_id: str) -> PackageArtifact | None:
        row = self.repositories.packages.get(package_id)
        return PackageArtifact(**row["data"]) if row else None

    def list_packages(
        self,
        *,
        status: str | None = None,
        organization_id: str | None = None,
    ) -> list[PackageArtifact]:
        items = [PackageArtifact(**row["data"]) for row in self.repositories.packages.list(status=status)]
        if organization_id:
            items = [item for item in items if item.organization_id == organization_id]
        return items

    def upsert_grounding_reference(self, ref: GroundingReference) -> None:
        self.repositories.grounding_references.upsert(
            ref.reference_id,
            ref.model_dump(mode="json"),
            status=ref.status.value,
        )

    def get_grounding_reference(self, reference_id: str) -> GroundingReference | None:
        row = self.repositories.grounding_references.get(reference_id)
        return GroundingReference(**row["data"]) if row else None

    def list_grounding_references(
        self,
        *,
        status: str | None = None,
        organization_id: str | None = None,
    ) -> list[GroundingReference]:
        items = [
            GroundingReference(**row["data"])
            for row in self.repositories.grounding_references.list(status=status)
        ]
        if organization_id:
            items = [item for item in items if item.organization_id == organization_id]
        return items

    def upsert_pr_context(self, ctx: PRContext) -> None:
        self.repositories.pr_contexts.upsert(
            ctx.pr_context_id,
            ctx.model_dump(mode="json"),
            status=ctx.status.value,
        )

    def get_pr_context(self, pr_context_id: str) -> PRContext | None:
        row = self.repositories.pr_contexts.get(pr_context_id)
        return PRContext(**row["data"]) if row else None

    def list_pr_contexts(
        self,
        *,
        status: str | None = None,
        organization_id: str | None = None,
    ) -> list[PRContext]:
        items = [PRContext(**row["data"]) for row in self.repositories.pr_contexts.list(status=status)]
        if organization_id:
            items = [item for item in items if item.organization_id == organization_id]
        return items

    def upsert_audit_result(self, result: AuditResult) -> None:
        self.repositories.audit_results.upsert(
            result.audit_id,
            result.model_dump(mode="json"),
            status=result.status.value,
        )

    def get_audit_result(self, audit_id: str) -> AuditResult | None:
        row = self.repositories.audit_results.get(audit_id)
        return AuditResult(**row["data"]) if row else None

    def list_audit_results(
        self,
        *,
        status: str | None = None,
        organization_id: str | None = None,
    ) -> list[AuditResult]:
        items = [AuditResult(**row["data"]) for row in self.repositories.audit_results.list(status=status)]
        if organization_id:
            items = [item for item in items if item.organization_id == organization_id]
        return items

    def upsert_repo_target_mapping(self, mapping: RepoTargetMapping) -> None:
        self.repositories.repo_target_mappings.upsert(
            mapping.mapping_id,
            mapping.model_dump(mode="json"),
            status=mapping.status.value,
        )

    def get_repo_target_mapping(self, mapping_id: str) -> RepoTargetMapping | None:
        row = self.repositories.repo_target_mappings.get(mapping_id)
        return RepoTargetMapping(**row["data"]) if row else None

    def list_repo_target_mappings(
        self,
        *,
        status: str | None = None,
        organization_id: str | None = None,
    ) -> list[RepoTargetMapping]:
        items = [RepoTargetMapping(**row["data"]) for row in self.repositories.repo_target_mappings.list(status=status)]
        if organization_id:
            items = [item for item in items if item.organization_id == organization_id]
        return items

    def upsert(self, artifact_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if artifact_type == "packages":
            item = PackageArtifact(**payload)
            self.upsert_package(item)
            return item.model_dump(mode="json")
        if artifact_type == "grounding_references":
            item = GroundingReference(**payload)
            self.upsert_grounding_reference(item)
            return item.model_dump(mode="json")
        if artifact_type == "pr_contexts":
            item = PRContext(**payload)
            self.upsert_pr_context(item)
            return item.model_dump(mode="json")
        if artifact_type == "audit_results":
            item = AuditResult(**payload)
            self.upsert_audit_result(item)
            return item.model_dump(mode="json")
        if artifact_type == "repo_target_mappings":
            item = RepoTargetMapping(**payload)
            self.upsert_repo_target_mapping(item)
            return item.model_dump(mode="json")
        raise ValueError(f"unsupported artifact_type: {artifact_type}")

    def list(
        self,
        artifact_type: str,
        *,
        status: str | None = None,
        organization_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if artifact_type == "packages":
            return [
                item.model_dump(mode="json")
                for item in self.list_packages(status=status, organization_id=organization_id)
            ]
        if artifact_type == "grounding_references":
            return [
                item.model_dump(mode="json")
                for item in self.list_grounding_references(status=status, organization_id=organization_id)
            ]
        if artifact_type == "pr_contexts":
            return [
                item.model_dump(mode="json")
                for item in self.list_pr_contexts(status=status, organization_id=organization_id)
            ]
        if artifact_type == "audit_results":
            return [
                item.model_dump(mode="json")
                for item in self.list_audit_results(status=status, organization_id=organization_id)
            ]
        if artifact_type == "repo_target_mappings":
            return [
                item.model_dump(mode="json")
                for item in self.list_repo_target_mappings(status=status, organization_id=organization_id)
            ]
        raise ValueError(f"unsupported artifact_type: {artifact_type}")
