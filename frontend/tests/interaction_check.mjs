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

// Stub the turn endpoint. Answers arrive with a delay so the waiting state can
// be observed mid-flight, exactly as it would be against a real backend.
const calls = []
let reply = {
  reply: 'Your cylinder was dispatched on 18 August 2026 and is expected by 21 August 2026.',
  owner: 'reasoning',
  stage: 'reasoned',
  authenticated: true,
  handoffs: [{ frm: 'none', to: 'reasoning', kind: 'to_reasoning', reason: 'Requires relations read across enrolment, cycle, order, and blocker records.' }],
  qa_verdict: 'pass',
  pending_otp: false,
}

global.fetch = async (url, opts) => {
  calls.push(JSON.parse(opts.body))
  await new Promise((r) => setTimeout(r, 60))
  return {
    ok: true,
    status: 200,
    json: async () => reply,
  }
}

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

const out = 'tests/.interaction.bundle.mjs'
writeFileSync(out, bundle.outputFiles[0].text)
const mod = await import(`../${out}`)

const container = document.getElementById('root')
const root = mod.createRoot(container)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => {
  results.push({ name, ok })
  console.log(ok ? 'PASS' : 'FAIL', name)
}

await mod.act(async () => {
  root.render(mod.React.createElement(mod.App))
})
await sleep(20)

check('app mounts', container.textContent.includes('Grievance service'))
check('masthead carries real presence', container.querySelector('.chat__sub')?.textContent.length > 20)
check('flow tree both routes render', container.textContent.includes('Delivery is already moving') && container.textContent.includes('Nothing further will move it'))
check('QA framed internal', container.textContent.includes('The QA agent runs behind the scenes'))
check('starts not verified', container.textContent.includes('Not verified'))

// Type into the composer and press Enter.
const input = container.querySelector('.composer__input')
check('composer input exists', Boolean(input))
check('composer starts empty', input.value === '')

await mod.act(async () => {
  const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, 'value').set
  setter.call(input, 'when will my cylinder arrive?')
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
})
await sleep(10)

check('text lands in the field', input.value === 'when will my cylinder arrive?')

// Enter must send, without touching the send button.
await mod.act(async () => {
  input.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
})
await sleep(10)

check('Enter sent the turn', calls.length === 1)
check('turn carried the typed text', calls[0]?.text === 'when will my cylinder arrive?')
check('outgoing bubble rendered', container.textContent.includes('when will my cylinder arrive?'))
check('composer cleared after send', input.value === '')
check('loading indicator shown while waiting', container.querySelector('.dots') !== null)
const waitText = container.querySelector('.waiting__label')?.textContent ?? ''
check('wait label is neutral, never claims to read records', waitText.length > 0 && !/record/i.test(waitText), `got "${waitText}"`)

await sleep(140)
await mod.act(async () => {})

check('reply rendered', container.textContent.includes('expected by 21 August 2026'))
check('agent panel updated to reasoning', container.querySelector('.speaking__role')?.textContent.includes('Reasoning agent'))
check('handoff trail shown', container.textContent.includes('Handed to analysis'))
check('loading indicator removed after reply', container.querySelector('.dots') === null)
check('session marked verified', container.textContent.includes('Verified'))

// Route highlighting from the reply.
check('flow tree highlights the delivery route', container.querySelector('.node--on') !== null)
check('escalation route stays dimmed', container.querySelectorAll('.node--ticked').length === 0)

// Shift+Enter must NOT send.
await mod.act(async () => {
  const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, 'value').set
  setter.call(input, 'second message')
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
})
await sleep(10)
const before = calls.length
await mod.act(async () => {
  input.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', shiftKey: true, bubbles: true }))
})
await sleep(10)
check('Shift+Enter does not send', calls.length === before)

unlinkSync(out)

const failed = results.filter((r) => !r.ok)
console.log(failed.length ? `RESULT ${failed.length} check(s) failed` : 'RESULT all interaction checks passed')
process.exit(failed.length ? 1 : 0)
