from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import SecretStr

from openhands.integrations.github.github_service import GithubServiceImpl
from openhands.integrations.provider import (
    PROVIDER_TOKEN_TYPE,
    ProviderHandler,
    ProviderType,
)
from openhands.integrations.service_types import (
    AuthenticationError,
    Repository,
    SuggestedTask,
    UnknownException,
    User,
)
from openhands.server.auth import get_idp_token, get_provider_tokens

app = APIRouter(prefix='/api/user')


from pydantic import BaseModel

class PaginationInfo(BaseModel):
    total_count: int
    has_more: bool
    provider_cursors: dict[str, str]

class RepositoryResponse(BaseModel):
    repositories: list[Repository]
    pagination: PaginationInfo

@app.get('/repositories', response_model=RepositoryResponse)
async def get_github_repositories(
    page: int = 1,
    per_page: int = 10,
    sort: str = 'pushed',
    installation_id: int | None = None,
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(get_provider_tokens),
    idp_token: SecretStr | None = Depends(get_idp_token),
):
    if provider_tokens:
        client = ProviderHandler(provider_tokens=provider_tokens, idp_token=idp_token)

        try:
            result = await client.get_repositories(
                page, per_page, sort, installation_id
            )
            return RepositoryResponse(**result)

        except AuthenticationError as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        except UnknownException as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return JSONResponse(
        content='GitHub token required.',
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@app.get('/info', response_model=User)
async def get_github_user(
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(get_provider_tokens),
    idp_token: SecretStr | None = Depends(get_idp_token),
):
    if provider_tokens:
        client = ProviderHandler(provider_tokens=provider_tokens, idp_token=idp_token)

        try:
            user: User = await client.get_user()
            return user

        except AuthenticationError as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        except UnknownException as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return JSONResponse(
        content='GitHub token required.',
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@app.get('/installations', response_model=list[int])
async def get_github_installation_ids(
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(get_provider_tokens),
    idp_token: SecretStr | None = Depends(get_idp_token),
):
    if provider_tokens and ProviderType.GITHUB in provider_tokens:
        token = provider_tokens[ProviderType.GITHUB]

        client = GithubServiceImpl(
            user_id=token.user_id, idp_token=idp_token, token=token.token
        )
        try:
            installations_ids: list[int] = await client.get_installation_ids()
            return installations_ids

        except AuthenticationError as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        except UnknownException as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return JSONResponse(
        content='GitHub token required.',
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@app.get('/search/repositories', response_model=list[Repository])
async def search_github_repositories(
    query: str,
    per_page: int = 5,
    sort: str = 'stars',
    order: str = 'desc',
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(get_provider_tokens),
    idp_token: SecretStr | None = Depends(get_idp_token),
):
    if provider_tokens and ProviderType.GITHUB in provider_tokens:
        token = provider_tokens[ProviderType.GITHUB]

        client = GithubServiceImpl(
            user_id=token.user_id, idp_token=idp_token, token=token.token
        )
        try:
            repos: list[Repository] = await client.search_repositories(
                query, per_page, sort, order
            )
            return repos

        except AuthenticationError as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        except UnknownException as e:
            return JSONResponse(
                content=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return JSONResponse(
        content='GitHub token required.',
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@app.get('/suggested-tasks', response_model=list[SuggestedTask])
async def get_suggested_tasks(
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(get_provider_tokens),
    idp_token: SecretStr | None = Depends(get_idp_token),
):
    """Get suggested tasks for the authenticated user across their most recently pushed repositories.

    Returns:
    - PRs owned by the user
    - Issues assigned to the user.
    """

    if provider_tokens and ProviderType.GITHUB in provider_tokens:
        token = provider_tokens[ProviderType.GITHUB]

        client = GithubServiceImpl(
            user_id=token.user_id, idp_token=idp_token, token=token.token
        )
        try:
            tasks: list[SuggestedTask] = await client.get_suggested_tasks()
            return tasks

        except AuthenticationError as e:
            return JSONResponse(
                content=str(e),
                status_code=401,
            )

        except UnknownException as e:
            return JSONResponse(
                content=str(e),
                status_code=500,
            )

    return JSONResponse(
        content='GitHub token required.',
        status_code=status.HTTP_401_UNAUTHORIZED,
    )
