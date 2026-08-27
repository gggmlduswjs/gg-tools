// 채점 프롬프트 조립 — 순수함수(문자열만 만든다).
//
// 원칙: 채점자에게 기대 라벨(expect)을 주지 않는다. 관찰만 시키고 pass/fail 은 verdict.ts 가 정한다.

import type { QaCase, ReviewCase } from "./cases.js";

export interface Prompt {
  system: string;
  user: string;
}

export const REVIEW_JUDGE_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    flagged: {
      type: "boolean",
      description: "리뷰어가 지목된 그 결함을 실제로 짚었으면 true",
    },
    evidence: {
      type: "string",
      description: "true 면 근거가 된 리뷰어 문장, false 면 리뷰어가 대신 무엇을 말했는지",
    },
  },
  required: ["flagged", "evidence"],
  additionalProperties: false,
};

export const QA_JUDGE_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    checks: {
      type: "array",
      description: "받은 항목 전부에 대해 하나씩. 항목 문자열은 받은 그대로 복사할 것",
      items: {
        type: "object",
        properties: {
          item: { type: "string" },
          kind: { type: "string", enum: ["must", "must_not"] },
          met: {
            type: "boolean",
            description: "must: 답변이 이 사실을 담고 있으면 true / must_not: 답변이 이 주장을 하면 true",
          },
          evidence: { type: "string" },
        },
        required: ["item", "kind", "met", "evidence"],
        additionalProperties: false,
      },
    },
  },
  required: ["checks"],
  additionalProperties: false,
};

const REVIEW_JUDGE_SYSTEM = `당신은 코드 리뷰 결과를 채점한다. 코드를 직접 리뷰하지 마라.

받는 것: (1) 리뷰 대상 코드 (2) 리뷰어가 낸 리뷰 (3) 이 케이스가 지목한 결함 한 줄.

판단할 것은 하나뿐이다 — 리뷰어가 (3)의 그 결함을 실제로 짚었는가?

- 표현이 달라도 같은 결함을 가리키면 짚은 것이다.
- 결함의 존재만 말하고 이유가 틀렸어도, 그 줄/그 문제를 지목했으면 짚은 것이다.
- 다른 문제만 잔뜩 지적하고 (3)은 언급하지 않았으면 안 짚은 것이다.
- "혹시 문제일 수도 있다" 수준의 일반론적 나열은 짚은 것이 아니다. 구체적으로 그 코드를 가리켜야 한다.

당신의 의견으로 코드가 괜찮은지 나쁜지는 채점 대상이 아니다.`;

export function buildReviewJudgePrompt(kase: ReviewCase, reviewerOutput: string): Prompt {
  // expect=pass 케이스에는 지목할 결함이 없다. 대신 "정상인 이 항목을 위반이라 주장했는가"를 묻는다.
  const target =
    kase.expect === "violation"
      ? kase.violation ?? ""
      : `이 코드가 다음 규칙을 어겼다는 주장: ${kase.rule}`;

  return {
    system: REVIEW_JUDGE_SYSTEM,
    user: [
      "## 리뷰 대상 코드",
      "```python",
      kase.input,
      "```",
      "",
      "## 리뷰어가 낸 리뷰",
      reviewerOutput.trim() || "(빈 응답)",
      "",
      "## 이 케이스가 지목한 결함",
      target,
      "",
      "리뷰어가 위 결함을 짚었는지 판정하라.",
    ].join("\n"),
  };
}

const QA_JUDGE_SYSTEM = `당신은 코드베이스 질의응답을 사실 기준으로 채점한다. 질문에 직접 답하지 마라.

받는 것: (1) 질문 (2) 응답자의 답변 (3) 확인할 항목 목록.

항목마다 하나씩, 답변만 근거로 판정한다:
- kind=must  → 답변이 그 사실을 담고 있으면 met=true
- kind=must_not → 답변이 그 주장을 하고 있으면 met=true (즉 met=true 가 나쁜 쪽이다)

규칙:
- 표현이 달라도 뜻이 같으면 담고 있는 것이다. 토씨를 맞출 필요는 없다.
- 스쳐 지나가듯 단어만 나온 것은 담은 것이 아니다. 그 사실을 실제로 주장해야 한다.
- 당신이 아는 지식으로 답변의 진위를 다시 따지지 마라. 항목이 답변에 있는지만 본다.
- 받은 항목은 하나도 빼지 말고 전부 판정하라. item 문자열은 받은 그대로 복사하라.`;

export function buildQaJudgePrompt(kase: QaCase, answer: string): Prompt {
  const items = [
    ...kase.must.map((item) => ({ kind: "must", item })),
    ...kase.must_not.map((item) => ({ kind: "must_not", item })),
  ];

  return {
    system: QA_JUDGE_SYSTEM,
    user: [
      "## 질문",
      kase.input,
      "",
      "## 응답자의 답변",
      answer.trim() || "(빈 응답)",
      "",
      "## 확인할 항목",
      JSON.stringify(items, null, 2),
      "",
      `항목 ${items.length}건 전부를 판정하라.`,
    ].join("\n"),
  };
}

/** qa 응답자(subject) 프롬프트 — 라이브 CLAUDE.md 를 컨텍스트로 준다. */
export function buildQaSubjectPrompt(kase: QaCase, liveClaudeMd: string): Prompt {
  return {
    system: [
      "당신은 이 코드베이스에서 일하는 개발자를 돕는다.",
      "아래는 이 레포의 현재 CLAUDE.md 다. 이것을 근거로 답하라.",
      "",
      "- 질문의 전제가 CLAUDE.md 와 어긋나면, 답하기 전에 그 전제를 바로잡아라.",
      "- 근거가 CLAUDE.md 에 없으면 없다고 말하라. 지어내지 마라.",
      "- 한국어로, 간결하게. 정본 파일 경로와 함수명은 원문 그대로 적어라.",
      "",
      "=== CLAUDE.md ===",
      liveClaudeMd,
      "=== CLAUDE.md 끝 ===",
    ].join("\n"),
    user: kase.input,
  };
}
