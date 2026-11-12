# gg-skills Codex 지원

사용자 승인: gg-skills 13개와 공용 hook·review를 Codex에서도 사용하도록 구현한다(2026-10-03, `ㄱ ㄱ`). 외부 bootstrap 플러그인 전체 이식은 제외한다.

## Codex 인수인계

- 완료 조건: 같은 13개 SKILL 원본을 Claude와 Codex가 등록하고, Codex 설치·온보딩 점검·review·안전 hook·OpenAI eval 경로를 검증한다.
- 정본: `CLAUDE.md`, `gg-skills/.claude-plugin/plugin.json`, 기존 hook 엔진과 eval client. 기존 분류·보관 스킬·자산을 보존한다.
- 작업: `codex/gg-skills-support`, 분리 worktree. 개인 설치 폴더의 staged 변경은 손대지 않는다.
- 구현 순서: (1) manifest/marketplace와 설치 검증 (2) Codex hook adapter와 review skill (3) onboard runtime 선택 (4) OpenAI eval provider (5) 문서·통합 검증·최종 독립 리뷰.
- 재사용: manifest의 등록 경로 13개, `guardrail.decide`, `secret_guard.find_secret`, 기존 onboard 프로젝트/위키 점검과 eval subject/judge 계약.
- 금지: 운영 write·merge·전역 권한 설정/인증 복제·자동 hook 신뢰·외부 스킬 복사. Codex용 스킬 본문을 별도로 복제하지 않는다.
- 검증: `python -m unittest discover -s tests`, onboard/guardrail selftest, `npm test`, `npx tsc --noEmit`, `pwsh ./bootstrap.ps1 -DryRun`, Claude plugin validate, 격리 CODEX_HOME에서 marketplace/add/list.
- 리뷰 초점: 실제 Codex discovery의 명시 목록과 보관 스킬 제외, 상대 경로/공백 있는 설치 경로, ask 미지원 시 보호 실패, apply_patch의 이동·추가/삭제 줄, 실패 응답과 비밀값 비노출, Claude 기본 동작 보존.

## 실행 기록

- 기존 경로 조사 완료. 별도 실행기/스킬 복제 대신 host manifest와 얇은 adapter를 추가한다.
- Task 1: manifest와 설치의 RED→GREEN. 격리 CODEX_HOME에서 add/list 성공, app-server skills/list 14개(공용 13 + review), 보관 스킬 제외·오류 0.
- Task 2: hook 테스트 RED→GREEN. 기존 guardrail·secret·선택 TDD 재사용. hooks/list에서 실제 경로 확장·untrusted 확인. Ruling: Codex ask 미지원은 deny로 변환 — 실패 후 도구 실행을 막기 위한 결정이며 Claude보다 엄격해질 수 있다.
- Task 3: onboard runtime 테스트 RED→GREEN, 기존 selftest 통과. Codex 전용/기존 대상 목록 우선순위를 유지하고 프로젝트 worktree의 .git 파일도 인정한다.
- Task 4: OpenAI client mock 테스트 RED→GREEN, 타입 검사 통과. Ruling: OpenAI 모델은 기본값 없이 명시 — 비용·모델 선택을 추정하지 않으며 처음 실행 시 설정이 필요하다.
- Task 5: 사용자 안내·공용 CI 추가. CI는 외부 프로젝트 golden set을 제외한 unit/mock 범위를 명시한다. 실제 스킬 자동 호출·trusted live hook·유료 eval은 이 단계에서 검증 완료로 보고하지 않는다.
- Final review: fresh reviewer, 두 Important(응답 JSON 오류 본문 노출, 현재 OpenAI 키 누락). Ruling: 선택 TDD disable 누락도 호환성 Important로 분류 — 사용자가 명시적으로 끈 설정이 Codex에서 계속 차단하므로 기존 제어를 보존한다. 변경 비용은 없음(기존 환경변수 계약 유지).
- Final: 세 재현 테스트 실패를 확인한 뒤 공용 regex·JSON 오류 경계·TDD disable을 한 번의 수정으로 보완한다. 유료 모델 동작·trusted live hook은 검토 범위에서 제외했고, 활성화를 완료한 것으로 보고하지 않는다.
- Final verification: Python 9/9, secret guard 14/14, guardrail 57/57, eval 95/95(실제 프로젝트 golden set 9개 포함, 모델 호출 없음), TypeScript 검사·diff check 통과. 기존 Claude bootstrap DryRun·plugin validate·onboard selftest 통과. 격리 Codex 설치 재실행은 캐시가 최신 source와 일치했고 다른 source의 동일 marketplace는 CLI가 거부했다.
- 설치 후속: 사용자 환경에서 PATH의 npm CLI가 캐시 활성화 `os error 5`로 실패했다. 같은 계정·설정의 desktop 동봉 CLI로 설치·재설치에 성공했다(둘 다 0.160.0). ACL 수정·관리자 실행 없이 해결했다. installer는 동봉본을 우선하고 실행 파일 명시 옵션을 제공한다. 선택 경로 테스트 RED→GREEN, Python 11/11. 실제 사용자 Codex의 installed/enabled=true, skills/list 14개·오류 0, hook untrusted를 확인했다. 정확한 하위 OS 거부 원인은 미확정이며 실행 파일별 결과 차이까지만 확인했다.
