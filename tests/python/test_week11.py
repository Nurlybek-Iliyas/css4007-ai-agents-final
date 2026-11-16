import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from study_radar.core import (AppError, Canvas, normalize, display_records,
                             ask_model, validate_answer, request_json, parse_due, assess_status)


def row(**values):
    return dict({'id': 1, 'name': 'Homework', 'due_at': None}, **values)


class Week11Tests(unittest.TestCase):
    def test_missing_due_remains_unknown(self):
        result = display_records([normalize(row(), 3)])[0]
        self.assertIsNone(result['due_at'])
        self.assertIsNone(result['hours_until_due'])
        self.assertEqual(result['status'], 'unknown')

    def test_timezone_and_remaining_time(self):
        records = [normalize(row(due_at='2026-11-10T18:00:00Z'), 3)]
        result = display_records(records, datetime.fromisoformat('2026-11-09T10:00:00+05:00'))[0]
        self.assertEqual(result['due_local'], '2026-11-10T23:00:00+05:00')
        self.assertEqual(result['hours_until_due'], 37)

    def test_graded_does_not_claim_submitted(self):
        result = normalize(row(submission={'workflow_state': 'graded', 'missing': True}), 3)
        self.assertEqual(result['status'], 'graded')
        self.assertTrue(result['missing'])
        self.assertIsNone(result['submitted_at'])

    def test_pagination_collects_all(self):
        calls = []
        def transport(url, token):
            calls.append(url)
            if len(calls) == 1:
                return [{'id': 1, 'name': 'A'}], {'Link': '</api/v1/courses?page=2>; rel="next"'}
            return [{'id': 2, 'name': 'B'}], {}
        self.assertEqual(len(Canvas('secret', transport).courses()), 2)
        self.assertEqual(len(calls), 2)

    def test_cross_origin_pagination_never_receives_token(self):
        calls = []
        def transport(url, token):
            calls.append(url)
            return [], {'Link': '<https://evil.example/api/v1/courses>; rel="next"'}
        with self.assertRaises(AppError):
            Canvas('secret', transport).courses()
        self.assertEqual(len(calls), 1)

    def test_page_limit_stops(self):
        calls = []
        def transport(url, token):
            calls.append(url)
            return [], {'Link': '</api/v1/courses?page=2>; rel="next"'}
        with self.assertRaises(AppError):
            Canvas('secret', transport, max_pages=1).courses()
        self.assertEqual(len(calls), 1)

    def test_invalid_course_rejected_before_network(self):
        calls = []
        with self.assertRaises(AppError):
            Canvas('secret', lambda *args: calls.append(args)).assignments(-1)
        self.assertEqual(calls, [])

    def test_no_timezone_date_rejected(self):
        with self.assertRaises(AppError):
            parse_due('2026-11-09T15:00:00')

    def test_unknown_source_and_duplicates_rejected(self):
        record = normalize(row(), 3)
        for ids in [['invented'], [record['id'], record['id']]]:
            with self.assertRaises(AppError):
                validate_answer({'source_ids': ids}, [record])

    def test_provider_adapter_and_canonical_evidence(self):
        record = normalize(row(), 3)
        calls = []
        def transport(url, token, payload):
            calls.append(payload)
            result = {'source_ids': [record['id']]}
            return {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(result)}]}]}, {}
        result = ask_model('What next?', [record], 'secret', 'test-model', transport)
        self.assertEqual(result['items'][0]['url'], record['url'])
        self.assertIsNone(result['items'][0]['due_at'])
        self.assertFalse(calls[0]['store'])
        self.assertTrue(calls[0]['text']['format']['strict'])

    def test_incomplete_model_response_rejected(self):
        with self.assertRaises(AppError):
            ask_model('Hello', [], 'secret', 'test-model', lambda *a: ({'status': 'incomplete'}, {}))

    def test_question_validation_prevents_request(self):
        calls = []
        with self.assertRaises(AppError):
            ask_model('', [], 'secret', 'test-model', lambda *a: calls.append(a))
        self.assertEqual(calls, [])

    def test_http_failure_does_not_expose_token(self):
        with patch('study_radar.core.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('https://example.com', 401, 'secret', {}, None)
            with self.assertRaises(AppError) as caught:
                request_json('https://example.com', 'secret')
            self.assertNotIn('secret', str(caught.exception))
            self.assertIn('401', str(caught.exception))

    def test_graded_past_due_without_submission_is_not_debt(self):
        record = normalize(row(due_at='2026-10-30T18:59:59Z', submission={
            'workflow_state': 'graded', 'missing': False, 'submitted_at': None}), 3)
        displayed = display_records([record], datetime.fromisoformat('2026-11-09T10:00:00+05:00'))
        answer = validate_answer({'source_ids': [record['id']]}, displayed)
        self.assertIsNone(answer['items'][0]['assessment']['needs_attention'])
        self.assertIn('задолженность не установлена', answer['items'][0]['reason'])
        self.assertTrue(answer['summary'].endswith(': 0.'))

    def test_submitted_past_due_not_debt(self):
        self.assertFalse(assess_status({'status': 'submitted', 'hours_until_due': -24})['needs_attention'])

    def test_explicit_missing_overrides_graded(self):
        self.assertTrue(assess_status({'status': 'graded', 'missing': True})['needs_attention'])

    def test_excused_not_outstanding(self):
        self.assertFalse(assess_status({'status': 'not_submitted', 'excused': True})['needs_attention'])

    def test_inconsistent_submission_requires_review(self):
        self.assertIsNone(assess_status({'status': 'not_submitted', 'submitted_at': '2026-11-01T00:00:00Z'})['needs_attention'])

    def test_old_hallucinated_summary_not_accepted(self):
        with self.assertRaises(AppError):
            validate_answer({'source_ids': [], 'summary': 'You owe homework'}, [])


if __name__ == '__main__':
    unittest.main()
