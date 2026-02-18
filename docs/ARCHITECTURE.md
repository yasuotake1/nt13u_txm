# nt13u_txm -- Architecture Overview

Last updated: 2026-02-18

------------------------------------------------------------------------

## 1. Design Philosophy

This project is a migration from a monolithic C# GUI-based measurement
system to a modular Python-based measurement environment.

Key goals:

-   Separate LIVE preview from measurement logic
-   Allow flexible, script-driven measurement workflows
-   Keep camera control (RemoteEx) reusable and isolated
-   Avoid tight coupling between GUI and measurement sequences
-   Enable long-term evolution of measurement logic

Operational rule:

-   All measurements start by launching `maincontrol`. `maincontrol` is
    the always-on main application.

------------------------------------------------------------------------

## 2. High-Level Architecture

maincontrol (GUI, owns camera session) ├── LiveWorker (thread) │ └──
RemoteExClient │ └── data/tmp + latest.json ├── Measurement (script or
GUI-launched routine) │ └── RemoteExClient └── viewlatest (separate
process, visualization only)

------------------------------------------------------------------------

## 3. Module Responsibilities

### remoteexclient

Responsible for:

-   TCP communication with HiPic RemoteEx
-   Camera acquisition control
-   app_start() / app_end()
-   Save/Delete image
-   Blocking acquisition (acq_and_wait)

Design rule:

-   **init** does NOT call AppStart
-   Camera connection controlled explicitly via app_start()

------------------------------------------------------------------------

### maincontrol

Purpose:

-   LIVE ON/OFF GUI
-   Exposure modification
-   Entry point for measurements

Confirmed rules:

-   On startup, always call app_start()
-   LIVE runs in worker thread
-   Cannot close while LIVE or measurement is active
-   On shutdown, call app_end()

------------------------------------------------------------------------

### viewlatest

Purpose:

-   Poll data/tmp/latest.json
-   Display most recent image

Must never:

-   Communicate with RemoteEx directly
-   Block measurement logic

------------------------------------------------------------------------

## 4. Device Locking Strategy

Lock file:

logs/remoteex.lock

Policy:

-   If lock exists → raise error (DeviceBusyError)
-   GUI or script handles error and informs user

------------------------------------------------------------------------

## 5. LIVE vs Measurement

LIVE:

-   Loop in worker thread
-   Apply exposure if changed
-   Acquire
-   Save rotating tmp file (mod 10)
-   Delete on device
-   Update latest.json

Measurement:

1.  External script (CLI/Jupyter)
2.  Standard routine launched from maincontrol GUI

No concurrent LIVE + measurement.

------------------------------------------------------------------------

## 6. RemoteEx Lifecycle

Observed behavior:

-   AppStart connects to camera
-   Closing TCP does NOT disconnect camera
-   Reconnecting TCP works without re-calling AppStart
-   AppEnd releases camera

Design decision:

-   maincontrol calls app_start() on launch
-   maincontrol calls app_end() on exit

------------------------------------------------------------------------

## 7. Data Flow

Temporary images:

data/tmp/ImagingXAFS_tmp_000.img ... \_009.img

Viewer trigger file:

data/tmp/latest.json

JSON format:

{ "path": "...", "idx": 0, "timestamp": "...", "mode":
"SingleAcquisition" }

------------------------------------------------------------------------

## 8. Future Direction

Planned:

-   Rewrite DCM driver
-   Rewrite Stage driver
-   Rewrite Counter driver
-   Abstract device interfaces

Long-term:

Measurement Script → Device Abstractions → Hardware Drivers
