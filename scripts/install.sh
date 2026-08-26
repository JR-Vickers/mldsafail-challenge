#!/usr/bin/env bash
# Install the mldsafail CLI.
# Safe to pipe to sh: curl -fsSL .../install.sh | sh
set -euo pipefail

FAILED=0
USAGE="Usage: curl -fsSL https://github.com/JR-Vickers/mldsafail-challenge/raw/main/scripts/install.sh | sh"

detect_platform() {
    local os
    os="$(uname -s)"
    case "$os" in
        Darwin) echo "macos" ;;
        Linux) echo "linux" ;;
        *) echo "unknown" ;;
    esac
}

banner() {
    echo "mldsafail CLI installer"
    echo ""
}

check_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

install_with_uv() {
    echo "Installing mldsafail with uv (uv tool install)..."
    if uv tool install mldsafail-challenge >/dev/null 2>&1; then
        echo "Installed mldsafail via uv tool install."
        return 0
    fi
    echo "uv tool install failed." >&2
    return 1
}

install_with_pip() {
    echo "Installing mldsafail with pip..."
    if python3 -m pip install mldsafail-challenge >/dev/null 2>&1; then
        echo "Installed mldsafail via pip."
        return 0
    fi
    echo "pip install failed. If you have the repository checked out, try: pip install -e ." >&2
    return 1
}

print_next_steps() {
    echo ""
    echo "Next steps:"
    echo "  mldsafail login TOKEN --server https://mldsa.fail"
    echo "  mldsafail clone [DIR]        # create a participant workspace"
    echo "  mldsafail submit --repo URL --commit SHA --hypothesis \"...\""
    echo "  mldsafail status SUBMISSION_ID --follow"
    echo ""
    echo "Local development (no account needed):"
    echo "  git clone https://github.com/JR-Vickers/mldsafail-challenge.git"
    echo "  cd mldsafail-challenge"
    echo "  uv sync --extra dev"
    echo "  source .venv/bin/activate"
    echo "  make test && make bench && make web"
    echo ""
}

main() {
    banner

    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        echo "$USAGE"
        echo ""
        echo "Installs the mldsafail CLI on macOS or Linux."
        exit 0
    fi

    PLATFORM="$(detect_platform)"
    if [[ "$PLATFORM" == "unknown" ]]; then
        echo "Unsupported platform: $(uname -s). Only macOS and Linux are supported." >&2
        exit 1
    fi

    if check_uv; then
        if ! install_with_uv; then
            echo "Falling back to pip..." >&2
            if ! install_with_pip; then
                echo "Installation failed." >&2
                exit 1
            fi
        fi
    else
        echo "uv not found. Installing with pip..." >&2
        if ! install_with_pip; then
            echo "Installation failed. Install uv (https://docs.astral.sh/uv/) or check out the repository and run: pip install -e ." >&2
            exit 1
        fi
    fi

    print_next_steps
}

main "$@"
