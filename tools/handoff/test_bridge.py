import copy
import unittest
from bridge import Bridge, Stop, body, digest, eligible, payload, PREFIX

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


if __name__ == '__main__':
    unittest.main()
