---
description: raw 소스를 읽어 세컨드 브레인 위키에 통합한다 (엔티티 추출·병합·교차링크·index/log 갱신)
---

Skill 도구로 이 플러그인에 번들된 **wiki-ingest** 스킬을 실행하세요.
반드시 먼저 레포 루트의 `WIKI_SCHEMA.md` 와 `wiki/index.md` 를 읽어 현재 상태를 파악한 뒤, 스킬 절차(엔티티 추출 → 병합 우선 작성 → 연결/모순 표시 → index·log 갱신)를 따릅니다.

통합 대상 소스(예: ep02, 또는 raw 파일 경로): $ARGUMENTS

인자가 비어 있으면 아직 ingest 되지 않은 raw 가 무엇인지 사용자에게 확인한 뒤 진행합니다.
