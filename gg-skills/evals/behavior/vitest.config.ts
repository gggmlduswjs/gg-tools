import { defineConfig } from "vitest/config";

// npm test 는 키도 네트워크도 쓰지 않는다. 파서·집계·판정 규칙과
// golden set 의 무결성/균형만 본다. 라이브 채점은 `npm run eval`.
export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
  },
});
