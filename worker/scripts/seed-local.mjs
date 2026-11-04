// Load a bucket dump (from scripts/make_worker_fixture.py) into wrangler dev's local R2.
//   node scripts/seed-local.mjs test/fixtures/bucket.json
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

const dump = JSON.parse(readFileSync(process.argv[2] ?? "test/fixtures/bucket.json", "utf8"));
const dir = mkdtempSync(join(tmpdir(), "afh-seed-"));
for (const [key, obj] of Object.entries(dump)) {
  const file = join(dir, "obj");
  writeFileSync(file, Buffer.from(obj.data, "base64"));
  execFileSync("npx", ["wrangler", "r2", "object", "put", `afh-findings/${key}`, "--file", file,
    "--content-type", obj.content_type, "--local"], { stdio: "ignore" });
}
console.log(`seeded ${Object.keys(dump).length} objects into local R2`);
