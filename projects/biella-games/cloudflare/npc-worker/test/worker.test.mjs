import test from "node:test";
import assert from "node:assert/strict";
import worker, { MODEL_ID, SCHEMA_VERSION } from "../src/index.mjs";

function request(body) {
  return new Request("https://worker.test/v1/npc/decision", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function validRequest(overrides = {}) {
  return {
    schema_version: "biella.npc-decision/v1",
    request_id: "req-001",
    npc_id: "rival-001",
    npc_archetype: "rival_contestant",
    session_id: "session-001",
    current_goal: "survive",
    perception: { player_visible: true },
    world_state: { pressure: "low" },
    memory_summary: { last_intent: "investigate" },
    candidate_targets: ["player-001", "cover-002"],
    allowed_intents: ["pursue", "evade", "investigate"],
    decision_context: { urgency: "medium" },
    ...overrides,
  };
}

function envFor(modelResult) {
  const calls = [];
  return {
    calls,
    env: {
      AI: {
        async run(model, input) {
          calls.push({ model, input });
          return modelResult;
        },
      },
    },
  };
}

test("rejects requests with an unsupported schema version before inference", async () => {
  const { env, calls } = envFor({ response: "{}" });
  const response = await worker.fetch(request(validRequest({ schema_version: "old" })), env);
  assert.equal(response.status, 400);
  assert.equal(calls.length, 0);
  const body = await response.json();
  assert.equal(body.error, "INVALID_REQUEST");
});

test("invokes the accepted Nemotron model and returns a bounded schema-valid decision", async () => {
  const { env, calls } = envFor({
    response: JSON.stringify({
      intent: "pursue",
      target_ref: "player-001",
      parameters: { approach: "flank" },
      dialogue: "Moving.",
      valid_for_ms: 3000,
    }),
  });

  const response = await worker.fetch(request(validRequest()), env);
  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].model, "@cf/nvidia/nemotron-3-120b-a12b");
  assert.equal(MODEL_ID, "@cf/nvidia/nemotron-3-120b-a12b");
  assert.equal(SCHEMA_VERSION, "biella.npc-decision/v1");

  const body = await response.json();
  assert.equal(body.schema_version, SCHEMA_VERSION);
  assert.equal(body.model, MODEL_ID);
  assert.deepEqual(body.decision, {
    decision_id: "req-001",
    intent: "pursue",
    target_ref: "player-001",
    parameters: { approach: "flank" },
    dialogue: "Moving.",
    valid_for_ms: 3000,
  });
});

test("rejects a model decision whose intent is outside allowed_intents", async () => {
  const { env } = envFor({
    response: JSON.stringify({
      intent: "teleport",
      target_ref: null,
      parameters: {},
      dialogue: "",
      valid_for_ms: 1000,
    }),
  });
  const response = await worker.fetch(request(validRequest()), env);
  assert.equal(response.status, 502);
  const body = await response.json();
  assert.equal(body.error, "INVALID_PROVIDER_DECISION");
});

test("rejects a model decision targeting a reference not supplied by the game", async () => {
  const { env } = envFor({
    response: JSON.stringify({
      intent: "pursue",
      target_ref: "invented-target",
      parameters: {},
      dialogue: "",
      valid_for_ms: 1000,
    }),
  });
  const response = await worker.fetch(request(validRequest()), env);
  assert.equal(response.status, 502);
  const body = await response.json();
  assert.equal(body.error, "INVALID_PROVIDER_DECISION");
});
