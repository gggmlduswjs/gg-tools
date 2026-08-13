// frontmatter 파서 — 순수함수. 외부 yaml 의존성을 두지 않는 이유:
// 이 파서 자체가 golden set 무결성의 1차 관문이라 키 없이 vitest 로 직접 검증돼야 한다.
// 지원 문법은 케이스 파일이 실제로 쓰는 것만: 스칼라, 불리언, 숫자, `- ` 목록.

export type FrontmatterValue = string | boolean | number | string[];
export type Frontmatter = Record<string, FrontmatterValue>;

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

const DELIMITER = "---";

/** `---` 블록과 본문을 가른다. 블록이 없거나 닫히지 않으면 던진다. */
export function splitFrontmatter(source: string): { raw: string; body: string } {
  const normalized = source.replace(/\r\n/g, "\n").replace(/^﻿/, "");
  const lines = normalized.split("\n");

  if (lines[0]?.trim() !== DELIMITER) {
    throw new Error("frontmatter 가 없다 — 파일이 `---` 로 시작해야 한다");
  }

  const closing = lines.findIndex((line, i) => i > 0 && line.trim() === DELIMITER);
  if (closing === -1) {
    throw new Error("frontmatter 가 닫히지 않았다 — 두 번째 `---` 줄이 없다");
  }

  return {
    raw: lines.slice(1, closing).join("\n"),
    body: lines.slice(closing + 1).join("\n").trim(),
  };
}

function coerceScalar(text: string): FrontmatterValue {
  const trimmed = text.trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"') && trimmed.length >= 2) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'") && trimmed.length >= 2)
  ) {
    return trimmed.slice(1, -1);
  }
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  return trimmed;
}

/** frontmatter 본문(구분자 제외)을 키/값으로 읽는다. */
export function parseFrontmatter(raw: string): Frontmatter {
  const out: Frontmatter = {};
  let currentListKey: string | null = null;

  for (const line of raw.split("\n")) {
    if (line.trim() === "" || line.trimStart().startsWith("#")) continue;

    const listItem = /^\s*-\s+(.*)$/.exec(line);
    if (listItem) {
      if (currentListKey === null) {
        throw new Error(`목록 항목에 대응하는 키가 없다: ${line.trim()}`);
      }
      (out[currentListKey] as string[]).push(String(coerceScalar(listItem[1] ?? "")));
      continue;
    }

    const separator = line.indexOf(":");
    if (separator === -1) {
      throw new Error(`frontmatter 줄에 ':' 이 없다: ${line.trim()}`);
    }

    const key = line.slice(0, separator).trim();
    if (key === "") throw new Error(`frontmatter 키가 비었다: ${line.trim()}`);
    if (key in out) throw new Error(`frontmatter 키가 중복이다: ${key}`);

    const value = line.slice(separator + 1);
    if (value.trim() === "") {
      // 값이 비면 뒤따르는 `- ` 줄들을 목록으로 모은다. 목록이 안 오면 빈 배열.
      out[key] = [];
      currentListKey = key;
    } else {
      out[key] = coerceScalar(value);
      currentListKey = null;
    }
  }

  return out;
}

export function parseDocument(source: string): ParsedDocument {
  const { raw, body } = splitFrontmatter(source);
  return { frontmatter: parseFrontmatter(raw), body };
}

// ── frontmatter 값을 타입으로 좁히는 헬퍼 (케이스 검증에서 쓴다) ──

export function requireString(fm: Frontmatter, key: string, where: string): string {
  const value = fm[key];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${where}: '${key}' 는 비어 있지 않은 문자열이어야 한다`);
  }
  return value;
}

export function requireStringList(fm: Frontmatter, key: string, where: string): string[] {
  const value = fm[key];
  if (!Array.isArray(value)) {
    throw new Error(`${where}: '${key}' 는 '- ' 목록이어야 한다`);
  }
  const empty = value.findIndex((item) => item.trim() === "");
  if (empty !== -1) {
    throw new Error(`${where}: '${key}' 의 ${empty + 1}번째 항목이 비었다`);
  }
  return value;
}

export function optionalStringList(fm: Frontmatter, key: string, where: string): string[] {
  if (!(key in fm)) return [];
  return requireStringList(fm, key, where);
}
