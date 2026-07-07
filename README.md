# steam-dl

Установка игр через **SteamTools/PortProton** и запуск их в **нативном Steam
Game Mode** на Linux-портативках (Bazzite/SteamOS) — одной командой или через
GUI. Инструмент сам качает игру, переносит её, обходит DRM (Goldberg) и
добавляет ярлык с Proton в игровой режим.

Ядро без сторонних зависимостей — работает на голом образе портативки.

> Первичная настройка чистой портативки — в [INSTALL.md](INSTALL.md).

## Установка

```bash
git clone https://github.com/canaldkz/steam-dl.git ~/steam-dl
pipx install ~/steam-dl        # даст команду steam-dl
```

## Как пользоваться

### GUI (проще всего)

```bash
steam-dl gui                 # откроется в браузере
steam-dl gui --host 0.0.0.0  # управление с телефона в той же сети
```

Тач-интерфейс: статус системы, поиск игр, загрузка бандла (`.zip`/`.lua`),
галочка «сухой прогон», лог установки.

### Терминал

```bash
# найти AppID по названию
steam-dl search "half-life 2"

# проверить, что система готова
steam-dl env

# установить из готового бандла (папка или .zip с lua + манифестами)
steam-dl install --bundle ~/mygame.zip --goldberg-dir ~/Goldberg

# «сухой прогон» — показать действия, ничего не меняя
steam-dl install --bundle ~/mygame.zip --dry-run -v
```

Игру можно задать тремя способами: `--bundle` (готовые файлы, проще всего),
`--spec game.yaml` (см. `examples/`), либо `AppID --depot ID:КЛЮЧ:MANIFEST`.

После установки переключись в **Game Mode** — игра уже в библиотеке.

## Как это работает

Конвейер из пяти шагов, каждый проверяет свой результат перед следующим:

1. **Манифесты** — кладёт `app_<AppID>.lua` и `.manifest` в префикс SteamTools.
2. **Загрузка** — запускает Windows-Steam через PortProton (`steam://install`).
3. **Ожидание** — следит за `appmanifest_<AppID>.acf`, пока игра не скачается.
4. **Перенос + DRM** — переносит игру в `~/Games`, подменяет `steam_api*.dll`
   на Goldberg и кладёт `steam_appid.txt`.
5. **Интеграция** — добавляет ярлык в `shortcuts.vdf` и назначает Proton в
   `config.vdf`, чтобы игра запускалась в Game Mode.

Есть и путь **без Wine**: если известны ключи депотов, бэкенд
`--backend depotdownloader` качает игру напрямую с CDN Steam, минуя
PortProton и SteamTools.

## Что нужно принести самому

Инструмент **не добывает** ключи и манифесты игр — это данные Steam из твоего
SteamTools-набора. Ты передаёшь их бандлом (`--bundle`) или в спеке; всё
остальное автоматизировано. Патч Goldberg работает для лёгкой защиты Steam и
не обходит Denuvo/CEG.
