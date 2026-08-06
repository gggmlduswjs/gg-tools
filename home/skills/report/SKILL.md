---
name: report
description: 분석·제안·before/after·감사결과 등 결과물을 plain 텍스트 대신 "실제 제품 디자인으로 렌더된 자체완결 HTML 보고서"로 뽑는다. 기존 화면/데이터를 실제 v2 디자인 토큰으로 재현하고, 바뀌거나 짚는 부분을 컬러 주석 배지(＋신규·변경·삭제·문제·제안)로 오버레이한 뒤, 로컬 서버로 Chrome에 열어 스크린샷+파일로 전달한다. UI 제안 목업, 대시보드 변경안, 데이터 감사 리포트, before/after 비교에 사용. "보고서로 만들어줘 / 이 스타일로 보여줘 / 목업 만들어줘 / before after 보여줘" 요청 시.
---

# report — bookmart 비주얼 보고서

결과물을 **실제 제품과 같은 화면으로 렌더된 HTML**로 내놓는다. 텍스트 설명이 아니라, 사장님이 **눈으로 바로 알아보는** 재현 + 컬러 주석.

## 언제
제안·분석·감사·before/after 처럼 "보여주면 이해가 빠른" 것. 순수 대화/사소한 답은 그냥 텍스트로(YAGNI).

## 워크플로 (고정)

