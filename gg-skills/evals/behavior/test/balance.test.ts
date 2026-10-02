import { describe, expect, it } from "vitest";

import { checkBalance } from "../src/balance.js";
import type { EvalCase, QaCase, ReviewCase } from "../src/cases.js";

const review = (id: string, expectLabel: ReviewCase["expect"], rule = `규칙 ${id}`): ReviewCase => ({
  track: "review",
  id,
  title: `제목 ${id}`,
  expect: expectLabel,
  rule,
  ...(expectLabel === "violation" ? { violation: `결함 ${id}` } : {}),
  input: "code",
});

const qa = (id: string, guard?: "false_premise"): QaCase => ({
  track: "qa",
  id,
  title: `제목 ${id}`,
  must: ["사실"],
  must_not: [],
  ...(guard ? { guard } : {}),
  input: "질문",
});

/** 균형이 맞는 최소 집합 */
function balancedSet(): EvalCase[] {
  return [
    review("1", "violation"),
    review("2", "violation"),
    review("3", "violation"),
    review("4", "violation"),
    review("5", "pass"),
    qa("1"),
    qa("2"),
    qa("3", "false_premise"),
  ];
}

describe("checkBalance", () => {
  it("균형이 맞으면 문제 없음", () => {
    expect(checkBalance(balancedSet())).toEqual([]);
  });

  it("review 정상 케이스가 없으면 막는다 — 전부 위반이라 답하는 리뷰어가 만점을 받는다", () => {
    const cases = balancedSet().filter((c) => !(c.track === "review" && c.expect === "pass"));
    const problems = checkBalance(cases);
    expect(problems.join("\n")).toMatch(/정상\(오탐방지\) 케이스가 0건/);
  });

  it("review 위반이 부족하면 막는다", () => {
    const cases = balancedSet().filter((c) => !(c.track === "review" && c.id === "4"));
    expect(checkBalance(cases).join("\n")).toMatch(/위반 케이스가 3건/);
  });

  it("qa 틀린 전제 가드가 없으면 막는다 — 순응만 하는 응답자가 만점을 받는다", () => {
    const cases = balancedSet().map((c) => (c.track === "qa" ? qa(c.id) : c));
    expect(checkBalance(cases).join("\n")).toMatch(/틀린 전제 반박 가드가 0건/);
  });

  it("qa 케이스가 부족하면 막는다", () => {
    const cases = balancedSet().filter((c) => !(c.track === "qa" && c.id === "2"));
    expect(checkBalance(cases).join("\n")).toMatch(/qa: 케이스가 2건/);
  });

  it("id 중복을 잡는다", () => {
    const cases = [...balancedSet(), qa("1")];
    expect(checkBalance(cases).join("\n")).toMatch(/id 가 중복이다: qa\/1/);
  });

  it("트랙이 다르면 같은 id 여도 중복이 아니다", () => {
    const problems = checkBalance([...balancedSet(), review("1", "pass")]);
    expect(problems.join("\n")).toMatch(/id 가 중복이다: review\/1/);
    // qa/1 과 review/1 은 서로 충돌하지 않는다
    expect(problems.join("\n")).not.toMatch(/id 가 중복이다: qa\/1/);
  });

  it("빈 집합은 전부 걸린다", () => {
    expect(checkBalance([]).length).toBeGreaterThanOrEqual(4);
  });
});
