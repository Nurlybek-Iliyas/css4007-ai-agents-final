"""Week 12 CLI commands, kept separate from the tested Week 11 workflow."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .core import AppError, Canvas, display_records, load_config, normalize, positive_id, require, request_json
from .storage import Store
from .google_sources import GoogleReader, google_token

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = {'sync', 'tasks', 'changes', 'sources', 'google-auth', 'classroom-courses', 'classroom-assignments', 'gmail'}


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def cached_account(store, requested):
    accounts = store.accounts()
    if requested:
        if requested not in accounts:
            raise AppError('Аккаунт отсутствует в локальной базе.')
        return requested
    if len(accounts) != 1:
        raise AppError('Сначала выполни sync. Если аккаунтов несколько, укажи --account: ' + ', '.join(accounts))
    return accounts[0]


def sync_courses(store, account, course_ids, fetch, at=None):
    if not 1 <= len(set(course_ids)) <= 20:
        raise AppError('Выбери от 1 до 20 курсов.')
    for course_id in course_ids:
        positive_id(course_id)
    outcomes = []
    for course_id in dict.fromkeys(course_ids):
        scope = 'canvas:' + str(course_id)
        try:
            records = fetch(course_id)
            counts = store.snapshot(account, scope, records, at)
            outcomes.append({'scope': scope, 'ok': True, 'records': len(records), 'changes': counts})
        except AppError:
            store.failure(account, scope, at)
            outcomes.append({'scope': scope, 'ok': False, 'error': 'Источник недоступен или данные некорректны; прежний снимок сохранён.'})
    return outcomes


def main(argv):
    parser = argparse.ArgumentParser(description='StudyRadar — сохранение задач и Google, неделя 12')
    parser.add_argument('command', choices=sorted(COMMANDS))
    parser.add_argument('--course', action='append', type=int, default=[])
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--account')
    parser.add_argument('--service', choices=['gmail', 'classroom'])
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args(argv)
    try:
        private = ROOT / '.private'
        if args.command in {'google-auth', 'classroom-courses', 'classroom-assignments', 'gmail'}:
            if args.demo:
                raise AppError('Google-команды не имеют демо-режима. Сетевые ответы проверяются отдельными тестами.')
            if args.command == 'google-auth' and args.service is None:
                raise AppError('Выбери --service gmail или --service classroom.')
            if args.command == 'classroom-assignments' and len(args.course) != 1:
                raise AppError('Для Classroom укажи один --course ID из classroom-courses.')
            if args.command == 'gmail' and not (1 <= args.days <= 30 and 1 <= args.limit <= 50):
                raise AppError('Допустимо 1–30 дней и 1–50 писем.')
            service = args.service if args.command == 'google-auth' else ('gmail' if args.command == 'gmail' else 'classroom')
            token = google_token(private, service, interactive=args.command == 'google-auth')
            reader = GoogleReader(token)
            if args.command == 'google-auth':
                emit({'service': service, 'authorized': True, 'note': 'Вход выполнен. Чтение данных проверяется отдельной командой.'})
            elif args.command == 'classroom-courses':
                emit({'source': 'classroom', 'courses': reader.courses()})
            elif args.command == 'classroom-assignments':
                records = reader.coursework(args.course[0])
                # Unlike Canvas, student submission status has not been fetched here.
                for record in records:
                    if record['due_at']:
                        due = datetime.fromisoformat(record['due_at'])
                        from zoneinfo import ZoneInfo
                        record['due_local'] = due.astimezone(ZoneInfo('Asia/Almaty')).isoformat()
                emit({'source': 'classroom', 'checked_at': datetime.now(timezone.utc).isoformat(),
                      'assignments': records, 'note': 'Статусы сдачи не проверены. Данные не сохраняются и не передаются модели.'})
            else:
                emit(reader.recent_mail(args.days, args.limit))
            return 0

        db_path = private / ('demo.sqlite3' if args.demo else 'study-radar.sqlite3')
        if args.command != 'sync' and not db_path.exists():
            raise AppError('Локальной базы пока нет. Сначала выполни sync (или sync --demo).')
        with Store(db_path) as store:
            if args.command == 'sync':
                if args.demo:
                    fixture = json.loads((ROOT / 'data/fixtures/canvas-demo.json').read_text())
                    courses, account = [101], 'demo'
                    fetch = lambda course_id: [normalize(r, course_id) for r in fixture['assignments']]
                else:
                    if not args.course or len(set(args.course)) > 20:
                        raise AppError('Для синхронизации укажи 1–20 --course ID.')
                    for course_id in args.course:
                        positive_id(course_id)
                    config = load_config(ROOT / '.env')
                    token = require(config, 'CANVAS_TOKEN')
                    client = Canvas(token)
                    profile, _ = request_json(Canvas.BASE + '/api/v1/users/self/profile', token)
                    if not isinstance(profile, dict):
                        raise AppError('Не удалось определить Canvas-аккаунт.')
                    account = 'canvas-user:' + str(positive_id(profile.get('id')))
                    courses, fetch = args.course, client.assignments
                outcomes = sync_courses(store, account, courses, fetch)
                success = all(x['ok'] for x in outcomes)
                emit({'mode': 'SYNTHETIC DEMO' if args.demo else 'LIVE CANVAS', 'account': account,
                      'complete': success, 'results': outcomes,
                      'note': 'Никакие данные не переданы модели. Проверены только выбранные курсы.'})
                return 0 if success else 1
            account = cached_account(store, args.account)
            payload = {'mode': 'LOCAL CACHE — NOT A LIVE CHECK', 'account': account,
                       'sources': store.health(account),
                       'note': 'Это сохранённые данные. Смотри last_success и error. available=false не означает выполнено.'}
            if args.command == 'tasks':
                payload['tasks'] = store.tasks(account)
            elif args.command == 'changes':
                payload['changes'] = store.history(account, args.limit)
            emit(payload)
            return 0
    except AppError as exc:
        print('Ошибка: ' + str(exc))
        return 1
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print('Ошибка локальных данных или формата ответа. Секреты скрыты.')
        return 1
