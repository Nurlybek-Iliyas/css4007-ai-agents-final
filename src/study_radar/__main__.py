import argparse
import getpass
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from .core import AppError, Canvas, ask_model, display_records, load_config, normalize, require

ROOT = Path(__file__).resolve().parents[2]


def setup():
    target = ROOT / '.env'
    if target.exists():
        raise AppError('.env уже существует. Отредактируй его локально; перезапись отключена.')
    canvas = getpass.getpass('Canvas-токен (ввод скрыт, Enter чтобы пропустить): ').strip()
    key = getpass.getpass('OpenAI API key (ввод скрыт, Enter чтобы пропустить): ').strip()
    if any('\n' in v or '\r' in v for v in (canvas, key)):
        raise AppError('Ключ не должен содержать переносы строки.')
    if not canvas and not key:
        raise AppError('Ключи не введены; файл не создан.')
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write('CANVAS_TOKEN=' + canvas + '\nOPENAI_API_KEY=' + key + '\nLLM_MODEL=gpt-5.4-mini\n')
    print('Сохранено локально в .env (исключён из Git). Значения ключей не выводятся.')


def main():
    parser = argparse.ArgumentParser(description='StudyRadar — прототип недели 11')
    parser.add_argument('command', choices=['setup', 'demo', 'courses', 'assignments', 'ask'])
    parser.add_argument('--course', type=int, action='append', default=[])
    parser.add_argument('--question', default='Какие задания требуют моего внимания?')
    parser.add_argument('--demo', action='store_true', help='Использовать синтетические данные вместо Canvas')
    parser.add_argument('--allow-private-data', action='store_true', help='Разрешить отправку выбранных Canvas-заданий в OpenAI')
    args = parser.parse_args()
    try:
        if args.command == 'setup':
            setup()
            return 0
        config = load_config(ROOT / '.env')
        demo = args.command == 'demo' or args.demo
        if demo:
            if args.command == 'courses':
                raise AppError('Для списка курсов используй courses без --demo.')
            fixture = json.loads((ROOT / 'data/fixtures/canvas-demo.json').read_text())
            records = [normalize(row, 101) for row in fixture['assignments']]
            now = datetime.fromisoformat(fixture['now'])
        else:
            client = Canvas(require(config, 'CANVAS_TOKEN'))
            if args.command == 'courses':
                print(json.dumps(client.courses(), ensure_ascii=False, indent=2))
                return 0
            if not args.course or len(set(args.course)) > 5:
                raise AppError('Укажи от 1 до 5 курсов: --course ID (ID смотри в courses).')
            records = []
            for course_id in dict.fromkeys(args.course):
                records.extend(client.assignments(course_id))
            now = datetime.now(timezone.utc)
        records = display_records(records, now)
        output = {'mode': 'SYNTHETIC DEMO' if demo else 'LIVE CANVAS',
                  'checked_at': now.isoformat(), 'timezone': 'Asia/Almaty',
                  'coverage': 'Только выбранные Canvas-курсы. Другие сервисы не проверялись.',
                  'assignments': records}
        if args.command == 'ask':
            if not demo and not args.allow_private_data:
                raise AppError('Для передачи выбранных заданий модели добавь --allow-private-data. Можно начать с ask --demo.')
            output['answer'] = ask_model(args.question, records, require(config, 'OPENAI_API_KEY'),
                                        config.get('LLM_MODEL', 'gpt-5.4-mini'))
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (AppError, OSError, ValueError) as exc:
        if isinstance(exc, AppError):
            print('Ошибка: ' + str(exc))
        else:
            print('Ошибка локальных данных или файлов. Проверь конфигурацию; секреты не выводятся.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
