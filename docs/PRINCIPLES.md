# PRINCIPLES

This document defines system assumptions and invariants.
These rules must remain valid across future changes.

---

# 1. Assumptions

## A-DEVICE-001
The measurement device may hang irrecoverably.
Recovery may require device or PC restart.

## A-DEVICE-002
Only one client may control the device at a time.

## A-STARTUP-001
`app_start()` is executed once at application startup.

## A-STOP-001
STOP means graceful stop:
The current acquisition is allowed to finish.
Forced interruption is not required.

## A-STOP-002
`RemoteExClient.stop()` exists but is not part of normal stop flow.

---

# 2. Invariants

## I-LOCK-001
If `connect()` is called, `disconnect()` must be executed in all exit paths.

## I-UI-001
The UI thread must not perform long blocking device I/O.

## I-STOP-001
After STOP request, no new acquisition may start.

## I-LIFECYCLE-001
The component that sends `AcqStart()` is responsible for sending `AcqEnd()`.

## I-STATE-001
LIVE and measurement operations must not run concurrently.

## I-DATA-001
`latest.json` must remain readable even if acquisition fails.

---

# 3. Design Boundaries

- Software is not required to recover from hardware-level hangs.
- Forced acquisition stop is optional, not mandatory.
- Operational recovery (restart) is acceptable for unrecoverable failures.

---

Any architectural change must be checked against these principles.
Verification results against this document are logged in `codex_reports/`.