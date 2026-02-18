# nt13u_txm — Architecture Overview
Last updated: 2026-02-18

---

## 1. Design Philosophy

This project is a migration from a monolithic C# GUI-based measurement system to a modular Python-based measurement environment.

Key goals:
- Separate **LIVE preview** from **measurement logic**
- Allow flexible, **script-driven** measurement workflows
- Keep camera control (RemoteEx) **reusable and isolated**
- Avoid tight coupling between GUI and measurement sequences
- Enable long-term evolution of measurement logic

Operational rule:
- All measurements start by launching `maincontrol`. `maincontrol` is the always-on main application.

---

## 2. High-Level Architecture

```
maincontrol (GUI, owns camera session)
├── LiveWorker (thread)
│   └── RemoteExClient
│       └── data/tmp + latest.json
├── Measurement (script or GUI-launched routine)
│   └── RemoteExClient
└── viewlatest (separate process, visualization only)
```

---

## 3. Module Responsibilities

### remoteexclient

Responsible for:
- TCP communication with HiPic RemoteEx
- Camera acquisition control
- `app_start()` / `app_end()`
- Save/Delete image
- Blocking acquisition (`acq_and_wait`)

Design rule:
- `__init__` does **NOT** call `app_start()`
- Camera connection is controlled explicitly via `app_start()`

### maincontrol

Purpose:
- LIVE ON/OFF GUI
- Exposure modification
- Entry point for measurements

Confirmed rules:
- On startup, always call `app_start()`
- LIVE runs in a worker thread
- Cannot close while LIVE or measurement is active
- On shutdown, call `app_end()`

### viewlatest

Purpose:
- Poll `data/tmp/latest.json`
- Display most recent image

Must never:
- Communicate with RemoteEx directly
- Block measurement logic

---

## 4. Device Locking Strategy

Lock file: `logs/remoteex.lock`

Policy:
- If lock exists → raise error (`DeviceBusyError`)
- GUI or script handles the error and informs the user

---

## 5. LIVE vs Measurement

LIVE:
- Loop in worker thread
- Apply exposure if changed
- Acquire
- Save rotating tmp file (mod 10)
- Delete on device
- Update `latest.json`

Measurement:
1. External script (CLI/Jupyter)
2. Standard routine launched from `maincontrol` GUI

No concurrent LIVE + measurement.

---

## 6. RemoteEx Lifecycle

Observed behavior:
- `app_start()` connects to camera
- Closing TCP does **NOT** disconnect camera
- Reconnecting TCP works without re-calling `app_start()`
- `app_end()` releases camera

Design decision:
- `maincontrol` calls `app_start()` on launch
- `maincontrol` calls `app_end()` on exit

---

## 7. Data Flow

Temporary images:
- `data/tmp/NT13U_TXM_tmp_000.img` … `_009.img` (rotating)

Viewer trigger file:
- `data/tmp/latest.json`

JSON format:
```json
{ "path": "...", "idx": 0, "timestamp": "...", "mode": "SingleAcquisition" }
```

---

## 8. External / Shared Code Policy (BL_Parameters, Package_libBL13U)

The following directories are treated as **externally-maintained shared code**:

- `src/nt13u_txm/BL_Parameters/`
- `src/nt13u_txm/Package_libBL13U/`

Current policy (single-maintainer, keep things stable):
- **Do not modify these directories locally**, even if there are obvious refactors or fixes to make.
- These directories may be updated externally in the future; local edits would create **merge/conflict risk** and make upstream updates painful.
- Folder names, file sets, and internal structure may change over time. Therefore:
  - Avoid writing new project code that depends on their internal layout beyond a small, well-defined surface.

If future changes are unavoidable:
- Prefer adding a thin **adapter/wrapper** layer in `nt13u_txm` (e.g., `nt13u_txm/adapters/`) rather than editing the shared code directly.
- Keep the adapter API stable so upstream updates can be absorbed by changing only the adapter.

---

## 9. Future Direction

Planned:
- Rewrite DCM driver
- Rewrite Stage driver
- Rewrite Counter driver
- Abstract device interfaces

Long-term:
- Measurement Script → Device Abstractions → Hardware Drivers
