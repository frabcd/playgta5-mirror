PlayGTA5 - Click to Play
========================

Extract the entire ZIP first.

WINDOWS x64:
Double-click Play.cmd (or PlayGTA5.exe).

MAC, APPLE SILICON:
Double-click Play.command. This is a development-signed executable, not an Apple-notarized application. If macOS blocks it, review the source and use the normal per-application security approval. Do not disable system-wide security.

FIRST LAUNCH:
The launcher downloads every archive of the published browser snapshot, verifies archive/file SHA-256 hashes, extracts only the mirror files, then opens a local game menu. No Python installation, Node, Rust or Java is required. A current Chrome/Edge browser is required separately.

Download: approximately 21.2 GB.
Installed mirror: 21,158,604,965 bytes, 12,482 files.
Free space: allow at least 25 GB; 35 GB provides room for runtime caches.
Default game folder: PlayGTA5-Local inside your home folder. This folder is separate from the extracted application ZIP.
Interrupted installation: run the same file again; downloads resume. Existing differing asset files are never overwritten. Keep the launch window open during offline play.

AVAILABLE MODES:
Continue story, new story, Los Santos sandbox and the existing experimental env_test development level. env_test is not the complete GTA VI game. No newer compatible full-game asset pack was verified. This installer retrieves the complete published browser snapshot, not the full retail versions of GTA V or GTA VI.

MULTIPLAYER:
Use Play-Multiplayer.cmd or Play-Multiplayer.command. It installs/verifies the same shared asset copy and opens the included native multiplayer launcher. If asked for resources, select the path printed in the window:
YOUR-HOME/PlayGTA5-Local/mirror/playgta5.com
Select a public line or the same custom WSS server as your friends. A private always-on server has not been deployed. Multiplayer remains experimental and supports up to eight players per upstream session. The env_test shortcut is offline; cross-map multiplayer is not implemented.

VERIFY:
Use Verify-Game.cmd / Verify-Game.command for a complete hash verification. On normal launches the install receipts and file sizes provide a faster check. A same-size local modification is detected by the explicit full verification.

OPTIONS:
PlayGTA5 --install-root "/absolute/path/to/installation"
PlayGTA5 --install-only
PlayGTA5 --verify
PlayGTA5 --no-open --port 8001
A different hostname/port changes the browser save origin. Default localhost:8000 preserves the existing launcher's save origin.

ISOLATION AND VALIDATION:
Builds and automated tests run in disposable GitHub-hosted VMs. No game assets or build tools are installed on the user's computer by the build. Game data is downloaded to that computer only when the user runs Play.
Automated tests cover resumable download, checksums, existing-file preservation, unsafe archive paths, installer locking, local isolation headers and Range serving. A separate Linux VM installs/verifies all 14 actual archives and starts the local game host. Rendering, missions, every map and physical controller behavior require real hardware testing and are not certified here.

ATTRIBUTION:
Mirror and release provider: https://github.com/alihammoud21/playgta5
User mirror: https://github.com/frabcd/playgta5-mirror
Multiplayer launcher: https://github.com/AliYa-chen/gtav-web-multiplayer-launcher
Upstream project website: https://gtav.2t.hk/
Preserve notices/ and multiplayer legal notices. The Python runtime and PyInstaller license notices accompany the executable.
Game content remains separately owned; this ZIP includes installer/launcher software and does not repackage the proprietary game files.
