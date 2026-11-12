"""Core8 metadata bridge. No LLM, deployment, subprocess, or production credentials."""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPO = 'V1P3eR1/Core8-AI'
PREFIX = f'/repos/{REPO}'
SECRET = re.compile(r'(?:sk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}|(?:ntn_|secret_)[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----|(?:api[_ -]?key|password|token|secret)\s*[:=]\s*\S{8,})', re.I)


class Stop(Exception):
    """Only fixed, non-sensitive reason codes may be emitted."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class API:
    def __init__(self, provider, token):
        if not token:
            raise Stop('missing_credentials')
        self.base = {'github': 'https://api.github.com', 'notion': 'https://api.notion.com/v1'}[provider]
        self.headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                        'User-Agent': 'core8-handoff', 'Accept': 'application/json'}
        self.headers.update({'Notion-Version': '2025-09-03'} if provider == 'notion' else {'X-GitHub-Api-Version': '2022-11-28'})

    def call(self, method, path, data=None):
        if not path.startswith('/') or path.startswith('//'):
            raise Stop('invalid_api_path')
        for attempt in range(3):
            try:
                req = Request(self.base + path, data=None if data is None else json.dumps(data).encode(),
                              headers=self.headers, method=method)
                with build_opener(NoRedirect()).open(req, timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                # Never retry ambiguous writes: a timed-out POST may already have succeeded.
                if method == 'GET' and error.code in (429, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise Stop(f'api_http_{error.code}') from None
            except (URLError, TimeoutError, ValueError):
                raise Stop('api_transport_or_response_error') from None

    def all(self, path):
        result = []
        for page in range(1, 1001):
            batch = self.call('GET', path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise Stop('pagination_limit')


def text_value(page, name):
    p = page['properties'].get(name, {})
    return ''.join(x.get('plain_text', x.get('text', {}).get('content', '')) for x in p.get('title', p.get('rich_text', [])))


def selected(page, name):
    return (page['properties'].get(name, {}).get('select') or {}).get('name', '')


def payload(page):
    uid = str(uuid.UUID(page['id']))
    fields = {k: text_value(page, k).strip() for k in ('Name', 'Scope', 'Acceptance')}
    if any(not v or len(v) > 6000 for v in fields.values()) or len(fields['Name']) > 180:
        raise Stop('missing_or_oversized_scope')
    if SECRET.search(json.dumps(fields)):
        raise Stop('possible_secret_blocked')
    return {'version': 1, 'task': uid, **fields}


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def eligible(page):
    props = page['properties']
    return (not page.get('archived') and not page.get('in_trash') and selected(page, 'Decision') == 'Approved'
            and props.get('Public export', {}).get('checkbox') is True
            and bool(props.get('Approval evidence', {}).get('url')))


def body(data):
    # JSON makes boundaries explicit; neither this bridge nor its gate executes task text.
    return ('Core8 implementation intake. This is not production or merge approval.\n\n'
            f'<!-- core8-task:{data["task"]} -->\n'
            f'Scope SHA256: `{digest(data)}`\n\n'
            '```json\n' + json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n```\n\n'
            'Lev: approve this exact scope by commenting `/core8-implement ' + digest(data) + '`.\n'
            'Changed scope needs a new approval. Public export approval is recorded privately in Notion.\n')


def rt(value):
    return {'rich_text': [{'text': {'content': value}}]} if value else {'rich_text': []}


class Bridge:
    def __init__(self, gh, notion, source, apply=False):
        self.gh, self.notion, self.source, self.apply = gh, notion, str(uuid.UUID(source)), apply

    def pages(self):
        cursor = None
        while True:
            data = {'page_size': 100}
            if cursor:
                data['start_cursor'] = cursor
            result = self.notion.call('POST', f'/data_sources/{self.source}/query', data)
            yield from result['results']
            if not result.get('has_more'):
                return
            cursor = result['next_cursor']

    def update(self, page, state, error='', issue=None, sha=None):
        props = {'Status': {'select': {'name': state}}, 'Sync error': rt(error),
                 'Last sync': {'date': {'start': datetime.now(timezone.utc).isoformat()}}}
        if issue:
            props['GitHub issue'] = {'url': issue['html_url']}
        if sha:
            props['Sync digest'] = rt(sha)
        if self.apply:
            self.notion.call('PATCH', f'/pages/{page["id"]}', {'properties': props})

    def sync(self):
        issues = self.gh.all(PREFIX + '/issues?state=all')
        failures = 0
        for original in self.pages():
            page = original
            try:
                # Re-read just before export, not a stale query snapshot.
                page = self.notion.call('GET', f'/pages/{original["id"]}')
                marker = f'<!-- core8-task:{str(uuid.UUID(page["id"]))} -->'
                matches = [i for i in issues if not i.get('pull_request') and marker in (i.get('body') or '')]
                if len(matches) > 1:
                    raise Stop('duplicate_mapping')
                issue = matches[0] if matches else None
                if not eligible(page):
                    self.update(page, 'Awaiting approval', 'approval_or_public_export_missing', issue)
                    continue
                data = payload(page)
                sha = digest(data)
                expected_title = f'[Core8] {data["Name"]}'
                if issue and (issue['body'] != body(data) or issue['title'] != expected_title):
                    # Never overwrite human edits or silently refresh previously approved scope.
                    raise Stop('scope_conflict_create_new_revision')
                if not issue:
                    if self.apply:
                        issue = self.gh.call('POST', PREFIX + '/issues', {'title': expected_title, 'body': body(data)})
                        issues.append(issue)
                    else:
                        print(json.dumps({'task': data['task'], 'action': 'would_create_issue', 'digest': sha}))
                        continue
                status = 'Queued'
                if issue['state'] == 'closed':
                    status = 'Closed - unverified'
                else:
                    comments = self.gh.all(PREFIX + f'/issues/{issue["number"]}/comments')
                    # Only fixed machine audit events from the configured GitHub Actions identity.
                    for comment in comments:
                        if comment.get('user', {}).get('login') == 'github-actions[bot]':
                            match = re.fullmatch(r'core8-run ([a-f0-9]{64}) (started|review|failed) https://github.com/V1P3eR1/Core8-AI/actions/runs/\d+', comment.get('body', ''))
                            if match and match[1] == sha:
                                status = {'started': 'In progress', 'review': 'Review', 'failed': 'Blocked'}[match[2]]
                self.update(page, status, issue=issue, sha=sha)
                print(json.dumps({'task': data['task'], 'issue': issue['number'], 'status': status, 'apply': self.apply}))
            except Stop as error:
                failures += 1
                self.update(page, 'Blocked', str(error))
                print(json.dumps({'task': page['id'], 'error': str(error)}))
        if failures:
            raise Stop('one_or_more_tasks_blocked')

    def gate(self, event, approver):
        comment = event.get('comment', {})
        user = comment.get('user', {})
        if (not approver.isdigit() or str(user.get('id')) != approver or user.get('type') != 'User'
                or comment.get('performed_via_github_app')
                or event.get('action') != 'created' or event.get('issue', {}).get('pull_request')):
            raise Stop('unauthorized_approval')
        match = re.fullmatch(r'/core8-implement ([a-f0-9]{64})', comment.get('body', '').strip())
        if not match:
            raise Stop('invalid_approval_command')
        number = int(event['issue']['number'])
        # Confirm still present and unedited; do not rely on a stale webhook payload.
        current = self.gh.call('GET', PREFIX + f'/issues/comments/{int(comment["id"])}')
        if current.get('performed_via_github_app') or any(current.get(k) != comment.get(k) for k in ('body', 'updated_at', 'created_at')) or current.get('user', {}).get('id') != user['id']:
            raise Stop('approval_changed')
        issue = self.gh.call('GET', PREFIX + f'/issues/{number}')
        markers = re.findall(r'<!-- core8-task:([a-f0-9-]{36}) -->', issue.get('body', ''))
        if issue.get('pull_request') or issue['state'] != 'open' or len(markers) != 1:
            raise Stop('invalid_issue')
        page = self.notion.call('GET', f'/pages/{str(uuid.UUID(markers[0]))}')
        parent = page.get('parent', {})
        if str(uuid.UUID(parent.get('data_source_id', '00000000-0000-0000-0000-000000000000'))) != self.source:
            raise Stop('wrong_task_source')
        if not eligible(page):
            raise Stop('approval_revoked')
        data = payload(page)
        sha = digest(data)
        if match[1] != sha or issue['body'] != body(data) or issue['title'] != f'[Core8] {data["Name"]}':
            raise Stop('stale_or_modified_scope')
        # Durable at-most-once claim. After an ambiguous failure, a new task revision is required.
        comments = self.gh.all(PREFIX + f'/issues/{number}/comments')
        claim = f'core8-run {sha} started '
        if any(c.get('user', {}).get('login') == 'github-actions[bot]' and c.get('body', '').startswith(claim) for c in comments):
            raise Stop('scope_already_attempted')
        return number, data


def audit(gh, number, sha, state):
    run = os.environ.get('GITHUB_RUN_ID', '')
    if not run.isdigit() or state not in ('started', 'review', 'failed') or not re.fullmatch('[a-f0-9]{64}', sha):
        raise Stop('invalid_audit_event')
    gh.call('POST', PREFIX + f'/issues/{int(number)}/comments',
            {'body': f'core8-run {sha} {state} https://github.com/{REPO}/actions/runs/{run}'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['sync', 'gate', 'report'])
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    gh = API('github', os.environ.get('GITHUB_TOKEN'))
    if args.command == 'report':
        audit(gh, os.environ['ISSUE_NUMBER'], os.environ['SCOPE_DIGEST'], os.environ['RUN_STATE'])
        return
    bridge = Bridge(gh, API('notion', os.environ.get('NOTION_TOKEN')), os.environ['NOTION_DATA_SOURCE_ID'], args.apply)
    if args.command == 'sync':
        bridge.sync()
    else:
        if os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
            raise Stop('rerun_requires_new_task_revision')
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        number, data = bridge.gate(event, os.environ.get('CORE8_APPROVER_ID', ''))
        sha = digest(data)
        audit(gh, number, sha, 'started')
        # Only validated public fields cross the job boundary. Never pass Notion tokens.
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
            out.write(f'issue={number}\ndigest={sha}\n')
            out.write('payload=' + json.dumps(data, ensure_ascii=True) + '\n')


if __name__ == '__main__':
    try:
        main()
    except (Stop, KeyError, ValueError) as error:
        print(str(error) if isinstance(error, Stop) else 'invalid_configuration_or_payload', file=sys.stderr)
        sys.exit(1)
