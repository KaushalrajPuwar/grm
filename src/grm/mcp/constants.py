"""Server identity and instructions, shared by the tools and the transport."""

SERVER_NAME = "grm-dialogue"
SERVER_VERSION = "1.0.0"
MCP_PREFIX = "/mcp"

INSTRUCTIONS = """\
This server is the beneficiary dialogue backend for a government social-benefit
service. Call route_turn once per transcribed utterance, with a session_id that
stays stable for the whole call. The reply carries `expects`, which tells the
caller what to ask next: beneficiary_id, otp, message, or closed. Call
reset_session on hangup. An answer is only trustworthy once authenticated is
true; before that, no record has been opened.
"""
