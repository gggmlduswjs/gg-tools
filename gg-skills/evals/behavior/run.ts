#!/usr/bin/env tsx
/**
 * 하네스 품질 회귀 게이트.
 *
 *   npm run eval                 두 트랙 전부
 *   npm run eval -- --track qa   한 트랙만 (비용 절약)
 *
 * 하나라도 실패하거나 오류가 나면 exit 1.
 * 네트워크와 비용이 붙는 유일한 진입점이다 — 순수 로직 검증은 `npm test`.
 */
// ⚠️★ **이 줄이 맨 앞이어야 한다.** import 는 선언 순서대로 평가되고 `config.ts` 의 상수는
//    import 시점에 `process.env` 를 읽는다. 아래로 내려가면 `.env` 가 늦게 실려
//    `EVAL_*` 설정이 조용히 기본값으로 돈다.
import { LOADED_KEYS } from "./src/env.js";

import fs from "node:fs";
import path from "node:path";

import { aggregate, exitCodeFor, formatReport, type CaseResult } from "./src/aggregate.js";
import { checkBalance } from "./src/balance.js";
import { TRACKS, loadAllCases, type EvalCase, type Track } from "./src/cases.js";
import { runJudge, runSubject } from "./src/client.js";
import { CONCURRENCY, JUDGE_MODEL, PROVIDER, SUBJECT_MODEL, SUBJECT_TEMPERATURE } from "./src/config.js";
import {
  QA_JUDGE_SCHEMA,
  REVIEW_JUDGE_SCHEMA,
  buildQaJudgePrompt,
  buildQaSubjectPrompt,
  buildReviewJudgePrompt,
} from "./src/judge-prompt.js";
import {
  CASES_DIR,
  CLAUDE_MD_PATH,
  REPO_ROOT,
  RESULTS_DIR,
  REVIEWER_SYSTEM_PATH,
} from "./src/target.js";
import { qaVerdict, reviewVerdict, type FactCheck, type ReviewObservation } from "./src/verdict.js";

// ⚠️★ 경로는 전부 **대상 레포** 기준이다(`src/target.ts`) — 이 파일이 사는 자리가 아니다.
//    프레임워크는 플러그인에 한 벌, cases·prompts·results 는 각 레포에 있다.
//    ★음성 대조: `EVAL_REVIEWER_SYSTEM=prompts/reviewer-system.degraded.md`
//      정본 파일을 손으로 바꿔치기하지 마라 — 복원을 잊으면 게이트가 조용히 무력해진다.

function parseTrackFlag(argv: string[]): Track | null {
  const i = argv.indexOf("--track");
  if (i === -1) return null;
  const value = argv[i + 1];
  if (!value || !TRACKS.includes(value as Track)) {
    throw new Error(`--track 은 ${TRACKS.join("|")} 중 하나여야 한다 (받은 값: ${value ?? "없음"})`);
  }
  return value as Track;
}

async function mapLimit<T, R>(items: T[], limit: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const results = new Array<R>(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    while (true) {
      const index = cursor++;
      if (index >= items.length) return;
      results[index] = await fn(items[index] as T);
    }
  });
  await Promise.all(workers);
  return results;
}

async function runOne(kase: EvalCase, reviewerSystem: string, liveClaudeMd: string): Promise<CaseResult> {
  const base = { track: kase.track, id: kase.id, title: kase.title } as const;
  try {
    if (kase.track === "review") {
      const output = await runSubject({ system: reviewerSystem, user: kase.input });
      const observation = await runJudge<ReviewObservation>(
        buildReviewJudgePrompt(kase, output),
        REVIEW_JUDGE_SCHEMA,
      );
      const judged = reviewVerdict(kase, observation);
      return { ...base, ...judged, detail: output.slice(0, 600) };
    }

    const answer = await runSubject(buildQaSubjectPrompt(kase, liveClaudeMd));
    const { checks } = await runJudge<{ checks: FactCheck[] }>(
      buildQaJudgePrompt(kase, answer),
      QA_JUDGE_SCHEMA,
    );
    const judged = qaVerdict(kase, checks);
    return { ...base, ...judged, detail: answer.slice(0, 600) };
  } catch (error) {
    return { ...base, verdict: "error", reason: error instanceof Error ? error.message : String(error) };
  }
}

