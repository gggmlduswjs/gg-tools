import { describe, expect, it } from "vitest";

import { parseCase, parseQaCase, parseReviewCase } from "../src/cases.js";

const REVIEW_VIOLATION = `---
title: 제목
expect: violation
rule: 어떤 규칙
violation: 무엇이 잘못됐는지
---

code_here()
`;

const REVIEW_PASS = `---
title: 제목
expect: pass
rule: 어떤 규칙
---

code_here()
`;

const QA_OK = `---
title: 제목
must:
  - 사실 하나
must_not:
  - 하면 안 되는 주장
---

질문?
`;

describe("parseReviewCase", () => {
  it("위반 케이스를 읽는다", () => {
    expect(parseReviewCase("01-x", REVIEW_VIOLATION)).toEqual({
      track: "review",
      id: "01-x",
      title: "제목",
      expect: "violation",
      rule: "어떤 규칙",
      violation: "무엇이 잘못됐는지",
      input: "code_here()",
    });
  });

  it("정상 케이스는 violation 없이 읽는다", () => {
    const parsed = parseReviewCase("05-x", REVIEW_PASS);
    expect(parsed.expect).toBe("pass");
    expect(parsed.violation).toBeUndefined();
  });

  it("expect 가 enum 밖이면 던진다", () => {
    expect(() => parseReviewCase("x", REVIEW_VIOLATION.replace("violation\n", "위반\n"))).toThrow(
      /violation\|pass/,
    );
  });

  it("expect=violation 인데 violation 이 없으면 던진다 — 채점 기준이 없다", () => {
    const src = REVIEW_VIOLATION.replace("violation: 무엇이 잘못됐는지\n", "");
    expect(() => parseReviewCase("x", src)).toThrow(/'violation'/);
  });

  it("expect=pass 인데 violation 이 있으면 던진다 — 라벨 모순", () => {
    const src = REVIEW_PASS.replace("rule: 어떤 규칙", "rule: 어떤 규칙\nviolation: 뭔가");
    expect(() => parseReviewCase("x", src)).toThrow(/라벨이 모순/);
  });

  it("본문이 비면 던진다", () => {
    expect(() => parseReviewCase("x", REVIEW_VIOLATION.replace("code_here()", "  "))).toThrow(/본문/);
  });

  it("에러 메시지에 케이스 id 가 들어간다", () => {
    expect(() => parseReviewCase("07-abc", REVIEW_PASS.replace("title: 제목\n", ""))).toThrow(
      /review\/07-abc/,
    );
  });
});

describe("parseQaCase", () => {
  it("must / must_not 을 읽는다", () => {
    expect(parseQaCase("01-x", QA_OK)).toEqual({
      track: "qa",
      id: "01-x",
      title: "제목",
      must: ["사실 하나"],
      must_not: ["하면 안 되는 주장"],
      input: "질문?",
    });
  });

  it("must_not 은 없어도 된다", () => {
    const src = QA_OK.replace("must_not:\n  - 하면 안 되는 주장\n", "");
    expect(parseQaCase("x", src).must_not).toEqual([]);
  });

  it("must 가 비면 던진다 — 기준 없는 케이스는 항상 통과한다", () => {
    const src = QA_OK.replace("must:\n  - 사실 하나\n", "must:\n");
    expect(() => parseQaCase("x", src)).toThrow(/'must' 가 비었다/);
  });

  it("guard 를 읽고 enum 밖이면 던진다", () => {
    const ok = QA_OK.replace("title: 제목", "title: 제목\nguard: false_premise");
    expect(parseQaCase("x", ok).guard).toBe("false_premise");

    const bad = QA_OK.replace("title: 제목", "title: 제목\nguard: 아무거나");
    expect(() => parseQaCase("x", bad)).toThrow(/false_premise/);
  });
});

describe("parseCase", () => {
  it("트랙에 맞는 파서로 보낸다", () => {
    expect(parseCase("review", "a", REVIEW_PASS).track).toBe("review");
    expect(parseCase("qa", "a", QA_OK).track).toBe("qa");
  });
});
