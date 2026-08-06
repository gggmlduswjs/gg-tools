# 레이아웃 타입 CSS 카탈로그

각 슬라이드에 적합한 레이아웃의 CSS를 여기서 복사하여 사용한다.

---

## 1. hero-cards — 타이틀 + 2~3 대형 카드

**용도:** 오프닝 훅, 피처 쇼케이스, 핵심 포인트 강조

```css
.cards {
  display: flex;
  gap: 32px;
  margin-bottom: 40px;
  width: 100%;
}
.card {
  flex: 1;
  background: linear-gradient(145deg, rgba(124, 58, 237, 0.1), rgba(56, 189, 248, 0.05));
  border: 1px solid rgba(124, 58, 237, 0.25);
  border-radius: 20px;
  padding: 40px 28px;
  text-align: center;
  position: relative;
  overflow: hidden;
  opacity: 0;
  transform: translateY(30px);
  animation: cardAppear 0.6s ease-out forwards;
}
.card:nth-child(1) { animation-delay: 0.2s; }
.card:nth-child(2) { animation-delay: 0.6s; }
.card:nth-child(3) { animation-delay: 1.0s; }
@keyframes cardAppear {
  to { opacity: 1; transform: translateY(0); }
}
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, #7c3aed, #38bdf8);
}
.card-icon { font-size: 48px; margin-bottom: 20px; display: block; position: relative; z-index: 1; }
.card-text { font-size: 17px; font-weight: 500; line-height: 1.7; color: #c9d1d9; position: relative; z-index: 1; }
.card-label {
  display: inline-block; margin-top: 14px; padding: 4px 14px; border-radius: 20px;
  font-size: 12px; font-weight: 700; position: relative; z-index: 1;
}
```

**콘텐츠 밀도:** 2~3개 카드, 카드당 이모지 + 2줄 텍스트 + 라벨

---

## 2. roadmap — 타임라인/프로그레스 바

**용도:** 에피소드 개요, 시리즈 진행률

```css
.progress-section { text-align: center; width: 100%; }
.progress-label { font-size: 16px; color: #8b949e; margin-bottom: 20px; }
.progress-bar { display: flex; gap: 8px; justify-content: center; align-items: center; }
.progress-segment { width: 180px; height: 12px; border-radius: 6px; }
.progress-segment.filled { background: #7c3aed; }
.progress-segment.empty { background: rgba(124, 58, 237, 0.15); border: 1px solid rgba(124, 58, 237, 0.2); }
.progress-segment.active {
  background: linear-gradient(90deg, #7c3aed, #a78bfa);
  box-shadow: 0 0 20px rgba(124, 58, 237, 0.6), 0 0 40px rgba(124, 58, 237, 0.3);
  animation: glow 2s ease-in-out infinite;
}
@keyframes glow {
  0%, 100% { box-shadow: 0 0 20px rgba(124, 58, 237, 0.6); }
  50% { box-shadow: 0 0 30px rgba(124, 58, 237, 0.8); }
}
.progress-labels { display: flex; gap: 8px; justify-content: center; margin-top: 12px; }
.progress-labels span { width: 180px; text-align: center; font-size: 13px; color: #8b949e; }
.progress-labels span.active-label { color: #a78bfa; font-weight: 700; }
```

**콘텐츠 밀도:** 3~6개 세그먼트, 각 1줄 라벨

---

## 3. comparison-2col — 좌우 비교 박스

**용도:** vs 슬라이드, before/after, 도구 비교

```css
.comparison { width: 100%; max-width: 1000px; }
.comparison-title { font-size: 22px; font-weight: 700; text-align: center; margin-bottom: 20px; color: #a78bfa; }
.comparison-row {
  display: grid; grid-template-columns: 1fr auto 1fr; gap: 16px;
  align-items: center; margin-bottom: 16px;
}
.comp-label { font-size: 14px; font-weight: 700; color: #7c3aed; margin-bottom: 4px; }
.comp-old {
  background: rgba(139, 148, 158, 0.06); border: 1px solid rgba(139, 148, 158, 0.15);
  border-radius: 12px; padding: 20px; font-size: 16px; color: #8b949e;
}
.comp-arrow { font-size: 24px; color: #7c3aed; }
.comp-new {
  background: rgba(124, 58, 237, 0.08); border: 1px solid rgba(124, 58, 237, 0.3);
  border-radius: 12px; padding: 20px; font-size: 16px; color: #e6edf3; font-weight: 600;
}
```

**콘텐츠 밀도:** 1~3개 비교 행

---

## 4. step-flow — 번호 붙은 세로 단계

**용도:** 설치 과정, 프로세스 설명

```css
.steps { display: flex; flex-direction: column; gap: 16px; width: 100%; max-width: 900px; }
.step {
  display: flex; align-items: flex-start; gap: 20px;
  background: rgba(139, 148, 158, 0.04); border: 1px solid rgba(139, 148, 158, 0.1);
  border-radius: 16px; padding: 24px 28px;
  opacity: 0; transform: translateX(-20px);
  animation: stepIn 0.5s ease-out forwards;
}
.step:nth-child(1) { animation-delay: 0.2s; }
.step:nth-child(2) { animation-delay: 0.4s; }
.step:nth-child(3) { animation-delay: 0.6s; }
.step:nth-child(4) { animation-delay: 0.8s; }
@keyframes stepIn {
  to { opacity: 1; transform: translateX(0); }
}
.step-num {
  width: 40px; height: 40px; border-radius: 50%;
  background: linear-gradient(135deg, #7c3aed, #38bdf8);
  display: flex; align-items: center; justify-content: center;
  font-weight: 900; font-size: 18px; flex-shrink: 0;
}
.step-content { flex: 1; }
.step-title { font-size: 20px; font-weight: 700; margin-bottom: 6px; }
.step-desc { font-size: 15px; color: #8b949e; line-height: 1.6; }
```

