// **대상 레포**가 어디인가. 프레임워크는 플러그인에 있고 데이터는 레포에 있으므로,
// "내 위치" 기준으로 경로를 만들면 안 된다 — 그러면 플러그인 자신을 레포로 착각한다.
//
// 계약 (2026-08-13 이관):
//   프레임워크 = `~/claude/gg-harness/evals/behavior/`  (한 벌 · npm ci 도 여기 한 번)
//   데이터      = `<레포>/.dev/harness/evals/behavior/`  (cases · prompts · results)
//
// 왜 갈랐나: 판정·집계·균형 로직은 레포와 무관하고, **무엇을 재는가는 레포마다 다르다.**
// ⚠️ 케이스 없이 프레임워크만 옮기면 그 레포는 "게이트가 생겼다"고 믿으면서 아무것도 안 잰다.
//    `balance.ts` 가 0건을 exit 1 로 잡지만, 사람이 그 exit 1 을 "설정 문제"로 읽으면 끝이다.

import path from "node:path";

import { findRepoRoot } from "./repo-root.js";

/**
 * 대상 레포 루트.
 * 1순위 `EVAL_REPO` · 2순위 현재 폴더에서 위로 `.git`+`CLAUDE.md` 찾기(레포 안에서 돌릴 때).
 */
export function resolveRepoRoot(env: NodeJS.ProcessEnv = process.env, cwd: string = process.cwd()): string {
  const explicit = env.EVAL_REPO?.trim();
  if (explicit) return path.resolve(explicit);
  try {
    return findRepoRoot(cwd);
  } catch {
    throw new Error(
      "대상 레포를 못 찾았다. 플러그인 자리에서 돌린다면 EVAL_REPO 를 줘라 — " +
        ' 예: EVAL_REPO="C:/Users/user/Desktop/쿠팡/Coupang_v2" npm run eval',
    );
  }
}

/** 데이터가 사는 자리. 레포마다 같은 규약을 쓴다. */
export function dataDir(repoRoot: string): string {
  return path.join(repoRoot, ".dev", "harness", "evals", "behavior");
}

export const REPO_ROOT = resolveRepoRoot();
export const DATA_DIR = dataDir(REPO_ROOT);
export const CASES_DIR = path.join(DATA_DIR, "cases");
export const RESULTS_DIR = path.join(DATA_DIR, "results");
export const CLAUDE_MD_PATH = path.join(REPO_ROOT, "CLAUDE.md");
export const ENV_PATH = path.join(REPO_ROOT, ".env");

/** review 시스템 프롬프트. 음성 대조는 `EVAL_REVIEWER_SYSTEM` 로 갈아끼운다(레포 상대경로). */
export const REVIEWER_SYSTEM_PATH = path.join(
  DATA_DIR,
  process.env.EVAL_REVIEWER_SYSTEM ?? path.join("prompts", "reviewer-system.md"),
);
