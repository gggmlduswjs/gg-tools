# claude-skills

전역 스킬 모음. `claude` 레포의 `home/skills/` 가 정본이고 `~/.claude/skills/` 는 그걸 가리키는
**심링크**라, 여기서 고치면 곧바로 반영된다(재설치·재시작 없음).

스킬은 평소 **description 만** 컨텍스트에 올라가고(~100B), 호출될 때 본문이 로드된다.
그래서 26개가 있어도 평소 부담은 거의 없다 — 다만 **뭐가 뭔지 모르면 안 쓰게 되므로** 이 지도가 있다.

---


## 새 PC 에서

```
git clone https://github.com/gggmlduswjs/claude.git $HOME\claude
pwsh $HOME\claude\install.ps1
```

스킬만 따로 설치하지 않는다 — `install.ps1` 이 CLAUDE.md·훅·PowerShell 함수까지 같이 배치한다.

> **`/plugin` 으로 안 쓰는 이유** — 플러그인은 clone 된 캐시를 보므로 고칠 때마다 push + update 가
> 필요하고, 스킬 이름에 `claude-skills:` 네임스페이스가 붙어 호출 방식이 달라진다. 그리고 플러그인은
> skills·commands·agents·hooks·mcp 만 배치할 수 있어 CLAUDE.md·settings.json·statusline 은 어차피
> `install.ps1` 이 해야 한다. **경로를 둘로 늘려서 얻는 게 없다.**
> (2026-08-06: 매니페스트 2개를 만들어만 두고 한 번도 설치하지 않은 채 archived 레포를 가리키고
> 있어서 지웠다.)

## 🔍 진단 — 지금 상태가 어떤지 볼 때

| 스킬 | 뭘 하나 | 산출물 |
|---|---|---|
| **ai-readiness-cartography** | 레포가 얼마나 agent-friendly 한지 **100점 채점** (7카테고리) | HTML 대시보드 + ROI 액션 |
| **harness-audit** | 작업 **환경 6축**(구조·맥락·계획·실행·검증·개선)의 빈 칸 + **썩은 자산** | 판정표 + 다음 액션 |
| **codebase-visualizer** | 파일 구조를 접었다 펴는 트리로 | 인터랙티브 HTML |
| **improve-token-efficiency** | 세션 로그 파싱 → **토큰·비용 hotspot** | HTML 대시보드 + 절감안 |

> **ai-readiness vs harness-audit** — 앞은 *코드베이스*가 읽기 좋은지(정량 점수), 뒤는 *환경*이 갖춰졌는지(빈 칸 찾기).
> harness-audit 은 구조·맥락 점수를 ai-readiness 에 위임한다. 둘 다 필요하면 ai-readiness 먼저.

### forge — 코드베이스를 「판」으로 놓고 보기

| 스킬 | 뭘 하나 | 산출물 |
|---|---|---|
| **arch-forge** | C4 L1~L3 + Clean Architecture 링 + 지표 트리 + 결정 이력 | `docs/forge/arch/board.html` |
| **backend-forge** | URL → View → Service → Model 을 **AST 로 실측**한 노선도 | `endpoints.json` 정본 + `routes.html` |
| **frontend-forge** | 「한 가지 일에 화면이 몇 개 필요한가」 업무 묶음 판 (before/after) | `docs/forge/frontend/` |
| **forge-loop** | 위 판들이 **실제 코드를 재고 있는지** 지키는 루프(골든 대조·drift) | 판정 리포트 |

> 이 4개만 **본체가 `Desktop/forge` 레포에 있고 여기엔 심링크**다(작업 산출물이 커서 분리).
> 그래서 `claude` 레포를 clone 해도 이 넷은 따라오지 않는다 — forge 레포를 따로 받아야 한다.

## 📋 계획 — 짓기 전에

| 스킬 | 뭘 하나 |
|---|---|
| **grill-me** | 계획을 물고 늘어져 구멍 찾기 (한 번에 한 질문씩) |
| **grilling** | 위와 같은 내용의 본체 — 다른 스킬이 참조용으로 부른다 |
| **grill-with-docs** | grill + 진행하면서 ADR·용어집까지 생성 |
| **domain-modeling** | 도메인 용어(ubiquitous language) 정리 · ADR 기록 |
| **product-spec-kit** | PRD·기능명세서·유저플로우·와이어프레임 **4종 한 세트** → HTML |
| **harness-steps** | 큰 작업을 **자기완결 step 으로 분해** → `execute.py` 로 순차 자동 실행·3회 자가교정 |

