// 레포 루트 `.env` 로더 — **import 되는 순간 한 번 돈다**(부수효과).
//
// 왜 필요한가 (2026-08-13): README 는 `ANTHROPIC_API_KEY 필요` 라고만 적어놨는데
// 어디서 읽는지를 안 적었다. 사장님이 `.env` 에 넣었는데 `run.ts` 는 `process.env`
// 만 봐서 **넣어도 아무 일이 안 일어났다**. 이 레포의 다른 도구는 전부 `.env` 를
// 보므로 여기도 같은 자리를 봐야 한다.
//
// ⚠️ 의존성을 새로 붙이지 않았다(dotenv 미사용) — 이 폴더는 **핀 고정된 최소 의존**이
//    원칙이고, 파서는 순수함수라 키 없이 vitest 로 검증된다.
// ⚠️ 값은 어디에도 로그로 남기지 않는다. 내보내는 건 **키 이름뿐**이다.
import fs from "node:fs";

import { ENV_PATH } from "./target.js";

const KEY = /^[A-Za-z_][A-Za-z0-9_]*$/;

/** `.env` 텍스트 → {키: 값}. 순수함수(파일도 process.env 도 안 건드린다). */
export function parseEnvFile(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of text.split(/\r?\n/)) {
    let line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("export ")) line = line.slice(7).trim();
    const eq = line.indexOf("=");
    // ⚠️ `=` 가 없는 줄은 **버린다.** 값만 덜렁 붙여넣은 줄(`sk-ant-…`)이 여기 해당하는데,
    //    이름 없는 값은 무엇으로 쓸지 알 수 없다. 조용히 주워 쓰면 더 위험하다.
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    if (!KEY.test(key)) continue;
    let val = line.slice(eq + 1).trim();
    if (val.length >= 2 && ((val.startsWith('"') && val.endsWith('"')) ||
                            (val.startsWith("'") && val.endsWith("'")))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

/**
 * `.env` 를 읽어 **아직 없는 키만** `process.env` 에 채운다.
 * 반환값은 실제로 채운 **키 이름 목록**(값 아님).
 *
 * ⚠️ 이미 있는 환경변수가 이긴다 — 셸에서 일부러 덮어쓴 걸 파일이 되돌리면 안 된다.
 */
export function applyEnvFile(file: string, env: NodeJS.ProcessEnv = process.env): string[] {
  let text: string;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch {
    return [];   // .env 가 없는 건 정상이다(CI·새 클론)
  }
  const applied: string[] = [];
  for (const [k, v] of Object.entries(parseEnvFile(text))) {
    if (env[k] === undefined || env[k] === "") {
      env[k] = v;
      applied.push(k);
    }
  }
  return applied;
}

/** 이 모듈을 import 하면 자동으로 채워진 키 이름들. run.ts 가 한 줄로 보고한다.
 *
 * ⚠️ 읽는 건 **대상 레포의 `.env`** 다 — 프레임워크가 사는 플러그인 폴더가 아니다.
 * ⚠️ 워크트리에서 돌리면 그 워크트리의 `.env` 를 본다. `wt.ps1` 이 만들 때 뜬 **사본**이라
 *    본체에 키를 나중에 넣어도 안 따라온다(2026-08-13 에 여기서 한 번 헛돌았다).
 */
export const LOADED_KEYS: string[] = (() => {
  try {
    return applyEnvFile(ENV_PATH);
  } catch {
    return [];
  }
})();
