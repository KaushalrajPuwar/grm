import { writeFileSync, unlinkSync } from 'node:fs'
import { JSDOM } from 'jsdom'
import * as esbuild from 'esbuild'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost:5173/',
  pretendToBeVisual: true,
})
global.window = dom.window
global.document = dom.window.document
Object.defineProperty(global, 'navigator', { value: dom.window.navigator, configurable: true })
global.HTMLElement = dom.window.HTMLElement
global.Element = dom.window.Element
global.Node = dom.window.Node
global.requestAnimationFrame = dom.window.requestAnimationFrame
global.IS_REACT_ACT_ENVIRONMENT = true

global.fetch = async () => ({
  ok: true,
  status: 200,
  json: async () => ({
    reply:
      'We could not find a dispatch date for your next cylinder. Would you like us to file a grievance ticket on your behalf?',
    owner: 'reasoning',
    stage: 'reasoned',
    authenticated: true,
    handoffs: [{ frm: 'none', to: 'reasoning', kind: 'to_reasoning', reason: 'No future dispatch in the records.' }],
    qa_verdict: 'pass',
    pending_otp: false,
  }),
})

const bundle = await esbuild.build({
  stdin: {
    contents:
      "import * as React from 'react'\nimport { createRoot } from 'react-dom/client'\nimport { act } from 'react'\nimport App from './src/App.jsx'\nexport { App, createRoot, act, React }\n",
    resolveDir: process.cwd(),
    loader: 'jsx',
  },
  bundle: true,
  format: 'esm',
  write: false,
  packages: 'external',
  jsx: 'automatic',
})

const out = 'tests/.branch.bundle.mjs'
writeFileSync(out, bundle.outputFiles[0].text)
const mod = await import(`../${out}`)
const container = document.getElementById('root')
const root = mod.createRoot(container)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

await mod.act(async () => root.render(mod.React.createElement(mod.App)))
await sleep(20)

const input = container.querySelector('.composer__input')
await mod.act(async () => {
  const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, 'value').set
  setter.call(input, 'why was it blocked?')
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
})
await mod.act(async () => {
  input.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
})
await sleep(80)
await mod.act(async () => {})

const ticked = container.querySelector('.node--ticked')
const on = container.querySelector('.node--on')
let failed = 0
const check = (n, ok) => { if (!ok) failed++; console.log(ok ? 'PASS' : 'FAIL', n) }

check('ticket branch highlighted', ticked !== null)
check('highlight is on route B only', ticked !== null && ticked === on)
check('route A not simultaneously highlighted', container.querySelectorAll('.node--on').length === 1)

unlinkSync(out)
console.log(failed ? `RESULT ${failed} check(s) failed` : 'RESULT branch routing checks passed')
process.exit(failed ? 1 : 0)
