export const SCHEMA_VERSION = "biella.npc-decision/v1";
export const MODEL_ID = "@cf/nvidia/nemotron-3-120b-a12b";

const MAX_VALID_FOR_MS = 60_000;
const MAX_DIALOGUE_CHARS = 512;
const MAX_ALLOWED_INTENTS = 32;
const MAX_TARGETS = 64;

function json(body, status = 200) {
  return Response.json(body, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function nonEmptyString(value, max = 256) {
  return typeof value === "string" && value.length > 0 && value.length <= max;
}

function stringArray(value, maxItems, maxLength = 128) {
  return (
    Array.isArray(value) &&
    value.length <= maxItems &&
    value.every((item) => nonEmptyString(item, maxLength))
  );
}

function validateRequest(body) {
  if (!isRecord(body) || body.schema_version !== SCHEMA_VERSION) return false;
  if (!nonEmptyString(body.request_id, 128)) return false;
  if (!nonEmptyString(body.npc_id, 128)) return false;
  if (!nonEmptyString(body.npc_archetype, 128)) return false;
  if (!nonEmptyString(body.session_id, 128)) return false;
  if (!nonEmptyString(body.current_goal, 512)) return false;
  if (!isRecord(body.perception) || !isRecord(body.world_state)) return false;
  if (!isRecord(body.memory_summary) || !isRecord(body.decision_context)) return false;
  if (!stringArray(body.candidate_targets, MAX_TARGETS)) return false;
  if (!stringArray(body.allowed_intents, MAX_ALLOWED_INTENTS, 64) || body.allowed_intents.length === 0) return false;
  if (new Set(body.allowed_intents).size !== body.allowed_intents.length) return false;
  return true;
}

function providerDecisionSchema(requestBody) {
  return {
    type: "json_schema",
    json_schema: {
      type: "object",
      additionalProperties: false,
      properties: {
        intent: { type: "string", enum: requestBody.allowed_intents },
        target_ref: {
          anyOf: [
            { type: "null" },
            { type: "string", enum: requestBody.candidate_targets },
          ],
        },
        parameters: { type: "object" },
        dialogue: { type: "string", maxLength: MAX_DIALOGUE_CHARS },
        valid_for_ms: {
          type: "integer",
          minimum: 0,
          maximum: MAX_VALID_FOR_MS,
        },
      },
      required: ["intent", "target_ref", "parameters", "dialogue", "valid_for_ms"],
    },
  };
}

function promptMessages(body) {
  const snapshot = {
    npc_id: body.npc_id,
    npc_archetype: body.npc_archetype,
    current_goal: body.current_goal,
    perception: body.perception,
    world_state: body.world_state,
    memory_summary: body.memory_summary,
    candidate_targets: body.candidate_targets,
    allowed_intents: body.allowed_intents,
    decision_context: body.decision_context,
  };

  return [
    {
      role: "system",
      content:
        "You are the bounded high-level NPC decision service for Biella Games. Return only one decision matching the supplied JSON schema. Choose only an allowed intent and only a supplied target reference or null. Do not invent gameplay authority, movement, physics, damage, spawning, inventory changes, mission state, or any target not supplied by the game.",
    },
    {
      role: "user",
      content: JSON.stringify(snapshot),
    },
  ];
}

function extractProviderDecision(output) {
  let candidate;

  if (isRecord(output) && Object.prototype.hasOwnProperty.call(output, "response")) {
    candidate = output.response;
  } else if (
    isRecord(output) &&
    Array.isArray(output.choices) &&
    output.choices.length > 0 &&
    isRecord(output.choices[0]) &&
    isRecord(output.choices[0].message)
  ) {
    candidate = output.choices[0].message.content;
  } else {
    candidate = output;
  }

  if (typeof candidate === "string") {
    try {
      candidate = JSON.parse(candidate);
    } catch {
      return null;
    }
  }

  return isRecord(candidate) ? candidate : null;
}

function validateProviderDecision(decision, requestBody) {
  if (!isRecord(decision)) return false;
  if (!requestBody.allowed_intents.includes(decision.intent)) return false;
  if (
    decision.target_ref !== null &&
    (!nonEmptyString(decision.target_ref, 128) || !requestBody.candidate_targets.includes(decision.target_ref))
  ) {
    return false;
  }
  if (!isRecord(decision.parameters)) return false;
  if (typeof decision.dialogue !== "string" || decision.dialogue.length > MAX_DIALOGUE_CHARS) return false;
  if (
    !Number.isInteger(decision.valid_for_ms) ||
    decision.valid_for_ms < 0 ||
    decision.valid_for_ms > MAX_VALID_FOR_MS
  ) {
    return false;
  }
  return true;
}

async function handleDecision(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "INVALID_REQUEST" }, 400);
  }

  if (!validateRequest(body)) {
    return json({ error: "INVALID_REQUEST" }, 400);
  }
  if (!env?.AI || typeof env.AI.run !== "function") {
    return json({ error: "AI_BINDING_UNAVAILABLE" }, 503);
  }

  let providerOutput;
  try {
    providerOutput = await env.AI.run(MODEL_ID, {
      messages: promptMessages(body),
      response_format: providerDecisionSchema(body),
      max_completion_tokens: 256,
      temperature: 0.2,
    });
  } catch {
    return json({ error: "PROVIDER_FAILURE" }, 502);
  }

  const decision = extractProviderDecision(providerOutput);
  if (!validateProviderDecision(decision, body)) {
    return json({ error: "INVALID_PROVIDER_DECISION" }, 502);
  }

  return json({
    schema_version: SCHEMA_VERSION,
    model: MODEL_ID,
    decision: {
      decision_id: body.request_id,
      intent: decision.intent,
      target_ref: decision.target_ref,
      parameters: decision.parameters,
      dialogue: decision.dialogue,
      valid_for_ms: decision.valid_for_ms,
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/v1/npc/decision") {
      return handleDecision(request, env);
    }
    return json({ error: "NOT_FOUND" }, 404);
  },
};
