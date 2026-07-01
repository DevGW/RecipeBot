/** Build the Devvit server bundle and mirror it for CLI entry resolution. */

import * as esbuild from "esbuild";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { copyServerBundle } from "./copy-server-bundle.mjs";

const projectRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const outfile = join(projectRoot, "dist/server/index.cjs");
const watch = process.argv.includes("--watch");

/** Run one esbuild of the Devvit server entrypoint. */
export async function buildServerBundle() {
  return await esbuild.build({
    entryPoints: [join(projectRoot, "src/main.ts")],
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node22",
    outfile,
    plugins: [
      {
        name: "copy-devvit-entry",
        setup(build) {
          build.onEnd((result) => {
            if (result.errors.length === 0) {
              copyServerBundle();
            }
          });
        },
      },
    ],
  });
}

/** Build once or watch and rebuild the Devvit server bundle. */
export async function runServerBuildScript(watchMode = watch) {
  if (!watchMode) {
    const result = await buildServerBundle();
    if (result.errors.length > 0) {
      process.exitCode = 1;
    }
    return;
  }

  const context = await esbuild.context({
    entryPoints: [join(projectRoot, "src/main.ts")],
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node22",
    outfile,
    plugins: [
      {
        name: "copy-devvit-entry",
        setup(build) {
          build.onEnd((result) => {
            if (result.errors.length === 0) {
              copyServerBundle();
            }
          });
        },
      },
    ],
  });

  await context.watch();
  console.log("RecipeBot server build watching for changes...");
}

const isMain = Boolean(process.argv[1]) &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  await runServerBuildScript();
}
