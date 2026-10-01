import { spawn } from "node:child_process";
const args = process.argv.slice(2).filter(arg => arg !== "--strictPort");
const host = args.indexOf("--host");
if (host >= 0) args[host] = "--hostname";
const child = spawn(process.execPath, ["node_modules/next/dist/bin/next", "dev", ...args], { stdio: "inherit", env: { ...process.env, CACHEMIND_PREVIEW: "1" } });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", code => process.exit(code ?? 1));
