---
name: owasp-security-scan
description: 레포 전체를 OWASP Top 10 2025에 따라 코드 근거 중심으로 점검한다. "보안 감사", "OWASP 점검", "레포 전체 취약점 스캔" 요청에 사용한다. 단 레포에 전용 보안 감사 스킬(예 bookmart-security-scan)이 있으면 그것을 우선 실행하고 범용 스킬은 명시적으로 요구하거나 전용 스킬이 없는 경우에만 사용한다. 지원 언어/도구의 커버리지 공백을 명시하고 검증된 발견과 미검증 단서를 구분한다.
user-invocable: true
---

# OWASP Top 10 2025 Security Scan

레포를 **OWASP Top 10 2025**(https://owasp.org/Top10/2025/) 기준으로 점검한다. 방식은 **하이브리드**:

1. **결정론적 레이어** (`scripts/scan.py`) — npm audit(A03)·시크릿 정규식·카테고리 lead-grep. 빠르고 정밀, LLM 0.
2. **LLM 레이어** — 카테고리 번들별 병렬 서브에이전트가 lead와 코드를 직접 읽어 판정. grep이 못 보는 의미·설계 결함을 잡는다.
3. **검증 레이어** — critical/high finding을 skeptic 에이전트가 반박(다수결)해 false positive 제거.


**호출 우선순위:** 로컬 전용 보안 스킬이 있으면 그 스킬을 먼저 사용하고 이 스킬을 중복 실행하지 않는다. 동시에 둘을 실행하는 것은 사용자가 각각의 관점을 명시적으로 요청할 때만 허용한다.

> 이 스킬은 **전체 레포 감사**가 기본이다. PR 변경분 리뷰는 `/review-code`(차원별·diff 기반)가 담당한다 — 역할이 다르다.

## When to use
- "보안 스캔/점검/감사 해줘", "security scan/audit", "OWASP로 점검"
- "이 레포(코드) 안전한지 봐줘", "취약점 있나 봐줘"
- 키워드 없이도 보안 취약점 전반 점검을 원하면 트리거

## 0. 범위 결정
- **인자 없음 → 전체 레포**(`scope = "full repository"`).
- 인자가 경로면 그 경로로 한정(예: `src/app/api` → `scope`에 표기, 에이전트에 범위 전달).
- 인자가 git 범위(`main...HEAD` 등)면 변경분 한정 스캔(scope에 표기).

## 1. 결정론적 pre-scan
출력 경로는 레포에 `docs/`가 있으면 `docs/`, 없으면 `.claude/`. (사용자가 경로 지정 시 그 경로 우선.)

```bash
python3 <실제_스킬_경로>/scripts/scan.py <repo-path> \
  --json <scratchpad>/owasp-prescan.json --scope "<scope label>"
```

- Python 3.10+ 표준 라이브러리로 실행한다. **먼저 설치된 플러그인에서 이 스킬의 실제 디렉터리**를 찾고 그 안의 `scripts/scan.py` 경로를 사용한다. 프로젝트의 `.claude/skills/`에 플러그인 파일이 복사돼 있다고 가정하지 않는다.
- 미설치 스캐너(osv-scanner/gitleaks/semgrep)는 graceful skip + `coverage_notes`에 공백 기록. Python 의존성 감사는 `npm audit`으로 대체할 수 없으므로 해당 도구를 별도로 사용하지 않았다면 커버리지 공백으로 보고한다.
- 산출 JSON: `meta·tools·coverage_notes·supply_chain(npm audit)·secrets·leads{A01,A02,A04,A05,A08,A10}·summary`.
- leads는 **단서**다(판정 아님). secrets의 `env_ref:true`는 placeholder/환경변수 참조 → 실제 비밀 아님.

## 2. 가드레일 문서 읽기
`CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/ADR.md` 또는 프로젝트가 지정한 동등한 현재 문서를 읽어 **해당 레포의 보안·운영 규칙**만 추린다. 특정 프로젝트의 스택이나 정책을 다른 레포에 가정하지 않는다.

## 3. 카테고리 번들별 병렬 리뷰 (LLM 레이어)
10개 카테고리를 **5개 번들**로 묶어 현재 환경의 agent 도구(Claude `Agent`, Codex `spawn_agent`)로 나눈다. 동시 실행 한도를 넘으면 번들을 순서대로 배정하고, agent 도구가 없으면 직접 순서대로 검사한다. 각 에이전트는 **read-only**(파일을 수정하지 마라):

| 번들 | 담당 카테고리 |
|---|---|
| B1 Access & Auth | A01 Broken Access Control · A07 Authentication Failures |
| B2 Injection & Misconfig | A05 Injection · A02 Security Misconfiguration |
| B3 Crypto & Integrity | A04 Cryptographic Failures · A08 Software/Data Integrity Failures |
| B4 Supply Chain & Design | A03 Software Supply Chain · A06 Insecure Design |
| B5 Logging & Exceptions | A09 Logging/Alerting Failures · A10 Mishandling of Exceptional Conditions |

각 에이전트 프롬프트 템플릿(`<...>` 채워서 전달):

```
너는 현재 대상 레포의 보안 감사관이다. OWASP Top 10 2025 중 <카테고리들>만 점검한다. read-only — 파일을 수정하지 마라.

먼저 다음을 읽어라:
- 루브릭: 현재 설치된 이 스킬의 `references/owasp-2025.md` (담당 카테고리 섹션 집중)
- 결정론 pre-scan 결과: <prescan.json 경로> (특히 leads의 담당 카테고리, supply_chain, secrets)

가드레일(대상 레포에서 확인된 규칙만):
<CLAUDE.md/ARCHITECTURE/ADR 요약>

점검 범위: <scope> (전체 레포면 실제로 사용하는 언어·프레임워크·설정·인증·배포 경로 중심)

규칙:
- lead는 단서일 뿐이다. 코드를 직접 Read/Grep해 실제 의미로 확인하거나 기각하라. grep이 못 본 문제도 적극적으로 찾아라.
- 추측 금지. 모든 finding은 파일:라인 + 코드 인용 근거가 있어야 한다.
- coverage gap(미설치 도구로 못 본 영역)은 finding이 아니다 — 보고하지 마라(메인이 따로 처리).
- 담당 카테고리에 문제가 없으면 그 카테고리 finding을 비우고 category_notes에 "확인된 위반 없음 + 근거"를 1줄로.
- A03는 실제 `package.json`이 있고 npm 감사가 성공한 경우에만 해당 `supply_chain` 결과를 확인한다. Python 등 타 생태계는 관련 감사 도구의 미실행 여부를 coverage gap에 적는다. 발견된 의존성의 직접/간접 여부를 근거에 명시한다.

severity(보안 표준): critical · high · medium · low · info (루브릭의 가이드 따름).

**오직 아래 JSON만** 출력하라(설명 텍스트 금지):
{
  "findings": [
    { "owasp": "A01", "severity": "high", "title": "...", "file": "src/...", "line": 42,
      "evidence": "무엇이 왜 취약한가 + 코드 근거", "fix": "구체적 수정", "confidence": "high|medium|low" }
  ],
  "category_notes": { "A01": "...", "A07": "..." }
}
```

> 번들이 너무 무거우면 카테고리당 1개(최대 10개)로 쪼개도 된다. 반대로 가벼운 레포면 그대로 5개로 충분.

## 4. Adversarial 검증 (critical/high만)
모든 번들의 finding을 모은 뒤, **severity가 critical 또는 high인 것만** 검증한다(medium/low/info는 `verified:false`로 그대로 싣되 대시보드에서 "미검증" 태그).

각 critical/high finding마다 skeptic 에이전트를 소환해 반박시킨다(critical은 3명·2/3 다수결, high는 1명). 프롬프트:

```
다음 보안 finding이 진짜 취약점인지 반박하라. 의심부터 하고, 확신이 없으면 isReal=false를 기본값으로.
[<severity>] <owasp> <title>
위치: <file>:<line>
근거: <evidence>
제안 수정: <fix>

코드를 직접 Read해 교차검증하라: 실제로 악용 가능한가? 이미 다른 레이어(RLS·미들웨어·서명검증 등)가 막고 있지 않은가? 존재하지 않는 라인/오해는 아닌가?
오직 JSON만: { "isReal": true|false, "confidence": "low|medium|high", "reason": "한 줄" }
```

- 다수결 통과한 것만 `verified:true`. 탈락은 최종 리스트에서 **제외**(또는 severity를 낮춰 info로 강등하지 말고 제거).
- 검증 호출이 15건을 넘으면 상한을 두고 초과분은 미검증으로 싣되 **상한 도달을 사용자에게 1줄 고지**(silent cap 금지).

## 5. 집계 + 대시보드 생성
**posture 판정:**
- verified critical ≥ 1 → **Vulnerable** (level `red`)
- critical 0, verified high ≥ 1 → **At Risk** (level `amber`)
- high 0, medium ≥ 1 → **Hardening Needed** (level `amber`)
- 그 외(검증된 위험 없음) → **점검 범위 내 심각 위험 미확인** (level `green`; 검사하지 못한 축은 coverage gap으로 별도 강조, 전체 레포 안전 보증 금지)

`assets/template.html`을 출력 경로로 복사한 뒤 **`<script id="scan-data">` JSON 블록만 교체**한다(HTML/CSS·렌더러는 건드리지 마라). 채울 필드:
- `repo·scope·date(오늘)·branch·files_scanned`(pre-scan meta에서)
- `posture {label, level, desc}` — desc는 최약 카테고리 1~2개를 한 줄로
- `counts {critical,high,medium,low,info}` — 최종 리스트 기준
- `categories[10]` — 각 `{id,name,max,status}`. `max`는 그 카테고리 최고 severity(없으면 `"clean"`), `status`는 category_notes/대표 finding 1줄
- `findings[]` — `{owasp,severity,title,file,line,evidence,fix,confidence,verified}`
- `coverage {ran[], gaps[]}` — `ran`은 실제 실행한 점검, `gaps`는 pre-scan `coverage_notes` + 범위 한정으로 못 본 영역

구조화 JSON도 함께 저장(`docs/owasp-security-scan.json` 등) — scan-data와 동일 객체. 다른 도구가 소비 가능.

```bash
open <out>/owasp-security-scan.html   # macOS. 사용자가 "열지 마라" 하면 경로만 알림
```

## 6. 요약 보고 (한 문단)
1. **posture** (예: `At Risk — verified high 1`)
2. **상위 리스크 1~3개** (severity + 한 줄)
3. **coverage 공백** (미설치 스캐너로 못 본 영역 1줄)
4. 생성된 **파일 경로**

## Style rules (non-negotiable)
- HTML은 `assets/template.html` 복사 후 **데이터만** 교체. 처음부터 쓰지 마라(디자인 일관성).
- 폰트 Inter(본문)+JetBrains Mono(숫자/코드·`.mono`), 배경 `#fafafa` light, 다크모드 없음.
- 색 팔레트는 템플릿 CSS 변수 고정. 차트 라이브러리·이모지 장식 금지(severity 점/pill만).
- 모든 finding은 **코드 근거 필수**. 추측성·일반론 finding 금지.

## Common pitfalls
- **leads를 그대로 finding으로 베끼기** — leads는 단서다. 반드시 코드로 확인. 다수는 정상(예: 정당한 service_role 웹훅 사용).
- **coverage 공백을 숨기기** — osv/gitleaks/semgrep 미설치는 정직히 `gaps`에 표기. "전부 안전"으로 과장하지 마라.
- **검증 생략하고 critical 남발** — critical/high는 adversarial 통과분만. 미검증을 critical로 싣지 마라.
- **프로젝트 전제 강요** — Django 레포에 Supabase RLS를, 결제 기능 없는 레포에 구독 등급을 요구하지 않는다. 대상 레포에 실제 존재하는 신뢰 경계와 보안 정책만 평가한다.
- **secrets의 env_ref 오인** — `env_ref:true`는 placeholder/`process.env` 참조. 실제 유출 아님.
- **diff 리뷰와 혼동** — 이건 전체 레포 감사다. PR 단위는 `/review-code`.

## Files
- `references/owasp-2025.md` — 프로젝트 중립 OWASP Top 10 2025 루브릭(카테고리별 공통 기준 + severity 가이드)
- `scripts/scan.py` — 결정론적 pre-scan(npm audit·시크릿·lead-grep → JSON). stdlib only
- `assets/template.html` — 데이터 주도형 대시보드. `scan-data` JSON만 교체하면 렌더
