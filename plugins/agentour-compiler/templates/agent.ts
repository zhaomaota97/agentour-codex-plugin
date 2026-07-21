import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { defineAgent } from "eve";

const agentourURL = process.env.AGENTOUR_URL?.replace(/\/$/, "");
if (!agentourURL) {
  throw new Error("AGENTOUR_URL is required before the Agent starts");
}
const runtimeToken = process.env.AGENTOUR_RUNTIME_TOKEN;
if (!runtimeToken) {
  throw new Error("AGENTOUR_RUNTIME_TOKEN is required before the Agent starts");
}

const provider = createOpenAICompatible({
  name: "agentour",
  baseURL: `${agentourURL}/v1/llm`,
  apiKey: runtimeToken,
});

export default defineAgent({
  model: provider("MODEL_ID"),
  modelContextWindowTokens: 1_000_000,
  system: `ROLE_AND_INSTRUCTIONS`,
});
