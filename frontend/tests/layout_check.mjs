import { readFileSync } from 'node:fs'

// The ratios and the palette are a hard spec, so they are asserted rather than
// eyeballed. Contrast is computed, because "you cannot read this" is the most
// basic failure and an assertion is the only thing that catches it.

const css = readFileSync('src/styles/app.css', 'utf8')

const vars = Object.fromEntries(
  [...css.matchAll(/(--[a-z-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]),
)

const resolve = (value) =>
  String(value)
    .trim()
    .replace(/var\((--[a-z-]+)\)/g, (_, name) => vars[name] ?? 'UNRESOLVED')
    .replace(/\s+/g, ' ')

const failures = []
const check = (name, ok, detail = '') => {
  console.log(ok ? 'PASS' : 'FAIL', name, detail)
  if (!ok) failures.push(name)
}

/* ---------- colour maths ---------- */

const hexToRgb = (hex) => {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16))
}

const luminance = (hex) => {
  const [r, g, b] = hexToRgb(hex).map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

const contrast = (a, b) => {
  const la = luminance(a)
  const lb = luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

/** Resolve the hex a declaration actually paints with. */
const paint = (selector, prop = 'background') => {
  const block = css.match(new RegExp(`\\${selector}\\s*\\{([^}]*)\\}`))
  if (!block) return null
  const m = block[1].match(new RegExp(`${prop}:\\s*([^;]+)`))
  if (!m) return null
  const first = resolve(m[1]).split(/[\s)]/)[0]
  return /^#[0-9a-f]{3,6}$/i.test(first) ? first : null
}

/* ---------- layout ratios ---------- */

const cols = resolve(css.match(/\.shell\s*\{[^}]*grid-template-columns:\s*([^;]+);/)?.[1] ?? '')
check('chat is two thirds of the width', cols === '2fr 1fr', `resolved to "${cols}"`)

const rows = resolve(css.match(/\.rail\s*\{[^}]*grid-template-rows:\s*([^;]+);/)?.[1] ?? '')
check('agent panel 40 percent, flow map 60 percent', rows === '2fr 3fr', `resolved to "${rows}"`)

/* ---------- palette integrity ---------- */

check('base is not pure black', !/#000\b|#000000/i.test(css))
check('no stock neutral gray', !/#f3f4f6|#eceef2|#e7ecf3|#f4f4f5/i.test(css))
check('no cream or bone premium-consumer background', !/#f5f1ea|#f7f5f1|#fbf8f1|#efeae0|#ece6db|#e8dfcb/i.test(css))
check('no purple or lilac anywhere', !/(8b5cf6|7c3aed|6366f1|a78bfa|6d28d9|c4b5fd)\b/i.test(css))
check('no cool blue-charcoal base', !/#0c0e15|#0d1117|#0b1120/i.test(css))
check('base is warm green-black, not grey', /#0d120e/i.test(vars['--plane'] ?? ''))
check('no em dash anywhere', !/—/.test(css))
check('no Google Fonts link in markup', !readFileSync('index.html', 'utf8').includes('fonts.googleapis'))

/* ---------- shape and depth ---------- */

check('one documented radius scale', /--r-container:\s*20px/.test(css) && /--r-bubble:\s*16px/.test(css) && /--r-control:\s*12px/.test(css))
check('reduced motion honoured', /prefers-reduced-motion/.test(css))
check('no hover lift on the send button', !/\.sendbtn:hover[^{]*\{[^}]*translateY/i.test(css))
check('no underline fill animation', !/transition:[^;]*background-size/i.test(css))
check('no grid paper background', !/repeating-linear-gradient/i.test(css))
check('no symmetric radial glow halo', !/radial-gradient\([^)]*at 50% 50%/i.test(css))
check('grain sits behind content, not over it', /body::after[\s\S]*?pointer-events:\s*none/.test(css) && /#root\s*\{[\s\S]*?z-index:\s*1/.test(css))
check('focus ring is visible', /:focus-visible[\s\S]*?outline:\s*2px solid var\(--brass\)/.test(css))

/* ---------- the contrast gate the previous version never ran ---------- */

const pairs = [
  ['primary text on the conversation recess', vars['--text'], vars['--recess'], 4.5],
  ['agent speech on its raised bubble', vars['--text'], vars['--surface'], 4.5],
  ['citizen text on brass', '#17130a', vars['--brass'], 4.5],
  ['send glyph on brass', '#17130a', vars['--brass'], 3],
  ['instrument heading on the panel', vars['--text'], vars['--surface'], 4.5],
  ['panel label on the panel', vars['--text-faint'], vars['--surface'], 4.5],
  ['handoff body on the panel', vars['--text-soft'], vars['--surface'], 4.5],
  ['muted note on the panel', vars['--text-ghost'], vars['--surface'], 4.5],
  ['composer hint on the recess', vars['--text-ghost'], vars['--recess'], 3],
  ['error text on the recess', vars['--clay'], vars['--recess'], 4.5],
  ['active route node on its wash', vars['--brass'], vars['--brass-wash'], 4.5],
  ['escalation node on its wash', vars['--clay'], vars['--clay-wash'], 4.5],
  ['input placeholder on the composer trough', vars['--text-ghost'], '#0b100c', 3],
]

for (const [name, fg, bg, min] of pairs) {
  if (!fg || !bg || !/^#[0-9a-f]{3,6}$/i.test(fg) || !/^#[0-9a-f]{3,6}$/i.test(bg)) {
    check(`contrast: ${name}`, false, 'could not resolve colours')
    continue
  }
  const ratio = contrast(fg, bg)
  check(`contrast: ${name}`, ratio >= min, `${ratio.toFixed(2)}:1, needs ${min}:1`)
}

/* ---------- the accent is used as one accent ---------- */

const brassUses = (css.match(/var\(--brass\)/g) ?? []).length
const clayUses = (css.match(/var\(--clay\)/g) ?? []).length
check('brass is the accent and is used', brassUses > 0, `${brassUses} uses`)
check('clay is confined to the needs-action status', clayUses <= 6, `${clayUses} uses`)

console.log()
console.log(failures.length ? `RESULT ${failures.length} check(s) failed` : 'RESULT all checks passed')
process.exit(failures.length ? 1 : 0)