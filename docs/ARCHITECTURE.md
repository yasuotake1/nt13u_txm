# ARCHITECTURE

This document describes the structural design of `nt13u_txm`.

It focuses on:
- Module responsibilities
- Runtime structure
- Threading model
- High-level data flow

Project-wide constraints and invariants are defined in `PRINCIPLES.md`.

---

## 1. Overall Structure

The project is organized into logical layers:

- `meas/`     : Measurement control and device communication
- `view/`     : Data visualization and live monitoring
- `common/`   : Shared utilities (paths, configuration, helpers)
- `docs/`     : Design documentation

This separation reflects functional responsibility, not physical isolation.

---

## 2. Entry Point

All measurement workflows start from `maincontrol`.

- The application is launched via `maincontrol.main()`.
- Measurement operations are initiated only from this entry point.
- No independent measurement process is assumed outside `maincontrol`.

---

## 3. Runtime Model

### 3.1 UI Layer

- Implemented using Qt.
- Responsible for:
  - User interaction
  - Status display
  - Starting/stopping LIVE
- Must not perform long-running device I/O.

### 3.2 Worker Layer

LIVE acquisition runs in a dedicated worker object.

Responsibilities:
- Device interaction via `RemoteExClient`
- Acquisition loop
- Saving images
- Updating `latest.json`
- Emitting signals to UI

Worker lifecycle:
- Created when LIVE starts
- Terminates when LIVE stops
- Always emits completion signals

---

## 4. Device Communication

`RemoteExClient` abstracts communication with the measurement device.

Responsibilities:
- Connection management
- Acquisition commands
- Status polling
- File save/delete commands

Design intent:
- Connection ownership is explicit.
- The caller controls acquisition start and end.
- `stop()` exists as a callable API but is not part of normal graceful stop flow.

---

## 5. Data Flow (LIVE)

1. UI toggles LIVE
2. Worker connects to device
3. Acquisition loop:
   - Acquire
   - Save
   - Delete
   - Update `latest.json`
4. UI reads `latest.json` (polling)
5. On STOP:
   - No new acquisition begins
   - Current acquisition completes
   - Worker disconnects

---

## 6. Shutdown Sequence

Application shutdown is controlled by `maincontrol`.

- `AcqEnd()` is sent by the component that initiated acquisition.
- Shutdown must leave the device in a clean state.
- No forced acquisition cancellation is assumed in normal flow.

---

## 7. Design Philosophy

- Single authoritative entry point
- Clear responsibility boundaries
- Explicit device lifecycle management
- Graceful stop preferred over forced interruption
- Failures that cannot be recovered in software are handled operationally

See `PRINCIPLES.md` for formal assumptions and invariants.
