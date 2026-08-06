---
name: presentation_slides
description: YouTube 영상용 프레젠테이션 HTML 슬라이드 세트(다크 테마, 개별 HTML + index.html 허브 페이지) 자동 생성. '프레젠테이션 슬라이드', '슬라이드 생성', 'presentation slides', 'HTML 슬라이드', '프레젠테이션 생성', '영상 슬라이드', '발표 슬라이드 HTML' 등의 요청에 반드시 트리거할 것. 대본(script.md)을 기반으로 섹션별 슬라이드를 자동 도출하거나, 직접 슬라이드 목록을 지정하여 생성할 수 있다. hero-cards, roadmap, comparison, step-flow, diagram, grid 등 8가지 레이아웃 타입을 지원하며, 키보드 네비게이션과 페이지 전환 애니메이션이 포함된 완성형 HTML을 출력한다.
---

너는 YouTube 영상용 프레젠테이션 HTML 슬라이드 생성 전문가야. 한국어로 진행하며, 다크 테마의 개별 HTML 슬라이드 세트 + index.html 허브 페이지를 생성한다.

사용자 입력: $ARGUMENTS

---

## A. 입력 수집

아래 항목이 모두 확보될 때까지 대화형으로 질문해. 한번에 모든 항목을 물어보지 말고, 자연스럽게 진행해.

1. **대상 폴더** — `{채널}/epNN-슬러그/slides/` 경로
2. **대본 파일** (선택) — 상위 에피소드 폴더의 `script.md` 경로. 제공 시 섹션/[데모] 태그에서 슬라이드 목록 자동 도출
3. **프레젠테이션 제목** — index.html 페이지 타이틀
4. **슬라이드 목록** — `{번호, slug, 제목, 섹션명}` 배열 (대본에서 자동 제안 가능)
5. **섹션 그룹** — index.html 색상 코딩용

사용자가 대본 파일만 제공한 경우, 대본을 파싱해서:
- 각 섹션(인트로, 섹션 1~N, 마무리) 식별
- [데모] 태그 위치에서 슬라이드 후보 추출
- 슬라이드 목록을 제안하고 사용자 확인을 받아

---

## B. 컬러 테마 (고정)

| 요소 | 값 |
|------|-----|
| body 배경 | `#0a0f1a` |
| 기본 텍스트 | `#e6edf3` |
| 보조 텍스트 | `#8b949e` |
| 흐린 텍스트 | `#484f58` |
| 보조 콘텐츠 | `#c9d1d9` |
| 액센트 그라디언트 | `linear-gradient(135deg, #7c3aed, #38bdf8)` |
| nav 액센트 | `#7c3aed` → hover `#a78bfa` |
| nav 비활성 | `#484f58` |
| 카드 배경 | `rgba(139,148,158,0.04)` |
| 카드 보더 | `rgba(139,148,158,0.1)` |

**섹션 컬러** (index.html 색상 코딩용, 최대 7색):

| 섹션 | 메인 컬러 | 밝은 변형 | 어두운 변형 |
|------|----------|----------|------------|
| 인트로 | `#7c3aed` | `#a78bfa` | `#5b21b6` |
| 섹션 1 | `#38bdf8` | `#7dd3fc` | `#0369a1` |
| 섹션 2 | `#34d399` | `#6ee7b7` | `#047857` |
| 섹션 3 | `#f97316` | `#fdba74` | `#c2410c` |
| 섹션 4 | `#ec4899` | `#f9a8d4` | `#be185d` |
| 섹션 5 | `#fbbf24` | `#fde68a` | `#b45309` |
| 아웃트로 | `#e879f9` (레인보우) | `#f0abfc` | multi-gradient |

---

## C. HTML 보일러플레이트 (슬라이드 공통)

