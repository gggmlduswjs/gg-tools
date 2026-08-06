# Index.html 전체 템플릿

index.html은 네비게이션 바 없이 허브 페이지로 동작. `navigateTo()` 함수는 카드 링크용으로 포함.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1280">
<title>{{프레젠테이션 제목}} — 비주얼 자료</title>
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
  padding: 60px 0 80px;
}
.container { width: 1280px; padding: 0 80px; }
.page-title {
  font-size: 42px; font-weight: 900;
  background: linear-gradient(135deg, #7c3aed, #38bdf8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  text-align: center; margin-bottom: 10px;
}
.page-subtitle {
  text-align: center; font-size: 16px; color: #8b949e; margin-bottom: 50px;
}

/* Sections */
.section { margin-bottom: 36px; }
.section-header {
  font-size: 18px; font-weight: 700; padding: 12px 20px;
  border-left: 4px solid; margin-bottom: 16px;
  display: flex; align-items: center; gap: 12px;
}
.num-range {
  display: inline-block; font-size: 12px; font-weight: 700; color: white;
  padding: 3px 10px; border-radius: 10px;
}

/* Grid */
.grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
}
.card {
  display: flex; flex-direction: column; gap: 6px; padding: 18px 20px;
  background: rgba(139,148,158,0.04); border: 1px solid rgba(139,148,158,0.1);
  border-radius: 12px; text-decoration: none; transition: all 0.25s ease;
}
.card:hover { transform: translateY(-3px); }
.card .card-num { font-size: 28px; font-weight: 900; }
.card .card-title { font-size: 14px; font-weight: 700; color: #c9d1d9; }
.card .card-file { font-size: 11px; color: #484f58; font-family: 'Courier New', monospace; }

/* === 섹션별 색상 CSS 패턴 === */
/* 인트로 (보라) */
.section-intro .section-header { border-color: #7c3aed; color: #a78bfa; }
.section-intro .num-range { background: #5b21b6; }
.section-intro .card:hover { border-color: #7c3aed; box-shadow: 0 8px 32px rgba(124, 58, 237, 0.18); }
.section-intro .card .card-num { color: #7c3aed; }

/* 섹션 1 (하늘) */
.section-1 .section-header { border-color: #38bdf8; color: #7dd3fc; }
.section-1 .num-range { background: #0369a1; }
.section-1 .card:hover { border-color: #38bdf8; box-shadow: 0 8px 32px rgba(56, 189, 248, 0.18); }
.section-1 .card .card-num { color: #38bdf8; }

/* 섹션 2 (초록) */
.section-2 .section-header { border-color: #34d399; color: #6ee7b7; }
.section-2 .num-range { background: #047857; }
.section-2 .card:hover { border-color: #34d399; box-shadow: 0 8px 32px rgba(52, 211, 153, 0.18); }
.section-2 .card .card-num { color: #34d399; }

/* 섹션 3 (주황) */
.section-3 .section-header { border-color: #f97316; color: #fdba74; }
.section-3 .num-range { background: #c2410c; }
.section-3 .card:hover { border-color: #f97316; box-shadow: 0 8px 32px rgba(249, 115, 22, 0.18); }
.section-3 .card .card-num { color: #f97316; }

/* 섹션 4 (핑크) */
.section-4 .section-header { border-color: #ec4899; color: #f9a8d4; }
.section-4 .num-range { background: #be185d; }
.section-4 .card:hover { border-color: #ec4899; box-shadow: 0 8px 32px rgba(236, 72, 153, 0.18); }
.section-4 .card .card-num { color: #ec4899; }

/* 섹션 5 (노랑) */
.section-5 .section-header { border-color: #fbbf24; color: #fde68a; }
.section-5 .num-range { background: #b45309; }
.section-5 .card:hover { border-color: #fbbf24; box-shadow: 0 8px 32px rgba(251, 191, 36, 0.18); }
.section-5 .card .card-num { color: #fbbf24; }

/* 아웃트로 (레인보우) */
.section-outro .section-header { border-color: #e879f9; color: #f0abfc; }
.section-outro .num-range { background: linear-gradient(90deg, #7c3aed, #38bdf8, #34d399, #f97316); }
.section-outro .card:hover { border-color: #e879f9; box-shadow: 0 8px 32px rgba(232, 121, 249, 0.18); }
.section-outro .card .card-num { background: linear-gradient(135deg, #7c3aed, #38bdf8, #34d399, #f97316); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }

/* 페이지 전환 애니메이션 */
body { opacity: 0; animation: fadeIn 0.4s ease forwards; }
body.fade-out { animation: fadeOut 0.3s ease forwards; }
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
  <h1 class="page-title">{{프레젠테이션 제목}} — 비주얼 자료</h1>
  <p class="page-subtitle">전체 {{TOTAL}}개 슬라이드 · 클릭하여 개별 페이지로 이동</p>

  <!-- 섹션별로 반복 -->
  <div class="section section-intro">
    <div class="section-header"><span class="num-range">{{범위}}</span> {{섹션명}}</div>
    <div class="grid">
      <a class="card" href="{{파일명}}" onclick="event.preventDefault(); navigateTo(this.href)">
        <span class="card-num">{{NN}}</span>
        <span class="card-title">{{슬라이드 제목}}</span>
        <span class="card-file">{{파일명}}</span>
      </a>
      <!-- 카드 반복 -->
    </div>
  </div>
  <!-- 섹션 반복 -->
</div>

<script>
function navigateTo(url) {
  document.body.classList.add('fade-out');
  setTimeout(function() { window.location.href = url; }, 300);
}
</script>
</body>
</html>
```

**핵심 규칙:**
- index.html에는 nav 바 없음
- `navigateTo()`는 카드 클릭 전환용
- 섹션별 색상 코딩 적용 (section-intro, section-1~5, section-outro)
- 4열 그리드 카드 레이아웃
