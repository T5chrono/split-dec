// One-off PWA icon generation from public/favicon.svg.
// Run: npm i --no-save sharp && node scripts/generate-icons.mjs
import { mkdir } from "node:fs/promises";
import sharp from "sharp";

// Full-bleed variant for maskable purpose: the launcher may crop up to ~20%
// from every edge, so the glyph sits smaller on an uncropped teal square.
const maskableSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" fill="#0d9488"/>
  <g fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"
     transform="translate(32 32) scale(0.62) translate(-32 -32)">
    <path d="M42 14h10v10"/>
    <path d="M22 14H12v10"/>
    <path d="M32 52V30.5a8 8 0 0 0-2.34-5.66L12 14"/>
    <path d="m38 26 14-12"/>
  </g>
</svg>`;

await mkdir("public/icons", { recursive: true });

for (const size of [192, 512]) {
  await sharp("public/favicon.svg", { density: 300 })
    .resize(size, size)
    .png()
    .toFile(`public/icons/icon-${size}.png`);
}
await sharp("public/favicon.svg", { density: 300 })
  .resize(180, 180)
  .flatten({ background: "#0d9488" }) // iOS dislikes transparency
  .png()
  .toFile("public/icons/apple-touch-icon.png");
await sharp(Buffer.from(maskableSvg), { density: 300 })
  .resize(512, 512)
  .png()
  .toFile("public/icons/icon-maskable-512.png");

console.log("icons written to public/icons/");
