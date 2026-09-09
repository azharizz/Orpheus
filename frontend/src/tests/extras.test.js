import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

test("every jsx file brings React into scope", () => {
  const folders = ["features", "app"];
  for (const folder of folders) {
    for (const name of readdirSync(join(root, folder))) {
      if (!name.endsWith(".jsx")) continue;
      const source = readFileSync(join(root, folder, name), "utf8");
      if (!source.includes("createElement") && !/<[A-Za-z]/.test(source)) continue;
      assert.match(
        source,
        /^import React(,|\s+from)/m,
        `${folder}/${name} renders markup without importing React`,
      );
    }
  }
});
