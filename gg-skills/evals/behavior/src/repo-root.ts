// 레포 루트 찾기 — 상위 폴더 개수를 세지 않는다.
//
// 왜: 이 폴더는 이미 두 번 옮겨졌다(루트 evals/ → .dev/harness/evals/behavior/).
// `path.resolve(HERE, "..", "..")` 처럼 깊이를 박아두면 다음 이사에서 조용히 엉뚱한
// 폴더를 가리킨다 — 파일을 못 찾으면 예외가 나지만, 찾아버리면 더 나쁘다.

import fs from "node:fs";
import path from "node:path";

/** `.git` 과 `CLAUDE.md` 가 함께 있는 첫 상위 폴더. 워크트리는 `.git` 이 파일이라 둘 다 받는다. */
export function findRepoRoot(start: string): string {
  let dir = path.resolve(start);
  while (true) {
    if (fs.existsSync(path.join(dir, ".git")) && fs.existsSync(path.join(dir, "CLAUDE.md"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      throw new Error(`레포 루트를 못 찾았다 (.git + CLAUDE.md 가 함께 있는 폴더). 시작점: ${start}`);
    }
    dir = parent;
  }
}
