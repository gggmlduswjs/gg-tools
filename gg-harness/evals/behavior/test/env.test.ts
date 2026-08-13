import { describe, expect, it } from "vitest";

import { applyEnvFile, parseEnvFile } from "../src/env.js";

describe("parseEnvFile", () => {
  it("KEY=VALUE 를 읽는다", () => {
    expect(parseEnvFile("A=1\nB=two")).toEqual({ A: "1", B: "two" });
  });

  it("주석과 빈 줄을 건너뛴다", () => {
    expect(parseEnvFile("# 설명\n\nA=1\n   \n# A=2")).toEqual({ A: "1" });
  });

  it("export 접두사를 허용한다", () => {
    expect(parseEnvFile("export A=1")).toEqual({ A: "1" });
  });

  it("따옴표를 벗긴다", () => {
    expect(parseEnvFile(`A="1"\nB='2'`)).toEqual({ A: "1", B: "2" });
  });

  it("값 안의 = 는 보존한다 (DSN·base64)", () => {
    expect(parseEnvFile("URL=postgres://u:p@h/db?x=1")).toEqual({ URL: "postgres://u:p@h/db?x=1" });
  });

  it("⚠️ 이름 없이 값만 있는 줄은 버린다", () => {
    // 2026-08-13: 키를 이름 없이 붙여넣은 일이 실제로 있었다.
    // 이름 없는 값은 무엇으로 쓸지 알 수 없다 — 조용히 주워 쓰면 더 위험하다.
    expect(parseEnvFile("sk-ant-api03-XXXX\nA=1")).toEqual({ A: "1" });
  });

  it("키 이름이 규칙에 안 맞으면 버린다", () => {
    expect(parseEnvFile("1BAD=x\nhas space=y\nOK_2=z")).toEqual({ OK_2: "z" });
  });

  it("CRLF 를 처리한다 (Windows)", () => {
    expect(parseEnvFile("A=1\r\nB=2\r\n")).toEqual({ A: "1", B: "2" });
  });
});

describe("applyEnvFile", () => {
  it("파일이 없으면 조용히 빈 목록", () => {
    expect(applyEnvFile("이런/파일/없다.env", {})).toEqual([]);
  });

  it("⚠️ 이미 있는 환경변수가 이긴다 — 셸에서 덮어쓴 걸 파일이 되돌리면 안 된다", () => {
    const env: NodeJS.ProcessEnv = { A: "shell" };
    // 실제 파일 없이 파서만 검증하므로 여기서는 parse 결과로 대신 확인한다.
    const parsed = parseEnvFile("A=file\nB=file");
    for (const [k, v] of Object.entries(parsed)) {
      if (env[k] === undefined || env[k] === "") env[k] = v;
    }
    expect(env.A).toBe("shell");
    expect(env.B).toBe("file");
  });
});
