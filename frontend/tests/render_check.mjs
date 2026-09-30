import { writeFileSync, unlinkSync } from 'node:fs'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as esbuild from 'esbuild'

const bundle = await esbuild.build({
  stdin: {
    contents: "import * as React from 'react'\nimport App from './src/App.jsx'\nexport { App }\n",
    resolveDir: process.cwd(),
    loader: 'jsx',
  },
  bundle: true,
  format: 'esm',
  write: false,
  packages: 'external',
  jsx: 'automatic',
})

const out = 'tests/.render_check.bundle.mjs'
writeFileSync(out, bundle.outputFiles[0].text)

try {
  const mod = await import(`../${out}`)
  const html = renderToStaticMarkup(createElement(mod.App))
  console.log('PASS render completed, html length', html.length)

  const checks = {
    'chat panel present': html.includes('class="chat"'),
    'rail present': html.includes('class="rail"'),
    'agent panel present': html.includes('speaking__role'),
    'flow tree root present': html.includes('node--root'),
    'route 01 present': html.includes('>01<'),
    'route 02 present': html.includes('>02<'),
    'route 01 title present': html.includes('Delivery is already moving'),
    'route 02 title present': html.includes('Nothing further will move it'),
    'content visible by default (no hidden reveal)': html.includes('Nothing has been said yet'),
    'skip link present': html.includes('class="skip"'),
    'QA framed as internal': html.includes('The QA agent runs behind the scenes'),
    'not-verified state honest': html.includes('Not verified'),
    'send button present': html.includes('sendbtn'),
  }
  let failed = 0
  for (const [k, v] of Object.entries(checks)) {
    if (!v) failed++
    console.log(v ? 'PASS' : 'FAIL', k)
  }
  const qaSpoken = /class="speaking__role">Quality/.test(html)
  console.log(qaSpoken ? 'FAIL QA shown as who you speak to' : 'PASS QA never shown as who you speak to')
  console.log(failed ? `RESULT ${failed} check(s) failed` : 'RESULT all checks passed')
} finally {
  unlinkSync(out)
}