1. **토큰 인라인** — ⚠️ 레포에 `tokens.css` 정본이 있다고 전제하지 마라. Coupang_v2 에는 **없다**(2026-08-04 실측 — 예전 이 줄이 `src/static/css/tokens.css` 를 "실제 v2 토큰"이라 단언했는데 그 파일은 존재한 적이 없다). 먼저 `find . -name "tokens.css"` 로 확인하고, **있으면** 그 `:root` 블록(oklch)을 `<style>`에 그대로 붙이고 **없으면 아래 fallback 팔레트**를 쓴다. 어느 쪽이든 **hex 직접 금지**, 토큰 변수만.
2. **맥락 재현** — 보고 대상이 기존 화면/표면(대시보드·표·앱)이면 **그 UI를 알아볼 수 있게 재현**(같은 레이아웃·컬럼·헤더색). 스크린샷을 받았으면 그걸 기준으로. 순수 분석이면 카드 + `.data-table` 레이아웃.
3. **주석 오버레이** — 바뀌거나 짚는 부분에만 아래 **배지 어휘**를 얹는다. 기존 부분은 건드린 티 없이. before/after는 좌우 병렬.
4. **렌더 & 전달** — scratchpad에 자체완결 HTML 저장 → `python3.11 -m http.server <port> --bind 127.0.0.1`(background) → `mcp__claude-in-chrome__navigate`로 `http://127.0.0.1:<port>/파일.html` 열기(**file:// 는 확장에서 차단됨**) → `computer` 스크린샷 → `SendUserFile`(display: render). 열었다고만 하지 말고 **직접 열 수 있는 URL도 알려준다**.
   - **공유가 필요하면(사장님/타인에게 메일·링크) → Artifact 링크로 발행이 정답.** `127.0.0.1` localhost는 이 PC에서만 열리고, `SendUserFile`(display:render)도 사용자 화면에서 **안 열리는 경우가 잦다**(실측). 리포트는 이미 자체완결이므로 wrapper 태그(`<!doctype>/<html>/<head>/<body>`)만 벗겨 `Artifact` 툴로 발행 → 클릭 가능한 URL 전달. (Artifact는 기본 비공개 — 타인 공유는 페이지 Share 메뉴에서 켜야 함을 함께 안내.)

## 주석 배지 어휘 (핵심 — 이걸 일관되게)

```css
/* 공통: 강조 대상에 .an 붙이고 종류 클래스 추가. 부모는 position:relative 필요 */
.an{position:relative;outline-offset:2px;border-radius:6px}
.an::after{position:absolute;top:-11px;left:8px;color:#fff;font-size:10px;
  font-weight:700;padding:1px 7px;border-radius:999px;letter-spacing:.02em;z-index:5}
.an-new{outline:2px dashed var(--accent-500)}      .an-new::after{content:"＋ 신규";background:var(--accent-600)}
.an-chg{outline:2px dashed var(--warning-500)}      .an-chg::after{content:"변경";background:var(--warning-fg)}
.an-del{outline:2px dashed var(--danger-500)}       .an-del::after{content:"삭제";background:var(--danger-500)}
.an-issue{outline:2px solid var(--danger-500)}      .an-issue::after{content:"문제";background:var(--danger-500)}
.an-note{outline:2px dashed var(--info-500)}        .an-note::after{content:"제안";background:var(--info-fg)}
/* 인라인 표기 */
del{color:var(--danger-fg);text-decoration:line-through}
.metric{color:var(--accent-700);font-weight:800}   /* 핵심 수치 강조 */
.legend{display:inline-flex;gap:7px;align-items:center;font-size:12px;color:var(--accent-700);
  background:var(--accent-50);border:1px dashed var(--accent-500);border-radius:999px;padding:3px 11px;font-weight:600}
```
- 배지는 **바뀌는 것에만**. 남발 금지(전부 신규면 신규가 의미 없음).
- 문서 상단에 무슨 배지를 썼는지 `.legend`로 한 줄 범례.

## 재사용 레이아웃 스니펫

**데이터 표** — 운영 `.data-table` 톤:
```css
table{width:100%;border-collapse:collapse;font-size:12px;background:var(--bg-surface)}
th{background:oklch(0.955 0.008 250);color:var(--fg-strong);font-weight:600;padding:8px 6px;
  text-align:right;border-bottom:1px solid var(--border-default);white-space:nowrap}
th:first-child,td:first-child{text-align:left;padding-left:12px}
td{padding:7px 6px;text-align:right;border-bottom:1px solid var(--border-subtle)}
tr:hover td{background:var(--accent-50)} .tot td{font-weight:700;background:var(--bg-muted);border-top:2px solid var(--border-strong)}
```
※ PsimBook 표 헤더는 예외 — `#D9E2F3`/`#B4C6E7` 그대로 보존.

**모바일 폰 프레임** — 간편주문 앱 톤(카드 + 하단 스티키 CTA):
```css
.phone{width:330px;background:var(--bg-surface);border:1px solid var(--border-default);
  border-radius:26px;box-shadow:var(--shadow-md);overflow:hidden}
.p-body{padding:16px;min-height:520px;display:flex;flex-direction:column}
.p-cta{position:sticky;bottom:0;margin:auto -16px 0;padding:12px 16px 16px;
  background:linear-gradient(to top,var(--bg-surface) 78%,transparent);border-top:1px solid var(--border-subtle)}
.tap{display:block;width:100%;text-align:center;padding:13px;border-radius:8px;font-size:15px;
  font-weight:700;border:1px solid var(--border-default);background:var(--bg-surface);margin-bottom:8px}
.tap.pri{background:var(--accent-600);color:#fff;border-color:var(--accent-600)}
```

**문서 골격**: `<h1>` 제목 + `.lead`(회색 한 줄 요약) + 섹션. `font-family:'Pretendard',system-ui,-apple-system,'Apple SD Gothic Neo','Segoe UI',sans-serif`.

## 하드 규칙 (어기지 말 것)
- **v2 토큰만, hex 직접 금지.** tokens.css `:root` 인라인.
- **UI 이모지 금지.** 아이콘 필요하면 단색 inline SVG.
- **PsimBook 헤더색 보존**(`#D9E2F3`·`#B4C6E7`).
- **운영코드 무변경** — 보고서는 scratchpad에만. 절대 `src/` 건드리지 않음.
- 자체완결(외부 CDN·폰트·이미지 요청 0). 렌더는 반드시 http.server 경유(file:// 차단).

## Fallback 팔레트 (tokens.css 못 찾을 때만)
```css
:root{--bg-app:oklch(0.985 0.003 264);--bg-surface:#fff;--bg-subtle:oklch(0.975 0.004 264);
--bg-muted:oklch(0.955 0.005 264);--bg-inset:oklch(0.93 0.006 264);
--border-subtle:oklch(0.93 0.006 264);--border-default:oklch(0.88 0.008 264);--border-strong:oklch(0.80 0.012 264);
--fg-strong:oklch(0.22 0.015 264);--fg-default:oklch(0.32 0.012 264);--fg-muted:oklch(0.52 0.010 264);--fg-faint:oklch(0.68 0.008 264);
--accent-50:oklch(0.97 0.025 264);--accent-500:oklch(0.58 0.18 264);--accent-600:oklch(0.52 0.18 264);--accent-700:oklch(0.44 0.16 264);
--success-bg:oklch(0.96 0.035 155);--success-fg:oklch(0.42 0.12 155);--success-500:oklch(0.58 0.13 155);
--warning-500:oklch(0.72 0.14 80);--warning-fg:oklch(0.44 0.11 70);
--danger-bg:oklch(0.96 0.035 25);--danger-fg:oklch(0.46 0.16 25);--danger-500:oklch(0.58 0.18 25);
--info-500:oklch(0.60 0.15 230);--info-fg:oklch(0.42 0.12 230);
--radius:6px;--radius-md:8px;--radius-lg:10px;--radius-xl:14px;
--shadow-sm:0 1px 2px 0 oklch(0.18 0.015 264/0.06);--shadow-md:0 10px 24px -4px oklch(0.18 0.015 264/0.08),0 4px 8px -4px oklch(0.18 0.015 264/0.04)}
```

## 참고
- 첫 성공 사례: 월별 확인폼 목업(더봄 대시보드 재현 + `＋신규` 오버레이 + 선생님 모바일 3화면). 이 SKILL이 그걸 일반화한 것.
- 공유가 필요하면 Artifact로 발행 가능하나, 기본은 로컬 렌더 + SendUserFile.
