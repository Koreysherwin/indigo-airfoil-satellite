# Changelog

## 0.1.7
- Removed artwork availability queries from normal polling to reduce the risk of AppleScript timeouts.
- Retained manual Refresh / Save Artwork action and saved artwork states.
- Preserved the UTF-8 output handling from 0.1.6.

## 0.1.6
- Explicitly decode AppleScript output as UTF-8, with safe replacement for invalid bytes to prevent polling errors involving non-ASCII metadata.

## 0.1.5
- Restored Indigo-compatible `UiDisplayStateId` XML declaration for `displayState`, fixing the device list State column.

## 0.1.4
- Added update-on-change behavior and optional per-poll duration updates.
- Added metadata debounce, streaming start/stop timestamps and counters, and last metadata update state.

## 0.1.3
- Revised the device list State column/display-state declaration.

## 0.1.2
- Added now-playing, connection/streaming durations, artwork states and save action, substring match states, optional Indigo variables and device state images.

## 0.1.1
- Rebuilt the bundle using an Indigo 2025-compatible structure and Python 3 polling/actions.

## 0.1.0
- Initial Airfoil Satellite monitor with connection and metadata reporting, inferred streaming state, refresh, transport, launch and quit actions.
