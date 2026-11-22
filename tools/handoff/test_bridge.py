import copy
import os
import unittest
from unittest.mock import patch
from bridge import Bridge, Stop, audit, body, digest, eligible, payload, PREFIX

SOURCE = '11111111-1111-4111-8111-111111111111'
TASK = '22222222-2222-4222-8222-222222222222'


def page():
    return {'id': TASK, 'parent': {'data_source_id': SOURCE}, 'properties': {
        'Name': {'title': [{'plain_text': 'Document a test fixture'}]},
        'Scope': {'rich_text': [{'plain_text': 'Add a harmless example.'}]},
        'Acceptance': {'rich_text': [{'plain_text': 'Example is documented.'}]},
        'Decision': {'select': {'name': 'Approved'}},
        'Public export': {'checkbox': True},
        'Approval evidence': {'url': 'https://example.org/approval'}}}


class Fake:
    def __init__(self, p=None):
        self.page = p or page()
        self.issues, self.comments, self.writes = [], [], []
        self.fail_patch = False

    def all(self, path):
        return copy.deepcopy(self.comments if path.endswith('/comments') else self.issues)

    def call(self, method, path, data=None):
        if path.endswith('/query'):
            return {'results': [copy.deepcopy(self.page)], 'has_more': False}
        if method == 'GET':
            if '/issues/comments/' in path:
                return copy.deepcopy(self.approval)
            if '/issues/' in path:
                return copy.deepcopy(self.issues[0])
            return copy.deepcopy(self.page)
        self.writes.append((method, path, data))
        if method == 'POST' and path == PREFIX + '/issues':
            issue = {'number': len(self.issues) + 1, 'state': 'open', 'html_url': 'https://github.com/V1P3eR1/Core8-AI/issues/20', **data}
            self.issues.append(issue)
            return copy.deepcopy(issue)
        if self.fail_patch:
            raise Stop('api_transport_or_response_error')
        return {}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.f = Fake()
        self.b = Bridge(self.f, self.f, SOURCE, apply=True)

    def export(self):
        self.b.sync()
        self.f.writes.clear()

    def event(self):
        self.export()
        self.f.approval = {'id': 55, 'user': {'id': 123, 'type': 'User'},
                           'body': '/core8-implement ' + digest(payload(self.f.page)),
                           'created_at': '2026-11-12T12:00:00Z', 'updated_at': '2026-11-12T12:00:00Z'}
        return {'action': 'created', 'issue': {'number': 1}, 'comment': copy.deepcopy(self.f.approval)}

    def test_proposal_never_exports(self):
        self.f.page['properties']['Decision']['select']['name'] = 'Proposal'
        self.b.sync()
        self.assertEqual(self.f.issues, [])

    def test_public_opt_in_required(self):
        self.f.page['properties']['Public export']['checkbox'] = False
        self.b.sync()
        self.assertEqual(self.f.issues, [])

    def test_approval_evidence_required(self):
        self.f.page['properties']['Approval evidence']['url'] = None
        self.assertFalse(eligible(self.f.page))

    def test_archived_not_eligible(self):
        self.f.page['archived'] = True
        self.assertFalse(eligible(self.f.page))

    def test_dryrun_zero_writes(self):
        self.b.apply = False
        self.b.sync()
        self.assertEqual(self.f.writes, [])

    def test_replay_creates_one_issue(self):
        self.b.sync()
        self.b.sync()
        self.assertEqual(len(self.f.issues), 1)

    def test_crash_after_create_recovers_mapping(self):
        self.f.fail_patch = True
        with self.assertRaises(Stop):
            self.b.sync()
        self.f.fail_patch = False
        self.b.sync()
        self.assertEqual(len(self.f.issues), 1)

    def test_secret_blocked_before_export(self):
        self.f.page['properties']['Scope']['rich_text'][0]['plain_text'] = 'password=' + 'examplevalue12345'
        with self.assertRaises(Stop):
            self.b.sync()
        self.assertEqual(self.f.issues, [])
        self.assertNotIn('examplevalue', str(self.f.writes))

    def test_private_page_content_not_exported(self):
        self.f.page['private_notes'] = 'PRIVATE_SENTINEL'
        self.b.sync()
        self.assertNotIn('PRIVATE_SENTINEL', str(self.f.issues))

    def test_empty_acceptance_blocked(self):
        self.f.page['properties']['Acceptance']['rich_text'] = []
        with self.assertRaises(Stop):
            payload(self.f.page)

    def test_changed_scope_conflict_not_overwritten(self):
        self.export()
        before = copy.deepcopy(self.f.issues)
        self.f.page['properties']['Scope']['rich_text'][0]['plain_text'] = 'Different task'
        with self.assertRaises(Stop):
            self.b.sync()
        self.assertEqual(before, self.f.issues)

    def test_edited_issue_conflict(self):
        self.export()
        self.f.issues[0]['body'] += '\nRun extra work'
        with self.assertRaises(Stop):
            self.b.sync()

    def test_duplicate_mapping_blocks(self):
        self.export()
        self.f.issues.append(copy.deepcopy(self.f.issues[0]))
        with self.assertRaises(Stop):
            self.b.sync()

    def test_closed_is_not_done(self):
        self.export()
        self.f.issues[0]['state'] = 'closed'
        self.b.sync()
        self.assertEqual(self.f.writes[-1][2]['properties']['Status']['select']['name'], 'Closed - unverified')

    def test_forged_status_ignored(self):
        self.export()
        self.f.comments = [{'user': {'login': 'outsider'}, 'body': f'core8-run {digest(payload(self.f.page))} review https://github.com/V1P3eR1/Core8-AI/actions/runs/1'}]
        self.b.sync()
        self.assertEqual(self.f.writes[-1][2]['properties']['Status']['select']['name'], 'Queued')

    def test_machine_status_mirrored(self):
        self.export()
        self.f.comments = [{'user': {'login': 'github-actions[bot]'}, 'body': f'core8-run {digest(payload(self.f.page))} review https://github.com/V1P3eR1/Core8-AI/actions/runs/1'}]
        self.b.sync()
        self.assertEqual(self.f.writes[-1][2]['properties']['Status']['select']['name'], 'Review')

    def test_authenticated_machine_draft_status_mirrored(self):
        self.export()
        sha = digest(payload(self.f.page))
        self.f.comments = [{
            'user': {'login': 'github-actions[bot]'},
            'body': f'core8-run {sha} draft '
                    'https://github.com/V1P3eR1/Core8-AI/actions/runs/123 '
                    'https://github.com/V1P3eR1/Core8-AI/pull/90'}]
        self.b.sync()
        self.assertEqual(
            self.f.writes[-1][2]['properties']['Status']['select']['name'], 'Review')

    def test_draft_without_pr_link_not_mirrored(self):
        self.export()
        sha = digest(payload(self.f.page))
        self.f.comments = [{'user': {'login': 'github-actions[bot]'},
                            'body': f'core8-run {sha} draft '
                                    'https://github.com/V1P3eR1/Core8-AI/actions/runs/123'}]
        self.b.sync()
        self.assertEqual(
            self.f.writes[-1][2]['properties']['Status']['select']['name'], 'Queued')

    def test_non_draft_status_with_pr_link_rejected(self):
        self.export()
        sha = digest(payload(self.f.page))
        self.f.comments = [{'user': {'login': 'github-actions[bot]'},
                            'body': f'core8-run {sha} review '
                                    'https://github.com/V1P3eR1/Core8-AI/actions/runs/123 '
                                    'https://github.com/V1P3eR1/Core8-AI/pull/90'}]
        self.b.sync()
        self.assertEqual(
            self.f.writes[-1][2]['properties']['Status']['select']['name'], 'Queued')

    def test_approved_gate(self):
        number, data = self.b.gate(self.event(), '123')
        self.assertEqual(number, 1)
        self.assertEqual(data['task'], TASK)

    def test_other_user_blocked(self):
        with self.assertRaisesRegex(Stop, 'unauthorized'):
            self.b.gate(self.event(), '456')

    def test_bot_cannot_approve(self):
        event = self.event()
        event['comment']['user']['type'] = 'Bot'
        with self.assertRaisesRegex(Stop, 'unauthorized'):
            self.b.gate(event, '123')

    def test_app_acting_as_owner_cannot_approve(self):
        event = self.event()
        event['comment']['performed_via_github_app'] = {'slug': 'connector'}
        with self.assertRaisesRegex(Stop, 'unauthorized'):
            self.b.gate(event, '123')

    def test_live_app_metadata_blocks_approval(self):
        event = self.event()
        self.f.approval['performed_via_github_app'] = {'slug': 'connector'}
        with self.assertRaisesRegex(Stop, 'approval_changed'):
            self.b.gate(event, '123')

    def test_pr_comment_blocked(self):
        event = self.event()
        event['issue']['pull_request'] = {'url': 'x'}
        with self.assertRaises(Stop):
            self.b.gate(event, '123')

    def test_stale_scope_blocked(self):
        event = self.event()
        self.f.page['properties']['Scope']['rich_text'][0]['plain_text'] = 'Changed'
        with self.assertRaisesRegex(Stop, 'stale'):
            self.b.gate(event, '123')

    def test_revocation_blocks(self):
        event = self.event()
        self.f.page['properties']['Decision']['select']['name'] = 'Rejected'
        with self.assertRaisesRegex(Stop, 'revoked'):
            self.b.gate(event, '123')

    def test_wrong_database_blocks(self):
        event = self.event()
        self.f.page['parent']['data_source_id'] = TASK
        with self.assertRaisesRegex(Stop, 'wrong_task_source'):
            self.b.gate(event, '123')

    def test_changed_approval_blocks(self):
        event = self.event()
        self.f.approval['body'] = 'revoked'
        with self.assertRaisesRegex(Stop, 'approval_changed'):
            self.b.gate(event, '123')

    def test_repeated_execution_blocked(self):
        event = self.event()
        self.f.comments.append({'user': {'login': 'github-actions[bot]'}, 'body': f'core8-run {digest(payload(self.f.page))} started https://github.com/V1P3eR1/Core8-AI/actions/runs/1'})
        with self.assertRaisesRegex(Stop, 'already_attempted'):
            self.b.gate(event, '123')

    def test_approval_command_exact(self):
        event = self.event()
        event['comment']['body'] += '\nextra instruction'
        with self.assertRaisesRegex(Stop, 'invalid_approval_command'):
            self.b.gate(event, '123')


