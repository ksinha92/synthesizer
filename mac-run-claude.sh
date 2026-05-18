#!/bin/bash
# =============================================================================
# mac-run-claude.sh
# ANSI color support
R='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
BCYAN='\033[1;96m'
BGREEN='\033[1;92m'
BYELLOW='\033[1;93m'
CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
WHITE='\033[97m'
GRAY='\033[90m'
# =============================================================================
# mac-run-claude.sh
# Launches Claude Code with the Ameritas LiteLLM proxy configuration.
# Checks for required prerequisites and offers to install them.
# Saves LANID, auth token, and preferences to ~/.ameritas-claude/config
# =============================================================================
# -----------------------------------------------------------------------------
# Banner
# -----------------------------------------------------------------------------
echo ""
printf "${BCYAN}     ___                         _ __            ${R}\n"
printf "${BCYAN}    /   |  ____ ___  ___  _____(_) /_____ ______${R}\n"
printf "${BCYAN}   / /| | / __ \`__ \\/ _ \\/ ___/ / __/ __ \`/ ___/${R}\n"
printf "${BCYAN}  / ___ |/ / / / / /  __/ /  / / /_/ /_/ (__  ) ${R}\n"
printf "${BCYAN} /_/  |_/_/ /_/ /_/\\___/_/  /_/\\__/\\__,_/____/  ${R}\n"
echo ""
printf "  ${WHITE}Claude Code Launcher${R}  ${GRAY}|${R}  ${WHITE}Enterprise AI Gateway${R}  ${GRAY}|${R}  ${YELLOW}macOS${R}\n"
printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
echo ""
# -----------------------------------------------------------------------------
# Model ID constants
#   Opus tier maps to Sonnet until Opus is enabled in the gateway.
#   When Opus is enabled, update MODEL_OPUS below.
# -----------------------------------------------------------------------------
MODEL_SONNET="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
MODEL_HAIKU="us.anthropic.claude-haiku-4-5-20251001-v1:0"
MODEL_OPUS="us.anthropic.claude-opus-4-5-20251101-v1:0"
# When a newer Opus cross-region profile is added to the gateway, update MODEL_OPUS.
# Set to 1 when Opus models are enabled in the Ameritas LiteLLM gateway.
OPUS_ENABLED=0
# Approved Claude Code version for this enterprise deployment.
APPROVED_VERSION="2.1.91"
# -----------------------------------------------------------------------------
# Config file paths
# -----------------------------------------------------------------------------
CONFIG_DIR="$HOME/.ameritas-claude"
CONFIG_FILE="$CONFIG_DIR/config"
# -----------------------------------------------------------------------------
# Load saved config if it exists
# -----------------------------------------------------------------------------
LANID=""
AUTH_TOKEN=""
DEFAULT_MODEL="sonnet"
TEAM_NAME="unassigned"
EFFORT_LEVEL="high"
VSCODE_CONFIGURED=0
CONFIG_LOADED=0
TEAM_LOADED=0
if [ -f "$CONFIG_FILE" ]; then
    # Source the config (KEY=VALUE format, lines starting with # ignored)
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        case "$key" in
            LANID)             LANID="$value" ;;
            AUTH_TOKEN)        AUTH_TOKEN="$value" ;;
            DEFAULT_MODEL)     DEFAULT_MODEL="$value" ;;
            TEAM_NAME)         TEAM_NAME="$value"; TEAM_LOADED=1 ;;
            EFFORT_LEVEL)      EFFORT_LEVEL="$value" ;;
            VSCODE_CONFIGURED) VSCODE_CONFIGURED="$value" ;;
        esac
    done < "$CONFIG_FILE"
    if [ -n "$LANID" ]; then
        CONFIG_LOADED=1
        MASKED_TOKEN="${AUTH_TOKEN:0:8}..."
        [ -z "$AUTH_TOKEN" ] && MASKED_TOKEN="(not saved)"
        printf "  ${BGREEN}Saved config loaded${R}\n"
        printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
        printf "   ${GRAY}LANID  ${R}${WHITE}$LANID${R}\n"
        printf "   ${GRAY}Token  ${R}${WHITE}$MASKED_TOKEN${R}\n"
        printf "   ${GRAY}Model  ${R}${WHITE}$DEFAULT_MODEL${R}\n"
        printf "   ${GRAY}Team   ${R}${WHITE}$TEAM_NAME${R}\n"
        printf "   ${GRAY}Effort ${R}${WHITE}$EFFORT_LEVEL${R}\n"
        printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
        echo ""
        read -p "  Press Enter to continue, or type 'r' to re-enter: " RELOAD
        [ "$RELOAD" = "r" ] && CONFIG_LOADED=0
        echo ""
    fi
