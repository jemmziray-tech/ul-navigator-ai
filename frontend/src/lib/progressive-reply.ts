/** Reveal incoming text at a readable pace, including large SSE chunks and final corrections. */
export class ProgressiveReply {
  private target = "";
  private visible = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private cancelled = false;
  private finished = false;
  private drained: (() => void) | null = null;

  private update: (text: string) => void;
  private intervalMs: number;
  private reducedMotion: boolean;

  constructor(update: (text: string) => void, intervalMs = 32, reducedMotion = false) {
    this.update = update;
    this.intervalMs = intervalMs;
    this.reducedMotion = reducedMotion;
  }

  append(text: string) {
    if (this.cancelled) return;
    this.target += text;
    this.schedule();
  }

  reset() {
    if (this.cancelled) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.target = "";
    this.visible = 0;
    this.update("");
  }

  finish(text: string): Promise<void> {
    if (this.cancelled) return Promise.resolve();
    // Keep the already-visible prefix only when it is also part of the verified answer.
    let common = 0;
    while (common < this.visible && common < text.length && this.target[common] === text[common]) common++;
    if (common < this.visible) {
      this.visible = common;
      this.update(text.slice(0, common));
    }
    this.target = text;
    this.finished = true;
    return new Promise(resolve => { this.drained = resolve; this.schedule(); });
  }

  cancel() {
    this.cancelled = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.drained?.();
    this.drained = null;
  }

  private schedule() {
    if (this.cancelled || this.timer) return;
    if (this.visible >= this.target.length) {
      if (this.finished) { this.drained?.(); this.drained = null; }
      return;
    }
    this.timer = setTimeout(() => {
      this.timer = null;
      if (this.cancelled) return;
      const remaining = this.target.slice(this.visible);
      // Whole words preserve emoji/Unicode and avoid a mechanical character-at-a-time feel.
      const portion = this.reducedMotion ? remaining : remaining.match(/^\s*\S+(?:\s+\S+)?\s*/u)?.[0] || remaining;
      this.visible += portion.length;
      this.update(this.target.slice(0, this.visible));
      this.schedule();
    }, this.reducedMotion ? 0 : this.intervalMs);
  }
}
