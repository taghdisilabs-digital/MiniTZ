# MiniTZ sandbox shell environment; reuse the already validated interpreter.
if [ -x /state/validation/startup-foundation-venv/bin/python ]; then
    export VIRTUAL_ENV=/state/validation/startup-foundation-venv
    export PATH="$VIRTUAL_ENV/bin:$PATH"
fi
