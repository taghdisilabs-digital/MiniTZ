#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK="$ROOT_DIR/ops/workstation/biella-provider-check.sh"
CONFIG="$ROOT_DIR/ops/workstation/biella-provider-configure.sh"
INSTALL="$ROOT_DIR/ops/workstation/install-biella-workstation.sh"

require_file() { [[ -f "$1" ]] || { echo "missing required artifact: $1" >&2; exit 1; }; }
require_literal() {
  local file="$1" literal="$2"
  rg -F --quiet -- "$literal" "$file" || {
    echo "missing provider contract literal in $file: $literal" >&2
    exit 1
  }
}

for f in "$CHECK" "$CONFIG" "$INSTALL"; do require_file "$f"; done
for name in \
  CLOUDFLARE_API_TOKEN GROQ_API_KEY CEREBRAS_API_KEY OPENROUTER_API_KEY \
  MISTRAL_API_KEY TAVILY_API_KEY GEMINI_API_KEY BIELLA_GOOGLE_API_KEY EXA_API_KEY \
  PINECONE_API_KEY QDRANT_API_KEY QDRANT_URL DEEPGRAM_API_KEY ASSEMBLYAI_API_KEY \
  ELEVENLABS_API_KEY STABILITY_API_KEY; do
  require_literal "$CONFIG" "$name"
done
for name in \
  SUPABASE_PUBLISHABLE_KEY SUPABASE_URL NEON_API_KEY UPSTASH_API_KEY UPSTASH_EMAIL \
  CLOUDINARY_API_KEY CLOUDINARY_API_SECRET CLOUDINARY_CLOUD_NAME AXIOM_API_TOKEN PEXELS_API_KEY; do
  require_literal "$CONFIG" "$name"
done

for literal in \
  'api.pinecone.io/indexes' 'api.deepgram.com/v1/projects' \
  'api.assemblyai.com/v2/transcript' 'api.elevenlabs.io/v1/models' \
  'api.stability.ai/v1/user/account' 'console.neon.tech/api/v2/projects' \
  'api.pexels.com/v1/curated' 'api.axiom.co/v2/tokens' 'api-key:' \
  'NEEDS_LOCATOR' 'CONFIGURED'; do
  require_literal "$CHECK" "$literal"
done

require_literal "$INSTALL" 'biella-provider-configure'
require_literal "$INSTALL" 'biella-provider-check'
bash -n "$CHECK"
bash -n "$CONFIG"
echo 'workstation provider registry: PASS'