> **grill 3종 차이** — `grill-me` = 그냥 시작. `grill-with-docs` = 문서까지 남길 때. `grilling` = 본체(직접 부를 일 적음).
> **harness-steps vs harness-audit** — `harness-steps` 는 **일을 시키는** 실행 프레임워크, `harness-audit` 은 **환경을 진단**하는 도구. 이름만 비슷하고 하는 일이 다르다.

## ✅ 검증 — 짜고 나서

| 스킬 | 뭘 하나 |
|---|---|
| **code-review-7p** | 변경분을 7관점(정확성·보안·단순함·가독성·에러처리·성능·테스트)으로 리뷰 → 🔴🟡🟢 분류 |
| **owasp-security-scan** | 레포 전체를 **OWASP Top 10 2025** 로 스캔 (PR diff 아님) → HTML + JSON |
| **supabase-db-advisor** | Supabase DB 를 MCP `get_advisors` 로 진단 → 4티어 분류 + 수정 SQL. **기본은 제안만** |

> `code-review-7p` = **매 변경마다**(문에서 검문). `owasp-security-scan` = **2주~월 1회**(집 전체 점검). 둘은 보완 관계다.

## 🎨 UI · 디자인

| 스킬 | 언제 |
|---|---|
| **baoyu-design** | UI 목업·프로토타입·랜딩·대시보드를 **자체완결 HTML** 로 |
| **ui-craft-dense-dashboard** | **정보 밀도 높은** 관리/내부도구 화면 (Bloomberg·Retool 류) |
| **apple-design** | 제스처·스프링 애니메이션·드래그/스와이프/시트 |
| **modern-css** | JS 없이 CSS 만으로 되는 최신 기법 레퍼런스 (View Transitions·`@starting-style` 등) |

> 표·대시보드는 **ui-craft-dense-dashboard** 부터. `baoyu-design` 은 범용이라 밀도 높은 표에는 약하다.

## 📄 산출물 — 남에게 보여줄 것

| 스킬 | 뭘 하나 |
|---|---|
| **report** | 분석·제안·before/after 를 **실제 제품 디자인으로 렌더된 HTML 보고서**로 (컬러 주석 배지 오버레이) |
| **presentation_slides** | 다크테마 HTML 슬라이드 세트 + 허브 index |
| **codebase-to-course** | 코드베이스를 **비개발자용 인터랙티브 강의**로 |

## 🔌 외부 · 자료 변환

| 스킬 | 뭘 하나 |
|---|---|
| **clova-note-meeting-minutes** | 구글드라이브 "회의" 폴더의 클로바노트 녹취 → 회의록 + 캘린더 일정 + Gmail 초안 |
| **book-to-skill** | 책·문서(PDF·EPUB·DOCX…) → 프레임워크를 추출한 **스킬로 변환** |

---

## 고르기 어려우면

| 하려는 것 | 이거 |
|---|---|
| 이 레포 에이전트가 다루기 좋나? | `ai-readiness-cartography` |
| 내 작업 환경 어디가 비었나? | `harness-audit` |
| 큰 작업을 어떻게 쪼개지? | `harness-steps` |
| 이 계획 구멍 없나? | `grill-me` |
| 방금 짠 코드 괜찮나? | `code-review-7p` |
| 보안 한번 훑고 싶다 | `owasp-security-scan` |
| 표·관리화면 만든다 | `ui-craft-dense-dashboard` |
| 결과를 보고서로 낸다 | `report` |
| 토큰 왜 이렇게 많이 쓰지? | `improve-token-efficiency` |

## 스킬 추가·수정할 때

1. **먼저 위 표에서 찾아본다.** 같은 일 하는 게 있으면 새로 만들지 말고 고친다 —
   같은 일을 하는 경로가 둘이면 에이전트가 틀린 걸 고를 확률이 **50%** 다.
2. `SKILL.md` 는 **대문자**여야 인식된다.
3. `description` 에 사용자가 쓸 법한 트리거 표현을 3개 이상 넣는다. 안 그러면 있어도 안 불린다.
4. 무거운 내용은 `references/` 로 내리고 `SKILL.md` 에는 **절차만** 남긴다.
5. **수정했으면 이 레포에 commit + push 까지.** 안 하면 다른 PC 에 반영 안 된다.
6. 새로 추가했으면 **이 README 에 한 줄 등록.** 등록 안 된 스킬은 없는 것과 같다.

## 아직 안 만든 것

- **하네스 Eval** — 스킬을 고쳤을 때 회귀했는지 재는 golden set 루프. (bookmart 는 `.dev/harness/evals/` 로 손수 구현돼 있음)
- **Alert as Code** — 대시보드 클릭으로 만든 설정은 에이전트가 못 고친다.

(**플러그인 패키징**은 「안 만든 것」이 아니라 **안 하기로 한 것**이다 — 위 「새 PC 에서」 참조.)
