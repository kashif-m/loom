from __future__ import annotations

from loom.adapters.langsmith_adapter import LangSmithAdapter
from loom.adapters.openai_agents_adapter import OpenAIAgentsAdapter
from loom.app.config import Settings
from loom.compiler.compiler_service import CompilerService
from loom.compiler.ir_validator import IRValidator
from loom.compiler.llm_compiler import DeterministicLLMCompiler
from loom.compiler.markdown_parser import WorkflowMarkdownParser
from loom.execution.async_worker import AsyncWorkerService
from loom.execution.collaborative_step_runner import CollaborativeStepRunner
from loom.execution.completion_evaluator import CompletionEvaluator
from loom.execution.model_router import ModelRouter
from loom.execution.step_runner import StepRunner
from loom.integrations.bootstrap_bindings import bootstrap_integration_bindings
from loom.kernel.execution_coordinator import ExecutionCoordinator
from loom.kernel.execution_planner import ExecutionPlanner
from loom.kernel.participant_resolver import ParticipantResolver
from loom.kernel.policy_engine import PolicyEngine
from loom.kernel.state_machine import TaskStateMachine
from loom.kernel.transition_engine import TransitionEngine
from loom.memory.memory_service import InMemoryMemoryService
from loom.observability.event_bus import EventBus
from loom.observability.topology_service import TopologyService
from loom.persistence.db import init_db
from loom.persistence.repositories import Repositories
from loom.registries.capability_registry import CapabilityRegistry
from loom.registries.domain_pack_registry import DomainPackRegistry
from loom.registries.model_provider_registry import ModelProviderRegistry
from loom.registries.model_registry import ModelRegistry
from loom.registries.policy_registry import PolicyRegistry
from loom.registries.prompt_registry import PromptRegistry
from loom.registries.role_registry import RoleRegistry
from loom.registries.schedule_registry import ScheduleRegistry
from loom.registries.service_model_registry import ServiceModelRegistry
from loom.registries.workflow_registry import WorkflowRegistry
from loom.scheduling.maintenance import default_maintenance_schedules
from loom.scheduling.scheduler_service import SchedulerService
from loom.triage.classifier import RuleBasedClassifier
from loom.triage.entity_extractor import EntityExtractor
from loom.triage.intake_service import IntakeService
from loom.triage.selector import WorkflowSelector


class Container:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session_factory = init_db(settings.database_url)
        self.repositories = Repositories(self.session_factory)

        self.workflow_registry = WorkflowRegistry(self.repositories)
        self.role_registry = RoleRegistry(self.repositories)
        self.capability_registry = CapabilityRegistry(self.repositories)
        self.policy_registry = PolicyRegistry(self.repositories)
        self.prompt_registry = PromptRegistry(self.repositories)
        self.domain_pack_registry = DomainPackRegistry(self.repositories)
        self.schedule_registry = ScheduleRegistry(self.repositories)
        self.model_provider_registry = ModelProviderRegistry(self.repositories)
        self.model_registry = ModelRegistry(self.repositories, self.model_provider_registry)
        self.service_model_registry = ServiceModelRegistry(self.repositories, self.model_registry)

        self.langsmith_adapter = LangSmithAdapter(
            enabled=settings.langsmith_enabled,
            api_key=settings.langsmith_api_key,
            project=settings.langsmith_project,
        )
        self.openai_agents_adapter = OpenAIAgentsAdapter(
            enabled=settings.openai_enabled,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

        self.parser = WorkflowMarkdownParser()
        self.compiler = DeterministicLLMCompiler()
        self.ir_validator = IRValidator(
            self.role_registry,
            self.capability_registry,
            self.policy_registry,
        )
        self.compiler_service = CompilerService(
            self.workflow_registry,
            self.parser,
            self.compiler,
            self.ir_validator,
        )

        self.classifier = RuleBasedClassifier(self.workflow_registry)
        self.entity_extractor = EntityExtractor()
        self.selector = WorkflowSelector(self.workflow_registry)
        self.model_router = ModelRouter(
            settings,
            self.model_provider_registry,
            self.model_registry,
            self.service_model_registry,
        )
        self.intake_service = IntakeService(
            self.repositories,
            self.classifier,
            self.entity_extractor,
            self.selector,
        )

        self.state_machine = TaskStateMachine()
        self.participant_resolver = ParticipantResolver(self.role_registry, self.capability_registry)
        self.execution_planner = ExecutionPlanner(self.workflow_registry)
        self.completion_evaluator = CompletionEvaluator()
        self.event_bus = EventBus(self.repositories)
        self.step_runner = StepRunner(
            self.completion_evaluator,
            self.event_bus,
            agent_adapter=self.openai_agents_adapter,
            model_router=self.model_router,
        )
        self.collab_step_runner = CollaborativeStepRunner(self.step_runner)
        self.transition_engine = TransitionEngine(self.state_machine, self.event_bus)
        self.policy_engine = PolicyEngine(self.policy_registry)
        self.execution_coordinator = ExecutionCoordinator(
            self.execution_planner,
            self.participant_resolver,
            self.policy_engine,
            self.step_runner,
            self.collab_step_runner,
            self.transition_engine,
            self.event_bus,
        )

        self.memory_service = InMemoryMemoryService(
            self.repositories,
            self.event_bus,
            graphiti_enabled=settings.graphiti_enabled,
            graphiti_base_url=settings.graphiti_base_url,
            graphiti_api_key=settings.graphiti_api_key,
            graphiti_workspace=settings.graphiti_workspace,
        )
        self.topology_service = TopologyService(self.repositories)
        self.scheduler_service = SchedulerService(self.schedule_registry, self.event_bus)
        self.async_worker = AsyncWorkerService(
            self.repositories,
            self.execution_coordinator,
            max_workers=settings.max_worker_threads,
        )

    def startup(self) -> None:
        bootstrap_integration_bindings(self.settings, self.repositories)
        self.model_router.bootstrap_default_litellm()
        if not self.schedule_registry.list():
            for schedule in default_maintenance_schedules():
                self.schedule_registry.upsert(schedule)
        if not self.settings.disable_scheduler:
            self.scheduler_service.start()

    def shutdown(self) -> None:
        if not self.settings.disable_scheduler:
            self.scheduler_service.stop()
