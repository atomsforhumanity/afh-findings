// Before the tests: embed bar.js, and publish sample findings with the real Python CLI.
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export default function setup(): void {
  const worker = join(dirname(fileURLToPath(import.meta.url)), "..");
  execFileSync("node", [join(worker, "scripts", "embed-static.mjs")], { stdio: "inherit" });
  execFileSync(
    "uv",
    ["run", "--project", join(worker, ".."), "python", join(worker, "..", "scripts", "make_worker_fixture.py"),
     join(worker, "test", "fixtures", "bucket.json")],
    { stdio: "inherit" },
  );
}
