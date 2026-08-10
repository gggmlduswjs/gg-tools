# gg-harness skills

`gg-harness` plugin에 포함되는 핵심 스킬 목록이다. 이 폴더는 plugin package의 정본이며, 설치는 루트 README의 `/plugin marketplace add` + `/plugin install gg-harness@gg-harness` 흐름을 따른다.

이 plugin은 더 이상 디자인, 강의 변환, 회의록, Supabase MCP, 하네스 실행기, 로컬 PC 배선을 싣지 않는다. 그런 것은 필요할 때 별도 plugin이나 프로젝트 로컬 도구로 관리한다.

## 계획

| 스킬 | 뭘 하나 |
|---|---|
| **grilling** | 계획을 한 번에 한 질문씩 압박해서 빈 구멍을 찾는다 |
| **domain-modeling** | 도메인 용어, 경계, ADR 후보를 정리한다 |
| **product-spec-kit** | PRD·기능명세서·유저플로우·와이어프레임 세트를 만든다 |

## 진단

| 스킬 | 뭘 하나 | 산출물 |
|---|---|---|
| **ai-readiness-cartography** | 레포가 agent-friendly 한지 100점 채점 | HTML 대시보드 + ROI 액션 |
| **harness-audit** | 작업 환경 6축의 빈 칸과 썩은 자산을 찾는다 | 판정표 + 다음 액션 |
| **improve-token-efficiency** | Claude Code 세션 로그에서 토큰/컨텍스트 낭비를 찾는다 | HTML 대시보드 + 절감안 |

## 검증

| 스킬 | 뭘 하나 |
|---|---|
| **code-review-7p** | 변경분을 정확성·보안·단순함·가독성·에러처리·성능·테스트 7관점으로 리뷰한다 |
| **owasp-security-scan** | 레포 전체를 OWASP Top 10 2025 기준으로 스캔한다 |

## 원칙

1. 같은 일을 하는 스킬을 여러 개 두지 않는다.
2. `SKILL.md`는 대문자여야 인식된다.
3. description에는 사용자가 쓸 법한 트리거 표현을 넣는다.
4. 무거운 내용은 `references/`로 내리고 `SKILL.md`에는 절차만 남긴다.
5. 수정했으면 이 레포에 commit + push 후 `/plugin update gg-harness@gg-harness`로 반영한다.