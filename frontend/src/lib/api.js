/**
 * Turn contract client.
 *
 * The only thing this file knows about the backend. It speaks the same shape
 * the voice team will speak, which is the point: swapping the channel means
 * changing this file and nothing above it.
 */

const ENDPOINT = '/v1/turns'

/**
 * The three agents, named exactly as they are named everywhere else.
 * No invented personas, no marketing names.
 */
export const ROLE_LABEL = {
  none: 'Waiting',
  chat: 'Chat agent',
  reasoning: 'Reasoning agent',
  qa: 'QA agent',
}

/**
 * Neutral wait labels, swapped at random while a turn is pending.
 *
 * Deliberately says nothing about what is happening. Before verification no
 * records are open, so a label claiming to read them would be untrue, and a
 * label naming the agent would leak routing the citizen is not meant to follow.
 */
const WAIT_LABELS = [
  'One moment',
  'Checking',
  'Working on it',
  'Still with you',
  'Almost there',
]

export function pickWaitLabel() {
  return WAIT_LABELS[Math.floor(Math.random() * WAIT_LABELS.length)]
}

const HANDOFF_LABEL = {
  gate_open: 'Identity gate',
  to_reasoning: 'Handed to analysis',
  to_chat: 'Returned to front line',
  qa_pass: 'Checked against the records',
  qa_fail: 'Sent back for correction',
}

/** Fresh session id per tab load. The backend holds no cookie. */
export function newSessionId() {
  return `web-${Math.random().toString(36).slice(2, 10)}`
}

export async function sendTurn(sessionId, text) {
  const response = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, text, channel: 'chat' }),
  })

  if (!response.ok) {
    throw new Error(`The service replied with ${response.status}.`)
  }

  const data = await response.json()
  return {
    reply: data.reply,
    owner: data.owner,
    stage: data.stage,
    authenticated: data.authenticated,
    handoffs: (data.handoffs || []).map((h) => ({
      ...h,
      label: HANDOFF_LABEL[h.kind] || h.kind,
    })),
    qaVerdict: data.qa_verdict,
    pendingOtp: data.pending_otp,
  }
}