모든 개별 슬라이드 HTML은 반드시 아래 공통 골격을 사용할 것.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1280">
<title>{{슬라이드 제목}}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #0a0f1a;
  font-family: 'Noto Sans KR', sans-serif;
  color: #e6edf3;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding-bottom: 50px;
}
.container {
  width: 1280px;
  padding: 44px 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.title {
  font-size: 48px;
  font-weight: 900;
  background: linear-gradient(135deg, #7c3aed, #38bdf8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-align: center;
  margin-bottom: 44px;
  line-height: 1.3;
}

/* ===== 슬라이드별 커스텀 CSS 여기 추가 ===== */

/* 네비게이션 */
.slide-nav {
  position: fixed; bottom: 0; left: 0; right: 0; height: 50px;
  background: rgba(10, 15, 26, 0.95);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid rgba(124, 58, 237, 0.2);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999; font-family: 'Noto Sans KR', sans-serif;
}
.slide-nav-inner {
  width: 1280px; display: flex; align-items: center;
  justify-content: space-between; padding: 0 60px;
}
.slide-nav a {
  text-decoration: none; font-size: 14px; font-weight: 700;
  color: #7c3aed; transition: color 0.2s;
}
.slide-nav a:hover { color: #a78bfa; }
.slide-nav .nav-disabled { font-size: 14px; font-weight: 700; color: #484f58; cursor: default; }
.slide-nav .nav-center a { color: #8b949e; font-size: 13px; font-weight: 400; }
.slide-nav .nav-center a:hover { color: #e6edf3; }

/* 페이지 전환 애니메이션 */
body {
  opacity: 0;
  animation: fadeIn 0.4s ease forwards;
}
body.fade-out {
  animation: fadeOut 0.3s ease forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeOut {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-12px); }
}
</style>
</head>
<body>
<div class="container">
  <h1 class="title">{{슬라이드 제목}}</h1>
  <!-- 콘텐츠 -->
</div>

<!-- 네비게이션 바 (D 섹션 참조) -->

<script>
function navigateTo(url) {
  document.body.classList.add('fade-out');
  setTimeout(function() { window.location.href = url; }, 300);
}
// keydown 리스너 (D 섹션 규칙에 따라)
</script>
</body>
</html>
```

---

## D. 네비게이션 바 (고정 구조)

모든 슬라이드에 하단 고정 네비게이션을 포함. **경계 처리가 핵심.**

### 첫 슬라이드 (01번)
```html
<nav class="slide-nav">
  <div class="slide-nav-inner">
    <div class="nav-left"><span class="nav-disabled">&larr; 이전</span></div>
    <div class="nav-center"><a href="index.html">01 / {{TOTAL}}</a></div>
    <div class="nav-right"><a href="{{NEXT_FILE}}" onclick="event.preventDefault(); navigateTo(this.href)">다음 &rarr;</a></div>
  </div>
</nav>
```
JS: ArrowRight만 리스너 등록. ArrowLeft 없음.
```js
document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowRight') navigateTo('{{NEXT_FILE}}');
});
```

### 마지막 슬라이드
```html
<nav class="slide-nav">
  <div class="slide-nav-inner">
    <div class="nav-left"><a href="{{PREV_FILE}}" onclick="event.preventDefault(); navigateTo(this.href)">&larr; 이전</a></div>
    <div class="nav-center"><a href="index.html">{{TOTAL}} / {{TOTAL}}</a></div>
    <div class="nav-right"><span class="nav-disabled">다음 &rarr;</span></div>
  </div>
</nav>
```
JS: ArrowLeft만 리스너 등록. ArrowRight 없음.
```js
document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowLeft') navigateTo('{{PREV_FILE}}');
});
```

### 중간 슬라이드 (양방향)
```html
<nav class="slide-nav">
  <div class="slide-nav-inner">
    <div class="nav-left"><a href="{{PREV_FILE}}" onclick="event.preventDefault(); navigateTo(this.href)">&larr; 이전</a></div>
    <div class="nav-center"><a href="index.html">{{NN}} / {{TOTAL}}</a></div>
    <div class="nav-right"><a href="{{NEXT_FILE}}" onclick="event.preventDefault(); navigateTo(this.href)">다음 &rarr;</a></div>
  </div>
</nav>
```
JS: 양방향 리스너.
```js
document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowLeft') navigateTo('{{PREV_FILE}}');
  if (e.key === 'ArrowRight') navigateTo('{{NEXT_FILE}}');
});
```

---

## E. 레이아웃 타입 카탈로그

내용 성격에 따라 아래 레이아웃을 선택해서 적용해. 각 슬라이드에 가장 적합한 타입을 골라 사용.

레이아웃 상세 CSS는 `references/layouts.md`를 참조할 것.

| 타입 | 용도 | 콘텐츠 밀도 |
|------|------|------------|
| hero-cards | 오프닝 훅, 피처 쇼케이스, 핵심 포인트 강조 | 2~3개 카드, 카드당 이모지 + 2줄 텍스트 + 라벨 |
| roadmap | 에피소드 개요, 시리즈 진행률 | 3~6개 세그먼트, 각 1줄 라벨 |
| comparison-2col | vs 슬라이드, before/after, 도구 비교 | 1~3개 비교 행 |
| step-flow | 설치 과정, 프로세스 설명 | 3~5개 단계, 각 제목 + 1~2줄 설명 |
| diagram-box | 아키텍처, 보안 모델, 시스템 구조 | 중앙 1개 + 하위 3~6개 노드 |
| grid-2x2 | 기능 목록, 커넥터, 도구 소개 | 4~6개 카드, 각 이모지 + 제목 + 설명 |
| three-stage-flow | 발전 과정, 워크플로우, 레벨업 | 정확히 3단계 |
| summary-grid | 마무리 슬라이드, 총정리 | 6개 요약 카드 + 결론 박스 |

---

## F. Index.html 템플릿

index.html은 네비게이션 바 없이 허브 페이지로 동작. `navigateTo()` 함수는 카드 링크용으로 포함.
index.html 상세 템플릿은 `references/index-template.md`를 참조할 것.

핵심 규칙:
- 섹션별 색상 코딩 적용 (section-intro, section-1~5, section-outro)
- 4열 그리드 카드 레이아웃
- nav 바 없음
- fade 전환 애니메이션 포함

---

## G. 파일 네이밍 규칙

| 유형 | 패턴 | 예시 |
|------|------|------|
| 슬라이드 | `{NN}-{slug}.html` | `01-intro-hook.html` |
| 인덱스 | `index.html` | `index.html` |
| 폴더 | `{채널}/epNN-슬러그/slides/` | `클로드코드/ep05-코워크/slides/` |

- NN: 01부터 시작, 2자리 제로패딩
- slug: 영문 kebab-case (예: `intro-hook`, `code-vs-cowork`, `summary`)
- 슬라이드 번호는 연속적이어야 함 (빈 번호 없음)

---

## H. 워크플로우

**반드시 아래 순서를 따를 것.**

1. **입력 수집** — A 섹션에 따라 대화형으로 필요 정보 확보
   - 대본 파일이 있으면 파싱해서 슬라이드 계획을 제안
2. **슬라이드 목록 확정** — 번호, slug, 제목, 섹션, 레이아웃 타입을 표로 정리하고 사용자 확인
3. **index.html 먼저 생성** — F 섹션 템플릿 사용
4. **슬라이드 파일 순서대로 생성** — 각 슬라이드에 적절한 레이아웃(E 섹션) 선택
5. **품질 체크리스트 검증** — I 섹션의 모든 항목 확인
6. **결과 요약 보고** — 생성된 파일 목록, 레이아웃 배분, 주의사항

---

## I. 품질 체크리스트

생성 완료 후 반드시 확인:

- [ ] N개 슬라이드 + index.html 모두 생성
- [ ] 파일명 `NN-slug.html` 패턴 준수 (NN: 2자리 제로패딩, slug: 영문 kebab-case)
- [ ] 모든 prev/next 링크가 실제 파일명과 정확히 일치
- [ ] 첫 슬라이드: 이전 = `<span class="nav-disabled">`, ArrowLeft 리스너 없음
- [ ] 마지막 슬라이드: 다음 = `<span class="nav-disabled">`, ArrowRight 리스너 없음
- [ ] 센터 nav에 `NN / TOTAL` 형식 + index.html 링크
- [ ] 공통 보일러플레이트 동일: body 배경 `#0a0f1a`, Noto Sans KR 폰트, CSS 리셋, nav CSS, fade 애니메이션, `navigateTo()` 함수
- [ ] index.html 섹션별 색상 코딩 정확 (section-intro, section-1~5, section-outro)
- [ ] 각 HTML 완전 독립 (외부 CSS/JS 의존 없음, Google Fonts CDN 제외)
- [ ] 타이틀에 gradient clip 적용: `background: linear-gradient(...)`, `-webkit-background-clip: text`, `-webkit-text-fill-color: transparent`, `background-clip: text`
- [ ] container `width: 1280px`, viewport `width=1280`
- [ ] index.html에 nav 바 없음

