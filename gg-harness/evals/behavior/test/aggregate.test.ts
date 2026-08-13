import { describe, expect, it } from "vitest";

import { aggregate, exitCodeFor, formatReport, type CaseResult } from "../src/aggregate.js";

const r = (track: "review" | "qa", id: string, verdict: CaseResult["verdict"]): CaseResult => ({
  track,
  id,
  title: `제목 ${id}`,
  verdict,
  reason: "사유",
});

describe("aggregate", () => {
  it("전체와 트랙별을 함께 센다", () => {
    const summary = aggregate([
      r("review", "1", "pass"),
      r("review", "2", "fail"),
      r("qa", "3", "pass"),
      r("qa", "4", "error"),
    ]);
    expect(summary).toMatchObject({ total: 4, passed: 2, failed: 1, errored: 1 });
    expect(summary.byTrack.review).toEqual({ total: 2, passed: 1, failed: 1, errored: 0 });
    expect(summary.byTrack.qa).toEqual({ total: 2, passed: 1, failed: 0, errored: 1 });
  });

  it("빈 입력이면 전부 0 이고 트랙 칸은 남아 있다", () => {
    const summary = aggregate([]);
    expect(summary.total).toBe(0);
    expect(summary.byTrack.qa.total).toBe(0);
  });
});

describe("exitCodeFor", () => {
  it("전부 통과면 0", () => {
    expect(exitCodeFor(aggregate([r("review", "1", "pass")]))).toBe(0);
  });

  it("하나라도 실패하면 1", () => {
    expect(exitCodeFor(aggregate([r("review", "1", "pass"), r("qa", "2", "fail")]))).toBe(1);
  });

  it("오류도 1 — 못 잰 것을 통과로 세면 게이트가 조용히 죽는다", () => {
    expect(exitCodeFor(aggregate([r("review", "1", "pass"), r("qa", "2", "error")]))).toBe(1);
  });

  it("케이스 0건도 1 — 빈 분모는 언제나 깨끗하다", () => {
    expect(exitCodeFor(aggregate([]))).toBe(1);
  });
});

describe("formatReport", () => {
  it("실패 사유는 찍고 통과 사유는 안 찍는다", () => {
    const results = [r("review", "1", "pass"), r("review", "2", "fail")];
    const text = formatReport(results, aggregate(results));
    expect(text).toContain("PASS  1");
    expect(text).toContain("FAIL  2");
    expect(text).toContain("사유");
    expect(text).toContain("합계 1/2 통과");
  });
});
