"""
After a successful build+release, open a PR on the config repo that bumps
the release_tag for the `dev` environment.  Merge → triggers deploy.

Required env vars (injected by build-artifact.yml):
  CONFIG_REPO_TOKEN  - GitHub PAT or App token
  CONFIG_REPO        - e.g. "org/config-repo"
  APP_NAME           - e.g. "app-sample"
  RELEASE_TAG        - e.g. "app-sample-abc1234-20261015120000"
  SOURCE_REPO        - e.g. "org/app-sample"
  SOURCE_SHA         - full commit SHA that triggered the build
"""

import os
import sys
import yaml
from github import Github, GithubException

TOKEN = os.environ["CONFIG_REPO_TOKEN"]
CONFIG_REPO = os.environ["CONFIG_REPO"]
APP_NAME = os.environ["APP_NAME"]
RELEASE_TAG = os.environ["RELEASE_TAG"]
SOURCE_REPO = os.environ["SOURCE_REPO"]
SOURCE_SHA = os.environ["SOURCE_SHA"]

# Only auto-promote to dev; higher envs require a human to retarget the PR.
TARGET_ENV = "dev"
CONFIG_FILE = f"apps/{APP_NAME}/{TARGET_ENV}.yml"

g = Github(TOKEN)
repo = g.get_repo(CONFIG_REPO)


def get_current_config(path: str) -> tuple[str, dict]:
    """Return (file_sha, parsed_yaml) for a config file."""
    file = repo.get_contents(path)
    return file.sha, yaml.safe_load(file.decoded_content)


def open_pr(branch: str, file_path: str, file_sha: str, new_content: str) -> str:
    default_branch = repo.default_branch
    base_ref = repo.get_branch(default_branch)

    # Create or reset the branch
    try:
        ref = repo.get_git_ref(f"heads/{branch}")
        ref.edit(base_ref.commit.sha, force=True)
    except GithubException:
        repo.create_git_ref(f"refs/heads/{branch}", base_ref.commit.sha)

    repo.update_file(
        path=file_path,
        message=f"chore({APP_NAME}): promote {RELEASE_TAG} → {TARGET_ENV}",
        content=new_content,
        sha=file_sha,
        branch=branch,
    )

    pr = repo.create_pull(
        title=f"[{APP_NAME}] Deploy {RELEASE_TAG} to {TARGET_ENV}",
        body=(
            f"**App:** `{APP_NAME}`\n"
            f"**Release tag:** `{RELEASE_TAG}`\n"
            f"**Source commit:** {SOURCE_REPO}@`{SOURCE_SHA[:8]}`\n\n"
            f"Merging this PR will trigger the deploy workflow for **{TARGET_ENV}**.\n\n"
            f"> To promote to staging/prod, update `release_tag` in the respective "
            f"env file and open another PR."
        ),
        head=branch,
        base=default_branch,
    )
    return pr.html_url


def main():
    file_sha, config = get_current_config(CONFIG_FILE)

    current_tag = config.get("release_tag", "")
    if current_tag == RELEASE_TAG:
        print(f"Config already at {RELEASE_TAG} — nothing to do.")
        sys.exit(0)

    config["release_tag"] = RELEASE_TAG
    config["last_promoted_by"] = SOURCE_REPO
    config["last_promoted_sha"] = SOURCE_SHA

    new_content = yaml.dump(config, default_flow_style=False)
    branch = f"promote/{APP_NAME}/{TARGET_ENV}/{RELEASE_TAG}"

    pr_url = open_pr(branch, CONFIG_FILE, file_sha, new_content)
    print(f"PR opened: {pr_url}")


if __name__ == "__main__":
    main()
