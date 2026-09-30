import { useEffect, useRef, useState } from 'react'
import { sendTurn, newSessionId, pickWaitLabel, ROLE_LABEL } from './lib/api.js'
import { renderMessage } from './lib/format.jsx'

/**
 * One conversation, one session, one owner at a time.
 *
 * The backend decides who answers. This component only renders what it is told
 * and never guesses an owner of its own, so the panel cannot disagree with the
 * harness about who is speaking.
 */
export default function App() {
  const [sessionId] = useState(newSessionId)
  const [turns, setTurns] = useState([])
  const [owner, setOwner] = useState('none')
  const [handoffs, setHandoffs] = useState([])
  const [authenticated, setAuthenticated] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [error, setError] = useState('')
  const [branch, setBranch] = useState(null)
  const [waitLabel, setWaitLabel] = useState('')

  const logRef = useRef(null)

  // Keep the newest turn in view as the conversation grows.
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [turns, waiting])

  async function submit(text) {
    const trimmed = text.trim()
    if (!trimmed || waiting) return

    setError('')
    setTurns((prev) => [...prev, { who: 'me', text: trimmed }])
    setWaitLabel(pickWaitLabel())
    setWaiting(true)

    try {
      const result = await sendTurn(sessionId, trimmed)
      setTurns((prev) => [...prev, { who: 'them', text: result.reply, owner: result.owner }])
      setOwner(result.owner)
      setHandoffs(result.handoffs)
      setAuthenticated(result.authenticated)
      setBranch(readBranch(result.reply))
    } catch {
      setError(
        'I could not reach the service. Check that the backend is running, then try again.',
      )
    } finally {
      setWaiting(false)
    }
  }

  return (
    <>
      <a className="skip" href="#conversation">
        Skip to the conversation
      </a>
      <main className="shell">
        <ChatPanel
          turns={turns}
          waiting={waiting}
          waitLabel={waitLabel}
          error={error}
          logRef={logRef}
          onSubmit={submit}
          sessionId={sessionId}
          authenticated={authenticated}
        />
        <aside className="rail">
          <AgentPanel owner={owner} handoffs={handoffs} authenticated={authenticated} />
          <FlowPanel branch={branch} />
        </aside>
      </main>
    </>
  )
}

/**
 * Which of the two demo outcomes the last reply points at.
 *
 * Demo scaffolding on purpose. This reads the reply for the signals a real
 * deployment would instead receive as an explicit disposition field on the turn
 * contract, and it lives only here: no agent prompt mentions either route, and
 * the backend knows nothing about it.
 */
function readBranch(reply) {
  const text = String(reply || '').toLowerCase()
  if (!text) return null

  const moving =
    /\bon (?:its|their) way\b|\bdispatched\b|\bdelivered\b|\bin transit\b|\bawaiting\b|\bon its way\b/.test(
      text,
    )
  const escalate =
    /\bfile a (?:grievance|ticket|complaint)\b|\bno (?:future|scheduled) dispatch\b|\bsubmit a (?:ticket|complaint)\b|\bfile a complaint\b/.test(
      text,
    )

  if (escalate) return 'ticket'
  if (moving) return 'delivery'
  return null
}

function ChatPanel({
  turns,
  waiting,
  waitLabel,
  error,
  logRef,
  onSubmit,
  sessionId,
  authenticated,
}) {
  return (
    <section className="chat" aria-label="Conversation" id="conversation">
      <header className="chat__head">
        <div>
          <h1 className="chat__title">Grievance service</h1>
          <p className="chat__sub">Ask about a benefit, or a problem you had receiving one.</p>
        </div>
        <span className="chat__session">
          <b className={authenticated ? 'is-open' : undefined}>
            {authenticated ? 'Verified' : 'Not verified'}
          </b>
          {sessionId}
        </span>
      </header>

      <div className="chat__log" ref={logRef} role="log" aria-live="polite">
        {turns.length === 0 && (
          <p className="empty">
            Nothing has been said yet. Tell me which scheme this is about, or what you were
            expecting to receive.
          </p>
        )}

        {turns.map((turn, i) =>
          turn.who === 'me' ? (
            <div className="turn turn--mine" key={i}>
              <div className="bubble bubble--mine">{turn.text}</div>
            </div>
          ) : (
            <div className="turn" key={i}>
              <span className="turn__who">{ROLE_LABEL[turn.owner] || 'Assistant'}</span>
              <div className="bubble bubble--theirs">{renderMessage(turn.text)}</div>
            </div>
          ),
        )}

        {waiting && (
          <div className="waiting">
            <span className="dots" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            <span className="waiting__label">{waitLabel}</span>
          </div>
        )}
      </div>

      <Composer onSubmit={onSubmit} waiting={waiting} error={error} />
    </section>
  )
}

