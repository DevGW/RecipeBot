/** Copy the bundled server entry to Devvit CLI's resolved server path. */

import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const bundlePath = join(projectRoot, "dist/server/index.cjs");
const devvitEntryPath = join(projectRoot, "dist/server/dist/server/index.cjs");

/** Copy dist/server/index.cjs to dist/server/dist/server/index.cjs for Devvit CLI entry resolution. */
export function copyServerBundle(
  sourcePath = bundlePath,
  targetPath = devvitEntryPath,
) {
  mkdirSync(dirname(targetPath), { recursive: true });
  copyFileSync(sourcePath, targetPath);
}

const isMain = process.argv[1] &&
  fileURLToPath(import.meta.url) === join(process.argv[1]);

if (isMain) {
  copyServerBundle();
}
