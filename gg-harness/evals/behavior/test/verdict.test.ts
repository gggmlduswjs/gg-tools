import { describe, expect, it } from "vitest";

import type { QaCase, ReviewCase } from "../src/cases.js";
import { qaVerdict, reviewVerdict, type FactCheck } from "../src/verdict.js";

const violationCase: ReviewCase = {
  track: "review",
  id: "01",
  title: "t",
  expect: "violation",
  rule: "r",
  violation: "1.11 을 직접 곱한다",
  input: "code",
};

const passCase: ReviewCase = {
  track: "review",
  id: "05",
  title: "t",
  expect: "pass",
  rule: "r",
  input: "code",
};

describe("reviewVerdict", () => {
  it("위반을 짚으면 통과", () => {
    expect(reviewVerdict(violationCase, { flagged: true, evidence: "e" }).verdict).toBe("pass");
  });

  it("위반을 놓치면 실패하고 무엇을 놓쳤는지 남긴다", () => {
    const judged = reviewVerdict(violationCase, { flagged: false, evidence: "e" });
    expect(judged.verdict).toBe("fail");
    expect(judged.reason).toContain("1.11 을 직접 곱한다");
  });

  it("정상 코드를 지목하면 오탐으로 실패", () => {
    const judged = reviewVerdict(passCase, { flagged: true, evidence: "여기가 위반" });
    expect(judged.verdict).toBe("fail");
    expect(judged.reason).toContain("오탐");
  });

  it("정상 코드를 지나가면 통과", () => {
    expect(reviewVerdict(passCase, { flagged: false, evidence: "" }).verdict).toBe("pass");
  });
});

const qaCase: QaCase = {
  track: "qa",
  id: "01",
  title: "t",
  must: ["사실 A", "사실 B"],
  must_not: ["금지 X"],
  input: "q",
};

const check = (kind: FactCheck["kind"], item: string, met: boolean): FactCheck => ({
  kind,
  item,
  met,
  evidence: "",
});

describe("qaVerdict", () => {
  it("must 전부 충족 + must_not 미출현이면 통과", () => {
    const judged = qaVerdict(qaCase, [
      check("must", "사실 A", true),
      check("must", "사실 B", true),
      check("must_not", "금지 X", false),
    ]);
    expect(judged.verdict).toBe("pass");
  });

  it("must 가 빠지면 실패하고 어떤 사실인지 남긴다", () => {
    const judged = qaVerdict(qaCase, [
      check("must", "사실 A", true),
      check("must", "사실 B", false),
      check("must_not", "금지 X", false),
    ]);
    expect(judged.verdict).toBe("fail");
    expect(judged.reason).toContain("빠진 사실: 사실 B");
  });

  it("must_not 이 나오면 실패", () => {
    const judged = qaVerdict(qaCase, [
      check("must", "사실 A", true),
      check("must", "사실 B", true),
      check("must_not", "금지 X", true),
    ]);
    expect(judged.verdict).toBe("fail");
    expect(judged.reason).toContain("하면 안 되는 주장: 금지 X");
  });

  it("채점자가 항목을 빠뜨리면 통과시키지 않는다 — 못 잰 것은 통과가 아니다", () => {
    const judged = qaVerdict(qaCase, [check("must", "사실 A", true)]);
    expect(judged.verdict).toBe("fail");
    expect(judged.reason).toContain("채점 누락(must): 사실 B");
    expect(judged.reason).toContain("채점 누락(must_not): 금지 X");
  });

  it("채점자가 항목을 지어내도 무시한다 — 케이스 라벨이 기준이다", () => {
    const judged = qaVerdict(qaCase, [
      check("must", "사실 A", true),
      check("must", "사실 B", true),
      check("must", "채점자가 지어낸 사실", false),
      check("must_not", "금지 X", false),
    ]);
    expect(judged.verdict).toBe("pass");
  });

  it("kind 가 다르면 다른 항목이다", () => {
    const oddCase: QaCase = { ...qaCase, must: ["같은 문구"], must_not: ["같은 문구"] };
    const judged = qaVerdict(oddCase, [
      check("must", "같은 문구", true),
      check("must_not", "같은 문구", false),
    ]);
    expect(judged.verdict).toBe("pass");
  });
});
