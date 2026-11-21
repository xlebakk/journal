// The JS side of the plugins is bundled by the frontend, the native side comes from mobile/:
// both package.json files must pin the same versions.
import { readFileSync } from "node:fs";

const read = (file) => JSON.parse(readFileSync(file, "utf8")).dependencies;
const frontend = read("../frontend/package.json");
const mobile = read("package.json");
const shared = ["@capacitor/core", "@capacitor/app", "capacitor-secure-storage-plugin"];
let ok = true;
for (const name of shared) {
  if (frontend[name] !== mobile[name]) {
    console.error(`✗ ${name}: frontend ${frontend[name]} ≠ mobile ${mobile[name]}`);
    ok = false;
  }
}
if (!ok) process.exit(1);
console.log("✓ Capacitor packages match in frontend and mobile");
