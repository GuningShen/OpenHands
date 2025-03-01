import dataclasses
import json

from openhands.core.logger import openhands_logger as logger
from openhands.events.action.message import MessageAction
from openhands.events.event import Event, EventSource
from openhands.events.observation.agent import (
    RecallObservation,
    RecallType,
)
from openhands.events.stream import EventStream, EventStreamSubscriber
from openhands.microagent import (
    BaseMicroAgent,
    KnowledgeMicroAgent,
    RepoMicroAgent,
    load_microagents_from_dir,
)
from openhands.utils.prompt import RepositoryInfo, RuntimeInfo


class Memory:
    """
    Memory is a component that listens to the EventStream for either user MessageAction (to create
    a RecallObservation).
    """

    def __init__(
        self,
        event_stream: EventStream,
        microagents_dir: str,
    ):
        self.event_stream = event_stream
        self.microagents_dir = microagents_dir
        # Subscribe to events
        self.event_stream.subscribe(
            EventStreamSubscriber.MEMORY,
            self.on_event,
            'Memory',
        )

        # Additional placeholders to store user workspace microagents if needed
        self.repo_microagents: dict[str, RepoMicroAgent] = {}
        self.knowledge_microagents: dict[str, KnowledgeMicroAgent] = {}

        # Track whether we've seen the first user message
        self._first_user_message_seen = False

        # Store repository / runtime info to send them to the templating later
        self.repository_info: RepositoryInfo | None = None
        self.runtime_info: RuntimeInfo | None = None

        # Load global microagents (Knowledge + Repo)
        # from typically OpenHands/microagents (i.e., the PUBLIC microagents)
        self._load_global_microagents()

        # TODO: enable_prompt_extensions

    def _load_global_microagents(self) -> None:
        """
        Loads microagents from the global microagents_dir
        This is effectively what used to happen in PromptManager.
        """
        repo_agents, knowledge_agents, _ = load_microagents_from_dir(
            self.microagents_dir
        )
        for name, agent in knowledge_agents.items():
            # if name in self.disabled_microagents:
            #    continue
            if isinstance(agent, KnowledgeMicroAgent):
                self.knowledge_microagents[name] = agent
        for name, agent in repo_agents.items():
            # if name in self.disabled_microagents:
            #    continue
            if isinstance(agent, RepoMicroAgent):
                self.repo_microagents[name] = agent

    def set_repository_info(self, repo_name: str, repo_directory: str) -> None:
        """Store repository info so we can reference it in an observation."""
        self.repository_info = RepositoryInfo(repo_name, repo_directory)

    def set_runtime_info(self, runtime_hosts: dict[str, int]) -> None:
        """Store runtime info (web hosts, ports, etc.)."""
        # e.g. { '127.0.0.1': 8080 }
        self.runtime_info = RuntimeInfo(available_hosts=runtime_hosts)

    def on_event(self, event: Event):
        """Handle an event from the event stream."""

        observation: RecallObservation | None = None
        if isinstance(event, MessageAction):
            if event.source == 'user':
                # If this is the first user message, create and add a RecallObservation
                # with info about repo and runtime.
                if not self._first_user_message_seen:
                    self._first_user_message_seen = True
                    observation = self._on_first_user_message(event)

                # continue with the next handler, to include microagents if suitable for this user message
                observation = self._on_user_message_action(
                    event, prev_observation=observation
                )

                # important: this hint will release the execution flow from waiting for this to complete
                if observation is not None:
                    observation._cause = event.id  # type: ignore[attr-defined]

                    self.event_stream.add_event(observation, EventSource.ENVIRONMENT)

    def _on_first_user_message(self, event: MessageAction) -> RecallObservation:
        """Add repository and runtime information to the stream as a RecallObservation."""

        # Collect raw repository instructions
        repo_instructions = ''
        assert (
            len(self.repo_microagents) <= 1
        ), f'Expecting at most one repo microagent, but found {len(self.repo_microagents)}: {self.repo_microagents.keys()}'

        # Retrieve the context of repo instructions
        for microagent in self.repo_microagents.values():
            # We assume these are the repo instructions
            if repo_instructions:
                repo_instructions += '\n\n'
            repo_instructions += microagent.content

        # Create observation with structured data
        obs_data = {
            'repository_info': dataclasses.asdict(self.repository_info)
            if self.repository_info
            else None,
            'runtime_info': dataclasses.asdict(self.runtime_info)
            if self.runtime_info
            else None,
            'repository_instructions': repo_instructions if repo_instructions else None,
        }

        # Send structured data in the observation
        # TODO: use NullObservation if there's no info to send
        obs = RecallObservation(
            recall_type=RecallType.ENVIRONMENT_INFO, content=json.dumps(obs_data)
        )

        return obs

    def _on_user_message_action(
        self, event: MessageAction, prev_observation: RecallObservation | None = None
    ) -> RecallObservation | None:
        """When a user message triggers microagents, create a RecallObservation with structured data."""
        if event.source != 'user':
            return prev_observation

        # If there's no text, do nothing
        user_text = event.content.strip()
        if not user_text:
            return prev_observation

        # Gather all triggered microagents
        triggered_agents = []
        for name, agent in self.knowledge_microagents.items():
            trigger = agent.match_trigger(user_text)
            if trigger:
                logger.info("Microagent '%s' triggered by keyword '%s'", name, trigger)
                # Create a dictionary with the agent and trigger word
                triggered_agents.append({'agent': agent, 'trigger_word': trigger})

        if triggered_agents:
            # Create structured data observation
            obs_data = {
                'type': 'microagent_knowledge',
                'triggered_agents': triggered_agents,
            }

            if not prev_observation:
                # if it's not the first user message, we may not have found any information yet
                obs = RecallObservation(
                    recall_type=RecallType.KNOWLEDGE_MICROAGENT,
                    content=json.dumps(obs_data),
                )

                return obs
            else:
                # if we already have an observation, update it
                prev_observation.content += '\n\n' + json.dumps(obs_data)

        return prev_observation

    def load_user_workspace_microagents(
        self, user_microagents: list[BaseMicroAgent]
    ) -> None:
        """
        If you want to load microagents from a user's cloned repo or workspace directory,
        call this from agent_session or setup once the workspace is cloned.
        """
        logger.info(
            'Loading user workspace microagents: %s', [m.name for m in user_microagents]
        )
        for ma in user_microagents:
            # if ma.name in self.disabled_microagents:
            #    continue
            if isinstance(ma, KnowledgeMicroAgent):
                self.knowledge_microagents[ma.name] = ma
            elif isinstance(ma, RepoMicroAgent):
                self.repo_microagents[ma.name] = ma
