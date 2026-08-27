// golden set 균형 규칙 — 순수함수.
//
// 왜 있나: eval 은 "통과했다"보다 "잴 수 있었나"가 먼저다. 위반 케이스만 모으면
// 「전부 위반이라고 답하는 리뷰어」가 만점을 받고, 정상 케이스만 모으면 아무것도 안 하는
// 리뷰어가 만점을 받는다. 라이브 실행 전에 여기서 먼저 막는다(돈 쓰기 전에).

import type { EvalCase, QaCase, ReviewCase } from "./cases.js";

export const MIN_REVIEW_VIOLATIONS = 4;
export const MIN_REVIEW_PASSES = 1;
export const MIN_QA_CASES = 3;
export const MIN_QA_FALSE_PREMISE_GUARDS = 1;

export function checkBalance(cases: EvalCase[]): string[] {
  const problems: string[] = [];

  const seen = new Set<string>();
  for (const kase of cases) {
    const key = `${kase.track}/${kase.id}`;
    if (seen.has(key)) problems.push(`케이스 id 가 중복이다: ${key}`);
    seen.add(key);
  }

  const review = cases.filter((c): c is ReviewCase => c.track === "review");
  const qa = cases.filter((c): c is QaCase => c.track === "qa");

  const violations = review.filter((c) => c.expect === "violation").length;
  const passes = review.filter((c) => c.expect === "pass").length;

  if (violations < MIN_REVIEW_VIOLATIONS) {
    problems.push(`review: 위반 케이스가 ${violations}건 — 최소 ${MIN_REVIEW_VIOLATIONS}건 필요`);
  }
  if (passes < MIN_REVIEW_PASSES) {
    problems.push(
      `review: 정상(오탐방지) 케이스가 ${passes}건 — 최소 ${MIN_REVIEW_PASSES}건 필요. ` +
        `없으면 「전부 위반」이라고 답하는 리뷰어가 만점을 받는다`,
    );
  }

  if (qa.length < MIN_QA_CASES) {
    problems.push(`qa: 케이스가 ${qa.length}건 — 최소 ${MIN_QA_CASES}건 필요`);
  }
  const guards = qa.filter((c) => c.guard === "false_premise").length;
  if (guards < MIN_QA_FALSE_PREMISE_GUARDS) {
    problems.push(
      `qa: 틀린 전제 반박 가드가 ${guards}건 — 최소 ${MIN_QA_FALSE_PREMISE_GUARDS}건 필요. ` +
        `없으면 질문에 순응만 하는 응답자가 만점을 받는다`,
    );
  }

  return problems;
}