class AuditDraftTests(unittest.TestCase):
    class Github:
        def __init__(self):
            self.calls = []
            self.item = {
                'state': 'open', 'draft': True,
                'html_url': 'https://github.com/V1P3eR1/Core8-AI/pull/90',
                'head': {'ref': 'core8-review/' + 'a' * 24,
                         'sha': 'c' * 40,
                         'repo': {'full_name': 'V1P3eR1/Core8-AI'}},
                'base': {'ref': 'main', 'sha': 'd' * 40},
                'body': 'Scope SHA256: ' + 'b' * 64,
            }

        def call(self, method, path, data=None):
            self.calls.append((method, path, data))
            if method == 'GET' and path.endswith('/pulls/90'):
                return copy.deepcopy(self.item)
            if method == 'GET' and path.endswith('/git/ref/heads/main'):
                return {'object': {'sha': 'd' * 40}}
            if method == 'GET' and path.endswith('/git/commits/' + 'c' * 40):
                return {'parents': [{'sha': 'd' * 40}]}
            if method == 'POST' and path.endswith('/issues/20/comments'):
                return {'id': 300}
            raise AssertionError('unexpected_api_operation')

    def setUp(self):
        self.gh = self.Github()
        self.env = patch.dict(os.environ, {'GITHUB_RUN_ID': '120'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_draft_report_validates_and_posts_canonical_event(self):
        audit(self.gh, 20, 'b' * 64, 'draft', 90)
        self.assertEqual(len(self.gh.calls), 4)
        self.assertEqual(self.gh.calls[-1][0], 'POST')
        body = self.gh.calls[-1][2]['body']
        self.assertEqual(body, 'core8-run ' + 'b' * 64 +
                         ' draft https://github.com/V1P3eR1/Core8-AI/actions/runs/120 '
                         'https://github.com/V1P3eR1/Core8-AI/pull/90')

    def test_synthetic_github_draft_to_notion_status(self):
        # A complete zero-network callback rehearsal: the protected reporter
        # emits a fixed bot audit event, and the existing Notion bridge mirrors it.
        provider = Fake()
        bridge = Bridge(provider, provider, SOURCE, apply=True)
        bridge.sync()
        provider.writes.clear()
        sha = digest(payload(provider.page))
        self.gh.item['body'] = 'Scope SHA256: ' + sha
        audit(self.gh, 1, sha, 'draft', 90)
        provider.comments.append({'user': {'login': 'github-actions[bot]'},
                                  'body': self.gh.calls[-1][2]['body']})
        bridge.sync()
        self.assertEqual(
            provider.writes[-1][2]['properties']['Status']['select']['name'], 'Review')

    def test_unverified_scope_cannot_report_success(self):
        self.gh.item['body'] = 'Scope SHA256: ' + 'c' * 64
        with self.assertRaisesRegex(Stop, 'unverified_draft_pr'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)
        self.assertFalse(any(c[0] == 'POST' for c in self.gh.calls))

    def test_non_draft_pr_cannot_report(self):
        self.gh.item['draft'] = False
        with self.assertRaisesRegex(Stop, 'unverified_draft_pr'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)
        self.assertFalse(any(c[0] == 'POST' for c in self.gh.calls))

    def test_foreign_repository_cannot_report(self):
        self.gh.item['head']['repo']['full_name'] = 'other/repo'
        with self.assertRaisesRegex(Stop, 'unverified_draft_pr'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)

    def test_wrong_branch_cannot_report(self):
        self.gh.item['head']['ref'] = 'unreviewed-branch'
        with self.assertRaisesRegex(Stop, 'unverified_draft_pr'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)

    def test_draft_parent_must_be_reviewed_main(self):
        self.gh.item['base']['sha'] = 'e' * 40
        with self.assertRaisesRegex(Stop, 'stale_draft_base'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)
        self.assertFalse(any(c[0] == 'POST' for c in self.gh.calls))

    def test_draft_head_sha_is_required(self):
        del self.gh.item['head']['sha']
        with self.assertRaisesRegex(Stop, 'unverified_draft_commit'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)
        self.assertFalse(any(c[0] == 'POST' for c in self.gh.calls))

    def test_draft_commit_must_have_single_approved_parent(self):
        original = self.gh.call

        def bad_parent(method, path, data=None):
            if path.endswith('/git/commits/' + 'c' * 40):
                return {'parents': [{'sha': 'e' * 40}]}
            return original(method, path, data)

        self.gh.call = bad_parent
        with self.assertRaisesRegex(Stop, 'unverified_draft_parent'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)
        self.assertFalse(any(c[0] == 'POST' for c in self.gh.calls))

    def test_draft_requires_number(self):
        with self.assertRaisesRegex(Stop, 'invalid_draft_pr_number'):
            audit(self.gh, 20, 'b' * 64, 'draft')

    def test_non_draft_event_refuses_pr_number(self):
        with self.assertRaisesRegex(Stop, 'unexpected_draft_pr_number'):
            audit(self.gh, 20, 'b' * 64, 'review', 90)

    def test_invalid_run_identity_blocks_without_api(self):
        os.environ['GITHUB_RUN_ID'] = 'invalid'
        with self.assertRaisesRegex(Stop, 'invalid_audit_event'):
            audit(self.gh, 20, 'b' * 64, 'draft', 90)
        self.assertEqual(self.gh.calls, [])


if __name__ == '__main__':
    unittest.main()