fi
# -----------------------------------------------------------------------------
# Prompt for LANID (skipped if loaded from config)
# -----------------------------------------------------------------------------
if [ "$CONFIG_LOADED" -eq 0 ]; then
    read -p "Enter your LANID:               " LANID
fi
# -----------------------------------------------------------------------------
# Prerequisite checks
# -----------------------------------------------------------------------------
MISSING=0
echo ""
CLAUDE_BIN=""
CLAUDE_VER=""
LANID_HOME="/Users/$LANID"
if command -v claude &>/dev/null; then
    CLAUDE_BIN=$(command -v claude)
    CLAUDE_VER=$("$CLAUDE_BIN" --version 2>/dev/null)
elif [ -n "$LANID" ] && [ -x "$LANID_HOME/.local/bin/claude" ]; then
    CLAUDE_BIN="$LANID_HOME/.local/bin/claude"
    CLAUDE_VER=$("$CLAUDE_BIN" --version 2>/dev/null)
elif [ -x "$HOME/.local/bin/claude" ]; then
    CLAUDE_BIN="$HOME/.local/bin/claude"
    CLAUDE_VER=$("$CLAUDE_BIN" --version 2>/dev/null)
else
    printf "  ${RED}[!!]${R} Claude Code  ${RED}NOT FOUND${R}\n"
    MISSING=1
fi
if [ "$MISSING" -eq 0 ]; then
    if echo "$CLAUDE_VER" | grep -qF "$APPROVED_VERSION"; then
        printf "  ${BGREEN}[OK]${R} Claude Code  ${CYAN}$CLAUDE_VER${R}  ${GRAY}$CLAUDE_BIN${R}\n"
    else
        printf "  ${YELLOW}[!!]${R} Claude Code  ${YELLOW}$CLAUDE_VER${R}  ${GRAY}(approved: v$APPROVED_VERSION)${R}\n"
        echo ""
        read -p "  Version mismatch. Update to v$APPROVED_VERSION now? [Y/n]: " AUTO_UPDATE
        if [[ "$AUTO_UPDATE" =~ ^[nN]$ ]]; then
            echo ""
            printf "   ${YELLOW}Proceeding with unapproved version.${R}\n"
            echo ""
        else
            echo ""
            export HTTP_PROXY="http://proxy.ameritas.com:8080"
            export HTTPS_PROXY="http://proxy.ameritas.com:8080"
            if ! command -v npm &>/dev/null; then
                printf "  ${RED}[!!]${R} npm not found -- cannot update automatically.\n"
                echo "   Install Node.js 18+ and re-run, or run manually:"
                echo "     npm install -g @anthropic-ai/claude-code@$APPROVED_VERSION"
                echo ""
                unset HTTP_PROXY HTTPS_PROXY
            else
                echo "   Updating Claude Code to v$APPROVED_VERSION ..."
                npm install -g "@anthropic-ai/claude-code@$APPROVED_VERSION"
                unset HTTP_PROXY HTTPS_PROXY
                echo ""
                CLAUDE_BIN=""
                CLAUDE_VER=""
                command -v claude &>/dev/null && CLAUDE_BIN=$(command -v claude)
                [ -z "$CLAUDE_BIN" ] && [ -n "$LANID" ] && [ -x "$LANID_HOME/.local/bin/claude" ] && CLAUDE_BIN="$LANID_HOME/.local/bin/claude"
                [ -z "$CLAUDE_BIN" ] && [ -x "$HOME/.local/bin/claude" ] && CLAUDE_BIN="$HOME/.local/bin/claude"
                if [ -n "$CLAUDE_BIN" ]; then
                    CLAUDE_VER=$("$CLAUDE_BIN" --version 2>/dev/null)
                    printf "  ${BGREEN}[OK]${R} Claude Code updated  ${CYAN}$CLAUDE_VER${R}  ${GRAY}$CLAUDE_BIN${R}\n"
                else
                    printf "  ${RED}[!!]${R} Update may have failed -- check output above.\n"
                fi
                echo ""
            fi
        fi
    fi
