---
name: observability-posthog-seo
description: PostHog error tracking/product analytics와 SEO 기본 자산(metadata, sitemap, Open Graph)을 점검하고, 이벤트 명명·알림·대시보드 빈칸을 정리한다. "PostHog", "관측성", "observability", "error tracking", "analytics", "SEO", "sitemap", "OG 이미지", "프로덕션 모니터링" 같은 요청에 트리거.
---

# Observability + PostHog + SEO

관측성은 "깔았다"가 아니라 **누가 보고, 어떤 신호가 사람을 깨우며, 어떤 행동으로 이어지는가**까지 포함한다.

## 점검 축

| 축 | 질문 |
|---|---|
| Error tracking | 클라이언트/서버 예외가 자동 수집되는가 |
| Alert | critical 오류가 사람에게 도달하는가 |
| Product analytics | 핵심 이벤트와 퍼널이 보이는가 |
| Naming | 이벤트 이름이 일관적인가 |
| SEO | metadata/sitemap/OG가 실제 경로와 맞는가 |

## 절차

### 1. 현재 자산 찾기

```bash
rg -n "posthog|capture|sentry|analytics|sitemap|metadata|Open Graph|og:" .
ls .github/workflows 2>/dev/null
```

확인할 파일:

- 앱 초기화/미들웨어/템플릿
- error boundary 또는 서버 exception logging
- analytics event 호출부
- `robots.txt`, `sitemap.xml`, route metadata, OG 이미지
- uptime/alert GitHub Actions 또는 외부 webhook 문서

### 2. 이벤트/알림 판단

이벤트는 적게, 일관되게 둔다.

예:

- `signed_up`
- `uploaded_csv`
- `created_order`
- `completed_checkout`
- `viewed_report`

민감 정보는 event property에 넣지 않는다. user id도 프로젝트 정책에 맞춰 해시/내부 id/익명 id 중 하나로 통일한다.

### 3. 출력

```markdown
## Observability

| 항목 | 판정 | 근거 | 빠진 것 |
|---|---|---|---|

## Analytics Events
| 이벤트 | 위치 | 목적 | 속성 |

## SEO
| 자산 | 판정 | 근거 |

## 다음 액션
1. ...
```

## 금지

- API key/project token을 플러그인 repo나 문서에 평문으로 넣지 않는다.
- analytics를 무작정 많이 심지 않는다. 핵심 퍼널부터.
- 수집만 하고 알림/대시보드가 없는 상태를 "완료"라고 하지 않는다.
