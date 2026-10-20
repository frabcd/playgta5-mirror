import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

const [origin = 'http://127.0.0.1:18787', output] = process.argv.slice(2);
const base = new URL(origin);
assert.ok(['127.0.0.1', 'localhost'].includes(base.hostname), 'CI smoke test only targets loopback');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
let initial;
for (let attempt = 0; attempt < 60; attempt++) {
  try {
    const response = await fetch(new URL('/health', base), { signal: AbortSignal.timeout(1000) });
    if (response.ok) { initial = await response.json(); break; }
  } catch {}
  await delay(500);
}
assert.ok(initial, 'Server did not become healthy within 30 seconds');
const sockets = [];
const ids = new Set();
const entityIds = new Set();
try {
  for (let index = 0; index < 8; index++) {
    const state = await new Promise((resolve, reject) => {
      const ws = new WebSocket(new URL('/ws', base).href.replace(/^http/, 'ws'));
      sockets.push(ws);
      const state = { chunks: 0, entities: new Set() };
      let done = false;
      const timer = setTimeout(() => finish(new Error('Snapshot/heartbeat timeout')), 15000);
      const finish = error => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        if (error) reject(error); else resolve(state);
      };
      ws.addEventListener('error', () => finish(new Error('WebSocket transport failed')));
      ws.addEventListener('close', () => {
        if (!done) finish(new Error('Connection closed before readiness'));
      });
      ws.addEventListener('message', event => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'error') throw new Error('Protocol rejected: ' + message.code);
          if (message.type === 'welcome') {
            assert.equal(message.server_version, initial.server_version);
            ws.send(JSON.stringify({ type: 'hello', name: 'VM player ' + (index + 1),
              capabilities: ['combat', 'resume', 'world_v2', 'heartbeat', 'entity_batch',
                'world_environment', 'shared_law', 'server_ai', 'session_policy', 'physics_queries',
                'equipment_v1', 'ped_pose', 'actions_v2'] }));
          } else if (message.type === 'profile') {
            assert.equal(typeof message.client_id, 'string');
            assert.equal(typeof message.entity_id, 'string');
            state.clientId = message.client_id;
            state.entityId = message.entity_id;
          } else if (message.type === 'snapshot_begin') {
            state.snapshotId = message.snapshot_id;
            state.epoch = message.world_epoch;
            state.entities.clear();
            state.chunks = 0;
          } else if (message.type === 'snapshot_chunk') {
            assert.equal(message.snapshot_id, state.snapshotId);
            assert.equal(message.world_epoch, state.epoch);
            state.chunks++;
            for (const entity of message.entities) state.entities.add(entity.entity_id);
          } else if (message.type === 'snapshot_end') {
            assert.equal(message.snapshot_id, state.snapshotId);
            assert.ok(state.chunks > 0);
            assert.ok(state.entities.has(state.entityId), 'Own player is absent from snapshot');
            state.snapshot = true;
            ws.send(JSON.stringify({ type: 'ping', nonce: 1000 + index }));
          } else if (message.type === 'pong' && message.nonce === 1000 + index) {
            assert.ok(state.snapshot && state.clientId && state.entityId);
            finish();
          }
        } catch (error) { finish(error); }
      });
    });
    assert.ok(!ids.has(state.clientId), 'Duplicate player identity');
    assert.ok(!entityIds.has(state.entityId), 'Duplicate entity identity');
    ids.add(state.clientId);
    entityIds.add(state.entityId);
  }
  const response = await fetch(new URL('/health', base));
  assert.equal(response.status, 200);
  const full = await response.json();
  assert.equal(full.players, 8);
  const report = { server_version: full.server_version, simultaneous_players: full.players,
    unique_player_ids: ids.size, unique_entity_ids: entityIds.size,
    all_snapshots_received: true, all_heartbeats_received: true,
    gameplay_validated: false, test_transport: 'loopback WebSocket' };
  if (output) await writeFile(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
} finally {
  for (const ws of sockets) ws.close();
  await delay(300);
}