fi
echo ""
# --- If Claude Code is missing, show install guidance ---
if [ "$MISSING" -eq 1 ]; then
    printf "  ${BYELLOW}Missing prerequisites detected${R}\n"
    printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
    echo ""
    echo "  Claude Code CLI"
    echo "    Recommended — Native installer:"
    echo "      curl -fsSL https://claude.ai/install.sh | bash"
    echo ""
    echo "    Alternative — Homebrew:"
    echo "      brew install --cask claude-code"
    echo ""
    echo "    Alternative — npm (requires Node.js 18+):"
    echo "      npm install -g @anthropic-ai/claude-code"
    echo ""
    read -p "  Would you like this script to attempt automatic installation? (y/N): " AUTO_INSTALL
    if [[ "$AUTO_INSTALL" =~ ^[Yy]$ ]]; then
        echo ""
        export HTTP_PROXY="http://proxy.ameritas.com:8080"
        export HTTPS_PROXY="http://proxy.ameritas.com:8080"
        if command -v brew &>/dev/null; then
            echo "   Installing Claude Code via Homebrew..."
            brew install --cask claude-code
        elif command -v npm &>/dev/null; then
            echo "   Homebrew not found. Installing Claude Code via npm..."
            npm install -g "@anthropic-ai/claude-code@$APPROVED_VERSION"
        else
            echo "   Installing Claude Code via native installer..."
            curl -fsSL https://claude.ai/install.sh | bash
        fi
        echo ""
        unset HTTP_PROXY HTTPS_PROXY
        # Re-resolve the binary
        CLAUDE_BIN=""
        command -v claude &>/dev/null && CLAUDE_BIN=$(command -v claude)
        [ -z "$CLAUDE_BIN" ] && [ -n "$LANID" ] && [ -x "$LANID_HOME/.local/bin/claude" ] && CLAUDE_BIN="$LANID_HOME/.local/bin/claude"
        [ -z "$CLAUDE_BIN" ] && [ -x "$HOME/.local/bin/claude" ] && CLAUDE_BIN="$HOME/.local/bin/claude"
        if [ -z "$CLAUDE_BIN" ]; then
            echo "  [!!]  Installation may have failed. Please check the output above."
            echo ""
            read -p "Press Enter to exit..."
            exit 1
        fi
        echo "  [OK]  Claude Code installed at $CLAUDE_BIN"
        echo ""
    else
        echo ""
        echo "  Please install Claude Code and re-run this script."
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi
fi
# -----------------------------------------------------------------------------
# Prompt for auth token (skipped if loaded from config)
# -----------------------------------------------------------------------------
if [ "$CONFIG_LOADED" -eq 0 ] || [ -z "$AUTH_TOKEN" ]; then
    read -sp "Enter your Anthropic Auth Token: " AUTH_TOKEN
    echo ""
    echo ""
fi
# -----------------------------------------------------------------------------
# Model selection menu
# -----------------------------------------------------------------------------
printf "  ${BYELLOW}Model Selection${R}\n"
printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
echo ""
printf "   ${CYAN}1${R}  Sonnet 4.5   ${GRAY}·${R}  balanced speed & quality  ${GREEN}(recommended)${R}\n"
printf "   ${CYAN}2${R}  Haiku 4.5    ${GRAY}·${R}  fast, lowest cost\n"
if [ "$OPUS_ENABLED" = "1" ]; then
    printf "   ${CYAN}3${R}  OpusPlan     ${GRAY}·${R}  Opus for planning, Sonnet for tasks\n"
else
    printf "   ${GRAY}3  OpusPlan     .  not available -- Opus not yet enabled in gateway${R}\n"
fi
echo ""
MODEL_DEFAULT_NUM=1
[ "$DEFAULT_MODEL" = "haiku" ] && MODEL_DEFAULT_NUM=2
if [ "$DEFAULT_MODEL" = "opusplan" ]; then
    if [ "$OPUS_ENABLED" = "1" ]; then
        MODEL_DEFAULT_NUM=3
    else
        MODEL_DEFAULT_NUM=1
        printf "   ${YELLOW}Saved model 'opusplan' is unavailable -- defaulting to Sonnet.${R}\n"
        echo ""
    fi