**콘텐츠 밀도:** 3~5개 단계, 각 제목 + 1~2줄 설명

---

## 5. diagram-box — 중앙 다이어그램 + 라벨

**용도:** 아키텍처, 보안 모델, 시스템 구조

```css
.diagram {
  width: 100%; max-width: 900px;
  background: rgba(22, 27, 40, 0.6); border: 1px solid rgba(124, 58, 237, 0.2);
  border-radius: 20px; padding: 40px; text-align: center;
  margin-bottom: 30px;
}
.diagram-center {
  display: inline-block; padding: 16px 32px; border-radius: 12px;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(56, 189, 248, 0.1));
  border: 2px solid #7c3aed;
  font-size: 24px; font-weight: 900; margin-bottom: 20px;
}
.diagram-arrows { font-size: 28px; color: #7c3aed; margin: 12px 0; }
.diagram-row { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
.diagram-node {
  background: rgba(139, 148, 158, 0.06); border: 1px solid rgba(139, 148, 158, 0.15);
  border-radius: 12px; padding: 16px 20px; min-width: 140px;
}
.diagram-node-title { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
.diagram-node-desc { font-size: 13px; color: #8b949e; }
```

**콘텐츠 밀도:** 중앙 1개 + 하위 3~6개 노드

---

## 6. grid-2x2 — 2x2 또는 2열 기능 카드

**용도:** 기능 목록, 커넥터, 도구 소개

```css
.grid {
  display: grid; grid-template-columns: repeat(2, 1fr);
  gap: 20px; width: 100%; max-width: 1000px;
}
.feature-card {
  background: rgba(139, 148, 158, 0.04); border: 1px solid rgba(139, 148, 158, 0.1);
  border-radius: 16px; padding: 28px 24px;
  transition: all 0.25s ease;
}
.feature-card:hover { transform: translateY(-3px); }
.feature-icon { font-size: 36px; margin-bottom: 12px; display: block; }
.feature-name { font-size: 20px; font-weight: 700; margin-bottom: 6px; }
.feature-desc { font-size: 15px; color: #8b949e; line-height: 1.5; }
```

**콘텐츠 밀도:** 4~6개 카드, 각 이모지 + 제목 + 설명

---

## 7. three-stage-flow — 가로 3단계 진행

**용도:** 발전 과정, 워크플로우, 레벨업

```css
.flow {
  display: flex; gap: 0; align-items: stretch; width: 100%; max-width: 1000px;
}
.flow-stage {
  flex: 1; padding: 32px 24px; text-align: center;
  background: rgba(139, 148, 158, 0.04); border: 1px solid rgba(139, 148, 158, 0.1);
}
.flow-stage:first-child { border-radius: 16px 0 0 16px; }
.flow-stage:last-child { border-radius: 0 16px 16px 0; }
.flow-arrow {
  display: flex; align-items: center; font-size: 24px; color: #7c3aed;
  padding: 0 8px;
}
.flow-stage-num { font-size: 14px; color: #8b949e; font-weight: 700; margin-bottom: 8px; }
.flow-stage-icon { font-size: 36px; margin-bottom: 12px; display: block; }
.flow-stage-title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
.flow-stage-desc { font-size: 14px; color: #8b949e; line-height: 1.5; }
```

**콘텐츠 밀도:** 정확히 3단계

---

## 8. summary-grid — 3x2 요약 그리드 + 결론

**용도:** 마무리 슬라이드, 총정리

```css
.summary-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 20px; width: 100%; margin-bottom: 44px;
}
.summary-card {
  background: rgba(22, 27, 40, 0.8); border: 1px solid rgba(139, 148, 158, 0.1);
  border-radius: 16px; padding: 32px 24px; text-align: center;
  position: relative; overflow: hidden;
  opacity: 0; transform: translateY(20px);
  animation: cardIn 0.5s ease-out forwards;
}
@keyframes cardIn { to { opacity: 1; transform: translateY(0); } }
.summary-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
}
.card-icon { font-size: 40px; margin-bottom: 14px; display: block; }
.card-name { font-size: 20px; font-weight: 900; margin-bottom: 8px; }
.card-desc { font-size: 14px; color: #8b949e; line-height: 1.5; }
.conclusion {
  text-align: center; padding: 28px 40px;
  background: rgba(22, 27, 40, 0.6); border: 1px solid rgba(124, 58, 237, 0.2);
  border-radius: 16px; width: 100%; max-width: 900px;
}
.conclusion-line {
  font-size: 22px; font-weight: 900; line-height: 1.8;
  background: linear-gradient(90deg, #7c3aed, #38bdf8, #34d399, #f97316, #ec4899, #fbbf24);
  background-size: 400% 400%;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  animation: gradient-shift 5s ease infinite;
}
@keyframes gradient-shift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
```

**콘텐츠 밀도:** 6개 요약 카드 + 결론 박스
- 각 summary-card에 nth-child별로 섹션 컬러를 `::before` background와 `.card-name` 색상에 적용
- animation-delay를 0.1s 간격으로 순차 적용
