---
name: harness-eval
description: Claude/Codex 하네스, 스킬, slash command, CLAUDE.md 규칙의 회귀를 golden set으로 측정한다. "하네스 eval", "에이전트 eval", "golden set", "프롬프트 회귀", "스킬 품질", "LLM-as-judge", "하네스 품질" 같은 요청에 트리거. 코드 테스트가 아니라 에이전트 행동 품질을 측정한다.
---

# Harness Eval

코드에는 테스트가 있고, 하네스에는 eval이 있다. 이 스킬은 스킬/명령어/CLAUDE.md를 바꿨을 때 에이전트 행동이 망가지지 않았는지 확인한다.

## 원칙

- golden set은 5개로 시작한다.
- 성공 케이스와 실패 케이스를 둘 다 넣는다.
- false positive 방지 케이스를 반드시 넣는다.
- 운영 DB/외부 실쓰기/배포를 eval에서 실행하지 않는다.

## 절차

### 1. 기존 eval 찾기

```bash
ls .dev/harness/evals 2>/dev/null
cat .dev/harness/evals/README.md 2>/dev/null
cat .dev/harness/evals/tasks.json 2>/dev/null
```

없으면 만들 것을 제안만 한다. 사용자가 구현을 승인해야 파일을 만든다.

### 2. golden set 설계

최소 5개:

| 유형 | 예 |
|---|---|
| 위험 diff | 보안/DB/권한 위반을 잡아야 함 |
| 정상 diff | 오탐 없이 통과해야 함 |
| 계획 분해 | 중요한 위험 step을 빼먹지 않아야 함 |
| 운영 안전 | 수동 DB 쓰기/배포를 거부해야 함 |
| 프로젝트 룰 | CLAUDE.md의 핵심 규칙이 실제 출력에 반영되어야 함 |

### 3. 채점

가능한 구조:

```text
input -> agent output -> judge rubric -> pass/fail/unverified
```

judge도 흔들릴 수 있으므로 critical한 판정은 사람이 샘플링한다. 애매하면 `unverified`로 둔다.

### 4. 출력

```markdown
## Harness Eval

| 케이스 | 목적 | 기대 행동 | 현재 상태 |
|---|---|---|---|

## 회귀 게이트
- 언제 돌릴지:
- 누가 판정할지:
- 실패 시 무엇을 막을지:
```

## 금지

- eval을 크게 시작하지 않는다. 5개로 시작한다.
- 모호한 프롬프트 때문에 아무 diff가 안 난 것을 pass로 세지 않는다.
- 운영 DB에 닿는 명령을 eval에서 실행하지 않는다.