fi
read -p "  Select [1-2] (default: $MODEL_DEFAULT_NUM): " MODEL_CHOICE
MODEL_CHOICE="${MODEL_CHOICE:-$MODEL_DEFAULT_NUM}"
echo ""
case "$MODEL_CHOICE" in
    2)
        LAUNCH_MODEL="$MODEL_HAIKU"
        TIER_OPUS="$MODEL_HAIKU"
        TIER_SONNET="$MODEL_HAIKU"
        TIER_HAIKU="$MODEL_HAIKU"
        TIER_SUBAGENT="$MODEL_HAIKU"
        DEFAULT_MODEL="haiku"
        LAUNCH_LABEL="Haiku 4.5"
        ;;
    3)
        if [ "$OPUS_ENABLED" = "1" ]; then
            LAUNCH_MODEL="$MODEL_OPUS"
            TIER_OPUS="$MODEL_OPUS"
            TIER_SONNET="$MODEL_SONNET"
            TIER_HAIKU="$MODEL_HAIKU"
            TIER_SUBAGENT="$MODEL_HAIKU"
            DEFAULT_MODEL="opusplan"
            LAUNCH_LABEL="OpusPlan [Opus + Sonnet + Haiku]"
        else
            printf "   ${YELLOW}OpusPlan is not available. Falling back to Sonnet.${R}\n"
            echo ""
            LAUNCH_MODEL="$MODEL_SONNET"
            TIER_OPUS="$MODEL_SONNET"
            TIER_SONNET="$MODEL_SONNET"
            TIER_HAIKU="$MODEL_HAIKU"
            TIER_SUBAGENT="$MODEL_HAIKU"
            DEFAULT_MODEL="sonnet"
            LAUNCH_LABEL="Sonnet 4.5"
        fi
        ;;
    *)
        LAUNCH_MODEL="$MODEL_SONNET"
        TIER_OPUS="$MODEL_SONNET"
        TIER_SONNET="$MODEL_SONNET"
        TIER_HAIKU="$MODEL_HAIKU"
        TIER_SUBAGENT="$MODEL_HAIKU"
        DEFAULT_MODEL="sonnet"
        LAUNCH_LABEL="Sonnet 4.5"
        ;;
esac
# -----------------------------------------------------------------------------
# Team selection (skipped if loaded from config)
# -----------------------------------------------------------------------------
if [ "$TEAM_LOADED" -eq 0 ]; then
    printf "  ${BYELLOW}Team Assignment${R}\n"
    printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
    echo ""
    read -p "  Enter your team name (default: unassigned): " TEAM_INPUT
    TEAM_NAME="${TEAM_INPUT:-$TEAM_NAME}"
    echo ""
fi
# -----------------------------------------------------------------------------
# Effort level — always shown; saved value used as default
# -----------------------------------------------------------------------------
printf "  ${BYELLOW}Effort Level${R}\n"
printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
echo ""
printf "   ${CYAN}1${R}  high    ${GRAY}·${R}  thorough, longer responses  ${GREEN}[recommended]${R}\n"
printf "   ${CYAN}2${R}  medium  ${GRAY}·${R}  balanced\n"
printf "   ${CYAN}3${R}  low     ${GRAY}·${R}  quick, concise\n"
echo ""
EFFORT_DEFAULT_NUM=1
[ "$EFFORT_LEVEL" = "medium" ] && EFFORT_DEFAULT_NUM=2
[ "$EFFORT_LEVEL" = "low" ]    && EFFORT_DEFAULT_NUM=3
read -p "  Select [1-3] (default: $EFFORT_DEFAULT_NUM): " EFFORT_CHOICE
EFFORT_CHOICE="${EFFORT_CHOICE:-$EFFORT_DEFAULT_NUM}"
case "$EFFORT_CHOICE" in
    2) EFFORT_LEVEL="medium" ;;
    3) EFFORT_LEVEL="low" ;;
    *) EFFORT_LEVEL="high" ;;
