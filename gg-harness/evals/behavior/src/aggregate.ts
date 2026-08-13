// 집계와 종료코드 — 순수함수.

import { TRACKS, type Track } from "./cases.js";

export type ResultVerdict = "pass" | "fail" | "error";

export interface CaseResult {
  track: Track;
  id: string;
  title: string;
  verdict: ResultVerdict;
  reason: string;
  /** 진단용 — subject 원문 발췌 */
  detail?: string;
}

export interface TrackTally {
  total: number;
  passed: number;
  failed: number;
  errored: number;
}

export interface Summary {
  total: number;
  passed: number;
  failed: number;
  errored: number;
  byTrack: Record<Track, TrackTally>;
}

function emptyTally(): TrackTally {
  return { total: 0, passed: 0, failed: 0, errored: 0 };
}

export function aggregate(results: CaseResult[]): Summary {
  const byTrack = Object.fromEntries(TRACKS.map((t) => [t, emptyTally()])) as Record<Track, TrackTally>;
  const overall = emptyTally();

  for (const r of results) {
    const tally = byTrack[r.track];
    tally.total += 1;
    overall.total += 1;
    if (r.verdict === "pass") {
      tally.passed += 1;
      overall.passed += 1;
    } else if (r.verdict === "fail") {
      tally.failed += 1;
      overall.failed += 1;
    } else {
      tally.errored += 1;
      overall.errored += 1;
    }
  }

  return { ...overall, byTrack };
}

/**
 * 하나라도 실패하면 1.
 * error 도 1이다 — 못 잰 것을 통과로 세면 게이트가 조용히 죽는다.
 * total=0 도 1이다 — 빈 분모는 언제나 깨끗하게 나온다.
 */
export function exitCodeFor(summary: Summary): 0 | 1 {
  if (summary.total === 0) return 1;
  return summary.failed > 0 || summary.errored > 0 ? 1 : 0;
}

const MARK: Record<ResultVerdict, string> = { pass: "PASS", fail: "FAIL", error: "ERR " };

export function formatReport(results: CaseResult[], summary: Summary): string {
  const lines: string[] = [];

  for (const track of TRACKS) {
    const inTrack = results.filter((r) => r.track === track);
    if (inTrack.length === 0) continue;
    const tally = summary.byTrack[track];
    lines.push(`\n[${track}] ${tally.passed}/${tally.total} 통과` + (tally.errored ? ` · 오류 ${tally.errored}` : ""));
    for (const r of inTrack) {
      lines.push(`  ${MARK[r.verdict]}  ${r.id} — ${r.title}`);
      if (r.verdict !== "pass") lines.push(`        ${r.reason}`);
    }
  }

  lines.push("");
  lines.push(
    `합계 ${summary.passed}/${summary.total} 통과` +
      (summary.failed ? ` · 실패 ${summary.failed}` : "") +
      (summary.errored ? ` · 오류 ${summary.errored}` : ""),
  );

  if (summary.total === 0) {
    lines.push("케이스가 0건이라 실패로 처리한다 — 빈 분모는 언제나 통과한다.");
  }

  return lines.join("\n");
}
