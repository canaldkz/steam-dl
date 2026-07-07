HEAVILY VIBECODED, USE AT YOUR OWN RISK


# steam-dl

Installs Steam games via **SteamTools/PortProton** and registers them for the
**native Steam Game Mode** on Linux handhelds (Bazzite/SteamOS). Handles the
download, relocation, DRM bypass (Goldberg), and Proton shortcut setup in a
single command or through a GUI.

The core has no third-party dependencies and runs on a stock handheld image.

> First-time setup of a fresh handheld: see [INSTALL.md](INSTALL.md).

## Installation

```bash
git clone https://github.com/canaldkz/steam-dl.git ~/steam-dl
pipx install ~/steam-dl        # provides the steam-dl command
```

## Usage

### GUI

```bash
steam-dl gui                 # opens in the browser
steam-dl gui --host 0.0.0.0  # reachable from a phone on the same network
```

Touch-friendly interface: system status, game search, bundle upload
(`.zip`/`.lua`), a dry-run toggle, and streamed install logs.

### Command line

```bash
# resolve an AppID from a name
steam-dl search "half-life 2"

# check that the system is ready
steam-dl env

# install from a bundle (folder or .zip with lua + manifests)
steam-dl install --bundle ~/mygame.zip --goldberg-dir ~/Goldberg

# dry run: print the actions without changing anything
steam-dl install --bundle ~/mygame.zip --dry-run -v
```

A game can be specified three ways: `--bundle` (ready-made files, simplest),
`--spec game.yaml` (see `examples/`), or `AppID --depot ID:KEY:MANIFEST`.

After install, switch to **Game Mode** — the game is already in the library.

## How it works

A five-stage pipeline; each stage validates its result before the next runs:

1. **Manifests** — write `app_<AppID>.lua` and `.manifest` into the SteamTools
   prefix.
2. **Download** — launch Windows Steam through PortProton (`steam://install`).
3. **Watch** — poll `appmanifest_<AppID>.acf` until the download completes.
4. **Relocate + DRM** — move the game to `~/Games`, replace `steam_api*.dll`
   with Goldberg, and write `steam_appid.txt`.
5. **Integrate** — add a `shortcuts.vdf` entry and map Proton in `config.vdf`
   so the game launches in Game Mode.

A Wine-free path also exists: when depot keys are known, the
`--backend depotdownloader` backend pulls the game straight from the Steam CDN,
skipping PortProton and SteamTools.

## Out of scope

Depot keys and manifests are not obtained by the tool — they are Steam data
supplied by the user via a bundle (`--bundle`) or a spec. Everything else is
automated. The Goldberg patch covers lightweight Steam DRM and does not bypass
Denuvo/CEG.
