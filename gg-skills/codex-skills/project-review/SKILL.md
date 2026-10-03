---
name: project-review
description: 변경분을 프로젝트의 아키텍처·운영 안전·데이터 규칙 기준으로 리뷰한다. "프로젝트 규칙 리뷰", "gg review", "운영 안전 리뷰" 요청에 사용한다.
---

# 프로젝트 규칙 리뷰

[기존 review 계약](../../commands/review.md)을 읽고 그대로 적용한다. `$ARGUMENTS`는 사용자가 지정한 PR/브랜치/경로다.

Codex에서는 Claude 전용 `/code-review`·`/security-review`를 호출하지 않는다. Codex의 리뷰 기능이나 실제로 설치된 보안 스킬을 필요할 때 사용한다. 외부 리뷰를 실행하지 않았다면 실행된 것처럼 보고하지 않는다. 읽기 전용으로 리뷰하며 구현을 자동으로 시작하지 않는다.
