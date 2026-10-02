// pass/fail 은 순수함수가 정한다.
//
// 채점자(LLM)에게는 "관찰"만 시키고 — 리뷰어가 그 결함을 짚었나 / 이 사실이 답변에 있나 —
// 그 관찰을 pass/fail 로 바꾸는 일은 여기서 결정론적으로 한다.
// 채점자가 라벨까지 알고 판정하면 라벨 쪽으로 끌려간다(그리고 그 편향은 재현이 안 된다).

import type { QaCase, ReviewCase } from "./cases.js";

export type Verdict = "pass" | "fail";

/** 채점자가 돌려주는 review 관찰 */
export interface ReviewObservation {
  /** 케이스가 지목한 그 결함을 리뷰어가 짚었는가 */
  flagged: boolean;
  evidence: string;
}

/** 채점자가 돌려주는 qa 관찰 — must/must_not 항목별 충족 여부 */
export interface FactCheck {
  item: string;
  kind: "must" | "must_not";
  met: boolean;
  evidence: string;
}

export interface Judged {
  verdict: Verdict;
  reason: string;
}

export function reviewVerdict(kase: ReviewCase, observation: ReviewObservation): Judged {
  if (kase.expect === "violation") {
    return observation.flagged
      ? { verdict: "pass", reason: "위반을 짚었다" }
      : { verdict: "fail", reason: `위반을 놓쳤다: ${kase.violation ?? ""}` };
  }
  // expect=pass — 정상 코드를 위반이라고 하면 오탐이다.
  return observation.flagged
    ? { verdict: "fail", reason: `오탐 — 정상 코드를 위반으로 지목했다: ${observation.evidence}` }
    : { verdict: "pass", reason: "정상 코드를 정상으로 봤다" };
}

/**
 * must 는 전부 충족(met=true), must_not 은 전부 미출현(met=false)이어야 통과.
 * 채점자가 항목을 빠뜨리면 통과시키지 않는다 — 못 잰 것은 통과가 아니다.
 */
export function qaVerdict(kase: QaCase, checks: FactCheck[]): Judged {
  const byItem = new Map(checks.map((c) => [`${c.kind}::${c.item}`, c]));
  const problems: string[] = [];

  for (const item of kase.must) {
    const check = byItem.get(`must::${item}`);
    if (!check) problems.push(`채점 누락(must): ${item}`);
    else if (!check.met) problems.push(`빠진 사실: ${item}`);
  }

  for (const item of kase.must_not) {
    const check = byItem.get(`must_not::${item}`);
    if (!check) problems.push(`채점 누락(must_not): ${item}`);
    else if (check.met) problems.push(`하면 안 되는 주장: ${item}`);
  }

  return problems.length === 0
    ? { verdict: "pass", reason: `사실 ${kase.must.length}건 충족, 금지 ${kase.must_not.length}건 미출현` }
    : { verdict: "fail", reason: problems.join(" / ") };
}
