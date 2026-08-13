// Anthropic 호출부 — 네트워크·비용이 붙는 유일한 자리. vitest 는 여기를 부르지 않는다.

import Anthropic from "@anthropic-ai/sdk";
import {
  JUDGE_MAX_TOKENS,
  JUDGE_MODEL,
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
