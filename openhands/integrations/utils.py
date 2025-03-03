from typing import Literal

from pydantic import SecretStr

from openhands.integrations.github.github_service import GitHubService
from openhands.integrations.gitlab.gitlab_service import GitLabService


async def determine_token_type(token: SecretStr) -> Literal['github', 'gitlab'] | None:
    """
    Determine whether a token is for GitHub or GitLab by attempting to get user info
    from both services.

    Args:
        token: The token to check

    Returns:
        'github' if it's a GitHub token
        'gitlab' if it's a GitLab token
        None if the token is invalid for both services
    """
    # Try GitHub first
    try:
        github_service = GitHubService(token=token)
        await github_service.get_user()
        return 'github'
    except Exception:
        pass

    # Try GitLab next
    try:
        gitlab_service = GitLabService(token=token)
        await gitlab_service.get_user()
        return 'gitlab'
    except Exception:
        pass

    return None
