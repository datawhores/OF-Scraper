#!/usr/bin/python3

import os
import sys
import requests
from datetime import datetime

# Add a timeout to all requests for robustness
DEFAULT_REQUEST_TIMEOUT = 20 # seconds

def get_commit_timestamp(owner, repo, sha, github_token):
    """Fetches the commit timestamp for a given SHA."""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {github_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    try:
        response = requests.get(url, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT)
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
    is_stable_release = sys.argv[2].lower().strip() == 'true'
    is_dev_release = sys.argv[3].lower().strip() == 'true'
    run_docker_logic = sys.argv[4].lower().strip() == 'true'


    # Get environment variables set by GitHub Actions
    github_token = os.getenv('GITHUB_TOKEN')
    github_repository = os.getenv('GITHUB_REPOSITORY') # e.g., "owner/repo"
    github_workflow_ref = os.getenv('GITHUB_WORKFLOW_REF') # e.g., "owner/repo/.github/workflows/filename.yml@ref"
    github_output_path = os.getenv('GITHUB_OUTPUT') # Path to the file for step outputs

    # --- Robustness checks and early exits ---
    if not github_token:
        print("::error::GITHUB_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)
    if not github_repository:
        print("::error::GITHUB_REPOSITORY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    if not github_workflow_ref:
        print("::error::GITHUB_WORKFLOW_REF environment variable not set. Cannot determine workflow file path.", file=sys.stderr)
        sys.exit(1)
    if not github_output_path:
        print("::error::GITHUB_OUTPUT environment variable not set. Cannot write step outputs.", file=sys.stderr)
        sys.exit(1)

    owner, repo = github_repository.split('/')
    
    # Extract workflow filename from GITHUB_WORKFLOW_REF
    workflow_path_start_index = github_workflow_ref.find('.github/workflows/')
    if workflow_path_start_index == -1:
        print(f"::error::Could not find '.github/workflows/' in GITHUB_WORKFLOW_REF: {github_workflow_ref}. Invalid format.", file=sys.stderr)
        sys.exit(1)
    
    workflow_path_with_ref = github_workflow_ref[workflow_path_start_index + len('.github/workflows/'):]
    workflow_filename = workflow_path_with_ref.split('@')[0]
    
    # --- Debug derived workflow filename ---
    print(f"DEBUG: Derived workflow filename: '{workflow_filename}'", file=sys.stderr) 

    # Initialize as Python boolean False - these are the final outputs
    should_apply_stable_latest = False
    should_apply_dev_latest = False

    # --- NEW LOGIC: Only run dynamic calculations if inputs.docker is true ---
    if not run_docker_logic:
        print("DEBUG: Docker input is false. Setting should_apply_stable_latest and should_apply_dev_latest to False directly.", file=sys.stderr)
        # They are already initialized to False, so nothing more to do here.
    else:
        print("DEBUG: Docker input is true. Proceeding with dynamic latest tag calculation.", file=sys.stderr)
        # Original dynamic calculation logic follows
        
        # Define job names for easy lookup
        JOB_NAME_DOCKER_HUB_STABLE = 'Publish Stable to Docker Hub'
        JOB_NAME_DOCKER_HUB_DEV = 'Publish Dev to Docker Hub'
        JOB_NAME_GHCR_STABLE = 'Publish Stable to GHCR'
        JOB_NAME_GHCR_DEV = 'Publish Dev to GHCR'

        print(f"DEBUG: Current Commit Timestamp: {current_commit_timestamp}", file=sys.stderr)
        print(f"DEBUG: Is Stable Release: {is_stable_release}", file=sys.stderr)
        print(f"DEBUG: Is Dev Release: {is_dev_release}", file=sys.stderr)

        # Fetch last 100 successful workflow runs of this workflow
        url_runs = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_filename}/runs"
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
            response_runs = requests.get(url_runs, headers=headers, params=params_runs, timeout=DEFAULT_REQUEST_TIMEOUT)
            response_runs.raise_for_status()
            successful_runs_data = response_runs.json()
            successful_runs = successful_runs_data.get('workflow_runs', [])
            print(f"DEBUG: Successfully fetched {len(successful_runs)} successful workflow runs.", file=sys.stderr)
        except requests.exceptions.RequestException as e:
            print(f"::error::Failed to list workflow runs: {e}. URL: {url_runs}", file=sys.stderr)
            # If this API call fails when docker input is true, we should still output false, not exit.
            # So, we catch the error, print it, and let should_apply_stable_latest/dev_latest remain False.
            successful_runs = [] # Ensure loop doesn't run

        last_successful_stable_docker_hub_commit_timestamp = 0
        last_successful_dev_docker_hub_commit_timestamp = 0
        last_successful_stable_ghcr_commit_timestamp = 0
        last_successful_dev_ghcr_commit_timestamp = 0

        for run in successful_runs:
            run_id = run['id']
            run_commit_sha = run['head_sha']
            
            run_commit_timestamp = get_commit_timestamp(owner, repo, run_commit_sha, github_token)
            if run_commit_timestamp == 0:
                print(f"DEBUG: Skipping run {run_id} due to missing commit timestamp for SHA {run_commit_sha}", file=sys.stderr)
                continue

            url_jobs = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
            try:
                response_jobs = requests.get(url_jobs, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT)
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
                            print(f"DEBUG: Updated last_successful_stable_docker_hub_commit_timestamp to {run_commit_timestamp} from run {run_id}", file=sys.stderr)
                    elif job['name'] == JOB_NAME_DOCKER_HUB_DEV:
                        if run_commit_timestamp > last_successful_dev_docker_hub_commit_timestamp:
                            last_successful_dev_docker_hub_commit_timestamp = run_commit_timestamp
                            print(f"DEBUG: Updated last_successful_dev_docker_hub_commit_timestamp to {run_commit_timestamp} from run {run_id}", file=sys.stderr)
                    elif job['name'] == JOB_NAME_GHCR_STABLE:
                        if run_commit_timestamp > last_successful_stable_ghcr_commit_timestamp:
                            last_successful_stable_ghcr_commit_timestamp = run_commit_timestamp
                            print(f"DEBUG: Updated last_successful_stable_ghcr_commit_timestamp to {run_commit_timestamp} from run {run_id}", file=sys.stderr)
                    elif job['name'] == JOB_NAME_GHCR_DEV:
                        if run_commit_timestamp > last_successful_dev_ghcr_commit_timestamp:
                            last_successful_dev_ghcr_commit_timestamp = run_commit_timestamp
                            print(f"DEBUG: Updated last_successful_dev_ghcr_latest_timestamp to {run_commit_timestamp} from run {run_id}", file=sys.stderr)
        
        print(f"DEBUG: Final last_successful_stable_docker_hub_commit_timestamp: {last_successful_stable_docker_hub_commit_timestamp}", file=sys.stderr)
        print(f"DEBUG: Final last_successful_dev_docker_hub_commit_timestamp: {last_successful_dev_docker_hub_commit_timestamp}", file=sys.stderr)
        print(f"DEBUGq: Final last_successful_stable_ghcr_commit_timestamp: {last_successful_stable_ghcr_commit_timestamp}", file=sys.stderr)
        print(f"DEBUG: Final last_successful_dev_ghcr_commit_timestamp: {last_successful_dev_ghcr_commit_timestamp}", file=sys.stderr)


        # Logic for `should_apply_stable_latest`
        if is_stable_release:
            if ((current_commit_timestamp > last_successful_stable_docker_hub_commit_timestamp) or
                (last_successful_stable_docker_hub_commit_timestamp == 0) or
                (current_commit_timestamp > last_successful_stable_ghcr_commit_timestamp) or
                (last_successful_stable_ghcr_commit_timestamp == 0)):
                should_apply_stable_latest = True
                print("DEBUG: should_apply_stable_latest set to True based on logic.", file=sys.stderr)
        else:
            print("DEBUG: Not a stable release, should_apply_stable_latest remains False.", file=sys.stderr)


        # Logic for `should_apply_dev_latest`
        if is_dev_release:
            if ((current_commit_timestamp > last_successful_dev_docker_hub_commit_timestamp) or
                (last_successful_dev_docker_hub_commit_timestamp == 0) or
                (current_commit_timestamp > last_successful_dev_ghcr_commit_timestamp) or
                (last_successful_dev_ghcr_commit_timestamp == 0)):
                should_apply_dev_latest = True
                print("DEBUG: should_apply_dev_latest set to True based on logic.", file=sys.stderr)
        else:
            print("DEBUG: Not a dev release, should_apply_dev_latest remains False.", file=sys.stderr)


    print(f"DEBUG: Final should_apply_stable_latest (Python value): {should_apply_stable_latest}", file=sys.stderr)
    print(f"DEBUG: Final should_apply_dev_latest (Python value): {should_apply_dev_latest}", file=sys.stderr)

    # Write to GITHUB_OUTPUT file
    try:
        with open(github_output_path, "a") as f: # Open in append mode
            f.write(f"should_apply_stable_latest={'true' if should_apply_stable_latest else 'false'}\n")
            f.write(f"should_apply_dev_latest={'true' if should_apply_dev_latest else 'false'}\n")
        print("DEBUG: Successfully wrote outputs to GITHUB_OUTPUT.", file=sys.stderr)
    except Exception as e:
        print(f"::error::Failed to write outputs to GITHUB_OUTPUT: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()