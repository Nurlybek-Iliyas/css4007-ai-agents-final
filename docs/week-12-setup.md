# Неделя 12: память заданий и Google-сервисы

## Что работает и что пока не проверено

- Canvas: чтение и сохранение выбранных курсов в SQLite, история изменений, отдельные аккаунты, состояние источников.
- Повторное чтение не создаёт копии. Смена оставшегося времени не считается изменением задания.
- Gmail: код чтения тем, отправителей и коротких фрагментов за 1–30 дней, максимум 50 сообщений. Важность ещё не определяется; тело письма и вложения не читаются.
- Classroom: код чтения активных курсов студента и опубликованных заданий. Статус сдачи не запрашивается, поэтому остаётся неизвестным.
- Google OAuth и чтение реальных Google-данных ожидают настройки и входа пользователя. Установка библиотек и тесты с подменёнными ответами не доказывают доступ к аккаунту.
- Telegram: уточнено, что преподаватель публикует в канале; способ доступа ещё не выбран. Teams, Calendar, ежедневный планировщик и автономный выбор инструментов остаются будущими этапами.

## 1. Открыть проект в Terminal

Для текущего компьютера:

```sh
cd "/Users/rinatzabyrbay/Documents/Codex/2026-11-03/https-github-com-ardakshalkar-css4007-ai/work/study-radar"
```

Если скачал архив на другом компьютере, открой свою папку проекта вместо этого пути.

## 2. Проверить память без новых ключей

```sh
python3 studyradar.py sync --course 9097
python3 studyradar.py tasks
python3 studyradar.py changes
python3 studyradar.py sources
```

ID курса замени своим. Для нескольких курсов повторяй `--course ID`, максимум 20. Каждая полная успешная выборка сохраняется отдельно. Сбой одного курса не уничтожает его старые данные и не мешает другим курсам. Команда возвращает `complete=false` и ненулевой код при частичном сбое.

`tasks` читает локальный снимок, а не Canvas: смотри `last_success` и `error` в `sources`. `available=false` означает «не найдено в последней полной выборке», а не «выполнено» или «удалено». История включает new, updated, not_seen, restored. Разные Canvas-пользователи разделены по ID профиля; при нескольких аккаунтах укажи `--account` с ID из результата sync.

Для синтетического демо:

```sh
python3 studyradar.py sync --demo
python3 studyradar.py sync --demo
python3 studyradar.py tasks --demo
```

Демо имеет отдельную базу `.private/demo.sqlite3`; живые данные — `.private/study-radar.sqlite3`. Команды sync/tasks/changes не обращаются к модели. Пользовательские исправления статусов и объединение между сервисами пока не реализованы.

## 3. Создать Google OAuth-клиент

1. Открой https://console.cloud.google.com/ и создай проект `StudyRadar` (или выбери свой проект для него).
2. В **APIs & Services → Library** включи **Gmail API** и **Google Classroom API**.
3. Открой **Google Auth platform → Branding** и заполни имя приложения `StudyRadar`, свой support email и contact email.
4. В **Audience** для личного тестового проекта выбери **External**, оставь статус **Testing** и добавь свой Google-аккаунт в **Test users**. Если администратор университета управляет настройками и не разрешает такой доступ, потребуется его разрешение; ограничения не обходить.
5. В **Data Access** укажи только используемые read-only scopes: `gmail.readonly`, `classroom.courses.readonly`, `classroom.coursework.me.readonly` (полные URL начинаются с `https://www.googleapis.com/auth/`).
6. В **Clients → Create client** выбери **Desktop app**, имя `StudyRadar local`.
7. Скачай JSON. Его нужно сохранить локально как `.private/google-client.json`. Это файл OAuth-клиента, не API key и не service-account key. В чат и на GitHub его не отправляй.

Для открытия локальной папки на Mac:

```sh
mkdir -p .private
chmod 700 .private
open .private
```

Перемести скачанный JSON в открывшуюся папку и переименуй в `google-client.json`. Конфигурация должна содержать раздел `installed`, официальный `auth_uri` Google и `token_uri` Google. Если они не совпадают, заново скачай Desktop client из своей Google Cloud консоли.

## 4. Окружение для Google

Canvas и локальная база продолжают работать на системном Python 3.9.6. Для Google рекомендуется Python 3.11+ с актуальным SSL: установленный системный Python показывает предупреждения о завершении поддержки 3.9 и LibreSSL. Если у тебя уже есть Python 3.11+, используй его для создания отдельного окружения:

```sh
python3.11 -m venv .venv-google
.venv-google/bin/python -m pip install -r requirements-google.txt
```

При другой актуальной версии замени `python3.11` соответствующей командой. Установить Python для macOS можно с https://www.python.org/downloads/macos/ . Не отключай проверку TLS для устранения ошибок.

На текущем компьютере также создано `.venv` на системном Python, библиотеки установлены и импортированы; живой OAuth пока не проверен. Это не основание считать предупреждения о старом Python устранёнными.

## 5. Войти и проверить Google

Сначала Gmail:

```sh
.venv-google/bin/python studyradar.py google-auth --service gmail
.venv-google/bin/python studyradar.py gmail --days 3 --limit 10
```

В браузере выбери свой тестовый аккаунт и проверь, что разрешается только чтение. При блокировке организации или непонятном экране остановись и выясни причину. Refresh/access tokens сохраняются отдельно по сервисам в `.private`; вывод программы не содержит их. Если разрешение отозвано или тестовый refresh token истёк, может понадобиться новый вход: удаляй только соответствующий локальный token-файл осознанно, не раскрывая его содержимое.

Затем Classroom:

```sh
.venv-google/bin/python studyradar.py google-auth --service classroom
.venv-google/bin/python studyradar.py classroom-courses
.venv-google/bin/python studyradar.py classroom-assignments --course 123
```

Замени `123` ID из Classroom, а не Canvas. Вход выполняется отдельно, поэтому Gmail и Classroom могут использовать разные аккаунты. Эти Google-команды пока только читают/показывают данные: не сохраняют их в общую базу и не передают OpenAI.

`truncated=true` у Gmail означает, что есть дополнительные письма за пределами выбранного лимита. `failed_messages` сообщает о частично недоступных письмах. Список не является классификацией важности. Даты Classroom трактуются в UTC; если есть dueDate без dueTime, применяется документированный Google default 23:59 UTC с явной отметкой `due_time_origin`.

## 6. Проверки и публикация

```sh
python3 -m unittest discover -s tests/python -v
```

43 теста: 19 предыдущих и 24 новых. Новые тесты проверяют сохранение, историю, отсутствие дублей, атомарность, разделение аккаунтов, частичные сбои, пагинацию Google, даты и ограничения чтения Gmail. Сетевые ответы подменены; реальные Google-аккаунты не использованы.

Не загружай `.env`, `.private`, `.venv`, `.venv-google`, скачанный OAuth JSON и базы SQLite. Архив изменённых файлов подготовлен только из отслеживаемого кода и документации.

## Официальные источники

- https://developers.google.com/workspace/classroom/quickstart/python
- https://developers.google.com/workspace/gmail/quickstart/python
- https://developers.google.com/workspace/classroom/reference/rest/v1/courses.courseWork/list
- https://developers.google.com/workspace/classroom/reference/rest/v1/courses.courseWork
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list
