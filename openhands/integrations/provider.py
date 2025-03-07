from enum import Enum

from pydantic import BaseModel, SecretStr, SerializationInfo, field_serializer
from pydantic.json import pydantic_encoder

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
        self, provider_tokens: PROVIDER_TOKEN_TYPE, idp_token: SecretStr | None = None
    ):
        self.service_class_map: dict[ProviderType, type[GitService]] = {
            ProviderType.GITHUB: GithubServiceImpl,
            ProviderType.GITLAB: GitLabServiceImpl,
        }

        self.provider_tokens = provider_tokens
        self.idp_token = idp_token

    def _get_service(self, provider: ProviderType) -> GitService:
        """Helper method to instantiate a service for a given provider"""
        token = self.provider_tokens[provider]
        service_class = self.service_class_map[provider]
        return service_class(
            user_id=token.user_id, idp_token=self.idp_token, token=token.token
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

    async def get_latest_provider_tokens(self) -> dict[ProviderType, SecretStr]:
        """Get latest token from services"""
        tokens = {}
        for provider in self.provider_tokens:
            service = self._get_service(provider)
            tokens[provider] = await service.get_latest_provider_token()

        return tokens

    async def get_repositories(
        self, page: int, per_page: int, sort: str, installation_id: int | None
    ) -> dict:
        """Get repositories from all available providers with pagination support
        
        Returns:
            dict: {
                'repositories': list[Repository],  # Combined list of repositories
                'pagination': {
                    'total_count': int,  # Total number of repositories across all providers
                    'has_more': bool,    # True if any provider has more results
                    'provider_cursors': dict[str, any]  # Provider-specific pagination cursors
                }
            }
        """
        all_repos = []
        total_count = 0
        has_more = False
        provider_cursors = {}
        
        # Calculate offset for each provider based on page and per_page
        provider_count = len(self.provider_tokens)
        items_per_provider = per_page // provider_count if provider_count > 0 else per_page
        
        for provider in self.provider_tokens:
            try:
                service = self._get_service(provider)
                # Each provider gets its share of the requested items
                repos = await service.get_repositories(
                    page, items_per_provider, sort, installation_id
                )
                
                if repos:
                    all_repos.extend(repos)
                    # Store provider-specific pagination info
                    if hasattr(repos[0], 'link_header'):
                        provider_cursors[provider.value] = repos[0].link_header
                    if hasattr(repos[0], 'total_count'):
                        total_count += repos[0].total_count
                        has_more = has_more or len(repos) < repos[0].total_count
                    else:
                        # If provider doesn't support total_count, assume more if we got full page
                        has_more = has_more or len(repos) >= items_per_provider
                        
            except Exception:
                continue
                
        # Sort combined results by the requested sort field
        if sort == 'pushed':
            all_repos.sort(key=lambda x: x.pushed_at or '', reverse=True)
            
        return {
            'repositories': all_repos[:per_page],  # Return only requested number of items
            'pagination': {
                'total_count': total_count,
                'has_more': has_more,
                'provider_cursors': provider_cursors
            }
        }
