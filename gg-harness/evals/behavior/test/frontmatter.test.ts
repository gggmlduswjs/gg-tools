import { describe, expect, it } from "vitest";

import {
  optionalStringList,
  parseDocument,
  parseFrontmatter,
  requireString,
  requireStringList,
  splitFrontmatter,
} from "../src/frontmatter.js";

describe("splitFrontmatter", () => {
  it("구분자 사이를 frontmatter, 뒤를 본문으로 가른다", () => {
    const { raw, body } = splitFrontmatter("---\ntitle: 가\n---\n\n본문\n");
    expect(raw).toBe("title: 가");
    expect(body).toBe("본문");
  });

  it("CRLF 와 BOM 을 견딘다", () => {
    const { raw, body } = splitFrontmatter("﻿---\r\ntitle: 가\r\n---\r\n본문\r\n");
    expect(raw).toBe("title: 가");
    expect(body).toBe("본문");
  });

  it("frontmatter 가 없으면 던진다", () => {
    expect(() => splitFrontmatter("본문만 있다")).toThrow(/frontmatter 가 없다/);
  });

  it("닫히지 않으면 던진다", () => {
    expect(() => splitFrontmatter("---\ntitle: 가\n본문")).toThrow(/닫히지 않았다/);
  });
});

describe("parseFrontmatter", () => {
  it("스칼라·불리언·숫자를 구분한다", () => {
    expect(parseFrontmatter("a: 문자열\nb: true\nc: 12\nd: 1.5")).toEqual({
      a: "문자열",
      b: true,
      c: 12,
      d: 1.5,
    });
  });

  it("따옴표를 벗긴다", () => {
    expect(parseFrontmatter(`a: "true"`)).toEqual({ a: "true" });
  });

  it("첫 콜론만 구분자로 쓴다 — 값 안의 콜론은 살린다", () => {
    expect(parseFrontmatter("rule: paths: OUT 앵커를 써라")).toEqual({ rule: "paths: OUT 앵커를 써라" });
  });

  it("`- ` 줄을 목록으로 모은다", () => {
    expect(parseFrontmatter("must:\n  - 하나\n  - 둘\ntitle: 가")).toEqual({
      must: ["하나", "둘"],
      title: "가",
    });
  });

  it("값 없는 키에 목록이 안 오면 빈 배열이다", () => {
    expect(parseFrontmatter("must_not:\ntitle: 가")).toEqual({ must_not: [], title: "가" });
  });

  it("빈 줄과 주석을 건너뛴다", () => {
    expect(parseFrontmatter("# 메모\n\ntitle: 가")).toEqual({ title: "가" });
  });

  it("키 없는 목록 항목은 던진다", () => {
    expect(() => parseFrontmatter("  - 고아")).toThrow(/대응하는 키가 없다/);
  });

  it("콜론 없는 줄은 던진다", () => {
    expect(() => parseFrontmatter("title 가")).toThrow(/':' 이 없다/);
  });

  it("키 중복은 던진다 — 조용히 덮어쓰면 라벨이 사라진다", () => {
    expect(() => parseFrontmatter("title: 가\ntitle: 나")).toThrow(/중복/);
  });
});

describe("parseDocument", () => {
  it("frontmatter 와 본문을 함께 돌려준다", () => {
    const doc = parseDocument("---\ntitle: 가\nmust:\n  - 하나\n---\n질문 본문\n");
    expect(doc.frontmatter).toEqual({ title: "가", must: ["하나"] });
    expect(doc.body).toBe("질문 본문");
  });
});

describe("타입 좁히기 헬퍼", () => {
  it("requireString 은 빈 문자열을 거부한다", () => {
    expect(() => requireString({ a: "  " }, "a", "x")).toThrow(/비어 있지 않은 문자열/);
    expect(() => requireString({ a: true }, "a", "x")).toThrow();
    expect(requireString({ a: "값" }, "a", "x")).toBe("값");
  });

  it("requireStringList 는 목록이 아니면 거부한다", () => {
    expect(() => requireStringList({ a: "값" }, "a", "x")).toThrow(/목록이어야 한다/);
    expect(requireStringList({ a: ["값"] }, "a", "x")).toEqual(["값"]);
  });

  it("requireStringList 는 빈 항목을 거부한다", () => {
    expect(() => requireStringList({ a: ["값", "  "] }, "a", "x")).toThrow(/2번째 항목이 비었다/);
  });

  it("optionalStringList 는 키가 없으면 빈 배열이다", () => {
    expect(optionalStringList({}, "a", "x")).toEqual([]);
  });
});