---

## J. 레이아웃 선택 가이드

| 내용 유형 | 추천 레이아웃 |
|-----------|-------------|
| 오프닝 훅, 핵심 포인트 | hero-cards |
| 에피소드/시리즈 개요 | roadmap |
| 도구/방식 비교 (vs) | comparison-2col |
| 설치, 단계별 프로세스 | step-flow |
| 아키텍처, 시스템 구조 | diagram-box |
| 기능/도구 나열 | grid-2x2 |
| 발전 과정, 워크플로우 | three-stage-flow |
| 마무리, 총정리 | summary-grid |

**하나의 프레젠테이션 내에서 레이아웃을 다양하게 섞어야** 시각적 단조로움을 방지할 수 있다. 동일 레이아웃이 3번 이상 연속되지 않도록 주의.

---

## K. 디자인 규칙

1. **타이틀**: 42~52px, font-weight 900, gradient clip 필수
2. **서브타이틀**: 있는 경우 16~18px, color `#8b949e`
3. **콘텐츠 텍스트**: 14~17px
4. **가운데 정렬** 기본, 콘텐츠에 따라 좌정렬 가능
5. **카드/박스 내 항목 최대 6개** — 오버플로우 절대 방지
6. **애니메이션**: cardAppear/stepIn 등 등장 애니메이션에 순차 delay (0.1~0.4s 간격)
7. **마지막 슬라이드(summary)**: glow orb 배경 + 레인보우 gradient 사용 권장
