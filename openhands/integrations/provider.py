from enum import Enum

from pydantic import BaseModel, SecretStr, SerializationInfo, field_serializer
from pydantic.json import pydantic_encoder

from openhands.integrations.github.github_service import GithubServiceImpl
from openhands.integrations.gitlab.gitlab_service import GitLabServiceImpl


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

    @field_serializer('provider_tokens')
    def provider_tokens_serializer(
        self, provider_tokens: PROVIDER_TOKEN_TYPE, info: SerializationInfo
    ):
        tokens = {}
        for token_type, provider_token in provider_tokens.items():
            if provider_token.token:
                if info.context and info.context.get('expose_secrets', False):
                    tokens[token_type.value] = {
                        'token': provider_token.token.get_secret_value(),
                        'user_id': provider_token.user_id
                    }
                else:
                    tokens[token_type.value] = {
                        'token': '**********' if provider_token.token else None,
                        'user_id': provider_token.user_id
                    }
        return tokens


class ProviderHandler:
    def __init__(self, secret_store: SecretStore):
        self.service_class_map = {
            ProviderType.GITHUB: GithubServiceImpl,
            ProviderType.GITLAB: GitLabServiceImpl,
        }

        self.provider_tokens = secret_store.provider_tokens

    def get_user(self):
        pass
