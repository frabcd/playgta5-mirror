# Build/run only on a remote VM or hosted CI runner.
FROM eclipse-temurin:17-jdk-jammy AS build
ARG UPSTREAM_COMMIT=9726fa0219120cafce8e26bc37eb3c01126df00e
RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /source
RUN git init && git remote add origin https://github.com/AliYa-chen/gtav-web-multiplayer-launcher.git && git fetch --depth=1 origin "$UPSTREAM_COMMIT" && git checkout --detach FETCH_HEAD && test "$(git rev-parse HEAD)" = "$UPSTREAM_COMMIT"
RUN python3 -B tools/build_multiplayer_server.py

FROM eclipse-temurin:17-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/* && groupadd --gid 10001 game && useradd --uid 10001 --gid game --no-create-home game
WORKDIR /app
COPY --from=build /source/server/multiplayer-server.jar /app/multiplayer-server.jar
COPY --from=build /source/LICENSE /source/NOTICE.md /source/NOTICE.zh-CN.md /app/
RUN mkdir /app/world-data && chown -R game:game /app
USER 10001:10001
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl --fail --silent http://127.0.0.1:8787/health >/dev/null || exit 1
ENTRYPOINT ["java", "-Xms64m", "-Xmx512m", "-jar", "/app/multiplayer-server.jar"]
CMD ["--host", "0.0.0.0", "--port", "8787", "--max-clients", "8", "--world-data", "/app/world-data"]
