#!/usr/bin/env bash
# Update an already provisioned, protected workbench. Does not create AWS resources or services.
set -Eeuo pipefail
umask 077
die() { printf '%s\n' "$*" >&2; exit 1; }
[[ $# == 2 && $1 =~ ^[0-9a-f]{40}$ ]] || die 'Usage: bash deploy/update-workbench.sh MAIN_SHA /absolute/deploy.env'
sha=$1
config=$2
[[ $config == /* && -f $config && ! -L $config ]] || die 'An explicit private deployment configuration is required'
[[ $(stat -c %a "$config") == 600 && $(stat -c %u "$config") == "$UID" ]] || die 'deploy.env must be owned by the deploy user with mode 600'
# Configuration is operator-maintained shell, never downloaded or generated from a response.
source "$config"
for key in REPO_DIR RELEASES_DIR CURRENT_LINK DATA_DIR SERVICE PYTHON_BIN HTTPS_URL AUTH_CURL_CONFIG LOCAL_HEALTH_URL; do
    [[ -n ${!key:-} ]] || die "Missing $key"
done
[[ $SERVICE =~ ^[a-zA-Z0-9_-]+\.service$ ]] || die 'Invalid service name'
for value in "$REPO_DIR" "$RELEASES_DIR" "$CURRENT_LINK" "$DATA_DIR" "$AUTH_CURL_CONFIG"; do
    [[ $value == /* ]] || die 'All configured paths must be absolute'
done
[[ -d $DATA_DIR && ! -L $DATA_DIR && $DATA_DIR != /tmp/* && $DATA_DIR != /var/tmp/* ]] || die 'Use an existing dedicated persistent data directory'
repo=$(realpath -e "$REPO_DIR")
data=$(realpath -e "$DATA_DIR")
releases=$(realpath -e "$RELEASES_DIR")
[[ $data != "$repo" && $data != "$repo/"* && $data != "$releases" && $data != "$releases/"* ]] || die 'Data must be outside repository and releases'
[[ ! -e $data/demo.sqlite3 ]] || die 'A temporary demo database cannot be deployed'
[[ -L $CURRENT_LINK ]] || die 'An existing workbench current symlink is required; this script never adopts another service'
previous=$(readlink -f "$CURRENT_LINK")
[[ $previous == "$releases/"* && -f $previous/DEPLOYED_SHA ]] || die 'Previous release is not a managed workbench'
[[ $(stat -c %a "$AUTH_CURL_CONFIG") == 600 && $(stat -c %u "$AUTH_CURL_CONFIG") == "$UID" ]] || die 'curl authentication configuration must be private'
[[ $HTTPS_URL == https://* ]] || die 'A certificate-verified HTTPS URL is required'
[[ $LOCAL_HEALTH_URL == http://127.0.0.1:*/*/_stcore/health ]] || die 'Local health must use loopback and the configured base path'
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] in {(3,12),(3,14)}, "Only Python 3.12/3.14 deployment environments have been verified"'
[[ $(df -Pk "$releases" | awk 'NR==2{print $4}') -ge 1048576 ]] || die 'Less than 1 GiB free release space'
systemctl is-enabled --quiet "$SERVICE" || die 'Existing service must have automatic startup configured'
systemctl is-active --quiet "$SERVICE" || die 'Start from a working service; investigate a failed service before updating'
unit=$(systemctl cat "$SERVICE")
[[ $unit == *"$CURRENT_LINK/.venv/bin/python"* && $unit == *'127.0.0.1'* && $unit == *"AI_TRADE_WORKBENCH_ROOT=$data"* && $unit == *"PYTHONPATH=$CURRENT_LINK/src"* && $unit == *'AI_TRADE_READ_ONLY=1'* ]] || die 'Service paths, loopback binding, persistent store or read-only gate differ'
memory_max=$(systemctl show "$SERVICE" --property MemoryMax --value)
[[ $memory_max =~ ^[0-9]+$ && $memory_max -gt 0 && $memory_max -le 251658240 ]] || die 'A maximum 240 MiB service memory limit is required on the shared micro instance'
[[ $(systemctl show "$SERVICE" --property CPUQuotaPerSecUSec --value) == 200ms ]] || die 'A 20% CPU quota is required to limit display load on t3.micro'
tls_args=()
if [[ -n ${TLS_RESOLVE:-} ]]; then
    [[ $TLS_RESOLVE =~ ^[a-zA-Z0-9._-]+:443:127\.0\.0\.1$ ]] || die 'TLS_RESOLVE must point only to local HTTPS; never bypass certificate checks'
    tls_args=(--resolve "$TLS_RESOLVE" --noproxy '*')
fi
sudo -n nginx -t
[[ $(curl "${tls_args[@]}" --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' "$HTTPS_URL/_stcore/health") == 401 ]] || die 'HTTPS route must reject unauthenticated access with 401'
git -C "$repo" fetch --no-tags origin main
case $(git -C "$repo" remote get-url origin) in
    https://github.com/fengjnah/a-share-quant-v1.git|git@github.com:fengjnah/a-share-quant-v1.git) ;;
    *) die 'Unexpected repository origin' ;;
esac
git -C "$repo" merge-base --is-ancestor "$sha" origin/main || die 'Requested SHA is not on fetched main'
release="$releases/$sha"
[[ ! -e $release ]] || die 'Release path already exists; inspect it before retrying'
mkdir "$release"
git -C "$repo" archive "$sha" | tar -x -C "$release"
printf '%s\n' "$sha" > "$release/DEPLOYED_SHA"
switched=0
stopped=0
local_healthy() {
    systemctl is-active --quiet "$SERVICE" && [[ $(curl --silent --show-error --fail --max-time 4 "$LOCAL_HEALTH_URL") == ok ]]
}
rollback() {
    status=$?
    trap - EXIT
    if [[ $status != 0 && $switched == 1 ]]; then
        ln -s "$previous" "$CURRENT_LINK.rollback"
        mv -Tf "$CURRENT_LINK.rollback" "$CURRENT_LINK"
        if ! sudo -n systemctl restart "$SERVICE"; then
            printf 'Rollback link restored, but service restart failed; operator attention required\n' >&2
        fi
        printf 'Deployment failed; previous release link restored: %s; inspect service health\n' "$previous" >&2
    elif [[ $status != 0 && $stopped == 1 ]]; then
        sudo -n systemctl restart "$SERVICE" || printf 'Previous service restart failed; operator attention required\n' >&2
    fi
    if [[ $status != 0 && $stopped == 1 ]]; then
        restored=0
        for attempt in {1..15}; do
            if local_healthy; then restored=1; break; fi
            sleep 2
        done
        [[ $restored == 1 ]] && printf 'Previous service loopback health restored\n' >&2 || printf 'Rollback health FAILED; operator attention required\n' >&2
    fi
    exit "$status"
}
trap rollback EXIT
# Personal micro instance: briefly stop ONLY this managed service to release RAM during installation.
# Any failure from here restarts the previous release. Java/Nginx are left running.
sudo -n systemctl stop "$SERVICE"
stopped=1
available=$(awk '/MemAvailable:/{print $2}' /proc/meminfo)
[[ $available -ge 262144 ]] || die 'Less than 256 MiB available RAM after stopping the managed workbench'
"$PYTHON_BIN" -m venv --without-pip "$release/.venv"
# Reuse the existing verified pip as installer; Ubuntu may not ship ensurepip.
"$previous/.venv/bin/python" -m pip --python "$release/.venv/bin/python" install --no-cache-dir --only-binary=:all: --no-binary=jsonpath --requirement "$release/deploy/requirements.lock"
"$release/.venv/bin/python" -m pip check
export PYTHONPATH="$release/src"
(cd "$release" && .venv/bin/python -m pytest -q tests/unit/test_market_analysis.py tests/unit/test_demo_data.py tests/unit/test_workbench_store.py)
# Refuse silent migrations; make an online SQLite backup including committed WAL pages.
store() { "$release/.venv/bin/python" -m ai_trade.workbench_store "$1" "$data"; }
store check-schema
store backup
before=$(store inventory)
ln -s "$release" "$CURRENT_LINK.next"
mv -Tf "$CURRENT_LINK.next" "$CURRENT_LINK"
switched=1
sudo -n systemctl restart "$SERVICE"
healthy=0
for attempt in {1..15}; do
    if local_healthy && [[ $(curl "${tls_args[@]}" --config "$AUTH_CURL_CONFIG" --silent --show-error --fail --max-time 4 "$HTTPS_URL/_stcore/health") == ok ]]; then
        healthy=1
        break
    fi
    sleep 2
done
[[ $healthy == 1 ]] || die 'Health check failed; rollback required'
pid=$(systemctl show "$SERVICE" --property MainPID --value)
[[ $(readlink -f "/proc/$pid/cwd") == "$release" ]] || die 'Healthy process is running a different release'
after=$(store inventory)
[[ $before == "$after" ]] || die 'Persistent data inventory changed during read-only restart'
switched=0
stopped=0
printf 'Deployment healthy: %s; persistent data content preserved\n' "$sha"
[[ -z ${TLS_RESOLVE:-} ]] || printf 'HTTPS checked on loopback only; public/mobile ingress remains UNVERIFIED\n'
