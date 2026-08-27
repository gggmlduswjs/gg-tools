import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { findRepoRoot } from "../src/repo-root.js";

function scratch(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "eval-root-"));
}

// ⚠️ 2026-08-13 이관 후로는 **자기 위치로 레포를 찾지 않는다.** 이 프레임워크는
//    플러그인(`~/claude/gg-harness/evals/behavior/`)에 살고 대상 레포는 밖에 있어서,
//    `import.meta.dirname` 에서 위로 올라가면 플러그인 레포를 찾거나 못 찾는다.
//    그래서 테스트도 임시 폴더로 짓는다 — 어디서 돌려도 같은 결과여야 한다.
function fakeRepo(): string {
  const dir = scratch();
  fs.writeFileSync(path.join(dir, ".git"), "gitdir: /elsewhere\n");
  fs.writeFileSync(path.join(dir, "CLAUDE.md"), "#");
  return fs.realpathSync(dir);
}

describe("findRepoRoot", () => {
  it("`.git`+`CLAUDE.md` 가 함께 있는 루트를 찾는다", () => {
    const root = fakeRepo();
    expect(findRepoRoot(root)).toBe(root);
  });

  it("몇 단계 아래에서 시작해도 같은 루트를 찾는다 — 깊이를 안 센다", () => {
    const root = fakeRepo();
    const deep = path.join(root, "a", "b", "c");
    fs.mkdirSync(deep, { recursive: true });
    expect(findRepoRoot(deep)).toBe(root);
    expect(findRepoRoot(path.join(root, "a"))).toBe(root);
  });

  it(".git 이 파일이어도 받는다 (워크트리)", () => {
    const dir = scratch();
    fs.writeFileSync(path.join(dir, ".git"), "gitdir: /elsewhere\n");
    fs.writeFileSync(path.join(dir, "CLAUDE.md"), "#");
    const nested = path.join(dir, "a", "b");
    fs.mkdirSync(nested, { recursive: true });
    expect(findRepoRoot(nested)).toBe(fs.realpathSync(dir));
  });

  it("CLAUDE.md 없이 .git 만 있으면 지나친다 — 둘 다 있어야 한다", () => {
    const dir = scratch();
    fs.mkdirSync(path.join(dir, ".git"));
    const nested = path.join(dir, "a");
    fs.mkdirSync(nested);
    expect(() => findRepoRoot(nested)).toThrow(/레포 루트를 못 찾았다/);
  });

  it("못 찾으면 시작점을 담아 던진다 — 조용히 엉뚱한 폴더를 고르지 않는다", () => {
    const dir = scratch();
    expect(() => findRepoRoot(dir)).toThrow(new RegExp(dir.replace(/\\/g, "\\\\")));
  });
});