esac
echo ""
# -----------------------------------------------------------------------------
# Claude Code settings (~/.claude/settings.json) — one-time setup
# -----------------------------------------------------------------------------
if [ "$VSCODE_CONFIGURED" -eq 0 ]; then
    printf "  ${BYELLOW}IDE Integration [one-time setup]${R}\n"
    printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
    echo ""
    read -p "  Configure Claude Code for the Ameritas gateway now? [Y/n]: " SETUP_CC
    if [[ ! "$SETUP_CC" =~ ^[nN]$ ]]; then
        CLAUDE_SETTINGS_DIR="$HOME/.claude"
        CLAUDE_SETTINGS_FILE="$CLAUDE_SETTINGS_DIR/settings.json"
        mkdir -p "$CLAUDE_SETTINGS_DIR"
        [ ! -f "$CLAUDE_SETTINGS_FILE" ] && echo "{}" > "$CLAUDE_SETTINGS_FILE"
        python3 -c "
import json
try:
    with open('$CLAUDE_SETTINGS_FILE', 'r') as f:
        settings = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    settings = {}
settings['disableLoginPrompt'] = True
env = settings.get('env', {})
env['ANTHROPIC_BASE_URL']                       = 'https://api.ai.inbison.com'
env['ANTHROPIC_AUTH_TOKEN']                     = '$AUTH_TOKEN'
env['ANTHROPIC_MODEL']                          = '$TIER_SONNET'
env['ANTHROPIC_DEFAULT_OPUS_MODEL']             = '$TIER_OPUS'
env['ANTHROPIC_DEFAULT_SONNET_MODEL']           = '$TIER_SONNET'
env['ANTHROPIC_DEFAULT_HAIKU_MODEL']            = '$TIER_HAIKU'
env['CLAUDE_CODE_SUBAGENT_MODEL']               = '$TIER_SUBAGENT'
env['DISABLE_AUTOUPDATER']                      = '1'
env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'] = '1'
env['CLAUDE_CODE_DISABLE_AUTO_COMPACT']         = '0'
env['CLAUDE_CODE_DISABLE_CRON']                 = '0'
env['NODE_TLS_REJECT_UNAUTHORIZED']             = '0'
settings['env'] = env
if 'permissions' not in settings:
    settings['permissions'] = {
        'allow': ['Bash(git *)', 'Bash(npm *)', 'Bash(node *)']
    }
with open('$CLAUDE_SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=4)
" 2>/dev/null
        if [ $? -eq 0 ]; then
            printf "   ${BGREEN}[OK]${R} Claude Code settings written  ${GRAY}$CLAUDE_SETTINGS_FILE${R}\n"
        else
            printf "   ${YELLOW}[!!]${R} Could not write settings automatically.\n"
            printf "   Add the following block to ${WHITE}~/.claude/settings.json${R}\n"
            echo "   (merge into existing JSON, do not replace the whole file)"
            echo ""
            echo "   \"disableLoginPrompt\": true,"
            echo "   \"env\": {"
            echo "     \"ANTHROPIC_BASE_URL\": \"https://api.ai.inbison.com\","
            echo "     \"ANTHROPIC_AUTH_TOKEN\": \"$AUTH_TOKEN\","
            echo "     \"ANTHROPIC_MODEL\": \"$TIER_SONNET\","
            echo "     \"ANTHROPIC_DEFAULT_OPUS_MODEL\": \"$TIER_OPUS\","
            echo "     \"ANTHROPIC_DEFAULT_SONNET_MODEL\": \"$TIER_SONNET\","
            echo "     \"ANTHROPIC_DEFAULT_HAIKU_MODEL\": \"$TIER_HAIKU\","
            echo "     \"CLAUDE_CODE_SUBAGENT_MODEL\": \"$TIER_SUBAGENT\","
            echo "     \"DISABLE_AUTOUPDATER\": \"1\","
            echo "     \"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC\": \"1\","
            echo "     \"CLAUDE_CODE_DISABLE_AUTO_COMPACT\": \"0\","
            echo "     \"CLAUDE_CODE_DISABLE_CRON\": \"0\","
            echo "     \"NODE_TLS_REJECT_UNAUTHORIZED\": \"0\""
            echo "   },"
            echo "   \"permissions\": {"
            echo "     \"allow\": ["
            echo "       \"Bash(git *)\","
            echo "       \"Bash(npm *)\","
            echo "       \"Bash(node *)\""
            echo "     ]"
            echo "   }"
        fi
        echo ""
        # VS Code / Cursor extension install
        if command -v code &>/dev/null; then
            read -p "  Install anthropic.claude-code VS Code extension? [y/N]: " INSTALL_EXT
            if [[ "$INSTALL_EXT" =~ ^[Yy]$ ]]; then
                echo "   Installing..."
                code --install-extension anthropic.claude-code
                echo ""
            fi
        fi
        # Optional SessionStart hook hint
        echo "   Optional SessionStart hook for team attribution:"
        echo "   \"hooks\": {"
        echo "     \"SessionStart\": [{"
        echo "       \"type\": \"command\","
        echo "       \"command\": \"echo CLAUDE_TEAM=$TEAM_NAME >> \\\$CLAUDE_ENV_FILE && echo CLAUDE_DEVELOPER=$LANID >> \\\$CLAUDE_ENV_FILE\""
        echo "     }]"
        echo "   }"
        echo ""
        VSCODE_CONFIGURED=1
    else
        VSCODE_CONFIGURED=1
        echo ""
    fi
fi
# -----------------------------------------------------------------------------
# Save config
# -----------------------------------------------------------------------------
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_FILE" <<EOF
# Ameritas Claude Code config — auto-generated
LANID=$LANID
AUTH_TOKEN=$AUTH_TOKEN
DEFAULT_MODEL=$DEFAULT_MODEL
TEAM_NAME=$TEAM_NAME
EFFORT_LEVEL=$EFFORT_LEVEL
VSCODE_CONFIGURED=$VSCODE_CONFIGURED
EOF
printf "  ${GRAY}Config saved to $CONFIG_FILE${R}\n"
echo ""
# -----------------------------------------------------------------------------
# Launch mode — VS Code or Terminal
# -----------------------------------------------------------------------------
printf "  ${BYELLOW}Launch Mode${R}\n"
printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
echo ""
printf "   ${CYAN}1${R}  Terminal     ${GRAY}·${R}  launch Claude Code in this terminal  ${GREEN}(default)${R}\n"
printf "   ${CYAN}2${R}  VS Code      ${GRAY}·${R}  open VS Code with Claude Code extension\n"
printf "   ${CYAN}3${R}  Cursor       ${GRAY}·${R}  open Cursor with Claude Code extension\n"
echo ""
read -p "  Select [1-3] (default: 1): " LAUNCH_MODE
LAUNCH_MODE="${LAUNCH_MODE:-1}"
echo ""
# -----------------------------------------------------------------------------
# Launch summary
# -----------------------------------------------------------------------------
case "$LAUNCH_MODE" in
    2) LAUNCH_TARGET="VS Code" ;;
    3) LAUNCH_TARGET="Cursor" ;;
    *) LAUNCH_TARGET="Terminal" ;;
