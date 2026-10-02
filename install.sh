#!/usr/bin/env bash
set -euo pipefail

APP_NAME="whosup"
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/whosup"
VENV_DIR="${INSTALL_ROOT}/venv"
LOCAL_BIN="${HOME}/.local/bin"
SYSTEM_BIN="/usr/local/bin"

command -v python3 >/dev/null 2>&1 || {
  echo "Error: python3 is required." >&2
  exit 1
}

if ! python3 -c 'import venv' >/dev/null 2>&1; then
  echo "Error: Python venv support is missing." >&2
  echo "On Debian/Ubuntu/Zorin OS, install it with:" >&2
  echo "  sudo apt install python3-venv" >&2
  exit 1
fi

mkdir -p "$INSTALL_ROOT" "$LOCAL_BIN"

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

"${VENV_DIR}/bin/python" -m pip install . >/dev/null

# Always create a user-local launcher.
cat > "${LOCAL_BIN}/whosup" <<LAUNCHER
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/whosup" "\$@"
LAUNCHER
chmod 755 "${LOCAL_BIN}/whosup"

# Also install a launcher into /usr/local/bin when possible, so the command
# works even when ~/.local/bin is not in PATH.
if [ -w "$SYSTEM_BIN" ] || [ "$(id -u)" -eq 0 ]; then
  cat > "${SYSTEM_BIN}/whosup" <<LAUNCHER
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/whosup" "\$@"
LAUNCHER
  chmod 755 "${SYSTEM_BIN}/whosup"
elif command -v sudo >/dev/null 2>&1; then
  TMP_LAUNCHER="$(mktemp)"
  cat > "$TMP_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/whosup" "\$@"
LAUNCHER
  chmod 755 "$TMP_LAUNCHER"
  if sudo install -m 755 "$TMP_LAUNCHER" "${SYSTEM_BIN}/whosup"; then
    rm -f "$TMP_LAUNCHER"
  else
    rm -f "$TMP_LAUNCHER"
    # Fall back to user-local installation below.
  fi
fi

# Persist user-local PATH for shells that use it.
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
for SHELL_RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [ -f "$SHELL_RC" ] && ! grep -Fqx "$PATH_LINE" "$SHELL_RC"; then
    printf '%s\n' '' "# whOS's up?" "$PATH_LINE" >> "$SHELL_RC"
  fi
done

export PATH="${LOCAL_BIN}:${PATH}"

if command -v whosup >/dev/null 2>&1; then
  echo "whOS's up? installed successfully."
  echo "Run: whosup"
else
  echo "whOS's up? installed successfully."
  echo "Open a new terminal, then run: whosup"
fi
