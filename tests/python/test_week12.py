import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from study_radar.core import AppError, normalize
from study_radar.storage import Store
from study_radar.week12 import sync_courses
from study_radar.google_sources import GoogleReader, classroom_record, resource_id, google_token, checked_scope_token, safe_auth_error, SCOPES, SUBMISSIONS_SCOPE, has_required_scopes


NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)

def record():
    return normalize({'id': 1, 'name': 'Synthetic task', 'due_at': None,
                      'submission': {'workflow_state': 'unsubmitted'}}, 10)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'private' / 'tasks.sqlite3'
        self.store = Store(self.path)

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def test_persists_across_connections(self):
        self.store.snapshot('a', 'canvas:10', [record()], '2026-11-16T12:00:00+00:00')
        with Store(self.path) as other:
            self.assertEqual(len(other.tasks('a')), 1)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_repeated_snapshot_is_idempotent(self):
        self.store.snapshot('a', 's', [record()])
        changes = self.store.snapshot('a', 's', [record()])
        self.assertEqual(sum(changes.values()), 0)
        self.assertEqual(len(self.store.history('a')), 1)

    def test_dynamic_hours_do_not_cause_updates(self):
        r = record()
        r['hours_until_due'] = 40
        self.store.snapshot('a', 's', [r])
        r['hours_until_due'] = 30
        self.assertEqual(self.store.snapshot('a', 's', [r])['updated'], 0)

    def test_deadline_change_records_before_after(self):
        r = record()
        self.store.snapshot('a', 's', [r])
        r['due_at'] = '2026-12-01T18:00:00+00:00'
        self.assertEqual(self.store.snapshot('a', 's', [r])['updated'], 1)
        history = self.store.history('a')[0]
        self.assertIsNone(json.loads(history['before_json'])['due_at'])
        self.assertEqual(json.loads(history['after_json'])['due_at'], r['due_at'])

    def test_accounts_and_scopes_are_isolated(self):
        self.store.snapshot('a', 's', [record()])
        self.store.snapshot('b', 's', [])
        self.store.snapshot('a', 'other', [])
        self.assertEqual(len(self.store.tasks('a')), 1)
        self.assertEqual(self.store.tasks('b'), [])

    def test_failure_preserves_success_and_records(self):
        self.store.snapshot('a', 's', [record()], '2026-11-16T10:00:00+00:00')
        self.store.failure('a', 's', '2026-11-16T11:00:00+00:00')
        health = self.store.health('a')[0]
        self.assertEqual(health['last_success'], '2026-11-16T10:00:00+00:00')
        self.assertIsNotNone(health['error'])
        self.assertTrue(self.store.tasks('a')[0]['available'])

    def test_absence_does_not_mark_completion_and_can_restore(self):
        self.store.snapshot('a', 's', [record()])
        self.assertEqual(self.store.snapshot('a', 's', [])['not_seen'], 1)
        item = self.store.tasks('a')[0]
        self.assertFalse(item['available'])
        self.assertEqual(item['status'], 'not_submitted')
        self.assertEqual(self.store.snapshot('a', 's', [record()])['restored'], 1)

    def test_invalid_snapshot_is_not_partially_saved(self):
        self.store.snapshot('a', 's', [record()])
        with self.assertRaises(AppError):
            self.store.snapshot('a', 's', [record(), {'id': 'broken'}])
        self.assertEqual(len(self.store.tasks('a')), 1)
        self.assertEqual(len(self.store.history('a')), 1)

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(AppError):
            self.store.snapshot('a', 's', [record(), record()])
        self.assertEqual(self.store.accounts(), [])

    def test_partial_sync_continues_after_source_failure(self):
        def fetch(course):
            if course == 1:
                raise AppError('secret should not be stored')
            return [record()]
        result = sync_courses(self.store, 'a', [1, 2], fetch)
        self.assertFalse(result[0]['ok'])
        self.assertTrue(result[1]['ok'])
        self.assertEqual(len(self.store.tasks('a')), 1)
        self.assertNotIn('secret', str(self.store.health('a')))

    def test_history_limit_validated(self):
        with self.assertRaises(AppError):
            self.store.history('a', 1000)


