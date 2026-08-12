#!/usr/bin/env bash
# Desktop launcher for macOS: an applet that opens the vault in Obsidian, with a 🧠 icon.
# Usage: ./launcher-macos.sh <VaultName>
set -euo pipefail

VAULT_NAME="${1:?usage: launcher-macos.sh <VaultName>}"
APP="$HOME/Desktop/${VAULT_NAME}.app"

osacompile -o "$APP" -e "do shell script \"open \\\"obsidian://open?vault=${VAULT_NAME}\\\"\""

# The icon needs Swift (Command Line Tools). Without it the launcher still works,
# it just keeps the default applet icon - never block on this.
if ! command -v swift >/dev/null 2>&1; then
  echo "no swift, icon skipped (optional). The launcher still works."
  echo "launcher ✓ $APP"
  exit 0
fi

cat > /tmp/render_brain.swift <<'SWIFT'
import AppKit
let out = CommandLine.arguments[1]
let size = 1024.0
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
let pt = size * 0.78
let font = NSFont(name: "Apple Color Emoji", size: pt) ?? NSFont.systemFont(ofSize: pt)
let s = "🧠" as NSString
let b = s.size(withAttributes: [.font: font])
s.draw(at: NSPoint(x: (size - b.width)/2, y: (size - b.height)/2), withAttributes: [.font: font])
img.unlockFocus()
if let t = img.tiffRepresentation, let r = NSBitmapImageRep(data: t),
   let p = r.representation(using: .png, properties: [:]) {
  try? p.write(to: URL(fileURLWithPath: out))
}
SWIFT
swift /tmp/render_brain.swift /tmp/brain.png

cat > /tmp/set_icon.swift <<'SWIFT'
import AppKit
let img = NSImage(contentsOfFile: CommandLine.arguments[1])!
let ok = NSWorkspace.shared.setIcon(img, forFile: CommandLine.arguments[2], options: [])
print(ok ? "icon ✓" : "icon FAILED")
SWIFT
swift /tmp/set_icon.swift /tmp/brain.png "$APP"

touch "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" 2>/dev/null || true

echo "launcher ✓ $APP"
echo "note: the obsidian:// handler only resolves after the vault has been opened in Obsidian once."
