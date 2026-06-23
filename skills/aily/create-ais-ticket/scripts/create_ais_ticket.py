#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv>=1.0",
# ]
# ///
"""Create an AIS support ticket for the infra team."""

import argparse
import base64
import json
import os
import sys
import urllib.request
from urllib.error import HTTPError

from dotenv import load_dotenv


def get_env(var: str) -> str:
    """Get environment variable or exit."""
    value = os.environ.get(var)
    if not value:
        print(f"Error: {var} environment variable not set", file=sys.stderr)
        sys.exit(1)
    return value


def make_auth_header(email: str, token: str) -> str:
    """Create Basic Auth header."""
    credentials = f"{email}:{token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def create_request(url: str, method: str, data: dict, auth_header: str) -> dict:
    """Make HTTP request to Jira."""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except HTTPError as e:
        error_body = e.read().decode()
        print(f"Error: {e.code}", file=sys.stderr)
        print(error_body, file=sys.stderr)
        sys.exit(1)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Create an AIS support ticket for the infra team"
    )
    parser.add_argument("--summary", required=True, help="Ticket summary/title")
    parser.add_argument("--description", required=True, help="Ticket description")
    parser.add_argument(
        "--urgency",
        default="Medium",
        choices=["Low", "Medium", "High"],
        help="Ticket urgency (default: Medium)",
    )
    args = parser.parse_args()

    jira_url = get_env("JIRA_URL")
    jira_email = get_env("JIRA_EMAIL")
    jira_token = get_env("JIRA_API_TOKEN")

    auth_header = make_auth_header(jira_email, jira_token)

    # Create via JSM service desk API. The service desk handles JSM-specific
    # fields (Responders, queue routing) automatically based on requestTypeId.
    # serviceDeskId=104 (AIS), requestTypeId=927 (Infrastructure request or guidance)
    # Only fields on the portal request form are accepted here; priority and
    # description are set via a follow-up PUT after creation.
    create_data = {
        "serviceDeskId": "104",
        "requestTypeId": "927",
        "requestFieldValues": {
            "summary": args.summary,
            "customfield_10175": {"value": args.urgency},
        },
    }

    result = create_request(
        f"{jira_url}/rest/servicedeskapi/request",
        "POST",
        create_data,
        auth_header,
    )

    issue_key = result["issueKey"]

    # Set description and priority via regular issue API
    create_request(
        f"{jira_url}/rest/api/2/issue/{issue_key}",
        "PUT",
        {
            "fields": {
                "description": args.description,
                "priority": {"name": "P3 - Medium"},
            }
        },
        auth_header,
    )

    print(f"Created: {issue_key}")
    print(f"{jira_url}/browse/{issue_key}")


if __name__ == "__main__":
    main()