esac
printf "  ${BGREEN}Launching Claude Code — $LAUNCH_TARGET${R}\n"
printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
printf "   ${GRAY}Model  ${R}${WHITE}$LAUNCH_LABEL${R}\n"
printf "   ${GRAY}User   ${R}${WHITE}$LANID${R}\n"
printf "   ${GRAY}Team   ${R}${WHITE}$TEAM_NAME${R}\n"
printf "   ${GRAY}Effort ${R}${WHITE}$EFFORT_LEVEL${R}\n"
printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
echo ""
# -----------------------------------------------------------------------------
# Export environment and launch
# -----------------------------------------------------------------------------
export ANTHROPIC_BASE_URL="https://api.ai.inbison.com"
export ANTHROPIC_AUTH_TOKEN="$AUTH_TOKEN"
export ANTHROPIC_API_KEY="$AUTH_TOKEN"
export ANTHROPIC_MODEL="$TIER_SONNET"
export ANTHROPIC_DEFAULT_OPUS_MODEL="$TIER_OPUS"
export ANTHROPIC_DEFAULT_SONNET_MODEL="$TIER_SONNET"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$TIER_HAIKU"
export CLAUDE_CODE_SUBAGENT_MODEL="$TIER_SUBAGENT"

export ANTHROPIC_CUSTOM_MODEL_OPTION="$MODEL_SONNET"
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="Sonnet 4.5 Ameritas Gateway"
# -----------------------------------------------------------------------------
# Gather system info
# -----------------------------------------------------------------------------
MACHINE_ID=$(ioreg -rd1 -c IOPlatformExpertDevice 2>/dev/null | awk '/IOPlatformUUID/ { gsub(/"/, "", $3); print $3 }')
[ -z "$MACHINE_ID" ] && MACHINE_ID="unknown"

OS_INFO=$(sw_vers 2>/dev/null | awk '/ProductName:/ { name=$2 } /ProductVersion:/ { ver=$2 } END { print name " " ver }')
[ -z "$OS_INFO" ] && OS_INFO="macOS unknown"

