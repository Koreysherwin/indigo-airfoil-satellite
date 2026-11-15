# Airfoil Satellite Control for Indigo

A local macOS integration for Rogue Amoeba [Airfoil Satellite](https://rogueamoeba.com/airfoil/satellite/) and Indigo home automation. Monitor the connected sender and now-playing information, trigger automations, and send transport commands through Airfoil Satellite's AppleScript dictionary.

**Current bundle version:** 0.1.7  
**Developer:** Korey Sherwin / SherwinSound  
**Plugin identifier:** `com.sherwinsound.airfoilsatellite`

## Requirements

- Indigo 2025.1 or later (Server API 3.0, Python 3 runtime).
- Airfoil Satellite for macOS installed on the Indigo server Mac, normally in /Applications.
- A running macOS user session that permits Apple Events from the Indigo plugin process to Airfoil Satellite. Grant macOS Automation permission when prompted, if required.
- A compatible Airfoil sender for testing.

The plugin uses local AppleScript; it does not require an API token or cloud account.

## Installation

1. Download the plugin ZIP from [Releases](https://github.com/Koreysherwin/indigo-airfoil-satellite/releases) when available, or obtain the plugin bundle from the repository.
2. Extract the ZIP and double-click `AirfoilSatellite.indigoPlugin`.
3. Install the plugin in Indigo and restart the server if prompted.
4. In Indigo, create a new device with type **Plugin**, plugin **Airfoil Satellite**, and model **Airfoil Satellite Monitor**.
5. Launch Airfoil Satellite and connect to it from a sender. Check the Indigo Event Log and device state changes.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| Poll Interval | 5 seconds | Select 1, 2, 5, 10 or 30 seconds. In 0.1.7 the polling loop is capped at a 5-second sleep by its implementation. |
| Only Update Indigo on Change | On | Suppress unnecessary duration-state updates. |
| Update Durations Every Poll | Off | Enable to refresh duration counters during each poll. |
| Metadata Debounce | 2 seconds | Wait for stable metadata before reporting changes. |
| Use Indigo State Images | On | Reflect connection and inferred streaming status in the device icon. |
| Save Artwork TIFF File | Off | Legacy setting in 0.1.7; use the manual Refresh / Save Artwork action instead. |
| Artist/Album/Track/Now Playing Contains Match | Blank | Optional case-insensitive substring matching. |
| Update Indigo Variables | Off | Optionally populate variables for automations. |
| Variable Prefix | AirfoilSatellite | Prefix for generated variables. |

Plugin preferences also provide Normal or Debug logging.

## Device states and triggers

| State | Meaning |
| --- | --- |
| `connected` | Airfoil Satellite reports a connected remote sender. |
| `streaming` | Inferred from connection and nonempty artist, album or track metadata. |
| `artist`, `album`, `trackTitle`, `nowPlaying` | Now-playing information provided by the sender. |
| `displayState` | Device list State column value. |
| `connectedSince`, `streamingSince` | Observed connection and inferred streaming start times. |
| `connectionDuration`, `streamingDuration` | Formatted durations. |
| `connectionDurationSeconds`, `streamingDurationSeconds` | Numeric duration values. |
| `lastConnectedStarted`, `lastConnectedStopped` | Observed connection start and stop timestamps. |
| `lastStreamingStarted`, `lastStreamingStopped` | Observed streaming start and stop timestamps. |
| `lastConnectedChange`, `lastStreamingChange` | Last observed state transition timestamps. |
| `streamingStartCounter`, `streamingStopCounter` | Counters for normal polling-based transitions. |
| `lastMetadataChange`, `lastMetadataUpdate`, `metadataChangeCounter` | Metadata tracking. |
| `artistMatch`, `albumMatch`, `trackMatch`, `nowPlayingMatch` | Configured text-match results. |
| `artworkAvailable`, `artworkPath` | Last manually retrieved artwork status and path; not live availability. |
| `lastError` | Latest polling error, cleared on successful poll. |

**Important:** Airfoil Satellite's AppleScript connection flag is not an audio-level or playback-status sensor. The streaming state is a metadata-based heuristic and can remain true while a sender is paused, or false when audio has no metadata. Test the appropriate trigger with your sender before using it for speaker power control. For connection-based automation use the connected state. Use streaming transitions or counters for metadata-based automation as appropriate.

## Actions

- Refresh Status
- Refresh / Save Artwork
- Play/Pause
- Next Track
- Previous Track
- Launch Airfoil Satellite
- Quit Airfoil Satellite

Transport commands depend on the capabilities of the connected sender. Artwork is retrieved only on demand in 0.1.7, avoiding a potentially blocking AppleScript artwork query during normal polling. Saved TIFF files are located beneath the Indigo installation's Preferences/Plugins/AirfoilSatellite/Artwork directory. The saved path may refer to previous artwork; it is not automatically cleared when tracks change.

## Example automation

Create an Indigo device-state trigger on the Airfoil Satellite Monitor's connected state changing to true to enable a listening zone, or use streamingStartCounter changing for an inferred playback-start event. Use a corresponding disconnect or streaming-stop trigger when appropriate. Validate these states with your own source before enabling power or source-switching automation.

[Music Manager](https://github.com/Koreysherwin/indigo-music-manager) 1.2.5 and later includes Airfoil Satellite integration for unified music automation.

## Troubleshooting

- Check the Indigo Event Log for AppleScript errors and enable Debug logging if required.
- Confirm the app is installed, available in the Indigo host's user session and has macOS Automation permissions.
- Test the app's dictionary with Script Editor: `tell application "Airfoil Satellite" to get is connected`.
- The normal snapshot uses an 8-second AppleScript timeout; manual artwork saving has a 10-second timeout. AppleScript can still time out if the app or sender is unresponsive.
- Unicode track metadata is explicitly decoded as UTF-8 with replacement for invalid byte sequences.

See [CHANGELOG.md](CHANGELOG.md) for development history. Report issues via [GitHub Issues](https://github.com/Koreysherwin/indigo-airfoil-satellite/issues).
