# Tapo DL-Series Home Assistant Integration

Custom Home Assistant integration for TP-Link Tapo DL-series locks.

## Features

- Adds supported DL-series locks as Home Assistant `lock` entities
- Adds a battery `sensor` entity for battery percentage
- Supports lock and unlock actions
- Polls lock status and battery information
- Config flow setup from Home Assistant UI

## Installation (HACS Custom Repository)

1. Push this repository to GitHub.
2. Create a release tag (for example `v0.1.0`).
3. In Home Assistant, open HACS.
4. Go to **HACS -> Menu -> Custom repositories**.
5. Add your repository URL and choose **Integration** as category.
6. Install **Tapo DL-Series** from HACS.
7. Restart Home Assistant.

## Manual Installation

1. Copy `custom_components/tapo_dl100` to your Home Assistant config directory under `custom_components`.
2. Restart Home Assistant.
3. Go to **Settings -> Devices & Services -> Add Integration**.
4. Search for **Tapo DL100** (integration domain is `tapo_dl100` for compatibility).
5. Enter:
   - lock name
   - lock local IP
   - TP-Link cloud username
   - TP-Link cloud password

## Notes

- If your TP-Link account has multiple DL-series locks, the integration `name` must match the lock alias in the Tapo app exactly.
- `lock_status` mapping:
  - `0` = locked
  - `1` = unlocked

## Entities and states

- One device per lock (TP-Link, model, firmware, hardware version, MAC, cloud device id as serial), holding:
  - the lock entity, named after the device
  - a battery sensor (diagnostic)
- The lock shows **jammed** when the lock reports `lock_status` 3 (jammed while unlocking) or 4 (jammed while locking).
- After Home Assistant unlocks the door, it checks the lock every 5 s for up to 60 s, so the lock's auto-relock shows up in seconds instead of at the next poll. Unlocks from the keypad, key or Tapo app are still only seen at the normal poll interval.

Not available: who unlocked it (keypad user, key, app), the lock's event history, keypad codes and lock settings. The integration only reads lock state and battery.

## Testing

Three levels, from no hardware to the real thing. All read credentials from a `.env` in the repo or its parent folder:

```
TAPO_USERNAME=you@example.com
TAPO_PASSWORD=...
TAPO_LOCK_IP=192.168.1.50
TAPO_LOCK_NAME=Front Door   # optional, must match the Tapo app name if the account has several locks
```

1. **Offline**, no lock or cloud needed: `scripts/test.sh`. Runs the status mapping, the relock watch, and `api.py` against an in-memory fake lock that checks every handshake step, plus the jam cases and the TLS rule (login verified, only control-key unverified).
2. **Real lock, no Home Assistant**: `scripts/live.sh info | lock | unlock | watch`. `unlock` unlocks the door and then runs the same relock watch Home Assistant uses, printing each poll.
3. **Real lock in a throwaway Home Assistant**: `dev/up.sh` starts HA in Docker on http://localhost:8123 (user `dev`, password `devdevdev`) with this integration mounted and the lock already added. `dev/down.sh` removes it. Code changes need a container restart (`docker restart tapo-dl100-dev-ha`).

Needs `uv` and Docker. The jammed state cannot be produced on a real lock on demand, so it is covered by level 1 only.

## Credits

- This integration is based on reverse-engineering and protocol work from Ted Holtz's Homebridge project: [tedholtz/homebridge-tapo-dl100](https://github.com/tedholtz/homebridge-tapo-dl100).