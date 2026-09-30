/**
 * Minimal formatter for the plain-ish text the agents return.
 *
 * Agents write short paragraphs, asterisk bullets, and double-asterisk
 * emphasis. Rendering that faithfully is the whole job. Nothing is injected as
 * HTML: every node here is built as a React element, so a model cannot smuggle
 * markup into the page.
 */

/** Emphasis and italic only. No links, no images, no raw HTML. */
function inline(text, keyPrefix) {
  const parts = []
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*)/g
  let lastIndex = 0
  let match
  let i = 0

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }
    const token = match[0]
    if (token.startsWith('**')) {
      parts.push(<strong key={`${keyPrefix}-b${i}`}>{token.slice(2, -2)}</strong>)
    } else {
      parts.push(<em key={`${keyPrefix}-i${i}`}>{token.slice(1, -1)}</em>)
    }
    i += 1
    lastIndex = match.index + token.length
  }

  if (lastIndex < text.length) parts.push(text.slice(lastIndex))
  return parts.length ? parts : text
}

/** Split a line into an optional bullet label and the rest. */
function parseBullet(line) {
  const star = line.match(/^\s*\*\s+(.*)$/)
  if (star) return { marker: '•', text: star[1] }

  const dash = line.match(/^\s*[-–]\s+(.*)$/)
  if (dash) return { marker: '–', text: dash[1] }

  const numbered = line.match(/^\s*(\d+)[.)]\s+(.*)$/)
  if (numbered) return { marker: `${numbered[1]}.`, text: numbered[2] }

  return null
}

export function renderMessage(text) {
  const lines = String(text || '').split('\n')
  const blocks = []
  let bullets = null
  let key = 0

  const flushBullets = () => {
    if (!bullets || !bullets.length) return
    blocks.push(
      <ul key={`ul-${key++}`}>
        {bullets.map((b, i) => (
          <li key={i}>{inline(b.text, `li-${i}-${key}`)}</li>
        ))}
      </ul>,
    )
    bullets = null
  }

  for (const line of lines) {
    const trimmed = line.trim()

    if (!trimmed) {
      flushBullets()
      continue
    }

    const bullet = parseBullet(line)
    if (bullet) {
      if (!bullets) bullets = []
      bullets.push(bullet)
      continue
    }

    flushBullets()
    blocks.push(<p key={`p-${key++}`}>{inline(trimmed, `p-${key}`)}</p>)
  }

  flushBullets()
  return blocks.length ? blocks : null
}