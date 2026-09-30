import { readFileSync } from 'node:fs'

// Every string the citizen can read, pulled out of source rather than trusted.
const files = ['src/App.jsx', 'src/lib/api.js', 'src/lib/format.jsx']
const visible = []

for (const file of files) {
  const src = readFileSync(file, 'utf8')
  for (const m of src.matchAll(/>\s*([A-Z][^<>{}\n]{3,})</g)) visible.push([file, m[1].trim()])
  for (const m of src.matchAll(/'([A-Z][^']{6,})'/g)) visible.push([file, m[1].trim()])
  for (const m of src.matchAll(/"([A-Z][^"]{6,})"/g)) visible.push([file, m[1].trim()])
}

const seen = new Set()
const unique = visible.filter(([f, s]) => {
  const k = `${f}:${s}`
  if (seen.has(k)) return false
  seen.add(k)
  return true
})

let failed = 0
const flags = []

for (const [file, s] of unique) {
  // Broken grammar and dashes are hard fails.
  if (/[—]/.test(s)) flags.push([file, s, 'em dash'])
  if (/\b(a|an)\s+\w+/i.test(s) && /\bthing\b|\bstuff\b|\bjourney\b|\bseamless\b|\bempower\b|\bdelve\b/i.test(s)) {
    flags.push([file, s, 'AI filler vocabulary'])
  }
  if (/\b(Welcome|Hello)\s*$/.test(s) && s.length < 4) flags.push([file, s, 'fragment'])
  if (/ {2,}/.test(s)) flags.push([file, s, 'double space'])
}

for (const [file, s, why] of flags) {
  console.log('FLAG', file, '::', why, '::', JSON.stringify(s))
  failed++
}

console.log(`audited ${unique.length} distinct strings`)
console.log(failed ? `RESULT ${failed} string(s) flagged` : 'RESULT no strings flagged')
