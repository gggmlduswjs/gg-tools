import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { dataDir, resolveRepoRoot } from "../src/target.js";

function scratch(): string {
  return fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "eval-target-")));
}

function fakeRepo(): string {
  const dir = scratch();
  fs.writeFileSync(path.join(dir, ".git"), "gitdir: /elsewhere\n");
  fs.writeFileSync(path.join(dir, "CLAUDE.md"), "#");
  return dir;
}

describe("resolveRepoRoot", () => {
  it("EVAL_REPO 가 있으면 그걸 쓴다 — 프레임워크 위치와 무관하다", () => {
    const repo = fakeRepo();
    expect(resolveRepoRoot({ EVAL_REPO: repo }, "/아무데나")).toBe(path.resolve(repo));
  });

  it("EVAL_REPO 의 공백은 무시한다", () => {
    const repo = fakeRepo();
    expect(resolveRepoRoot({ EVAL_REPO: `  ${repo}  ` }, "/아무데나")).toBe(path.resolve(repo));
  });

  it("EVAL_REPO 가 없으면 현재 폴더에서 위로 찾는다 (레포 안에서 돌릴 때)", () => {
    const repo = fakeRepo();
    const deep = path.join(repo, "x", "y");
    fs.mkdirSync(deep, { recursive: true });
    expect(resolveRepoRoot({}, deep)).toBe(repo);
  });

  it("⚠️ 둘 다 실패하면 EVAL_REPO 를 주라고 말하며 던진다 — 조용히 엉뚱한 곳을 고르지 않는다", () => {
    expect(() => resolveRepoRoot({}, scratch())).toThrow(/EVAL_REPO/);
  });
});

describe("dataDir", () => {
  it("레포마다 같은 규약 자리를 쓴다", () => {
    expect(dataDir(path.join("C:", "repo"))).toBe(
      path.join("C:", "repo", ".dev", "harness", "evals", "behavior"),
    );
  });
});
