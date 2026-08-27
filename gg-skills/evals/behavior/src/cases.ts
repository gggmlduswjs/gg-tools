// 케이스 파싱·검증 — 순수함수. 파일 읽기는 loadCases 하나에만 있다.
//
// 라벨은 사람이 박제한다. 여기서 하는 일은 "사람이 적은 라벨이 형식상 온전한가"뿐이고,
// 라벨이 맞는지는 판단하지 않는다.

import path from "node:path";
import fs from "node:fs";
import {
  optionalStringList,
  parseDocument,
  requireString,
  requireStringList,
  type Frontmatter,
} from "./frontmatter.js";

export type Track = "review" | "qa";
export const TRACKS: readonly Track[] = ["review", "qa"];

export type ReviewExpect = "violation" | "pass";

export interface ReviewCase {
  track: "review";
  id: string;
  title: string;
  /** violation = 리뷰어가 잡아야 한다 · pass = 정상 코드라 잡으면 오탐 */
  expect: ReviewExpect;
  /** 어떤 CLAUDE.md 규칙에 걸리는가(또는 어떤 규칙을 올바르게 지키는가) */
  rule: string;
  /** expect=violation 일 때만. 리뷰어가 짚어야 할 결함 한 줄 */
  violation?: string;
  input: string;
}

export interface QaCase {
  track: "qa";
  id: string;
  title: string;
  /** 답변에 반드시 들어가야 하는 사실 */
  must: string[];
  /** 답변에 있으면 안 되는 주장 */
  must_not: string[];
  /** false_premise = 질문의 전제가 틀렸고 답변이 그걸 반박해야 한다 */
  guard?: "false_premise";
  input: string;
}

export type EvalCase = ReviewCase | QaCase;

const REVIEW_EXPECTS: readonly string[] = ["violation", "pass"];
const QA_GUARDS: readonly string[] = ["false_premise"];

function requireBody(body: string, where: string): string {
  if (body.trim() === "") throw new Error(`${where}: 본문(입력)이 비었다`);
  return body.trim();
}

export function parseReviewCase(id: string, source: string): ReviewCase {
  const where = `review/${id}`;
  const { frontmatter, body } = parseDocument(source);

  const expect = requireString(frontmatter, "expect", where);
  if (!REVIEW_EXPECTS.includes(expect)) {
    throw new Error(`${where}: 'expect' 는 violation|pass 중 하나여야 한다 (받은 값: ${expect})`);
  }

  const parsed: ReviewCase = {
    track: "review",
    id,
    title: requireString(frontmatter, "title", where),
    expect: expect as ReviewExpect,
    rule: requireString(frontmatter, "rule", where),
    input: requireBody(body, where),
  };

  if (expect === "violation") {
    // 결함 설명이 없으면 채점자가 "무엇을 잡아야 하는지" 모른 채 인상으로 판정한다.
    parsed.violation = requireString(frontmatter, "violation", where);
  } else if ("violation" in frontmatter) {
    throw new Error(`${where}: expect=pass 인데 'violation' 이 있다 — 라벨이 모순이다`);
  }

  return parsed;
}

export function parseQaCase(id: string, source: string): QaCase {
  const where = `qa/${id}`;
  const { frontmatter, body } = parseDocument(source);

  const parsed: QaCase = {
    track: "qa",
    id,
    title: requireString(frontmatter, "title", where),
    must: requireStringList(frontmatter, "must", where),
    must_not: optionalStringList(frontmatter, "must_not", where),
    input: requireBody(body, where),
  };

  if (parsed.must.length === 0) {
    throw new Error(`${where}: 'must' 가 비었다 — 채점 기준 없는 케이스는 항상 통과한다`);
  }

  if ("guard" in frontmatter) {
    const guard = requireString(frontmatter as Frontmatter, "guard", where);
    if (!QA_GUARDS.includes(guard)) {
      throw new Error(`${where}: 'guard' 는 ${QA_GUARDS.join("|")} 중 하나여야 한다 (받은 값: ${guard})`);
    }
    parsed.guard = guard as "false_premise";
  }

  return parsed;
}

export function parseCase(track: Track, id: string, source: string): EvalCase {
  return track === "review" ? parseReviewCase(id, source) : parseQaCase(id, source);
}

/** cases/<track>/*.md 를 파일명 순으로 읽는다. id = 확장자 뺀 파일명. */
export function loadCases(casesDir: string, track: Track): EvalCase[] {
  const dir = path.join(casesDir, track);
  if (!fs.existsSync(dir)) {
    throw new Error(`케이스 폴더가 없다: ${dir}`);
  }
  const files = fs
    .readdirSync(dir)
    .filter((name) => name.endsWith(".md"))
    .sort();

  if (files.length === 0) {
    throw new Error(`케이스가 0건이다: ${dir} — 빈 분모는 언제나 통과한다`);
  }

  return files.map((name) =>
    parseCase(track, name.replace(/\.md$/, ""), fs.readFileSync(path.join(dir, name), "utf8")),
  );
}

export function loadAllCases(casesDir: string): EvalCase[] {
  return TRACKS.flatMap((track) => loadCases(casesDir, track));
}
