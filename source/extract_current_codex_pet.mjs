#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoDir = path.dirname(scriptDir);
const defaultAsar = "/Applications/ChatGPT.app/Contents/Resources/app.asar";
const asarPath = path.resolve(process.argv[2] ?? defaultAsar);
const outputDir = path.resolve(process.argv[3] ?? path.join(repoDir, "installed"));

if (!fs.existsSync(asarPath)) {
  throw new Error(`Codex application archive not found: ${asarPath}`);
}

const fd = fs.openSync(asarPath, "r");

try {
  const prefix = Buffer.alloc(16);
  fs.readSync(fd, prefix, 0, prefix.length, 0);

  const headerSize = prefix.readUInt32LE(12);
  const headerBuffer = Buffer.alloc(headerSize);
  fs.readSync(fd, headerBuffer, 0, headerSize, 16);

  const header = JSON.parse(headerBuffer.toString("utf8"));
  const matches = [];

  function walk(entry, currentPath = "") {
    for (const [name, child] of Object.entries(entry.files ?? {})) {
      const childPath = currentPath ? `${currentPath}/${name}` : name;
      if (child.files) {
        walk(child, childPath);
      } else if (/^webview\/assets\/codex-spritesheet-v\d+-.*\.webp$/.test(childPath)) {
        matches.push({ path: childPath, entry: child });
      }
    }
  }

  walk(header);

  if (matches.length !== 1) {
    throw new Error(`Expected one built-in Codex spritesheet, found ${matches.length}.`);
  }

  const match = matches[0];
  const bytes = Buffer.alloc(match.entry.size);
  const dataOffset = 16 + headerSize + Number(match.entry.offset);
  fs.readSync(fd, bytes, 0, bytes.length, dataOffset);

  if (bytes.subarray(0, 4).toString("ascii") !== "RIFF" || bytes.subarray(8, 12).toString("ascii") !== "WEBP") {
    throw new Error("Extracted asset is not a WebP file.");
  }

  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, "spritesheet.webp"), bytes);
  fs.writeFileSync(
    path.join(outputDir, "pet.json"),
    `${JSON.stringify(
      {
        id: "codex-current-backup",
        displayName: "Codex (Backup)",
        description: "A snapshot of the built-in blue pixel Codex companion.",
        spriteVersionNumber: 2,
        spritesheetPath: "spritesheet.webp"
      },
      null,
      2
    )}\n`
  );

  console.log(`Extracted ${match.path}`);
  console.log(`Wrote ${path.join(outputDir, "spritesheet.webp")}`);
} finally {
  fs.closeSync(fd);
}
