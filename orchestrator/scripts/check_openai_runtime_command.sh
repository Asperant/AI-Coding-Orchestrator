#!/usr/bin/env bash
set -e

echo "=== OpenAI Agent Runtime Validation ==="
echo "Checklist:"
echo "1. Required Env Var: OPENAI_API_KEY must be set."
echo "2. Safety Warning: Real API calls require: --agent-runtime openai + --llm-enabled + --confirm-llm-agent"
echo "3. Security: Raw API key is securely handled and never printed."
echo "4. Fallback Behavior: Gracefully uses deterministic runtime if key/provider/contract fails."
echo ""
echo "Safe First Command (Plan Mode):"
echo "PYTHONPATH=src python3 src/main.py --run-orchestrator --mode plan --task \"hello orchestrator\" --agent-runtime openai --llm-enabled --confirm-llm-agent --llm-provider openai --llm-model gpt-4o --llm-api-key-env OPENAI_API_KEY"
echo ""

if [ "${RUN_OPENAI_LIVE_CHECK:-0}" = "1" ]; then
    echo "RUN_OPENAI_LIVE_CHECK=1 detected. Executing live check..."
    PYTHONPATH=src python3 src/main.py --run-orchestrator --mode plan --task "hello orchestrator" --agent-runtime openai --llm-enabled --confirm-llm-agent --llm-provider openai --llm-model gpt-4o --llm-api-key-env OPENAI_API_KEY
else
    echo "Live check skipped. To run the API check, set RUN_OPENAI_LIVE_CHECK=1."
fi