async function main(): Promise<void> {
  const trackFilter = parseTrackFlag(process.argv.slice(2));

  // 균형 검사는 필터와 무관하게 **전체** 케이스에 건다.
  // --track 으로 절반만 돌리고 게이트를 통과했다고 말하면 안 된다.
  const allCases = loadAllCases(CASES_DIR);
  const problems = checkBalance(allCases);
  if (problems.length > 0) {
    console.error("golden set 균형 검사 실패 — 라이브 채점을 시작하지 않는다:");
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }

  const cases = trackFilter ? allCases.filter((c) => c.track === trackFilter) : allCases;

  const reviewerSystem = fs.readFileSync(REVIEWER_SYSTEM_PATH, "utf8");
  const liveClaudeMd = fs.readFileSync(CLAUDE_MD_PATH, "utf8");

  console.log(
    [
      `케이스 ${cases.length}건${trackFilter ? ` (--track ${trackFilter})` : ""}`,
      `subject=${SUBJECT_MODEL}${SUBJECT_TEMPERATURE === undefined ? "" : ` temp=${SUBJECT_TEMPERATURE}`}`,
      `judge=${JUDGE_MODEL}`,
      `provider=${PROVIDER}`,
      `동시 ${CONCURRENCY}`,
    ].join(" · "),
  );
  // ⚠️ 값은 절대 로그에 남기지 않는다. 이 eval 이 쓰는 변수의 **이름만** 보고한다
  //    (.env 에는 무관한 키가 수십 개라 전부 찍으면 노이즈다).
  const mine = LOADED_KEYS.filter((k) => k.startsWith("EVAL_") || k.startsWith("ANTHROPIC_") || k.startsWith("OPENAI_"));
  console.log(`.env 에서 채운 설정: ${mine.length ? mine.join(", ") : "없음(셸 환경변수 사용)"}`);
  // ⚠️ 프롬프트 경로를 **실제 값으로** 찍는다 — 음성 대조로 갈아끼운 걸 모르고
  //    "5/5 통과" 를 정상으로 읽는 일이 없어야 한다.
  console.log(`대상 레포: ${REPO_ROOT}`);
  console.log(`review 시스템 프롬프트: ${path.relative(REPO_ROOT, REVIEWER_SYSTEM_PATH)}`);
  console.log(`qa 컨텍스트: ${path.relative(REPO_ROOT, CLAUDE_MD_PATH)} (라이브, ${liveClaudeMd.length}자)`);

  const results = await mapLimit(cases, CONCURRENCY, (kase) => runOne(kase, reviewerSystem, liveClaudeMd));
  const summary = aggregate(results);

  console.log(formatReport(results, summary));

  fs.mkdirSync(RESULTS_DIR, { recursive: true });
  const snapshot = {
    // 시각은 실행할 때 찍는다. 이 파일은 gitignore 다 — 로컬 값이 커밋되면 스냅샷이 거짓말한다.
    ran_at: new Date().toISOString(),
    provider: PROVIDER,
    subject_model: SUBJECT_MODEL,
    judge_model: JUDGE_MODEL,
    track_filter: trackFilter,
    summary,
    results,
  };
  const out = path.join(RESULTS_DIR, "latest.json");
  fs.writeFileSync(out, JSON.stringify(snapshot, null, 2), "utf8");
  console.log(`\n결과: ${path.relative(REPO_ROOT, out)}`);

  process.exit(exitCodeFor(summary));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : error);
  process.exit(1);
});
