# evals/behavior — 하네스 **행동** 회귀 게이트 (프레임워크)

`CLAUDE.md` 와 프롬프트가 **실제로 에이전트 행동을 바꾸고 있는지**를 모델을 돌려 재고,
**다른 모델**(judge)이 채점한다. 코드에는 테스트가 있고, 하네스에는 eval 이 있다.

## ⚠️ 프레임워크와 데이터가 갈려 있다

| | 어디 | 무엇 |
|---|---|---|
| **프레임워크** | `~/claude/gg-skills/evals/behavior/` (여기 · 한 벌) | 판정·집계·균형·클라이언트. `npm ci` 도 여기 한 번 |
| **데이터** | `<레포>/.dev/harness/evals/behavior/` | `cases/` · `prompts/` · `results/` |

**왜 갈랐나:** 판정 로직은 레포와 무관하고, **무엇을 재는가는 레포마다 다르다.**
쿠팡은 WING 승인·매출 창을 재고 북마트는 운영 DB 직결·수동 migrate 를 재야 한다.

⚠️★★★ **케이스 없이 프레임워크만 깔지 마라.** 그 레포는 "게이트가 생겼다"고 믿으면서
아무것도 안 재게 된다 — `balance.ts` 가 0건을 exit 1 로 잡지만, 사람이 그 exit 1 을
"설정 문제"로 읽으면 끝이다. **케이스를 쓰고 한 번 돌려 초록/빨강을 본 뒤에** 켰다고 말해라.

## 돌리는 법

```bash
cd ~/claude/gg-skills/evals/behavior
npm ci                                    # 한 번

EVAL_REPO="C:/…/Coupang_v2" npm test                    # 키 없이. 파서·판정·균형·golden set
EVAL_REPO="C:/…/Coupang_v2" npm run eval                # 라이브 채점. 키·비용
EVAL_REPO="C:/…/Coupang_v2" npm run eval -- --track qa  # 한 트랙만
```

레포 **안에서** 돌리면 `EVAL_REPO` 없이도 된다(현재 폴더에서 위로 `.git`+`CLAUDE.md` 를 찾는다).
⚠️ 플러그인 자리에서 `EVAL_REPO` 없이 돌리면 **조용히 넘어가지 않고 던진다.**

## ★ 음성 대조 — 통과만 보면 「안 잡는 게이트」와 구분이 안 된다

```bash
EVAL_REPO=… EVAL_REVIEWER_SYSTEM=prompts/reviewer-system.degraded.md \
  npm run eval -- --track review
# → 2/5 · exit 1 이 정상. 5/5 가 나오면 이 게이트는 아무것도 안 잡고 있다.
```

정본 프롬프트를 **손으로 바꿔치기하지 마라** — 복원을 잊으면 게이트가 조용히 무력해진다.
실행할 때 프롬프트 경로를 그대로 찍으므로, 갈아끼운 채 "통과"를 오독할 일도 없다.

⚠️ **살아남는 케이스가 무엇인지가 중요하다.** 쿠팡 실측(2026-08-13)에서 프롬프트를
망가뜨려도 *일반적인 코드 냄새* 와 *오탐 방지* 는 통과했고, 무너진 건 **그 레포에서만
아는 규칙 셋**이었다 — 이 게이트가 재는 건 모델의 일반 실력이 아니라 **문서가 붙잡고
있는 지식**이라는 뜻이다.

## 설정

Claude 없이 실행하려면 `EVAL_PROVIDER=openai`, `OPENAI_API_KEY`, `EVAL_SUBJECT_MODEL`, `EVAL_JUDGE_MODEL`을 지정한다. OpenAI 모델은 기본값 없이 서로 다른 두 모델을 명시한다. OpenAI에서는 temperature를 기본 전송하지 않는다. 기존 Anthropic 기본값은 유지한다. Codex 구독 인증은 API 키를 대신하지 않으며 live eval은 별도 비용과 외부 전송이 발생한다. 이 실행기는 실제 CLI 세션/도구를 실행하는 테스트가 아니다.