DATESTAMP=$(date +%Y%m%d)
TIMESUFFIX=$(date +%H%M%S)
SESSION_ID="${LANID}-${DATESTAMP}${TIMESUFFIX}-${RANDOM}"

PROJECT_DIR="$(pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
GIT_REPO=""
if git rev-parse --is-inside-work-tree &>/dev/null; then
    GIT_REPO="$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")"
fi
PROJECT_LABEL="${GIT_REPO:-$PROJECT_NAME}"

# -----------------------------------------------------------------------------
# Request attribution headers
# -----------------------------------------------------------------------------
export ANTHROPIC_CUSTOM_HEADERS="x-user-lanid: ${LANID}
x-machine-id: ${MACHINE_ID}
x-os-info: ${OS_INFO}
x-project-name: ${PROJECT_LABEL}
x-team-name: ${TEAM_NAME}
x-session-id: ${SESSION_ID}"

# LiteLLM proxy metadata for usage tracking & cost allocation
LITELLM_METADATA="{\"user\":\"$LANID\",\"team\":\"$TEAM_NAME\",\"model_tier\":\"$DEFAULT_MODEL\",\"launch_mode\":\"$LAUNCH_TARGET\",\"project\":\"$PROJECT_LABEL\",\"project_path\":\"$PROJECT_DIR\",\"session\":\"$SESSION_ID\"}"
export LITELLM_USER="$LANID"
export LITELLM_TEAM="$TEAM_NAME"
export LITELLM_METADATA="$LITELLM_METADATA"
printf "  ${GRAY}Tagging requests → user=$LANID  team=$TEAM_NAME  tier=$DEFAULT_MODEL  project=$PROJECT_LABEL${R}\n"
printf "  ${GRAY}Session ${R}${DIM}$SESSION_ID${R}\n"
echo ""
# -----------------------------------------------------------------------------
# TLS configuration
# -----------------------------------------------------------------------------
AMERITAS_CA_BUNDLE="/Library/Application Support/Ameritas/certs/ameritas-root-ca.pem"
if [ -f "$AMERITAS_CA_BUNDLE" ]; then
    export NODE_EXTRA_CA_CERTS="$AMERITAS_CA_BUNDLE"
else
    export NODE_TLS_REJECT_UNAUTHORIZED=0
fi
# -----------------------------------------------------------------------------
# Miscellaneous settings
# -----------------------------------------------------------------------------
export DISABLE_AUTOUPDATER=1
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export DISABLE_TELEMETRY=1
export CLAUDE_CODE_DISABLE_AUTO_COMPACT=0
export CLAUDE_CODE_DISABLE_CRON=0
export CLAUDE_CODE_EFFORT_LEVEL="$EFFORT_LEVEL"

# -----------------------------------------------------------------------------
# Offer to persist env vars to shell profile (one-time)
# -----------------------------------------------------------------------------
SHELL_PROFILE=""
[ -f "$HOME/.zshrc" ]        && SHELL_PROFILE="$HOME/.zshrc"
[ -z "$SHELL_PROFILE" ] && [ -f "$HOME/.bash_profile" ] && SHELL_PROFILE="$HOME/.bash_profile"

ENV_ALREADY_SET=0
[ -n "$SHELL_PROFILE" ] && grep -q "ANTHROPIC_BASE_URL" "$SHELL_PROFILE" 2>/dev/null && ENV_ALREADY_SET=1

