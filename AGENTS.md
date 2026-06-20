# AGENTS.md

Short tour. The full module-by-module reference is in the code; this is just a map.

## What it is

Small Python service. Reads Forza Horizon's UDP telemetry (5300) and drives
**DualSense adaptive triggers** over raw HID, while leaving rumble bytes alone
so Steam Input still handles rumble.

## Stack

- Python `>=3.13`, `uv` for deps.
- Deps: `hidapi`, `textual`, `psutil`.
- Distributed as a `uv tool install` package (an `fhds` command on PATH).
- Windows + Linux. No tests.

## Layout

```
pyproject.toml               # version, deps, build/packaging config (repo root)
src/fhds/                    # the importable package
  main.py                    # entry: args, GUI/TUI/headless boot
  lang/                      # i18n: one module per language (en/tr/zh/ja), auto-discovered
  modules/
    settings.py              # @dataclass Settings - ALL tunables live here
    preferences.py           # JSON persistence (globals + active profile)
    profiles.py              # named profile CRUD
    loop.py                  # per-packet driver
    forzahorizon/
      udp_listener.py        # UDP socket + 324-byte FH packet parser
      effects.py             # Forza-aware Controller + TriggerAnimations
    dualsense/
      main.py                # HID writer (USB+BT), persistent mode
      adaptive_trigger.py  # generic effect primitives
      hidhide.py             # filesystem-only HidHide detection
    tui/                     # Textual app (controls/profiles/settings/system/lang/logs)
    emulation/               # optional fake telemetry for offline dev
    exit_detection/          # watches game proc, closes when it exits
.github/workflows/release.yml    # CI: build wheel + sdist, publish release
```

## Data flow (one frame)

```
FH UDP 5300 -> parse_packet -> TriggerAnimation.update -> (left, right)
                                                              |
                              DualSense.set (state-change only)
                                                              v
                                                  HID write (trigger bytes only,
                                                   rumble bytes untouched)
```

Trigger command = `(mode, p1, p2)`:
- `M_OFF (0x05)` free, `M_RIGID (0x01)` constant force, `M_PULSE (0x06)` vibration.

## Run

### Dev
```powershell
uv sync
uv run python -m fhds.main
```

### Install as a tool
```powershell
uv tool install .
fhds
```

Version is the single source of truth in `src/fhds/__init__.py` (`__version__`);
`pyproject.toml` reads it dynamically.

### In-game (once)
Forza Horizon -> **Settings -> HUD and Gameplay -> Data Out: ON**, IP `127.0.0.1`,
Port `5300`.

## CI gating

`.github/workflows/release.yml`:
- Push to `dev` with `prerelease` in commit msg -> prerelease tagged at the next patch above the latest stable release (e.g. latest `v1.4.5` -> `v1.4.6`).
- Push to `main` with `release vX.Y.Z` in commit msg -> stable `vX.Y.Z`.
- Push tag `v*.*.*` -> stable release.
- `workflow_dispatch` -> prerelease at the next patch (same rule as above).

## Conventions

- **KISS.** Don't abstract for one caller.
- All tunables go in `settings.py`, never inside module logic.
- **Globals stay global.** Add to `preferences.GLOBAL_FIELDS`; never copy into per-profile dicts.
- **Don't touch rumble bits.** HID writer only flips trigger bits in `valid_flag0`.
- **Always drain UDP** via `recv_latest()`; never react to stale packets.
- **State-change writes only.** The loop diffs `(left, right)` against `prev` and only calls `ds.set(...)` on change.
- No em dash (`-`) anywhere - in code, docs, or chat. Plain hyphens only.
- UTF-8 source files.

## HidHide

I do NOT call `HidHideCLI.exe`. `hidhide.is_detected()` is a pure filesystem
probe. When detected, the I/O loop latches into **persistent mode** on the
first successful connect: keeps the HID handle open, ignores read/write
errors, skips the watchdog, ignores the `enable_reconnect` setting. This way
HidHide cloaking the device mid-session doesn't tear our handle down.

## Common edits

| Want to... | Open this |
|---|---|
| Change a tunable / disable an effect | `src/fhds/modules/settings.py` |
| Change how an effect feels | `src/fhds/modules/dualsense/adaptive_trigger.py` (primitive) or `src/fhds/modules/forzahorizon/effects.py` (game logic) |
| Touch raw HID bytes | `src/fhds/modules/dualsense/main.py` |
| Add a telemetry field | `src/fhds/modules/forzahorizon/udp_listener.py` |
| Change CLI / startup wiring | `src/fhds/main.py` |
| Change persistence layout | `src/fhds/modules/preferences.py` |
| Edit the TUI | `src/fhds/modules/tui/` |
| Add/translate a UI language | `src/fhds/lang/` (drop a `<code>.py` with `NAME` + `STRINGS`) |
| Change CI gating | `.github/workflows/release.yml` |
