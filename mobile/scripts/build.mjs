// node scripts/build.mjs debug|release — frontend (--mode mobile) → cap sync → Gradle.
//
// debug:   VITE_API_URL defaults to http://10.0.2.2:8000 (the computer seen from the emulator);
//          plain http and WebView debugging are allowed in this build only.
// release: VITE_API_URL must be https://…, JOURNAL_SIGNING must point to the signing
//          properties file kept outside the repository (see mobile/README.md).
// Gradle needs JDK 21 or newer in JAVA_HOME (Capacitor 8).
import { execFileSync, execSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const mode = process.argv[2];
if (mode !== "debug" && mode !== "release") {
  console.error("usage: node scripts/build.mjs debug|release");
  process.exit(2);
}
const mobile = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const frontend = path.join(mobile, "..", "frontend");
const android = path.join(mobile, "android");
const windows = process.platform === "win32";

const env = { ...process.env };
if (mode === "debug") {
  env.VITE_API_URL ??= "http://10.0.2.2:8000";
  env.JOURNAL_DEV_SERVER = "1";
} else {
  delete env.JOURNAL_DEV_SERVER;
  if (!env.VITE_API_URL?.startsWith("https://")) {
    console.error("release: set VITE_API_URL=https://<server> (cleartext is forbidden)");
    process.exit(2);
  }
  if (!env.JOURNAL_SIGNING || !existsSync(env.JOURNAL_SIGNING)) {
    console.error("release: set JOURNAL_SIGNING to the signing properties file");
    process.exit(2);
  }
}

// Only constant arguments here; Windows needs a shell for npm, npx and gradlew.bat.
function run(command, args, cwd) {
  const line = [command, ...args].join(" ");
  console.log(`\n> ${line}`);
  if (windows) execSync(line, { cwd, env, stdio: "inherit" });
  else execFileSync(command, args, { cwd, env, stdio: "inherit" });
}

run("npm", ["run", "build:mobile"], frontend);
run("npx", ["cap", "sync", "android"], mobile);
const task = mode === "debug" ? "assembleDebug" : "assembleRelease";
run(path.join(android, windows ? "gradlew.bat" : "gradlew"), [task, "--no-daemon"], android);

const apk =
  mode === "debug"
    ? path.join(android, "app", "build", "outputs", "apk", "debug", "app-debug.apk")
    : path.join(android, "app", "build", "outputs", "apk", "release", "app-release.apk");
console.log(`\nAPK: ${apk}`);
