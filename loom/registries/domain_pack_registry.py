from __future__ import annotations

import yaml

from loom.models import DomainPackManifest


class DomainPackRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def load_manifest_file(self, manifest_path: str) -> DomainPackManifest:
        with open(manifest_path, "r", encoding="utf-8") as f:
            payload = yaml.safe_load(f)
        manifest = DomainPackManifest(**payload)
        self.upsert(manifest)
        return manifest

    def upsert(self, manifest: DomainPackManifest) -> None:
        self.repositories.domain_packs.upsert(
            manifest.pack_id,
            manifest.model_dump(),
            status=manifest.status.value,
        )

    def get(self, pack_id: str) -> DomainPackManifest | None:
        row = self.repositories.domain_packs.get(pack_id)
        return DomainPackManifest(**row["data"]) if row else None

    def list(self, status: str | None = None) -> list[DomainPackManifest]:
        return [DomainPackManifest(**row["data"]) for row in self.repositories.domain_packs.list(status=status)]

    def activate(self, pack_id: str) -> None:
        manifest = self.get(pack_id)
        if not manifest:
            raise KeyError(pack_id)
        manifest.status = manifest.status.active
        self.upsert(manifest)

    def deactivate(self, pack_id: str) -> None:
        manifest = self.get(pack_id)
        if not manifest:
            raise KeyError(pack_id)
        manifest.status = manifest.status.retired
        self.upsert(manifest)
