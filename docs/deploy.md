# Развёртывание на сервере

Для того, кто ставит журнал на сервер центра. Нужен VPS с Ubuntu 24.04 LTS (2 ГБ памяти и 20 ГБ диска хватит на несколько сотен учеников) и домен, у которого A-запись указывает на сервер. Команды ниже выполняются от root, пока не сказано иначе.

Схема:
- снаружи открыт только Caddy (80 и 443): HTTPS от Let's Encrypt, заголовки безопасности, статика фронтенда;
- API — Django и gunicorn, без прав root, корневая файловая система только для чтения;
- PostgreSQL и Redis — во внутренней сети Docker без выхода в интернет;
- бэкап — каждую ночь, зашифрован, хранится вне сервера.

## 1. Сервер

```sh
apt update && apt full-upgrade -y
adduser --disabled-password --gecos "" deploy
mkdir -p /home/deploy/.ssh && cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh
usermod -aG sudo deploy && passwd deploy   # пароль нужен только для sudo
```

Проверьте с другого компьютера, что `ssh deploy@<сервер>` входит по ключу. **Только после этого** запрещайте пароли и root:

```sh
git clone <адрес репозитория> /opt/journal
cp /opt/journal/infra/server/ssh/10-journal.conf /etc/ssh/sshd_config.d/
sshd -t && systemctl reload ssh
```

Фаервол — только 22, 80 и 443:

```sh
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw enable
```

Docker публикует порты в обход ufw, поэтому в `docker-compose.prod.yml` порты есть только у Caddy (80 и 443). У базы и Redis их нет — CI это проверяет.

fail2ban и автоматические обновления безопасности:

```sh
apt install -y fail2ban unattended-upgrades
cp /opt/journal/infra/server/fail2ban/journal.local /etc/fail2ban/jail.d/
cp /opt/journal/infra/server/apt/20auto-upgrades /opt/journal/infra/server/apt/52journal-unattended-upgrades /etc/apt/apt.conf.d/
systemctl restart fail2ban && fail2ban-client status sshd
```

Если ядро обновилось, сервер перезагружается сам в 04:30 — после бэкапа.