class GoogleTests(unittest.TestCase):
    def test_classroom_utc_deadline(self):
        r = classroom_record({'id': '2', 'title': 'Work', 'dueDate': {'year': 2026, 'month': 11, 'day': 20},
                              'dueTime': {'hours': 18, 'minutes': 30}}, '1')
        self.assertEqual(r['due_at'], '2026-11-20T18:30:00+00:00')
        self.assertEqual(r['status'], 'unknown')
        self.assertFalse(r['submission_checked'])

    def test_classroom_submission_states_and_user_filter(self):
        states = [('NEW', 'not_submitted', True), ('CREATED', 'not_submitted', True),
                  ('TURNED_IN', 'submitted', False), ('RETURNED', 'returned', None),
                  ('RECLAIMED_BY_STUDENT', 'not_submitted', True), ('FUTURE', 'unknown', None)]
        for state, expected, attention in states:
            calls = []
            def transport(url, token):
                calls.append(url)
                if 'studentSubmissions' in url:
                    return {'studentSubmissions': [{'courseId': '1', 'courseWorkId': '2',
                                                    'state': state, 'late': True}]}, {}
                return {'courseWork': [{'id': '2', 'title': 'Test'}]}, {}
            row = GoogleReader('synthetic', transport).coursework('1')[0]
            self.assertEqual(row['status'], expected)
            self.assertIs(row['assessment']['needs_attention'], attention)
            self.assertTrue(row['submission_checked'])
            self.assertIn('userId=me', calls[1])

    def test_classroom_submission_failure_preserves_assignments(self):
        def transport(url, token):
            if 'studentSubmissions' in url:
                raise AppError('private failure')
            return {'courseWork': [{'id': '2', 'title': 'Test'}]}, {}
        row = GoogleReader('s', transport).coursework('1')[0]
        self.assertFalse(row['submission_checked'])
        self.assertEqual(row['status'], 'unknown')
        self.assertNotIn('private failure', str(row))

    def test_classroom_missing_foreign_or_duplicate_submission_unknown(self):
        for submissions in ([], [{'courseId': 'other', 'courseWorkId': '2', 'state': 'TURNED_IN'}],
                            [{'courseId': '1', 'courseWorkId': '2', 'state': 'NEW'}] * 2):
            def transport(url, token):
                if 'studentSubmissions' in url:
                    return {'studentSubmissions': submissions}, {}
                return {'courseWork': [{'id': '2', 'title': 'Test'}]}, {}
            row = GoogleReader('s', transport).coursework('1')[0]
            self.assertEqual(row['status'], 'unknown')
            self.assertIsNone(row['assessment']['needs_attention'])

    def test_classroom_missing_due_stays_unknown(self):
        self.assertIsNone(classroom_record({'id': '2', 'title': 'Work'}, '1')['due_at'])

    def test_classroom_date_only_uses_documented_default(self):
        r = classroom_record({'id': '2', 'title': 'Work', 'dueDate': {'year': 2026, 'month': 11, 'day': 20}}, '1')
        self.assertEqual(r['due_at'], '2026-11-20T23:59:00+00:00')
        self.assertEqual(r['due_time_origin'], 'google_default_23_59_UTC')
        self.assertEqual(r['due_date_only'], '2026-11-20')

    def test_classroom_invalid_date_rejected(self):
        with self.assertRaises(AppError):
            classroom_record({'id': '2', 'title': 'Work', 'dueDate': {'year': 2026, 'month': 2, 'day': 31}}, '1')

    def test_google_id_path_traversal_rejected(self):
        with self.assertRaises(AppError):
            resource_id('../other')

    def test_google_pagination(self):
        calls = []
        def transport(url, token):
            calls.append(url)
            return ({'courses': [{'id': '1'}], 'nextPageToken': 'next'} if len(calls) == 1 else
                    {'courses': [{'id': '2'}]}), {}
        result = GoogleReader('secret', transport).courses()
        self.assertEqual(len(result), 2)
        self.assertIn('studentId=me', calls[0])
        self.assertIn('pageToken=next', calls[1])

    def test_google_repeated_page_is_bounded(self):
        calls = []
        def transport(url, token):
            calls.append(url)
            return {'courses': [], 'nextPageToken': 'same'}, {}
        with self.assertRaises(AppError):
            GoogleReader('secret', transport).courses()
        self.assertEqual(len(calls), 2)

    def test_google_page_budget(self):
        with self.assertRaises(AppError):
            GoogleReader('secret', lambda *a: ({'nextPageToken': 'next'}, {}), max_pages=1).courses()

    def test_gmail_cap_and_interval_and_metadata(self):
        calls = []
        def transport(url, token):
            calls.append(url)
            if '/messages?' in url:
                return {'messages': [{'id': 'abc'}], 'nextPageToken': 'more'}, {}
            return {'internalDate': str(int(NOW.timestamp() * 1000)), 'snippet': 'Synthetic message',
                    'payload': {'headers': [{'name': 'Subject', 'value': 'Practice'}]}}, {}
        result = GoogleReader('secret', transport).recent_mail(3, 1, NOW)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['messages'][0]['subject'], 'Practice')
        self.assertEqual(result['messages'][0]['status'], 'not_classified')
        self.assertIn('format=metadata', calls[1])

    def test_gmail_outside_window_not_included(self):
        count = []
        def transport(*a):
            count.append(1)
            return ({'messages': [{'id': 'a'}]} if len(count) == 1 else {'internalDate': '0'}), {}
        self.assertEqual(GoogleReader('s', transport).recent_mail(now=NOW)['messages'], [])

    def test_gmail_individual_failure_reported(self):
        def transport(url, token):
            if '/messages?' in url:
                return {'messages': [{'id': 'a'}]}, {}
            raise AppError('private error')
        result = GoogleReader('s', transport).recent_mail(now=NOW)
        self.assertEqual(result['failed_messages'], 1)
        self.assertNotIn('private error', str(result))

    def test_gmail_invalid_limit_prevents_network(self):
        calls = []
        with self.assertRaises(AppError):
            GoogleReader('s', lambda *a: calls.append(a)).recent_mail(limit=100)
        self.assertEqual(calls, [])

    def test_unknown_google_service_rejected(self):
        with self.assertRaises(AppError):
            google_token('unused', 'calendar')

    def test_oauth_existing_readonly_scopes_accepted(self):
        warning = Warning('hidden')
        warning.token = {'access_token': 'synthetic'}
        warning.new_scope = SCOPES['gmail'] + SCOPES['classroom']
        token, scopes = checked_scope_token(warning, SCOPES['classroom'])
        self.assertTrue(set(SCOPES['classroom']).issubset(scopes))
        self.assertEqual(token['access_token'], 'synthetic')

    def test_classroom_alternative_readonly_scope_is_preserved(self):
        warning = Warning('hidden')
        warning.token = {'access_token': 'synthetic'}
        warning.new_scope = [SCOPES['classroom'][0], SUBMISSIONS_SCOPE]
        token, scopes = checked_scope_token(warning, SCOPES['classroom'])
        self.assertIn(SUBMISSIONS_SCOPE, scopes)
        self.assertNotIn(SCOPES['classroom'][1], scopes)
        from types import SimpleNamespace
        saved = SimpleNamespace(scopes=scopes, granted_scopes=None)
        self.assertTrue(has_required_scopes(saved, SCOPES['classroom']))
        saved.granted_scopes = SCOPES['classroom'][:1]
        self.assertFalse(has_required_scopes(saved, SCOPES['classroom']))

    def test_oauth_partial_consent_rejected(self):
        warning = Warning('hidden')
        warning.token = {'access_token': 'synthetic'}
        warning.new_scope = SCOPES['classroom'][:1]
        with self.assertRaises(AppError):
            checked_scope_token(warning, SCOPES['classroom'])

    def test_oauth_missing_scope_diagnostic_hides_token(self):
        warning = Warning('secret-warning')
        warning.token = {'access_token': 'secret-token'}
        warning.new_scope = SCOPES['gmail'] + SCOPES['classroom'][:1]
        with self.assertRaises(AppError) as caught:
            checked_scope_token(warning, SCOPES['classroom'])
        message = str(caught.exception)
        self.assertIn('classroom.coursework.me.readonly', message)
        self.assertIn('gmail.readonly', message)
        self.assertNotIn('secret', message)

    def test_oauth_unexpected_scopes_rejected(self):
        warning = Warning('hidden')
        warning.token = {'access_token': 'synthetic'}
        warning.new_scope = SCOPES['classroom'] + ['https://mail.google.com/']
        with self.assertRaises(AppError):
            checked_scope_token(warning, SCOPES['classroom'])

    def test_oauth_diagnostic_does_not_print_secrets(self):
        self.assertNotIn('synthetic-secret', safe_auth_error(ValueError('synthetic-secret')))
        self.assertIn('ValueError', safe_auth_error(ValueError('synthetic-secret')))


if __name__ == '__main__':
    unittest.main()
