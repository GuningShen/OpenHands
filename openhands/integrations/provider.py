from enum import Enum

from pydantic import BaseModel, SecretStr, SerializationInfo, field_serializer
from pydantic.json import pydantic_encoder

from openhands.events.action.commands import CmdRunAction
from openhands.events.stream import EventStream
from openhands.integrations.github.github_service import GithubServiceImpl
from openhands.integrations.gitlab.gitlab_service import GitLabServiceImpl
from openhands.integrations.service_types import (
    AuthenticationError,
    GitService,
    Repository,
    User,
)


class ProviderType(Enum):
    GITHUB = 'github'
    GITLAB = 'gitlab'


class ProviderToken(BaseModel):
    token: SecretStr | None
    user_id: str | None


PROVIDER_TOKEN_TYPE = dict[ProviderType, ProviderToken]
CUSTOM_SECRETS_TYPE = dict[str, SecretStr]


class SecretStore(BaseModel):
    provider_tokens: PROVIDER_TOKEN_TYPE = {}

    @classmethod
    def _convert_token(
        cls, token_value: str | ProviderToken | SecretStr
    ) -> ProviderToken:
        if isinstance(token_value, ProviderToken):
            return token_value
        elif isinstance(token_value, str):
            return ProviderToken(token=SecretStr(token_value), user_id=None)
        elif isinstance(token_value, SecretStr):
            return ProviderToken(token=token_value, user_id=None)
        else:
            raise ValueError(f'Invalid token type: {type(token_value)}')

    def model_post_init(self, __context) -> None:
        # Convert any string tokens to ProviderToken objects
        converted_tokens = {}
        for token_type, token_value in self.provider_tokens.items():
            if token_value:  # Only convert non-empty tokens
                try:
                    if isinstance(token_type, str):
                        token_type = ProviderType(token_type)
                    converted_tokens[token_type] = self._convert_token(token_value)
                except ValueError:
                    # Skip invalid provider types or tokens
                    continue
        self.provider_tokens = converted_tokens

    @field_serializer('provider_tokens')
    def provider_tokens_serializer(
        self, provider_tokens: PROVIDER_TOKEN_TYPE, info: SerializationInfo
    ):
        tokens = {}
        expose_secrets = info.context and info.context.get('expose_secrets', False)

        for token_type, provider_token in provider_tokens.items():
            if not provider_token or not provider_token.token:
                continue

            token_type_str = (
                token_type.value
                if isinstance(token_type, ProviderType)
                else str(token_type)
            )
            tokens[token_type_str] = {
                'token': provider_token.token.get_secret_value()
                if expose_secrets
                else pydantic_encoder(provider_token.token),
                'user_id': provider_token.user_id,
            }

        return tokens


class ProviderHandler:
    def __init__(
        self,
        provider_tokens: PROVIDER_TOKEN_TYPE,
        external_auth_token: SecretStr | None = None,
    ):
        self.service_class_map: dict[ProviderType, type[GitService]] = {
            ProviderType.GITHUB: GithubServiceImpl,
            ProviderType.GITLAB: GitLabServiceImpl,
        }

        self.provider_tokens = provider_tokens
        self.external_auth_token = external_auth_token


    def _get_service(self, provider: ProviderType) -> GitService:
        """Helper method to instantiate a service for a given provider"""
        token = self.provider_tokens[provider]
        service_class = self.service_class_map[provider]
        return service_class(
            user_id=token.user_id,
            external_auth_token=self.external_auth_token,
            token=token.token,
        )

    async def get_user(self) -> User:
        """Get user information from the first available provider"""
        for provider in self.provider_tokens:
            try:
                service = self._get_service(provider)
                return await service.get_user()
            except Exception:
                continue
        raise AuthenticationError('Need valid provider token')

    async def _get_latest_provider_token(self, provider: ProviderType) -> SecretStr | None:
        """Get latest token from service"""
        service = self._get_service(provider)    
        return await service.get_latest_token()
    
    async def get_repositories(
        self, page: int, per_page: int, sort: str, installation_id: int | None
    ) -> list[Repository]:
        """Get repositories from all available providers"""
        all_repos = []
        for provider in self.provider_tokens:
            try:
                service = self._get_service(provider)
                repos = await service.get_repositories(
                    page, per_page, sort, installation_id
                )
                all_repos.extend(repos)
            except Exception:
                continue
        return all_repos


    @classmethod
    def set_or_update_event_stream_secrets(cls, event_stream: EventStream, provider_tokens: PROVIDER_TOKEN_TYPE | dict[ProviderToken, SecretStr]):
        for provider in provider_tokens:
            token = provider_tokens[provider].token if isinstance(provider_tokens[provider], ProviderToken) else provider_tokens[provider]
            if token:
                token_name = f"{provider.value}_token"
                event_stream.set_secrets(
                    {
                        token_name: token.get_secret_value(),
                    }
                )

    
    async def get_env_vars(self, required_providers: dict[ProviderType, bool]) -> dict[ProviderType, SecretStr]:
        if not self.provider_tokens:
            return {}
    
        env_vars = {}
        for provider in required_providers:
            if provider in self.provider_tokens:
                token = await self._get_latest_provider_token(provider)
                if token:
                    env_vars[provider] = token
        return env_vars
    
    @classmethod
    def check_cmd_action_for_provider_token_ref(cls, event: CmdRunAction) -> dict[ProviderType, bool]:
        if not isinstance(event, CmdRunAction):
            return {}
        
        called_providers = {}
        for provider in ProviderType:
            env_name = f"${provider.value.upper()}_TOKEN"
            if env_name in event.command:
                called_providers[provider] = True

        return called_providers            