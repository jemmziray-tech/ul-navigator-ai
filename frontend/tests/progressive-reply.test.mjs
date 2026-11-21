import { test } from "node:test";
import assert from "node:assert/strict";
import { ProgressiveReply } from "../src/lib/progressive-reply.ts";

test("a full response chunk and done event still reveal progressively", async () => {
  const updates = [];
  const reply = new ProgressiveReply(t => updates.push(t), 1);
  const answer = "One sentence arrives first. Another sentence follows with a source [S1].";
  reply.append(answer);
  await reply.finish(answer);
  assert.ok(updates.length > 3);
  assert.ok(updates[0].length < answer.length);
  assert.equal(updates.at(-1), answer);
});

test("verified corrections replace unsupported text and preserve final Markdown", async () => {
  const updates = [];
  const reply = new ProgressiveReply(t => updates.push(t), 1);
  reply.append("An unfinished answer (");
  await new Promise(r => setTimeout(r, 8));
  reply.reset();
  const verified = "**Verified passage.** [S1]\n\n- A second point 😊";
  reply.append(verified);
  await reply.finish(verified);
  assert.equal(updates.at(-1), verified);
  assert.ok(updates.includes(""));
});

test("Stop cancels queued text and resolves draining without later updates", async () => {
  const updates = [];
  const reply = new ProgressiveReply(t => updates.push(t), 1);
  const done = reply.finish("This answer has many words that should not all be displayed after stopping.");
  await new Promise(r => setTimeout(r, 3));
  reply.cancel();
  await done;
  const count = updates.length;
  await new Promise(r => setTimeout(r, 8));
  assert.equal(updates.length, count);
  assert.notEqual(updates.at(-1), "This answer has many words that should not all be displayed after stopping.");
});
