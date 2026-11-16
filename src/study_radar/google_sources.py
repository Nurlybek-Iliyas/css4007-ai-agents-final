"""Optional read-only Google integration. OAuth credentials never enter LLM input."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from .core import AppError, request_json

SCOPES = {
    'gmail': ['https://www.googleapis.com/auth/gmail.readonly'],
    'classroom': ['https://www.googleapis.com/auth/classroom.courses.readonly',
                  'https://www.googleapis.com/auth/classroom.coursework.me.readonly']}


def google_token(private_dir, service, interactive=False):
    if service not in SCOPES:
        raise AppError('Неизвестный Google-сервис.')
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise AppError('Установи Google-зависимости: python3 -m pip install -r requirements-google.txt') from None
    private_dir = Path(private_dir)
    private_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    token_path = private_dir / ('google-' + service + '-token.json')
    client_path = private_dir / 'google-client.json'
    try:
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES[service])
        if creds and not creds.has_scopes(SCOPES[service]):
            creds = None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif interactive:
                if not client_path.exists():
                    raise AppError('Сохрани OAuth Desktop client JSON в .private/google-client.json. См. docs/week-12-setup.md.')
                # Refuse arbitrary auth/token endpoints from a malformed client file.
                client = json.loads(client_path.read_text()).get('installed', {})
                if (client.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth' or
                        client.get('token_uri') != 'https://oauth2.googleapis.com/token'):
                    raise AppError('Ожидается официальный Google OAuth JSON типа Desktop app.')
                flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES[service])
                creds = flow.run_local_server(host='127.0.0.1', port=0, timeout_seconds=180,
                                             authorization_prompt_message='Открывается браузер Google для входа.',
                                             success_message='StudyRadar: вход завершён. Вернись в Terminal.')
            else:
                raise AppError('Сначала выполни google-auth --service ' + service)
        if not creds or not creds.valid or not creds.has_scopes(SCOPES[service]):
            raise AppError('Google не предоставил необходимые разрешения.')
        tmp = token_path.with_suffix('.tmp')
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(creds.to_json())
        os.replace(tmp, token_path)
        os.chmod(token_path, 0o600)
        return creds.token
    except AppError:
        raise
    except Exception:
        raise AppError('Не удалось авторизовать Google. Проверь OAuth-клиент, test user и разрешения организации; секреты скрыты.') from None


def resource_id(value):
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise AppError('Некорректный Google ID.')
    return value


class GoogleReader:
    def __init__(self, token, transport=request_json, max_pages=10):
        if not token or type(max_pages) is not int or not 1 <= max_pages <= 20:
            raise AppError('Не задан токен или неверен лимит страниц.')
        self.token, self.transport, self.max_pages = token, transport, max_pages

    def get(self, url, params=None):
        data, _ = self.transport(url + ('?' + urlencode(params) if params else ''), self.token)
        if not isinstance(data, dict):
            raise AppError('Google вернул неожиданный формат ответа.')
        return data

    def pages(self, url, params, field):
        params, results, seen = dict(params), [], set()
        for _ in range(self.max_pages):
            data = self.get(url, params)
            rows = data.get(field, [])
            if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
                raise AppError('Google вернул некорректный список.')
            results.extend(rows)
            token = data.get('nextPageToken')
            if not token:
                return results
            if not isinstance(token, str) or token in seen:
                raise AppError('Google повторяет страницу; проверка остановлена.')
            seen.add(token)
            params['pageToken'] = token
        raise AppError('Достигнут лимит страниц Google; результат неполный.')

    def courses(self):
        rows = self.pages('https://classroom.googleapis.com/v1/courses',
                          {'studentId': 'me', 'courseStates': 'ACTIVE', 'pageSize': 100}, 'courses')
        return [{'id': resource_id(r['id']), 'name': r.get('name', '')} for r in rows]

    def coursework(self, course_id):
        course_id = resource_id(course_id)
        base = 'https://classroom.googleapis.com/v1/courses/' + course_id + '/courseWork'
        works = self.pages(base, {'pageSize': 100, 'courseWorkStates': 'PUBLISHED'}, 'courseWork')
        return [classroom_record(r, course_id) for r in works]

    def recent_mail(self, days=3, limit=20, now=None):
        if type(days) is not int or not 1 <= days <= 30 or type(limit) is not int or not 1 <= limit <= 50:
            raise AppError('Допустимо 1–30 дней и 1–50 писем.')
        now = now or datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        base = 'https://gmail.googleapis.com/gmail/v1/users/me/messages'
        params = {'q': 'after:%d before:%d' % (int(start.timestamp()), int(now.timestamp()) + 1), 'maxResults': limit}
        page = self.get(base, params)
        refs = page.get('messages', [])
        if not isinstance(refs, list):
            raise AppError('Gmail вернул некорректный список.')
        result, errors = [], 0
        for ref in refs[:limit]:
            try:
                message_id = resource_id(ref['id'])
                mail = self.get(base + '/' + message_id, {'format': 'metadata'})
                received = datetime.fromtimestamp(int(mail['internalDate']) / 1000, timezone.utc)
                if not start <= received <= now:
                    continue
                headers = {h['name'].lower(): h.get('value', '') for h in mail.get('payload', {}).get('headers', [])}
                result.append({'id': 'gmail:' + message_id, 'subject': headers.get('subject', '(без темы)'),
                               'from': headers.get('from', ''), 'received_at': received.isoformat(),
                               'snippet': mail.get('snippet', ''), 'thread_id': mail.get('threadId'),
                               'status': 'not_classified', 'deadline': None})
            except (AppError, KeyError, TypeError, ValueError, OverflowError):
                errors += 1
        result.sort(key=lambda x: x['received_at'], reverse=True)
        return {'messages': result, 'window_start': start.isoformat(), 'window_end': now.isoformat(),
                'truncated': bool(page.get('nextPageToken')) or len(refs) > limit,
                'failed_messages': errors, 'classification': 'Письма ещё не оценены по важности. Тело и вложения не загружены.',
                'coverage': 'Только Gmail. По умолчанию спам и корзина исключены. Данные не передаются в LLM.'}


def classroom_record(work, course_id):
    work_id = resource_id(work.get('id', ''))
    title = work.get('title')
    if not isinstance(title, str) or not title.strip():
        raise AppError('У задания Classroom нет названия.')
    date, time = work.get('dueDate'), work.get('dueTime')
    due, date_only = None, None
    if date is not None:
        try:
            date_value = datetime(date['year'], date['month'], date['day'], tzinfo=timezone.utc)
            if time is None:
                date_only = date_value.date().isoformat()
                # Documented Classroom default, not an LLM-invented time.
                due = date_value.replace(hour=23, minute=59).isoformat()
            else:
                due = date_value.replace(hour=time.get('hours', 0), minute=time.get('minutes', 0),
                                         second=time.get('seconds', 0)).isoformat()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise AppError('Некорректная дата Classroom.') from None
    return {'id': 'classroom:%s:%s' % (course_id, work_id), 'title': title,
            'source': 'classroom', 'course_id': course_id, 'due_at': due, 'due_date_only': date_only,
            'due_time_origin': 'google_default_23_59_UTC' if date_only else ('explicit' if due else 'unknown'),
            'status': 'unknown', 'submission_checked': False, 'missing': None, 'excused': None,
            'description': str(work.get('description', ''))[:4000],
            'url': work.get('alternateLink'),
            'coverage': 'Проверено задание; статус сдачи студента пока не запрашивается.'}
