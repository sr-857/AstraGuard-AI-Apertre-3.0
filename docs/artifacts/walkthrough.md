# Walkthrough - Dashboard Enhancements

## 1. Keyboard Shortcut Manager
Implemented a global keyboard shortcut manager to enhance navigation and control efficiency.

### Features
- **Command Palette (`Cmd+K` / `Ctrl+K`)**: Modal to search and execute commands.
- **Quick Navigation (`1-4`)**: Switch tabs (Mission, Systems, Chaos, Uplink).
- **Uplink Focus (`/`)**: Switches to Uplink tab and auto-focuses input.
- **Replay Control (`Space`)**: Toggles Play/Pause in Replay Mode.

### Verification
- Tested shortcuts on various screens.
- Confirmed terminal focus behavior works reliably.

## 2. Voice Command Integration ("Astra Voice")
Implemented a Web Speech API-based voice assistant for the Uplink Terminal.

### Features
- **Speech-to-Text**: Toggle listening with the microphone button.
- **Voice Commands**:
    - "Status", "Scan", "Help", "Clear".
- **Text-to-Speech**: Auditory feedback for actions.

### Verification
- **Manual Test**:
    - Click microphone.
    - Speak "Status".
    - Confirm terminal executes command and AI speaks response.

## 3. Battle Mode (Red Alert View)
Implemented a high-contrast "Battle Mode" for critical situations.

### Features
- **Auto-Trigger**: Activates automatically when a **Critical** anomaly is detected.
- **Red Alert Overlay**: Visual warning with pulsing vignette and scan lines.
- **Focused Layout**: Hides standard navigation. Maximizes the Command Terminal and Anomaly Investigator.
- **Manual Toggle**: "🛡️ BATTLE" button in header for testing/override.

### Verification
- **Test**: Click "Shield/Battle" icon in header.
- **Result**: View switches to red high-contrast mode with large terminal.
- **Exit**: Click "⚠️ BATTLE" to return to normal.
