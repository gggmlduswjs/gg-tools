import { afterEach, beforeEach, expect, it, vi } from "vitest";

const anthropicCreate = vi.hoisted(() => vi.fn());
vi.mock("@anthropic-ai/sdk", () => ({default: class {
  messages = {create: anthropicCreate};
}}));

beforeEach(() => {
  vi.resetModules();
  anthropicCreate.mockReset();
  vi.stubEnv("EVAL_PROVIDER", "openai");
  vi.stubEnv("OPENAI_API_KEY", "test-key");
  vi.stubEnv("EVAL_SUBJECT_MODEL", "subject-model");
  vi.stubEnv("EVAL_JUDGE_MODEL", "judge-model");
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

function mockResponse(content: unknown[], status = "completed") {
  const fetcher = vi.fn().mockResolvedValue({ok: true, json: async () => ({status, output: [{type: "message", content}]})});
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

it("OpenAI subject uses Responses without Anthropic or implicit temperature", async () => {
  const fetcher = mockResponse([{type: "output_text", text: "answer"}]);
  const {runSubject} = await import("../src/client.js");
  expect(await runSubject({system: "rules", user: "question"})).toBe("answer");
  const [url, options] = fetcher.mock.calls[0]!;
  expect(url).toBe("https://api.openai.com/v1/responses");
  expect(JSON.parse(options.body)).toMatchObject({model: "subject-model", instructions: "rules", input: "question", store: false});
  expect(JSON.parse(options.body)).not.toHaveProperty("temperature");
  expect(anthropicCreate).not.toHaveBeenCalled();
});

it("judge sends structured output and parses JSON", async () => {
  const fetcher = mockResponse([{type: "output_text", text: '{"ok":true}'}]);
  const {runJudge} = await import("../src/client.js");
  const schema = {type: "object", properties: {ok: {type: "boolean"}}, required: ["ok"], additionalProperties: false};
  expect(await runJudge({system: "judge", user: "result"}, schema)).toEqual({ok: true});
  expect(JSON.parse(fetcher.mock.calls[0]![1].body).text.format).toMatchObject({type: "json_schema", schema, strict: true});
});

it.each([
  [[{type: "refusal", refusal: "no"}], "completed", "모델 거절"],
  [[{type: "output_text", text: "partial"}], "incomplete", "응답 미완료"],
  [[], "completed", "응답 text 없음"],
])("refused/incomplete/empty responses fail", async (content, status, error) => {
  mockResponse(content, status as string);
  const {runSubject} = await import("../src/client.js");
  await expect(runSubject({system: "rules", user: "question"})).rejects.toThrow(error as string);
});

it("existing default Anthropic request stays unchanged", async () => {
  vi.stubEnv("EVAL_PROVIDER", undefined);
  vi.stubEnv("EVAL_SUBJECT_MODEL", undefined);
  vi.stubEnv("EVAL_JUDGE_MODEL", undefined);
  vi.stubEnv("EVAL_SUBJECT_TEMPERATURE", undefined);
  anthropicCreate.mockResolvedValue({stop_reason: "end_turn", content: [{type: "text", text: "claude answer"}]});
  const {runSubject} = await import("../src/client.js");
  expect(await runSubject({system: "rules", user: "question"})).toBe("claude answer");
  expect(anthropicCreate).toHaveBeenCalledWith({model: "claude-sonnet-4-6", max_tokens: 4000, temperature: 0,
    system: "rules", messages: [{role: "user", content: "question"}]});
});

it.each(["key", "models", "same-model"])("invalid OpenAI setup fails before transport: %s", async kind => {
  const fetcher = mockResponse([{type: "output_text", text: "unexpected"}]);
  if (kind === "key") vi.stubEnv("OPENAI_API_KEY", undefined);
  if (kind === "models") vi.stubEnv("EVAL_SUBJECT_MODEL", undefined);
  if (kind === "same-model") vi.stubEnv("EVAL_JUDGE_MODEL", "subject-model");
  const {runSubject} = await import("../src/client.js");
  await expect(runSubject({system: "rules", user: "question"})).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});

it("HTTP failure does not log key or server payload", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ok: false, status: 401, json: async () => ({error: "test-key"})}));
  const {runSubject} = await import("../src/client.js");
  await expect(runSubject({system: "rules", user: "question"})).rejects.toThrow("HTTP 401");
});

it("malformed successful response never exposes its body in errors", async () => {
  const marker = "SENSITIVE_SERVER_PAYLOAD";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(marker, {status: 200})));
  const {runSubject} = await import("../src/client.js");
  try {
    await runSubject({system: "rules", user: "question"});
    expect.fail("malformed response must fail");
  } catch (error) {
    expect((error as Error).message).not.toContain(marker.slice(0, 10));
    expect((error as Error).message).toBe("OpenAI eval: 응답 JSON 해석 실패");
  }
});