function Composer({ onSubmit, waiting, error }) {
  const [value, setValue] = useState('')
  const areaRef = useRef(null)

  function submit(event) {
    event.preventDefault()
    if (!value.trim() || waiting) return
    onSubmit(value)
    setValue('')
    requestAnimationFrame(() => {
      if (areaRef.current) {
        areaRef.current.style.height = 'auto'
        areaRef.current.focus()
      }
    })
  }

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer__row">
        <div className="composer__field">
          <textarea
            ref={areaRef}
            className="composer__input"
            rows={1}
            value={value}
            placeholder="Type your message"
            aria-label="Your message"
            onChange={(e) => {
              setValue(e.target.value)
              const el = e.target
              el.style.height = 'auto'
              el.style.height = `${Math.min(el.scrollHeight, 132)}px`
            }}
            onKeyDown={(e) => {
              // Enter sends. Shift and Enter is a newline.
              if (e.key === 'Enter' && !e.shiftKey) submit(e)
            }}
          />
          <button
            type="button"
            className="iconbtn"
            aria-label="Attach a document"
            title="Attach a document"
          >
            <Paperclip />
          </button>
        </div>
        <button
          type="submit"
          className="sendbtn"
          disabled={waiting || !value.trim()}
          aria-label="Send message"
        >
          <Arrow />
        </button>
      </div>

      <p className="composer__hint">
        <kbd>Enter</kbd> sends · <kbd>Shift</kbd> + <kbd>Enter</kbd> for a new line
      </p>
      {error && <p className="composer__error">{error}</p>}
    </form>
  )
}

/** Bespoke marks. One family, one stroke weight, bare on the surface. */
function Paperclip() {
  return (
    <svg width="17" height="17" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M14.5 9.2 8.9 14.8a3.4 3.4 0 0 1-4.8-4.8l6.6-6.6a2.3 2.3 0 0 1 3.2 3.2l-6.5 6.5a1.1 1.1 0 0 1-1.6-1.6l5.7-5.7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Arrow() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M3.5 10h13m0 0-4.8-4.8M16.5 10l-4.8 4.8"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function AgentPanel({ owner, handoffs, authenticated }) {
  const spoken = owner !== 'none' && owner !== 'qa'
  const label = spoken ? ROLE_LABEL[owner] : 'Not connected'
  const note = !authenticated
    ? 'Identity is being verified. No records are open yet.'
    : spoken
      ? 'Handling your conversation.'
      : 'The QA agent never speaks to you directly.'

  return (
    <section className="panel" aria-label="Who is answering">
      <header className="panel__head">
        <h2 className="panel__title">You are speaking with</h2>
      </header>
      <div className="panel__body">
        <div className="speaking">
          <h3 className="speaking__role">{label}</h3>
        </div>
        <p className="speaking__note">{note}</p>

        {handoffs.length === 0 ? (
          <p className="empty">No handoffs yet.</p>
        ) : (
          handoffs.map((h, i) => (
            <div className={`handoff handoff--${h.kind}`} key={i}>
              <span className="handoff__mark" aria-hidden="true" />
              <span className="handoff__text">
                <b>{h.label}</b>
                <span className="handoff__why">{shorten(h.reason)}</span>
              </span>
            </div>
          ))
        )}

        <p className="internal">
          <b>The QA agent runs behind the scenes.</b> It never speaks to you, and an answer
          only reaches you after it has been checked against your records.
        </p>
      </div>
    </section>
  )
}

function shorten(text) {
  if (!text) return ''
  const flat = String(text).replace(/\s+/g, ' ').trim()
  return flat.length > 96 ? `${flat.slice(0, 96)}…` : flat
}

function FlowPanel({ branch }) {
  return (
    <section className="panel" aria-label="How this conversation is routed">
      <header className="panel__head">
        <h2 className="panel__title">Where this conversation stands</h2>
      </header>
      <div className="panel__body">
        <p className="flow__lede">
          A benefit problem takes one of two routes. The check runs behind the
          conversation and never speaks to you.
        </p>
        <div className="tree">
          <div className="node node--root">Beneficiary reports a benefit problem</div>
          <div className="link" />

          <div className="node node--branch">Are the records enough to explain it?</div>

          <div className="fork">
            <span className="fork__stem" />
            <span className="fork__base" />
          </div>

          <div className="legs">
            <div className="leg">
              <p className="leg__cap">01</p>
              <div className={`node ${branch === 'delivery' ? 'node--on' : 'node--off'}`}>
                Delivery is already moving
                <span className="node__sub">
                  Dispatched or scheduled. The answer gives the date and the beneficiary waits.
                </span>
              </div>
            </div>
            <div className="leg">
              <p className="leg__cap">02</p>
              <div
                className={`node ${branch === 'ticket' ? 'node--on node--ticked' : 'node--off'}`}
              >
                Nothing further will move it
                <span className="node__sub">
                  No future dispatch. A grievance ticket is offered on their behalf.
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}