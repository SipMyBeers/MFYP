#!/bin/bash
# Gormers Colony Validation Suite
# Run from MacBook after all setup is complete: bash validate.sh

echo "=== GORMERS VALIDATION SUITE ==="
echo ""

PASS=0
FAIL=0

check() {
    if eval "$2" > /dev/null 2>&1; then
        echo "  ✓ $1"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $1"
        FAIL=$((FAIL + 1))
    fi
}

# Tailscale connectivity
echo "— Network —"
check "Tailscale — Ghengis reachable" "ping -c 1 -W 3 ghengis"
check "Tailscale — Nikola reachable"  "ping -c 1 -W 3 nikola"

# SSH keyless auth
echo ""
echo "— SSH —"
SSH_KEY="$HOME/.ssh/mfyp_automation"
if [ -f "$SSH_KEY" ]; then
    check "SSH keyless — Ghengis" "ssh -i $SSH_KEY -o ConnectTimeout=5 beers@ghengis 'echo ok' | grep -q ok"
    check "SSH keyless — Nikola"  "ssh -i $SSH_KEY -o ConnectTimeout=5 beers@nikola 'echo ok' | grep -q ok"
else
    check "SSH keyless — Ghengis" "ssh -o ConnectTimeout=5 beers@ghengis 'echo ok' | grep -q ok"
    check "SSH keyless — Nikola"  "ssh -o ConnectTimeout=5 beers@nikola 'echo ok' | grep -q ok"
fi

# Ollama
echo ""
echo "— Inference —"
check "Ollama — Ghengis serving Gemma" \
    "ssh beers@ghengis 'curl -s http://localhost:11434/api/tags' | grep -q gemma2"
check "Ollama — Nikola serving Gemma" \
    "ssh beers@nikola 'curl -s http://localhost:11434/api/tags' | grep -q gemma2"

# Cloudflare tunnels (test from MacBook through public URL)
echo ""
echo "— Tunnels —"
GHENGIS_TUNNEL=$(fly secrets list -a gormers 2>/dev/null | grep OLLAMA_BASE_URL | awk '{print $2}')
NIKOLA_TUNNEL=$(fly secrets list -a gormers 2>/dev/null | grep OLLAMA_SECONDARY_URL | awk '{print $2}')

if [ -n "$GHENGIS_TUNNEL" ]; then
    check "Ghengis tunnel reachable" "curl -sf '$GHENGIS_TUNNEL/api/tags' | grep -q models"
else
    echo "  ? Ghengis tunnel — OLLAMA_BASE_URL not in Fly secrets"
    FAIL=$((FAIL + 1))
fi

if [ -n "$NIKOLA_TUNNEL" ]; then
    check "Nikola tunnel reachable" "curl -sf '$NIKOLA_TUNNEL/api/tags' | grep -q models"
else
    echo "  ? Nikola tunnel — OLLAMA_SECONDARY_URL not in Fly secrets (optional)"
fi

# Platform
echo ""
echo "— Platform —"
check "gormers.com responding" "curl -sf https://gormers.com > /dev/null"

# MFYP process
echo ""
echo "— MFYP —"
check "MFYP running on Ghengis" "ssh beers@ghengis 'pgrep -f mfyp_orchestrator'"

# Summary
echo ""
echo "=== RESULTS: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "All checks passed. Colony is live."
    echo "Check Telegram for briefing messages to confirm full loop."
else
    echo ""
    echo "Some checks failed. Fix issues above and re-run."
fi