Docker — из официального репозитория (https://docs.docker.com/engine/install/ubuntu/): пакеты `docker-ce` и `docker-compose-plugin`.

## 2. Настройки и запуск

```sh
cd /opt/journal
cp .env.prod.example .env.prod && chmod 600 .env.prod
nano .env.prod
```

Замените каждое `change-me`; команды генерации — в начале файла. В `.env.prod` три разные роли PostgreSQL:
- **суперпользователь** — существует только внутри контейнера;
- **владелец** (`DB_OWNER_USER`) — под ним идут только миграции;
- **приложение** (`DB_USER`) — читает и пишет строки, но не может изменить журнал аудита и отключить его триггер.

Запуск:

```sh
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod ps
```

При каждом `up` сначала выполняется задача `migrate`: миграции, выдача прав роли приложения (`db_grants`) и проверка, что прав не больше нужного. API стартует, только если всё прошло. Сертификат Caddy получает сам за минуту, пока домен указывает на сервер.

Первый администратор:

```sh
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod exec api python manage.py shell -c "
from apps.accounts.models import User
User.objects.create_user(login='admin', password='<временный пароль>', last_name='Фамилия',
                         first_name='Имя', roles=['admin'], must_change_password=True)"
```

При первом входе он сменит пароль и настроит 2FA. Дальше пользователи заводятся через интерфейс; как начать учебный год — в [admin-guide.md](admin-guide.md).

## 3. Фоновые задания

```sh
cp infra/server/systemd/journal-*.service infra/server/systemd/journal-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now journal-nightly.timer journal-backup.timer journal-restore-check.timer
systemctl list-timers 'journal-*'
```

| Таймер | Когда | Что делает |
| --- | --- | --- |
| `journal-nightly` | 01:30 | занятия на 4 недели вперёд, очистка записей об отказах старше 30 дней |
| `journal-backup` | 02:30 | зашифрованный бэкап вне сервера, ротация 14 / 8 / 12 |
| `journal-restore-check` | 1-го числа, 04:00 | восстановление последнего бэкапа во временную базу и проверка |

Результат бэкапа и проверки восстановления виден администратору в «Настройки» → «Резервные копии». Подробности — `journalctl -u journal-backup`.

## 4. Бэкапы

Бэкап — это `pg_dump` (custom-формат), зашифрованный [age](https://age-encryption.org) открытым ключом и скопированный через [rclone](https://rclone.org) в любое внешнее хранилище: S3-совместимое (Backblaze B2, Yandex Object Storage, Selectel и т. п.), SFTP на другой сервер или Google Drive. Хранится 14 ежедневных, 8 еженедельных и 12 ежемесячных копий; ротацию делает `infra/backup/retention.py`.

```sh
apt install -y age rclone
mkdir -p /etc/journal && chmod 700 /etc/journal
age-keygen -o /etc/journal/backup-identity.txt          # закрытый ключ
age-keygen -y /etc/journal/backup-identity.txt > /etc/journal/backup-recipients.txt
chmod 600 /etc/journal/backup-identity.txt
rclone config                                            # создайте удалённое хранилище, например «offsite»
cp infra/backup/backup.env.example /etc/journal/backup.env && chmod 600 /etc/journal/backup.env
nano /etc/journal/backup.env                             # RCLONE_REMOTE=offsite:имя-бакета
systemctl start journal-backup && journalctl -u journal-backup -n 20
```

**Скопируйте `/etc/journal/backup-identity.txt` в надёжное место вне сервера** (менеджер паролей, зашифрованная флешка). Без этого ключа бэкапы не расшифровать. На сервере он нужен только для ежемесячной проверки восстановления.

### Восстановление после аварии

На новом сервере выполните шаги 1–2. Затем, до первого входа пользователей:

```sh
rclone copyto offsite:journal-backups/journal-<дата>.dump.age /tmp/backup.dump.age
age --decrypt --identity backup-identity.txt --output /tmp/backup.dump /tmp/backup.dump.age
C="docker compose -f infra/docker-compose.prod.yml --env-file .env.prod"
$C stop api web
$C exec -T db sh -c 'pg_restore --username "$DB_OWNER_USER" --dbname "$DB_NAME" --clean --if-exists --no-owner' < /tmp/backup.dump
$C run --rm migrate        # права роли приложения и проверка
$C up -d
```

Ключи `DJANGO_SECRET_KEY` и `TOTP_ENCRYPTION_KEYS` берите из старого `.env.prod` (храните его копию вместе с ключом age). Если `TOTP_ENCRYPTION_KEYS` другой, 2FA администраторов придётся сбрасывать. Если другой `DJANGO_SECRET_KEY`, перестанут работать все ссылки на календарь (их перевыпускают в профиле) и все входы.

## 5. Обновление

```sh
cd /opt/journal && git pull
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build
```

Миграции применяются сами. Перед обновлением с миграциями сделайте внеплановый бэкап: `systemctl start journal-backup`. Откат — `git checkout <предыдущий тег>` и тот же `up -d --build`, но только если в обновлении не было миграций; иначе — восстановление из бэкапа.

## 6. Проверки перед запуском

- [ ] `https://<домен>` открывается, `http://` перенаправляет на HTTPS.
- [ ] https://observatory.mozilla.org — оценка A+ (CSP, HSTS, заголовки ставит Caddy).
- [ ] https://www.ssllabs.com/ssltest/ — A или A+.
- [ ] `ssh root@<сервер>` и вход по паролю отклоняются.
- [ ] `ufw status` — только 22, 80, 443.
- [ ] `systemctl list-timers 'journal-*'` — три таймера; в «Настройках» есть успешный бэкап.
- [ ] Проверка восстановления запущена вручную хотя бы раз: `systemctl start journal-restore-check`.
- [ ] Копия `backup-identity.txt` и `.env.prod` хранится вне сервера.
- [ ] Android-приложение собрано с `VITE_API_URL=https://<домен>` ([mobile/README.md](../mobile/README.md)).
- [ ] ZAP baseline по тестовому стенду без предупреждений уровня FAIL (задача `prod-stack` в CI, отчёт — артефакт `zap-report`).

## 7. Журналы и мониторинг

- Журналы всех контейнеров — JSON в stdout, Docker ротирует их (5 файлов по 10 МБ): `docker compose … logs api --since 1h`.
  - Пароли, токены, cookie и телефоны в журналы не попадают: Caddy скрывает `Cookie` и `Authorization`, gunicorn пишет путь без строки запроса.
- Обзор администратора в журнале показывает:
  - блокировки входа;
  - всплески отказов в доступе (перебор чужих записей);
  - входы администраторов с новых устройств;
  - последние события аудита.
- Простая внешняя проверка доступности: любой сервис мониторинга, опрашивающий `https://<домен>/api/v1/health`.
