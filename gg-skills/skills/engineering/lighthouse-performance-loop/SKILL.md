---
name: lighthouse-performance-loop
description: Lighthouse/Core Web Vitals 기준으로 성능을 측정하고, 병목 상위 1~3개를 코드 위치와 연결해 개선 후 재측정 루프를 만든다. "Lighthouse", "성능 점검", "Core Web Vitals", "LCP", "INP", "CLS", "페이지 느림", "프로덕션 성능" 같은 요청에 트리거. 숫자 없는 추측 튜닝을 금지한다.
---

# Lighthouse Performance Loop

성능은 추측으로 고치지 않는다. **측정 -> 분석 -> 개선 제안 -> 재측정**이 기본 루프다.

## 목표

- LCP: 2.5초 이하를 1차 목표로 본다.
- INP/CLS: Lighthouse 진단과 실제 사용자 흐름을 같이 본다.
- 점수 100점이 목표가 아니다. 사용자가 기다리지 않는 것이 목표다.

## 절차

### 1. 측정 대상 확정

확인할 것:

- URL: production, staging, local 중 어디인가
- 주요 경로: 홈, 로그인 후 대시보드, 핵심 업무 화면
- 모바일 기준 우선. 데스크톱은 보조.

### 2. Lighthouse 실행

Lighthouse가 설치되어 있으면 JSON으로 저장한다.

```bash
npx lighthouse <url> --preset=desktop --output=json --output-path=out/lighthouse-desktop.json
npx lighthouse <url> --form-factor=mobile --output=json --output-path=out/lighthouse-mobile.json
```

설치/네트워크가 필요하면 사용자 승인 없이는 진행하지 않는다. 실행이 어렵다면 Chrome DevTools/Lighthouse 리포트를 받아 분석한다.

### 3. 분석

리포트에서 다음만 우선순위로 뽑는다.

- LCP를 늦추는 리소스/쿼리/서버 응답
- 렌더 차단 CSS/JS
- 이미지 크기/포맷/lazy loading
- 초기 번들 과다
- layout shift 원인

각 항목은 코드 위치나 템플릿/라우트와 연결한다. 연결 못 하면 "조사 필요"로 둔다.

### 4. 출력

```markdown
## Lighthouse 결과

| 페이지 | 환경 | Performance | LCP | INP/TBT | CLS |
|---|---|---:|---:|---:|---:|

## 병목 Top 3
1. 무엇 / 근거 숫자 / 코드 위치 / 수정안 / 재측정 방법

## 하지 않을 것
- 점수 대비 효과 낮은 항목
```

## 금지

- 측정 전 코드 변경 금지.
- 한 번에 10개 최적화 금지. 상위 1~3개만.
- lab 측정만 보고 운영 성공을 단정하지 않는다. 가능하면 PostHog/RUM/서버 로그와 교차 확인한다.
