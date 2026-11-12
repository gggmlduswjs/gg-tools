// 모델 호출부 — 네트워크·비용이 붙는 유일한 자리. vitest는 전송을 mock한다.

import Anthropic from "@anthropic-ai/sdk";
import {
  JUDGE_MAX_TOKENS,
  JUDGE_MODEL,
  PROVIDER,
  SUBJECT_MAX_TOKENS,
  SUBJECT_MODEL,
  SUBJECT_TEMPERATURE,
} from "./config.js";
import type { Prompt } from "./judge-prompt.js";

// 지연 생성. import 시점에 만들면 키가 없을 때 run.ts 의 균형 게이트(무료)까지
// 같이 죽어서, 케이스 라벨이 깨졌다는 진단 대신 "키가 없다"만 보인다.
let _client: Anthropic | null = null;
function anthropic(): Anthropic {
  if (_client === null) _client = new Anthropic();
  return _client;
}

function firstText(message: Anthropic.Message): string {
  // thinking 이 켜진 모델은 content[0] 이 thinking 블록이다. 첫 text 블록을 찾아야 한다.
  const block = message.content.find((b): b is Anthropic.TextBlock => b.type === "text");
  return block?.text ?? "";
}

function assertNotRefused(message: Anthropic.Message, where: string): void {
  if (message.stop_reason === "refusal") {
    const category = message.stop_details?.category ?? "unknown";
    // 게이트는 이걸 error 로 처리해 exit 1 한다. 조용히 통과시키지 않는다.
    throw new Error(`${where}: 모델이 요청을 거절했다 (category=${category})`);
  }
}

/** 피험자 호출 — 리뷰어든 응답자든 여기 하나를 쓴다. */
export async function runSubject(prompt: Prompt): Promise<string> {
  if (PROVIDER === "openai") return openai(prompt, SUBJECT_MODEL, SUBJECT_MAX_TOKENS, undefined, SUBJECT_TEMPERATURE);
  const message = await anthropic().messages.create({
    model: SUBJECT_MODEL,
    max_tokens: SUBJECT_MAX_TOKENS,
    ...(SUBJECT_TEMPERATURE === undefined ? {} : { temperature: SUBJECT_TEMPERATURE }),
    system: prompt.system,
    messages: [{ role: "user", content: prompt.user }],
  });
  assertNotRefused(message, "subject");
  return firstText(message);
}

/**
 * 채점자 호출 — structured outputs 로 스키마를 강제한다.
 * 파싱 실패로 게이트가 흔들리는 걸 막는 게 목적이다.
 */
export async function runJudge<T>(prompt: Prompt, schema: Record<string, unknown>): Promise<T> {
  if (PROVIDER === "openai") {
    const text = await openai(prompt, JUDGE_MODEL, JUDGE_MAX_TOKENS, schema);
    try { return JSON.parse(text) as T; }
    catch { throw new Error("judge: JSON 파싱 실패"); }
  }
  const message = await anthropic().messages.create({
    model: JUDGE_MODEL,
    max_tokens: JUDGE_MAX_TOKENS,
    system: prompt.system,
    messages: [{ role: "user", content: prompt.user }],
    output_config: { format: { type: "json_schema", schema } },
  });
  assertNotRefused(message, "judge");

  const text = firstText(message);
  if (text.trim() === "") throw new Error("judge: 응답에 text 블록이 없다");
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(`judge: JSON 파싱 실패 — ${text.slice(0, 200)}`);
  }
}

type ResponseBody = {
  status: string;
  output?: {type: string; content?: {type: string; text?: string}[]}[];
};

async function openai(prompt: Prompt, model: string, maxTokens: number,
                      schema?: Record<string, unknown>, temperature?: number): Promise<string> {
  if (!model || !SUBJECT_MODEL || !JUDGE_MODEL) throw new Error("OpenAI eval: EVAL_SUBJECT_MODEL·EVAL_JUDGE_MODEL을 명시하세요");
  if (SUBJECT_MODEL === JUDGE_MODEL) throw new Error("OpenAI eval: subject와 judge는 다른 모델이어야 합니다");
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error("OpenAI eval: OPENAI_API_KEY 필요 (Codex 로그인과 별도)");
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {Authorization: `Bearer ${key}`, "Content-Type": "application/json"},
    signal: AbortSignal.timeout(120_000),
    body: JSON.stringify({model, instructions: prompt.system, input: prompt.user,
      max_output_tokens: maxTokens, store: false,
      ...(temperature === undefined ? {} : {temperature}),
      ...(schema ? {text: {format: {type: "json_schema", name: "eval_judge", strict: true, schema}}} : {}),
    }),
  });
  // 에러 본문에는 요청이나 개인정보가 담길 수 있으므로 출력하지 않는다.
  if (!response.ok) throw new Error(`OpenAI eval: HTTP ${response.status}`);
  let body: ResponseBody;
  try { body = await response.json() as ResponseBody; }
  catch { throw new Error("OpenAI eval: 응답 JSON 해석 실패"); }
  if (body.status !== "completed") throw new Error("OpenAI eval: 응답 미완료");
  const content = (body.output ?? []).filter(item => item.type === "message").flatMap(item => item.content ?? []);
  if (content.some(item => item.type === "refusal")) throw new Error("OpenAI eval: 모델 거절");
  const text = content.filter(item => item.type === "output_text").map(item => item.text ?? "").join("");
  if (!text.trim()) throw new Error("OpenAI eval: 응답 text 없음");
  return text;
}
