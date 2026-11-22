import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/shared/api/client";

import {
  enqueue,
  flush,
  queueSnapshot,
  rememberVersion,
  resetQueue,
  resolve,
  versionOf,
  type Queued,
} from "./offlineQueue";

const offline = () => Promise.reject(new TypeError("Failed to fetch"));
const conflict = () => Promise.reject(new ApiError(409, { detail: "version_conflict" }));

function item(extra: Partial<Queued> & { run: Queued["run"] }): Queued {
  return { id: crypto.randomUUID(), label: "Алиев Ф. · н", ...extra };
}

describe("offline queue", () => {
  let client: QueryClient;
  beforeEach(() => {
    resetQueue();
    client = new QueryClient();
  });

  it("keeps only the newest change of the same thing and patches the cache at once", () => {
    client.setQueryData(["journal", "lesson", "l1"], { attendance: [] as string[] });
    const patch = (data: unknown) => ({
      attendance: [...(data as { attendance: string[] }).attendance, "x"],
    });
    enqueue(item({ key: "att:l1:s1", run: offline, patch }), client);
    enqueue(item({ key: "att:l1:s1", run: offline, label: "Алиев Ф. · был" }), client);
    expect(queueSnapshot().pending.map((p) => p.label)).toEqual(["Алиев Ф. · был"]);
    expect(client.getQueryData(["journal", "lesson", "l1"])).toEqual({ attendance: ["x"] });
  });

  it("stops at a network error and goes on later in the same order", async () => {
    const sent: string[] = [];
    let network = false;
    const send = (name: string) => () =>
      network ? Promise.resolve(sent.push(name)) : Promise.reject(new TypeError("offline"));
    enqueue(item({ key: "a", run: send("a") }), client);
    enqueue(item({ key: "b", run: send("b") }), client);
    await flush(client);
    expect(queueSnapshot().pending).toHaveLength(2);
    network = true;
    await flush(client);
    expect(sent).toEqual(["a", "b"]);
    expect(queueSnapshot().pending).toHaveLength(0);
  });

  it("turns a 409 into a conflict, unless the server already has our value", async () => {
    enqueue(item({ key: "a", run: conflict, alreadyThere: async () => true }), client);
    enqueue(item({ key: "b", run: conflict, force: async () => "forced" }), client);
    await flush(client);
    const { problems } = queueSnapshot();
    expect(problems.map((p) => [p.item.key, p.kind])).toEqual([["b", "conflict"]]);

    const force = vi.fn().mockResolvedValue("ok");
    const [problem] = problems;
    await resolve({ ...problem!, item: { ...problem!.item, force } }, true, client);
    expect(force).toHaveBeenCalledOnce();
  });

  it("shows any other refusal with its reason and drops it from the queue", async () => {
    const refusal = () => Promise.reject(new ApiError(400, { detail: ["too_many_grades"] }));
    enqueue(item({ key: "g", run: refusal }), client);
    await flush(client);
    expect(queueSnapshot().pending).toHaveLength(0);
    expect(queueSnapshot().problems[0]?.kind).toBe("refused");
  });

  it("sends the newest version it knows of", () => {
    expect(versionOf("att", null)).toBeNull();
    rememberVersion("att", 3);
    expect(versionOf("att", null)).toBe(3); // the server has it, the screen does not yet
    expect(versionOf("att", 2)).toBe(3);
    expect(versionOf("att", 5)).toBe(5); // an undo or a refresh moved it on
  });
});
