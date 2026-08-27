// 실제 golden set 을 대상으로 도는 무결성·균형 검사.
// 키도 네트워크도 안 쓴다 — 케이스 파일과 그 파일이 가리키는 프롬프트만 읽는다.

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { checkBalance } from "../src/balance.js";
import { loadAllCases, loadCases, type QaCase, type ReviewCase } from "../src/cases.js";
import { CASES_DIR, DATA_DIR as HARNESS_DIR, REPO_ROOT } from "../src/target.js";

// ⚠️ 이 파일만 **대상 레포**가 필요하다 — golden set 은 레포의 것이지 프레임워크의 것이 아니다.
//    플러그인 자리에서 돌린다면 `EVAL_REPO=<레포>` 를 줘야 한다. 없으면 target.ts 가 던진다.
//    ⛔ "레포가 없으면 skip" 으로 만들지 마라 — 그건 **안 잰 것을 통과로 그리는 것**이다.

describe("golden set 무결성", () => {
  it("모든 케이스가 파싱되고 라벨이 온전하다", () => {
    // loadCases 는 라벨이 깨지면 케이스 id 를 담아 던진다.
    expect(() => loadAllCases(CASES_DIR)).not.toThrow();
  });

  it("케이스 id 가 파일명과 일치하고 서로 겹치지 않는다", () => {
    const cases = loadAllCases(CASES_DIR);
    const keys = cases.map((c) => `${c.track}/${c.id}`);
    expect(new Set(keys).size).toBe(keys.length);
    for (const c of cases) {
      expect(fs.existsSync(path.join(CASES_DIR, c.track, `${c.id}.md`))).toBe(true);
    }
  });

  it("review 위반 케이스는 서로 다른 규칙을 겨눈다", () => {
    const review = loadCases(CASES_DIR, "review") as ReviewCase[];
    const rules = review.filter((c) => c.expect === "violation").map((c) => c.rule);
    expect(new Set(rules).size).toBe(rules.length);
  });

  it("qa 의 must / must_not 항목에 중복이 없다", () => {
    const qa = loadCases(CASES_DIR, "qa") as QaCase[];
    for (const c of qa) {
      expect(new Set(c.must).size, `${c.id}: must 중복`).toBe(c.must.length);
      expect(new Set(c.must_not).size, `${c.id}: must_not 중복`).toBe(c.must_not.length);
    }
  });
});

describe("golden set 균형", () => {
  it("checkBalance 를 통과한다", () => {
    expect(checkBalance(loadAllCases(CASES_DIR))).toEqual([]);
  });

  it("review 에 위반 4건 + 정상 1건 이상이 있다", () => {
    const review = loadCases(CASES_DIR, "review") as ReviewCase[];
    expect(review.filter((c) => c.expect === "violation").length).toBeGreaterThanOrEqual(4);
    expect(review.filter((c) => c.expect === "pass").length).toBeGreaterThanOrEqual(1);
  });

  it("qa 에 틀린 전제 반박 가드가 있다", () => {
    const qa = loadCases(CASES_DIR, "qa") as QaCase[];
    expect(qa.filter((c) => c.guard === "false_premise").length).toBeGreaterThanOrEqual(1);
  });
});

describe("게이트가 읽는 파일이 실재한다", () => {
  it("리뷰어 시스템 프롬프트가 있고 비어 있지 않다", () => {
    const p = path.join(HARNESS_DIR, "prompts", "reviewer-system.md");
    expect(fs.existsSync(p)).toBe(true);
    expect(fs.readFileSync(p, "utf8").trim().length).toBeGreaterThan(200);
  });

  it("qa 컨텍스트로 쓰는 라이브 CLAUDE.md 가 있다", () => {
    // 레포에서 evals/harness/ 를 옮기면 여기가 먼저 깨진다.
    expect(fs.existsSync(path.join(REPO_ROOT, "CLAUDE.md"))).toBe(true);
  });
});
