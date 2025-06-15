
import os
import sys
import requests
from datetime import datetime

def get_commit_timestamp(owner, repo, sha, github_token):
    """Fetches the commit timestamp for a given SHA."""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {github_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    try:
        response = requests.get(url, headers=headers,timeout=20)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        commit_data = response.json()
        commit_date_str = commit_data['commit']['committer']['date']
        # Parse ISO 8601 string and convert to Unix timestamp (seconds since epoch)
        dt_object = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
        return int(dt_object.timestamp())
    except requests.exceptions.RequestException as e:
        print(f"::warning::Could not get commit info for SHA {sha}: {e}", file=sys.stderr)
        return 0 # Return 0 if commit info is unavailable

def main():
    # Get inputs from command line arguments
    current_commit_timestamp = int(sys.argv[1])
    is_stable_release = sys.argv[2].lower() == 'true'
    is_dev_release = sys.argv[3].lower() == 'true'

    # Get environment variables set by GitHub Actions
    github_token = os.getenv('GITHUB_TOKEN')
    github_repository = os.getenv('GITHUB_REPOSITORY') # e.g., "owner/repo"

    if not github_token:
        print("::error::GITHUB_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)
    if not github_repository:
        print("::error::GITHUB_REPOSITORY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    owner, repo = github_repository.split('/')
    workflow_id = os.getenv('GITHUB_WORKFLOW') # The workflow filename, e.g., "package-builder-release.yml"

    if not workflow_id:
        print("::error::GITHUB_WORKFLOW environment variable not set. Cannot determine workflow_id.", file=sys.stderr)
        sys.exit(1)

    should_apply_stable_latest = False
    should_apply_dev_latest = False

    # Define job names for easy lookup
    JOB_NAME_DOCKER_HUB_STABLE = 'Publish Stable to Docker Hub'
    JOB_NAME_DOCKER_HUB_DEV = 'Publish Dev to Docker Hub'
    JOB_NAME_GHCR_STABLE = 'Publish Stable to GHCR'
    JOB_NAME_GHCR_DEV = 'Publish Dev to GHCR'

    print(f"Current Commit Timestamp: {current_commit_timestamp}")
    print(f"Is Stable Release: {is_stable_release}")
    print(f"Is Dev Release: {is_dev_release}")

    # Fetch last 100 successful workflow runs of this workflow
    url_runs = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
    params_runs = {
        "status": "success",
        "per_page": 100
    }
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {github_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        response_runs = requests.get(url_runs, headers=headers, params=params_runs,timeout=20)
        response_runs.raise_for_status()
        successful_runs_data = response_runs.json()
        successful_runs = successful_runs_data.get('workflow_runs', [])
    except requests.exceptions.RequestException as e:
        print(f"::error::Failed to list workflow runs: {e}", file=sys.stderr)
        sys.exit(1)

    last_successful_stable_docker_hub_commit_timestamp = 0
    last_successful_dev_docker_hub_commit_timestamp = 0
    last_successful_stable_ghcr_commit_timestamp = 0
    last_successful_dev_ghcr_commit_timestamp = 0

    for run in successful_runs:
        run_id = run['id']
        run_commit_sha = run['head_sha']
        
        run_commit_timestamp = get_commit_timestamp(owner, repo, run_commit_sha, github_token)
        if run_commit_timestamp == 0:
            continue

        url_jobs = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        try:
            response_jobs = requests.get(url_jobs, headers=headers,timeout=20)
            response_jobs.raise_for_status()
            jobs_data = response_jobs.json()
            jobs = jobs_data.get('jobs', [])
        except requests.exceptions.RequestException as e:
            print(f"::warning::Failed to list jobs for run {run_id}: {e}", file=sys.stderr)
            continue

        for job in jobs:
            if job['conclusion'] == 'success':
                if job['name'] == JOB_NAME_DOCKER_HUB_STABLE:
                    if run_commit_timestamp > last_successful_stable_docker_hub_commit_timestamp:
                        last_successful_stable_docker_hub_commit_timestamp = run_commit_timestamp
                elif job['name'] == JOB_NAME_DOCKER_HUB_DEV:
                    if run_commit_timestamp > last_successful_dev_docker_hub_commit_timestamp:
                        last_successful_dev_docker_hub_commit_timestamp = run_commit_timestamp
                elif job['name'] == JOB_NAME_GHCR_STABLE:
                    if run_commit_timestamp > last_successful_stable_ghcr_commit_timestamp:
                        last_successful_stable_ghcr_commit_timestamp = run_commit_timestamp
                elif job['name'] == JOB_NAME_GHCR_DEV:
                    if run_commit_timestamp > last_successful_dev_ghcr_commit_timestamp:
                        last_successful_dev_ghcr_commit_timestamp = run_commit_timestamp
    
    print(f"Last successful stable Docker Hub commit timestamp: {last_successful_stable_docker_hub_commit_timestamp}")
    print(f"Last successful dev Docker Hub commit timestamp: {last_successful_dev_docker_hub_commit_timestamp}")
    print(f"Last successful stable GHCR commit timestamp: {last_successful_stable_ghcr_commit_timestamp}")
    print(f"Last successful dev GHCR commit timestamp: {last_successful_dev_ghcr_commit_timestamp}")

    # Logic for `should_apply_stable_latest`
    if is_stable_release:
        if ((current_commit_timestamp > last_successful_stable_docker_hub_commit_timestamp) or
            (last_successful_stable_docker_hub_commit_timestamp == 0) or
            (current_commit_timestamp > last_successful_stable_ghcr_commit_timestamp) or
            (last_successful_stable_ghcr_commit_timestamp == 0)):
            should_apply_stable_latest = True

    # Logic for `should_apply_dev_latest`
    if is_dev_release:
        if ((current_commit_timestamp > last_successful_dev_docker_hub_commit_timestamp) or
            (last_successful_dev_docker_hub_commit_timestamp == 0) or
            (current_commit_timestamp > last_successful_dev_ghcr_commit_timestamp) or
            (last_successful_dev_ghcr_commit_timestamp == 0)):
            should_apply_dev_latest = True

    # Output results in GitHub Actions format
    print(f"::set-output name=should_apply_stable_latest::{str(should_apply_stable_latest).lower()}")
    print(f"::set-output name=should_apply_dev_latest::{str(should_apply_dev_latest).lower()}")

if __name__ == "__main__":
    main()