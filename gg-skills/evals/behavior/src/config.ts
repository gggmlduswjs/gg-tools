// 모델 설정. 바꾸면 결과가 바뀐다 — 게이트 숫자를 비교할 땐 같은 설정인지부터 봐라.

/**
 * subject(피험자) — 경량 리뷰어.
 *
 * ⚠️ temperature 0 을 쓰려고 sonnet-4-6 에 고정했다. claude-sonnet-5 는 기본값이 아닌
 * temperature 를 400 으로 거부한다. 회귀 게이트라 재현성이 최신 모델보다 우선이다.
 * sonnet-5 로 올릴 거면 EVAL_SUBJECT_TEMPERATURE 를 비우고(=미전송) 올려라.
 */
export const SUBJECT_MODEL = process.env.EVAL_SUBJECT_MODEL ?? "claude-sonnet-4-6";
export const SUBJECT_TEMPERATURE =
  process.env.EVAL_SUBJECT_TEMPERATURE === "" ? undefined : Number(process.env.EVAL_SUBJECT_TEMPERATURE ?? 0);
export const SUBJECT_MAX_TOKENS = 4000;

/** judge(채점자) — subject 와 다른 모델이어야 자기 답을 자기가 채점하지 않는다. */
export const JUDGE_MODEL = process.env.EVAL_JUDGE_MODEL ?? "claude-opus-5";
export const JUDGE_MAX_TOKENS = 16000;

/** 동시 실행 수. 올리면 빨라지지만 rate limit 에 걸리면 error 로 떨어지고 게이트는 exit 1 이다. */
export const CONCURRENCY = Number(process.env.EVAL_CONCURRENCY ?? 3);
