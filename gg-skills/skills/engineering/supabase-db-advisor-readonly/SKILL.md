---
name: supabase-db-advisor-readonly
description: Supabase MCP get_advisors 읽기 전용 공통 점검. "DB advisor", "DB 보안·성능 점검", "RLS·인덱스 점검" 요청에 사용한다. 단 현재 레포에 전용 DB advisor 스킬(예 bookmart-db-advisor)이 있으면 그 스킬이 우선하며 공통 스킬은 보조 점검에만 쓴다. 프로젝트별 DB 인증·ref는 플러그인에 저장하지 않는다.
---

# Supabase DB Advisor Read-Only

이 스킬은 Supabase live DB 상태를 **진단만** 한다. 운영 DB 변경은 절대 직접 실행하지 않는다.

**호출 우선순위:** 해당 레포에 `.claude/skills/*db-advisor*/SKILL.md` 등 전용 스킬이 있으면 먼저 읽고 전용 스킬을 실행한다. 이 공통 스킬을 중복 실행하지 않는다. 전용 스킬이 없을 때 이 공통 진단을 사용한다. 스킬 이름만으로 실제 운영 DB 연결의 안전성을 추정하지 않는다.

## 원칙

- 현재 환경에 Supabase MCP가 연결되어 있어야 한다(Claude `.mcp.json`/MCP 설정, Codex 연결 도구 목록과 MCP 설정). Claude 인증 파일을 Codex로 복사하지 않는다.
- 운영 연결은 반드시 `read_only=true`여야 한다.
- 허용: `get_advisors(type="security")`, `get_advisors(type="performance")`
- 금지: `execute_sql`, `apply_migration`, SQL editor 지시, `dbshell` DDL, 수동 migrate
- 적용 경로: 코드/마이그레이션 파일 생성 -> 테스트/staging -> PR/main push -> CI/CD migrate

## 절차

### 1. 연결 확인

프로젝트 루트에서 먼저 확인한다.

```bash
cat .mcp.json 2>/dev/null
```

확인할 것:

- `mcpServers.supabase`가 있는가
- URL에 `read_only=true`가 있는가
- 프로젝트 ref가 현재 repo의 운영/스테이징 문서와 일치하는가

MCP 툴이 세션에 없으면 사용자에게 인증/재시작이 필요하다고 말한다. 인증은 사용자가 해야 한다.

Codex에서는 실제 노출된 `get_advisors` 도구를 찾아 사용한다. `.mcp.json`만 없다는 이유로 연결이 없다고 단정하지 않는다. 플랫폼이 `read_only=true` URL을 노출하지 않으면 연결의 읽기 전용 권한과 프로젝트를 공식 설정에서 확인한다. 확인되지 않은 운영 연결은 조회하지 않고 `미확인`으로 보고한다. 프로젝트 전용 스킬은 `.agents/skills` 및 현재 설치 목록에서도 찾는다.

### 2. advisor 실행

가능한 경우 두 축을 모두 조회한다.

```text
get_advisors(type="security")
get_advisors(type="performance")
```

프로젝트 로컬 스킬이 있으면 그 루브릭을 우선한다. 예: `.claude/skills/*db-advisor*/SKILL.md`

### 3. 분류

| 등급 | 의미 | 처리 |
|---|---|---|
| critical | 데이터 노출/권한 우회 가능 | 사람 승인 전 수정 금지 |
| high | 운영 성능/보안 리스크 큼 | 마이그레이션 제안 |
| medium | 개선 가치 있음 | 영향/비용 설명 |
| keep | 프로젝트 구조상 N/A 또는 유지 | 근거와 함께 유지 |

advisor 권고는 명령이 아니다. Django 서버가 직접 Postgres에 붙는 repo, Supabase Auth 미사용 repo, anon API 미사용 repo처럼 스택 전제가 다르면 RLS/auth 경고의 의미가 달라질 수 있다.

### 4. 출력

```markdown
## Supabase DB Advisor

연결: read-only 확인/미확인

| lint | 축 | 등급 | 판단 | 근거 | 제안 |
|---|---|---|---|---|---|

## 적용 경로
- 마이그레이션 파일:
- 검증:
- 배포:
```

## 금지

- advisor 결과를 보고 즉시 DB를 고치지 않는다.
- read-only가 아닌 MCP 연결을 사용하지 않는다.
- 프로젝트 ref, access token, API key를 플러그인 repo에 기록하지 않는다.
