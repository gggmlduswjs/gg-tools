/skill-creator codebase 가 ai-ready 한지 score 하는 Skill 을 만들어줘. 임의의 git 리포지토리를 AI-Ready 루브릭 (100점, 7 카테고리) 으로 감사하고 JSON 점수표 + 한국어 HTML 대시보드 + ROI 우선순위 액션 리스트를 산출하는 스킬이야. scoring rubric 파일과 score 하는 파이선 스크립트 만들어줘

Improved AI-Ready Codebase Rubric, 100점
Category	Points	What It Measures
A. AI Navigation & Coverage	15	AI가 전체 codebase/module/workflow를 빠르게 찾을 수 있는가
B. Context Document Quality	20	context files가 “compass, not encyclopedia” 원칙을 따르는가
C. Tribal Knowledge Externalization	20	숨은 규칙, 실패 패턴, human-only knowledge가 구조화되었는가
D. Cross-Module Dependency & Data Flow Mapping	15	변경 영향 범위를 AI가 추적할 수 있는가
E. Verification & Quality Gates	15	AI-generated context와 code changes를 검증하는 체계가 있는가
F. Freshness & Self-Maintenance	10	context가 stale해지지 않도록 자동 유지되는가
G. Agent Performance Outcomes	5	실제 AI task 성공률/효율 개선이 측정되는가
A. AI Navigation & Coverage, 15점
Score	Criteria
0	AI가 repo를 직접 grep/search하며 구조를 추측해야 함
5	주요 module 일부에 README/context 존재
10	대부분의 핵심 module에 역할, entry point, related files 정리
15	모든 핵심 module/workflow에 AI navigation guide 존재. “어디를 봐야 하는가”를 1-2 hops 안에 찾을 수 있음
권장 측정식:

Navigation Coverage = AI-context로 안내 가능한 핵심 module 수 / 전체 핵심 module 수
파일 개수보다 module/workflow coverage가 중요합니다.

B. Context Document Quality, 20점
항목	Points	Full Score Criteria
B1. Conciseness	4	25-35 lines 또는 약 1,000 tokens 내외
B2. Quick Commands	4	copy-paste 가능한 명령어와 사용 시점 포함
B3. Key Files	4	실제 수정에 필요한 3-5개 핵심 파일 제시
B4. Non-Obvious Patterns	4	실패를 유발하는 hidden rule과 예외 명시
B5. See Also / Cross References	4	관련 module, context file, dependency map으로 연결
여기서 중요한 건 “문서가 많다”가 아니라 task-relevant context만 담는 것입니다.

C. Tribal Knowledge Externalization, 20점
Score	Criteria
0	senior engineer, Slack, 과거 PR에만 지식 존재
5	일부 gotcha가 README나 comment에 흩어져 있음
10	반복 작업의 암묵지 일부가 문서화됨
15	compatibility rule, naming convention, generated code rule, deprecated-but-required rule 등이 정리됨
20	식별된 tribal knowledge 대부분이 context file/checklist/playbook에 반영되고, AI가 질의로 회수 가능
Meta의 Five-Question Framework를 그대로 평가 기준으로 쓰면 좋습니다.

각 module마다 아래 5개 질문에 답할 수 있으면 4점씩, 총 20점:

What does this module configure/own?
What are common modification patterns?
What non-obvious patterns cause failures?
What are the cross-module dependencies?
What tribal knowledge is hidden in comments/history/human memory?
D. Cross-Module Dependency & Data Flow Mapping, 15점
Score	Criteria
0	변경 영향 범위를 사람이 수동으로 추적
5	일부 architecture diagram 또는 dependency note 존재
10	주요 module 간 dependency와 ownership이 문서화됨
15	“What depends on X?”에 대해 graph/index/map으로 답 가능. 변경이 repo/service/test/data flow에 어떻게 전파되는지 추적 가능
이 항목은 large-scale codebase에서 특히 중요합니다. Meta 사례의 핵심 문제도 “한 field change가 six subsystems에 ripple effect를 만든다”는 점이었습니다.

E. Verification & Quality Gates, 15점
항목	Points	Full Score Criteria
E1. Reference Accuracy	5	file path, API, command hallucination 0건
E2. Independent Critic Review	4	최소 2-3 round의 독립 review 또는 checklist
E3. Task Validation	4	build/test/lint/typecheck/e2e 등 변경 유형별 검증 명령 제공
E4. Prompt/Workflow Tests	2	대표 AI task query를 실제로 테스트
Meta article의 “zero hallucinated paths”는 강의에서 강조하기 좋습니다. AI-ready는 “AI가 읽기 좋은 문서”가 아니라 검증된 문맥 인프라입니다.

F. Freshness & Self-Maintenance, 10점
Score	Criteria
0	context가 수동 관리되며 stale 여부 불명
3	문서 owner가 있고 가끔 업데이트
6	CI나 script로 broken path/reference 일부 검출
10	주기적으로 file path validation, coverage gap detection, critic review, stale reference repair가 자동 실행됨
이 항목은 기존 rubric보다 더 강조하는 게 맞습니다. Meta 표현대로 stale context는 없는 context보다 위험할 수 있습니다.

G. Agent Performance Outcomes, 5점
Score	Criteria
0	AI 성능 개선 측정 없음
2	정성적으로 “도움 된다” 수준
3	대표 task success rate 또는 human intervention rate 측정
5	tool calls, token usage, task completion time, correctness, prompt pass rate 등을 before/after로 측정
예시 metric:

- AI task pass rate
- 평균 tool calls per task
- 평균 tokens per task
- human clarification count
- failed PR/rework rate
- hallucinated file path count
- time-to-first-correct-change
Final Grade
Score	Level	Meaning
90-100	AI-Native / Agentic-Ready	Agent가 대부분의 반복 작업을 자율 수행하고, context layer도 self-maintaining
75-89	AI-Ready	대부분의 개발 작업에서 AI가 안정적으로 navigation, edit, verify 가능
60-74	AI-Assisted	AI가 유용하지만 complex/domain-specific task에는 human context 필요
40-59	AI-Fragile	간단한 task는 가능하나 hidden rule과 dependency 때문에 오류 위험 높음
<40	AI-Hostile	tribal knowledge 의존도가 높고 AI가 추측 기반으로 작업함