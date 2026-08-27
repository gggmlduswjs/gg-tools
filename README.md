# Claude 공용 도구

이 저장소는 여러 프로젝트에서 공통으로 쓰는 **보완 도구**를 관리한다.

## 개발 workflow의 정본

범용 소프트웨어 개발 절차는 더 이상 이 저장소에서 자체 구현하지 않는다.

- 기획/요구사항 정리: **Superpowers `brainstorming`**
- 구현 계획: **Superpowers `writing-plans`**
- 격리 작업공간: **Superpowers `using-git-worktrees`** + 각 프로젝트의 로컬 worktree 규칙
- 구현 실행: **Superpowers `subagent-driven-development` 또는 `executing-plans`**
- TDD: **Superpowers `test-driven-development`**
- 디버깅: **Superpowers `systematic-debugging`**
- 리뷰: **Superpowers code-review workflow**
- 완료 검증: **Superpowers `verification-before-completion`**

Claude Code와 Codex 양쪽에 Superpowers를 설치해 같은 spec/plan을 공유한다. 권장 역할은 **Claude = 기획·설계**, **Codex = 구현·반복 검증**이다. 프로젝트 지시(`CLAUDE.md`, `AGENTS.md`)가 Superpowers보다 우선한다.

## 이 저장소가 맡는 것

`gg-harness` plugin은 이름은 당분간 호환성을 위해 유지하지만, 역할은 **전문 보완 도구**로 축소한다.

유지 대상 예:
- domain-modeling
- Supabase read-only advisor
- Lighthouse/performance
- OWASP/security
- AI-readiness/cartography
- wiki-ingest / wiki-lint / wiki-query

기존 `/harness`, 자체 phase/step 실행기, 자체 TDD/review workflow는 **deprecated**다. 새 작업에는 사용하지 않는다. 기존 프로젝트가 아직 참조할 수 있으므로 1차 마이그레이션에서는 파일을 즉시 삭제하지 않는다.

## 구조

```text
claude/
├── .claude-plugin/marketplace.json
├── README.md
└── gg-harness/                  # 호환 이름; 전문 보완 plugin
    ├── .claude-plugin/plugin.json
    ├── commands/                # wiki 등 보완 command
    └── skills/                  # 전문 skill
```

## 역할 분리

```text
~/.claude/                 개인 기본 설정
Superpowers plugin         범용 개발 workflow
이 repo의 gg-harness       전문 보완 도구
각 프로젝트 CLAUDE.md      프로젝트 헌법/안전 규칙
각 프로젝트 .claude/       프로젝트 전용 rule/skill/hook
각 프로젝트 src/           실제 제품 코드
worktree                   임시 격리 작업 자리
```

원칙은 하나다: **범용 개발 방법론은 Superpowers, 프로젝트 고유 지식은 프로젝트, 전문 도구만 이 plugin.**

## 설치/업데이트

기존 gg-harness 설치는 호환성을 위해 유지한다.

```text
/plugin marketplace add gggmlduswjs/claude
/plugin install gg-harness@gg-harness
```

변경 후:

```text
/plugin marketplace update gg-harness
/plugin update gg-harness@gg-harness
```

Superpowers는 Claude Code와 Codex 각각의 plugin 설치 흐름으로 별도 설치한다. 한 harness에 설치했다고 다른 harness에 자동 적용되는 것으로 가정하지 않는다.

## 마이그레이션 원칙

1. 새 작업은 자체 `/harness`로 phase/step을 만들지 않는다.
2. Superpowers spec/plan을 Claude가 만들고 Git에 저장한다.
3. Codex가 같은 plan을 읽어 구현한다.
4. 프로젝트별 DB/배포/worktree 안전 규칙은 각 repo의 `CLAUDE.md`/`AGENTS.md`에 남긴다.
5. 기존 harness 파일은 참조가 제거된 뒤 별도 cleanup PR에서 삭제한다.
