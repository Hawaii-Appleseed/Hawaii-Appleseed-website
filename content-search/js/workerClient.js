// Thin promise-based client over the ML worker (request/response by id).

export class WorkerClient {
  constructor(onProgress) {
    this.worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
    this.pending = new Map();
    this.seq = 0;
    this.onProgress = onProgress || (() => {});
    this.worker.onmessage = (e) => {
      const { id, type, payload, error, msg } = e.data;
      if (type === "progress") { this.onProgress(msg); return; }
      if (type === "ready") return;
      const p = this.pending.get(id);
      if (!p) return;
      this.pending.delete(id);
      if (type === "error") p.reject(new Error(error));
      else p.resolve(payload);
    };
  }

  _call(type, payload, transfer) {
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ id, type, payload }, transfer || []);
    });
  }

  init() { return this._call("init", {}); }
  embed(text) { return this._call("embed", { text }); }
  rerank(pairs) { return this._call("rerank", { pairs }); }
}