if [ "$ENV_ALREADY_SET" -eq 0 ] && [ -n "$SHELL_PROFILE" ]; then
    read -p "  Save env vars permanently to $SHELL_PROFILE? [y/N]: " PERSIST
    if [[ "$PERSIST" =~ ^[Yy]$ ]]; then
        {
            echo ""
            echo "# Ameritas Claude Code Gateway — added by mac-run-claude.sh"
            echo "export ANTHROPIC_BASE_URL=\"https://api.ai.inbison.com\""
            echo "export ANTHROPIC_AUTH_TOKEN=\"$AUTH_TOKEN\""
            echo "export ANTHROPIC_MODEL=\"$TIER_SONNET\""
            echo "export ANTHROPIC_DEFAULT_OPUS_MODEL=\"$TIER_OPUS\""
            echo "export ANTHROPIC_DEFAULT_SONNET_MODEL=\"$TIER_SONNET\""
            echo "export ANTHROPIC_DEFAULT_HAIKU_MODEL=\"$TIER_HAIKU\""
            echo "export CLAUDE_CODE_SUBAGENT_MODEL=\"$TIER_SUBAGENT\""
            echo "export DISABLE_AUTOUPDATER=1"
            echo "export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1"
            echo "export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"
            echo "export DISABLE_TELEMETRY=1"
            echo "export CLAUDE_CODE_DISABLE_AUTO_COMPACT=0"
            echo "export CLAUDE_CODE_DISABLE_CRON=0"
        } >> "$SHELL_PROFILE"
        printf "  ${BGREEN}[OK]${R} Env vars saved to $SHELL_PROFILE\n"
        echo "   Open a new terminal to launch Claude directly with:"
        echo "     claude --model $LAUNCH_MODEL"
        echo ""
    else
        echo "   Skipped — no changes made."
        echo ""
    fi
fi

case "$LAUNCH_MODE" in
    2)
        # Launch VS Code with Claude Code extension + terminal
        if command -v code &>/dev/null; then
            printf "  ${GRAY}Opening VS Code with Claude Code...${R}\n"
            # Ensure Claude Code extension is installed
            if ! code --list-extensions 2>/dev/null | grep -qi "anthropic.claude-code"; then
                printf "  ${YELLOW}Installing Claude Code extension for VS Code...${R}\n"
                code --install-extension anthropic.claude-code 2>/dev/null
            fi
            # Open VS Code in current directory
            code .
            # Wait briefly for VS Code to start, then open integrated terminal with claude
            sleep 2
            # Use osascript to send claude command to VS Code's integrated terminal
            osascript -e '
                tell application "Visual Studio Code" to activate
                delay 1
                tell application "System Events"
                    keystroke "`" using {control down}
                    delay 0.5
                    keystroke "'"$CLAUDE_BIN"'"
                    key code 36
                end tell
            ' 2>/dev/null
            printf "  ${BGREEN}[OK]${R} VS Code opened with Claude Code terminal\n"
        else
            printf "  ${RED}[!!]${R} 'code' command not found.\n"
            echo "   Open VS Code → Cmd+Shift+P → 'Shell Command: Install code command in PATH'"
            echo ""
            read -p "  Press Enter to fall back to terminal..." _
            "$CLAUDE_BIN" --model "$LAUNCH_MODEL"
        fi
        ;;
    3)
        # Launch Cursor with Claude Code extension + terminal
        if command -v cursor &>/dev/null; then
            printf "  ${GRAY}Opening Cursor with Claude Code...${R}\n"
            # Ensure Claude Code extension is installed
            if ! cursor --list-extensions 2>/dev/null | grep -qi "anthropic.claude-code"; then
                printf "  ${YELLOW}Installing Claude Code extension for Cursor...${R}\n"
                cursor --install-extension anthropic.claude-code 2>/dev/null
            fi
            # Open Cursor in current directory
            cursor .
            # Wait briefly for Cursor to start, then open integrated terminal with claude
            sleep 2
            osascript -e '
                tell application "Cursor" to activate
                delay 1
                tell application "System Events"
                    keystroke "`" using {control down}
                    delay 0.5
                    keystroke "'"$CLAUDE_BIN"'"
                    key code 36
                end tell
            ' 2>/dev/null
            printf "  ${BGREEN}[OK]${R} Cursor opened with Claude Code terminal\n"
        else
            printf "  ${RED}[!!]${R} 'cursor' command not found.\n"
            echo "   Open Cursor → Cmd+Shift+P → 'Shell Command: Install cursor command in PATH'"
            echo ""
            read -p "  Press Enter to fall back to terminal..." _
            "$CLAUDE_BIN" --model "$LAUNCH_MODEL"
        fi
        ;;
    *)
        # Launch Claude Code in terminal
        "$CLAUDE_BIN" --model "$LAUNCH_MODEL"
        echo ""
        printf "  ${BYELLOW}Session ended${R}\n"
        printf "  ${GRAY} ─────────────────────────────────────────────────${R}\n"
        echo ""
        echo "   Next steps:"
        echo "     claude --resume    continue your last conversation"
        echo "     claude --continue  start new conversation with same context"
        echo ""
        ;;
esac





