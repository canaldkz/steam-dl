# Установка и запуск игр — шпаргалка

Практический порядок для чистой Bazzite-портативки в **Desktop Mode**.
Делится на разовую настройку (один раз) и установку игры (каждый раз, 2 команды).

---

## Разовая настройка (один раз, ~15 мин)

### 1. Терминал (Konsole) и базовые пакеты

На Bazzite `git` и `python3` уже есть. Ставим менеджер и клонируем инструмент:

```bash
python3 -m ensurepip --user 2>/dev/null; python3 -m pip install --user pipx
git clone https://github.com/canaldkz/steam-dl.git ~/steam-dl
pipx install ~/steam-dl        # даст команду steam-dl глобально
```

Если `pipx` недоступен — вариант через venv:

```bash
python3 -m venv ~/.venv-steamdl && ~/.venv-steamdl/bin/pip install ~/steam-dl
# тогда вместо steam-dl вызывай:  ~/.venv-steamdl/bin/steam-dl
```

### 2. PortProton

```bash
flatpak install -y flathub ru.linux_gaming.PortProton
```

Запусти PortProton один раз из меню — он создаст префикс. Имя префикса по
умолчанию у инструмента — `STEAM` (любое другое укажешь флагом `--prefix`).

### 3. SteamTools в этот префикс

Запусти инсталлятор SteamTools **внутри PortProton** (правый клик по `.exe` →
открыть в PortProton, либо через меню PortProton). Должна появиться папка:

```
~/.var/app/ru.linux_gaming.PortProton/data/PortProton/prefixes/STEAM/drive_c/Program Files (x86)/Steam/config/st/
```

### 4. Шаблоны Goldberg (обход DRM при запуске из нативного Steam)

Распакуй `steam_api.dll` и `steam_api64.dll` из сборки Goldberg emulator в
отдельную папку, например `~/Goldberg/`.

### 5. Один раз войди в нативный Steam

Запусти нативный Steam из меню и войди в аккаунт — так появится
`userdata/<id>`, без него Этап 5 (интеграция) не найдёт профиль.

### 6. Проверка

```bash
steam-dl env
```

Все `exists=` для префикса и SteamTools должны быть `True`, а `native steam
root` и `user id` — определены. Если что-то `False` / `None` — вернись к
соответствующему шагу.

---

## Установка игры (каждый раз)

### Самый простой путь — из готового бандла

Если у тебя есть набор файлов для игры (`app_<appid>.lua` + `.manifest`),
сложи их в папку или `.zip` и просто укажи его — appid, депоты и ключи
подхватятся из lua автоматически, спек писать не нужно:

```bash
steam-dl install --bundle ~/hl2.zip --goldberg-dir ~/Goldberg
```

`--bundle` принимает и папку, и `.zip`. Имя игры можно задать через `--name`,
исполняемый файл — через `--exe` (иначе найдётся крупнейший `.exe`).

### Путь через спек (когда нужен ручной контроль)

**A. Спек игры** (`hl2.yaml`) — appid и депоты с ключами берутся из твоего
SteamTools-набора для игры:

```yaml
appid: 220
name: Half-Life 2
executable: hl2.exe          # можно не указывать — найдётся крупнейший .exe
depots:
  - depot_id: 221
    key: "<hex-ключ-депота>"
    manifest_id: "<gid>"      # если известен
```

**B. Установка:**

```bash
# сухой прогон — посмотреть, что произойдёт:
steam-dl install --spec hl2.yaml --goldberg-dir ~/Goldberg --dry-run -v

# по-настоящему:
steam-dl install --spec hl2.yaml --goldberg-dir ~/Goldberg
```

Инструмент сам: впрыснет манифесты → запустит загрузку через PortProton →
дождётся завершения → перенесёт игру в `~/Games/` → пропатчит DRM → добавит
ярлык в нативный Steam с Proton.

**Запуск:** переключись в **Game Mode** — игра уже в библиотеке, жми Play.

Поиск appid по названию:

```bash
steam-dl search "half-life 2"
```

---

## Короче: путь без Wine

Если известны **ключи депотов**, PortProton/SteamTools для загрузки не нужны —
[DepotDownloader](https://github.com/SteamRE/DepotDownloader) качает напрямую:

```bash
steam-dl install --spec hl2.yaml --backend depotdownloader --goldberg-dir ~/Goldberg
```

Из разовой настройки тогда нужны только шаги 1, 4, 5, 6.

---

## Что нельзя автоматизировать за тебя

- **Инсталлятор SteamTools** — сторонний, ставится вручную (шаг 3).
- **Ключи и `.manifest` депотов** конкретной игры — это данные от Steam; они
  в твоём SteamTools-наборе. Инструмент их не генерирует, а использует.

Всё остальное автоматизировано.
