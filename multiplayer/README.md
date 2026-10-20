# PlayGTA5 multiplayer: isolated builds and remote server

This integration reuses the MIT-licensed [GTAV Web Multiplayer Launcher](https://github.com/AliYa-chen/gtav-web-multiplayer-launcher) by AliYa-chen, project website https://gtav.2t.hk/. Exact source and mirror engine identities are in upstream.lock.json. Upstream engine-version validation and read-only resource rules remain enabled.

## Build isolation and downloads

The Multiplayer workflow builds Windows x64 and macOS Apple Silicon clients in separate disposable GitHub-hosted VMs. A Linux VM compiles and exercises the Java server with eight independent protocol clients and builds its container. That Linux VM also downloads four verified mirror archives, extracts only required engine/character inputs, generates mandatory character collision data and builds the adapted runtime outside its resource directory.

Open this repository's Actions tab, choose "Multiplayer - isolated Windows, Mac and server builds", and download completed run artifacts:
- PlayGTA5-Multiplayer-Windows-x64: portable EXE package, notices, provenance, size and SHA-256.
- PlayGTA5-Multiplayer-macOS-arm64: development App ZIP, notices, provenance, size and SHA-256.
- PlayGTA5-Multiplayer-server: standalone Java 17 JAR, deployment files and protocol-check report.
The server artifact includes engine-validation.json with hashes and adapter checks; no game assets or derived geometry are uploaded.

Artifacts expire after seven days. Pushing integration changes or using Run workflow rebuilds them. Builds do not publish releases, contact production servers, install tools on the user's PC, or include game data. The workflow does not run upstream's deployment workflow.

A green build proves executable architecture, version, packaging and automated checks. It does not prove rendered Windows/Mac gameplay or complete synchronization. The app remains upstream's experimental launcher, not a new engine.

## Use on Windows and Mac

1. Finish the mirror's normal complete installation. It has 21,158,604,965 bytes of mirror data; the ordinary source ZIP alone is insufficient.
2. Extract your platform's multiplayer artifact. Run PlayGTA5-Multiplayer.exe on Windows or the GTA5Data Launcher App on an Apple Silicon Mac.
3. Select your existing mirror/playgta5.com resource folder. It contains b/8b0b5899ed and data/manifest.json. Do not choose the source repository root.
4. Use a recent Chrome or Edge with WebGPU, memory64 and shared-memory support. The launcher prepares its own runtime cache and opens the game in the browser.
5. Choose a public session. For your own server, enter the full wss://YOUR-DOMAIN/session/ws endpoint in the join panel; all friends must select the same endpoint.

Windows needs WebView2. The Mac App has development/ad hoc signing, not Apple notarization; do not disable system security globally. Intel Mac builds and rendered Mac gameplay are not validated by this integration. Story/sandbox and player resources remain separate from multiplayer runtime copies.

The unmodified launcher retains upstream's public catalog. Building packages does not create an always-on session or reserve upstream capacity. Use the manual WSS endpoint for the private server below. A branded catalog can be configured later using upstream's remote-config endpoint; no permanent server address is assumed here.

## Deploy the eight-player server on a remote VM

Run these commands on a remote Linux VM with Docker Engine and Compose, not on the user's computer.

1. Extract the server package and enter its deploy folder.
2. Point your domain's DNS to that VM. Allow inbound TCP 80 and 443 for trusted HTTPS; keep the Java port private.
3. Copy .env.example to .env and set GAME_DOMAIN to the real hostname.
4. Generate the mandatory character collision data using the container commands below. Install separately generated static collision/navigation data for local world coverage. The server refuses player joins without compatible ped-collision.json; a healthy HTTP endpoint alone does not establish readiness.
5. Run docker compose config, then docker compose up -d --build.
6. Check docker compose ps and https://YOUR-DOMAIN/session/health. Confirm the actual server version and loaded world-data capabilities, not just HTTP 200.
7. Give friends wss://YOUR-DOMAIN/session/ws. The packaged launcher serves local assets; this deployment hosts only multiplayer state.

Generate character collision data on that remote VM, using a compatible resource folder available there (never mount a resource folder as writable):

\`\`\`sh
mkdir -p world-data
docker build --target world-data-export -t playgta5-world-data .
# Set RESOURCE_ROOT to the absolute mirror/playgta5.com folder on the remote VM.
docker run --rm --user "$(id -u):$(id -g)" -v "$RESOURCE_ROOT:/resources:ro" -v "$PWD/world-data:/output" playgta5-world-data
\`\`\`

The exporter verifies the source engine/assets and writes derived data only to world-data. This setup does not distribute game-derived geometry. The automated VM validation independently exercises the same exporter using selected inputs from verified release archives.

One Java process is one session capped at eight players. The container starts with a 512 MiB maximum Java heap and a 768 MiB container memory limit; provision an initial 2 vCPU / 2 GB RAM VM and measure before scaling. World state is in memory and resets on restart. No database, accounts, rewards or progression are added.

Caddy obtains a trusted certificate for the configured domain. Certificates persist in Docker volumes. No production credentials or certificate files belong in Git. Stop with docker compose down; omit --volumes to retain certificate state. Before updates, retain the previous image ID and configuration so the prior image can be restored if health or gameplay checks fail.

The Dockerfile builds directly from the pinned upstream source. It needs network access during build and does not need the 21 GB game installation. The standalone JAR is also included for existing Java 17 VM deployments.

## Verification and limits

Automated checks cover pinned source, compatible inventory, downloaded engine checksums, isolated runtime generation, unchanged input hashes, eight unique player/entity identities, initial snapshots, heartbeat, executable formats, Mac development signature and package checksums. They do not run a full asset installation, GPU rendering, vehicle seat interactions or combat on real Windows/Mac hardware.

Before calling the server ready for friends, use two physical supported devices on the same endpoint, then eight players for one hour. Verify mutual visibility, movement, driver/passenger seats, combat, respawn, late join, reconnect and disconnect cleanup. Record CPU, process memory, network usage, browser/GPU errors and the loaded world-data coverage.

Current upstream limits include experimental synchronization, eight players, 256 world entities and approximately 600 by 600 metres of collision/navigation around the test spawn when the derived data is installed. Full-map synchronization, GTA Online/FiveM compatibility and persistent progression are outside this setup.

## Storage and bandwidth

Mirror data: 21.16 GB decimal / approximately 19.71 GiB per player. Mirror installation guidance allows 25 GB free, or 45 GB when keeping archives. Allow 35 GB initially for local data, caches and launcher headroom; actual launcher ZIP sizes are recorded in the build artifacts.

There is no host-machine game download during the hosted build. The server verification VM downloads about 5.34 GB across parts 01, 12, 13 and 14 temporarily and discards original/derived engine files when the VM is destroyed.

Network planning assumption, not measured throughput: 25-100 KB/s outbound per connected player means 1.6-6.4 Mbps for eight players, or 0.72-2.88 GB per full-session hour. Players serve assets locally, so game asset downloads do not pass through the multiplayer VPS.

## Attribution and resource boundary

Preserve upstream LICENSE, NOTICE.md and NOTICE.zh-CN.md alongside packages. The MIT grant covers project code and documentation; game resources and the original engine remain separately supplied. Never commit original/derived game data, runtime caches or keys. Do not bypass the engine hash check.
