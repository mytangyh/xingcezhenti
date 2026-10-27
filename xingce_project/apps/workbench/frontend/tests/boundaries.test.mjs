import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const source = readFileSync(
  new URL("../src/main.tsx", import.meta.url),
  "utf8",
);
test("UI uses text rendering, never raw HTML or inline frame", () => {
  assert.doesNotMatch(source, /dangerouslySetInnerHTML|<iframe|innerHTML\s*=/);
});
test("submission serialization and stable server attempt id are present", () => {
  assert.match(source, /if\s*\(busyRef.current\)\s*return/);
  assert.match(source, /await saveQueue.current/);
  assert.match(source, /attempt_id:\s*attempt.attempt_id/);
});
test("training item endpoint is separate from gated review endpoint", () => {
  assert.match(source, /sessions\/\$\{encodeURIComponent\(id\)\}\/items/);
  assert.match(source, /review_available\s*!==\s*false/);
  assert.doesNotMatch(
    source,
    /current\.(source_answer|verified_answer|explanation)/,
  );
});
test("no background visibility pause handler is installed", () => {
  assert.doesNotMatch(source, /visibilitychange|document.hidden/);
  assert.match(source, /canPause\(session.mode\)/);
});
test('source-only training requires an explicit opt-in',()=>{assert.match(source,/\[allowSource,\s*setAllowSource\]\s*=\s*useState\(false\)/);assert.match(source,/allow_source_only:\s*allowSource/)});
