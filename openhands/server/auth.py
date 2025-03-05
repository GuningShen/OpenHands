from fastapi import Request
from pydantic import SecretStr

from openhands.integrations.provider import PROVIDER_TOKEN_TYPE, ProviderType


def get_provider_tokens(request: Request) -> PROVIDER_TOKEN_TYPE | None:
    """Get GitHub token from request state. For backward compatibility."""
    return getattr(request.state, 'provider_tokens', {})


def get_gh_user_id_from_provider_tokens(request: Request) -> str | None:
    provider_tokens = get_provider_tokens(request)

    if provider_tokens and ProviderType.GITHUB in provider_tokens:
        return provider_tokens[ProviderType.GITHUB].user_id

    return None


def get_idp_token(request: Request) -> SecretStr | None:
    return getattr(request.state, 'idp_token', None)
