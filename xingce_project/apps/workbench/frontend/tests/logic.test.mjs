import test from "node:test";
import assert from "node:assert/strict";
import {
  safeImage,
  safeLink,
  formatTime,
  canPause,
  visibleElapsed,
  statusLabel,
} from "../src/logic.mjs";
test("images stay on trusted local content routes", () => {
  assert.equal(safeImage("https://tracker.test/a.png"), "");
  assert.equal(safeImage("javascript:alert(1)"), "");
  assert.equal(safeImage("/api/assets/../secret"), "");
  assert.equal(safeImage("/api/assets/%2e%2e/secret"), "");
  assert.equal(safeImage("/api/assets/%5csecret"), "");
  assert.equal(safeImage("/api/assets/abc.png"), "/api/assets/abc.png");
});
test("links disallow executable URLs", () => {
  assert.equal(safeLink("javascript:alert(1)"), "");
  assert.equal(safeLink("data:text/html,x"), "");
  assert.equal(safeLink("https://github.com/x"), "https://github.com/x");
});
test("timer survives background elapsed time and respects explicit pause", () => {
  assert.equal(visibleElapsed(1000, 0, null, 61000), 60);
  assert.equal(visibleElapsed(1000, 10000, 41000, 90000), 30);
  assert.equal(canPause("simulation"), false);
  assert.equal(canPause("practice"), true);
});
test("formatting never implies point score or verified status", () => {
  assert.equal(formatTime(75.9), "01:15");
  assert.equal(formatTime(-3), "00:00");
  assert.match(statusLabel("source_only"), /待核验/);
  assert.match(statusLabel("missing"), /未提供/);
});
test('review maps stable IDs to visible option labels without guessing missing maps',async()=>{const {optionLabels}=await import('../src/logic.mjs');assert.equal(optionLabels(['q-1-opt-A'],[{option_id:'q-1-opt-A',label:'A'}]),'A');assert.equal(optionLabels(['q-1-opt-X'],[]),'选项映射待核对');assert.equal(optionLabels([],[]),'')});
