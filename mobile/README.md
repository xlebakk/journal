# Android-приложение (Capacitor)

Тот же фронтенд, что и сайт, внутри APK. Приложение грузит свои файлы из себя (не удалённый адрес) и ходит к API сервера по HTTPS с токенами. Access-токен на 10 минут живёт только в памяти, refresh-токен на 30 дней — в Android Keystore.

## Что нужно

- Node.js 22+;
- JDK 21 или новее в `JAVA_HOME` (Capacitor 8);
- Android SDK (`ANDROID_HOME`), платформа 36 и build-tools.

```sh
cd frontend && npm ci && cd ../mobile && npm ci
```

## Отладочная сборка

```sh
npm run apk:debug
```

APK появится в `android/app/build/outputs/apk/debug/app-debug.apk`. По умолчанию он ходит к `http://10.0.2.2:8000`: так эмулятор видит компьютер. Адрес можно поменять через `VITE_API_URL`.

Обычный http и отладка WebView разрешены только в debug-сборке (`src/debug/res/xml/network_security_config.xml`, `JOURNAL_DEV_SERVER=1`). Серверу разработки нужен `APP_ORIGINS`, включающий `https://localhost` (это значение по умолчанию).

## Подписанная сборка для раздачи

```sh
VITE_API_URL=https://journal.example.com \
JOURNAL_SIGNING=D:/Android/keys/journal-signing.properties \
npm run apk:release
```

Результат: `android/app/build/outputs/apk/release/app-release.apk`.

В release-сборке:
- только HTTPS к системным центрам сертификации;
- `android:allowBackup="false"` и правила, исключающие данные из облачного бэкапа и переноса;
- приложение не отлаживаемое, отладка WebView выключена.

### Ключ подписи

Ключ и пароль лежат **вне репозитория**:

- `D:\Android\keys\journal-release.jks` — ключ (RSA 4096, срок 30 лет);
- `D:\Android\keys\journal-signing.properties` — путь к ключу, алиас и пароли.

Сохраните копию обоих файлов в надёжном месте, например в менеджере паролей или на зашифрованном носителе. Без этого ключа обновить уже установленное приложение нельзя: Android примет только APK с той же подписью.

Отпечаток сертификата (SHA-256) смотрится командой `keytool -list -keystore journal-release.jks`.

## Раздача

Сначала APK раздаётся напрямую: файл по ссылке, на телефоне — «разрешить установку из этого источника». Потом — Google Play. Для новых личных аккаунтов Play требует закрытое тестирование перед публикацией и верификацию разработчика; требования меняются, проверьте их перед публикацией. `appId` (`uz.journal.center` в `capacitor.config.ts`) нужно окончательно выбрать до первой публикации.

## Иконки

```sh
npm run icons
```

Скрипт рисует PNG для PWA и Android: страница тетради, красное поле, «Ж». Результат нужно закоммитить.

## Как устроено

- `frontend/src/platform/` — единственное место, которое знает, где работает код:
  - `isNativeApp` — сайт или приложение;
  - `apiRoot()` — адрес API;
  - `tokens` — refresh в Keystore, одно обновление на все параллельные 401;
  - `onBackButton` — системная «Назад»: закрыть диалог → назад по истории → выйти.
- Печать и выгрузка файлов в WebView не работают, поэтому в приложении вместо кнопок — подсказка «в веб-версии».
- Плагины стоят и во `frontend` (JS-часть), и в `mobile` (нативная часть). Версии одинаковые, это проверяет `npm run check:versions`.