```powershell
$env:EVAL_PROVIDER = 'openai'
$env:EVAL_REPO = '<대상 프로젝트>'
$env:EVAL_SUBJECT_MODEL = '<피험자 모델 ID>'
$env:EVAL_JUDGE_MODEL = '<다른 채점자 모델 ID>'
# OPENAI_API_KEY는 개인 환경변수나 대상 레포의 무시된 .env에서 설정한다.
npm run eval
```

`npm test -- --exclude test/goldenset.test.ts`는 공용 unit/mock 검사만 실행한다. 전체 `npm test`는 대상 프로젝트의 실제 golden set이 필요하다. 제외한 검사는 실제 프로젝트 데이터 검증으로 보고하지 않는다.

**어디서 읽나:** 셸 환경변수 → 없으면 **대상 레포의 `.env`**(`src/env.ts`). 환경변수가 이긴다.

⚠️★★★ 워크트리에서 돌리면 **그 워크트리의 `.env`** 를 본다. `wt.ps1` 이 만들 때 뜬 **사본**이라
본체에 키를 나중에 넣어도 **안 따라온다**(2026-08-13 에 여기서 한 번 헛돌았다).
`.env 에서 채운 설정: 없음` 이 찍히면 그 얘기다.
⚠️ **이름 없이 값만 붙여넣은 줄은 버린다**(`sk-ant-…` 한 줄) — 이름 없는 값을 조용히 주워
쓰는 게 더 위험하다. 반드시 `ANTHROPIC_API_KEY=` 를 붙여라.

| env | 기본값 | 비고 |
|---|---|---|
| `EVAL_REPO` | — | 대상 레포. 플러그인 자리에서 돌리면 **필수** |
| `ANTHROPIC_API_KEY` | — | `npm run eval` 에만 필요 |
| `EVAL_SUBJECT_MODEL` | `claude-sonnet-4-6` | ⚠️ `claude-sonnet-5` 는 non-default temperature 를 400 으로 거부한다 |
| `EVAL_SUBJECT_TEMPERATURE` | `0` | 빈 문자열이면 전송하지 않음 |
| `EVAL_JUDGE_MODEL` | `claude-opus-5` | subject 와 달라야 자기 답을 자기가 채점하지 않는다 |
| `EVAL_CONCURRENCY` | `3` | 올리면 rate limit → `error` → exit 1 |
| `EVAL_REVIEWER_SYSTEM` | `prompts/reviewer-system.md` | 레포의 `prompts/` 기준 상대경로 |

## 원칙 (레포 쪽 README 와 같이 읽어라)

1. **golden set 은 작게.** 커버리지가 아니라 **실제로 밟은 사고**로 하나씩 넣는다.
2. **라벨은 사람이 박제한다.** 모델 출력에서 뽑으면 순환논리다 — 회귀를 재려던 자가 회귀를 정의해 버린다.
3. **균형이 무너지면 시작도 안 한다.** 위반만 있으면 "전부 위반"이라 답하는 리뷰어가 만점을 받는다.
4. **못 잰 것은 통과가 아니다.** 케이스 0건 · API 오류 · 거절 · 채점 누락 → 전부 exit 1.
5. **채점자는 관찰만, 판정은 코드가.** judge 에게 기대 라벨을 주지 않는다 — 그래야 판정 규칙을 `npm test` 로 검증할 수 있다.
6. **흔들리면 프롬프트가 아니라 케이스를 고쳐라.** 2026-08-13 에 같은 입력에서 결과가 뒤집힌
   케이스가 있었는데, 원인은 **질문이 안 물어본 걸 `must` 가 요구한 것**이었다. 질문을 고치자
   3회 연속 안정됐다. ★**새 케이스는 같은 입력으로 3회 돌려보고 넣어라.**
7. **운영에 닿지 않는다.** review 케이스의 코드는 읽히기만 하는 문자열이고 실행되지 않는다.
