"""Exercise the real shell orchestrator with isolated OS/network command doubles."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux systemd deployment script")
SCRIPT = Path(__file__).resolve().parents[2] / "deploy/update-workbench.sh"


@pytest.fixture
def deployment(request):
    # Use the deploy user's home so the real production /tmp guard remains tested.
    isolated = tempfile.TemporaryDirectory(prefix="offline-deploy-", dir=Path.home())
    request.addfinalizer(isolated.cleanup)
    tmp_path = Path(isolated.name)
    commands = tmp_path / "bin"
    commands.mkdir()
    repo = tmp_path / "repository"
    repo.mkdir()
    git = shutil.which("git")
    def run_git(*args):
        return subprocess.check_output([git, "-C", str(repo), *args], text=True).strip()
    run_git("init", "-b", "main")
    run_git("config", "user.name", "Offline test")
    run_git("config", "user.email", "offline@example.invalid")
    (repo / "placeholder").write_text("isolated release")
    run_git("add", ".")
    run_git("commit", "-m", "fixture")
    sha = run_git("rev-parse", "HEAD")
    run_git("update-ref", "refs/remotes/origin/main", sha)
    run_git("remote", "add", "origin", "https://github.com/fengjnah/a-share-quant-v1.git")
    releases = tmp_path / "releases"
    previous = releases / ("0" * 40)
    previous.mkdir(parents=True)
    (previous / "DEPLOYED_SHA").write_text("0" * 40)
    current = tmp_path / "current"
    current.symlink_to(previous, target_is_directory=True)
    data = tmp_path / "persistent"
    data.mkdir()
    # The orchestrator must never replace/remove the store itself.
    (data / "workbench.sqlite3").write_bytes(b"unchanged store sentinel")
    auth = tmp_path / "health.curl"
    auth.write_text('user="offline:fixture"')
    auth.chmod(0o600)
    config = tmp_path / "deploy.env"
    config.write_text("\n".join(f"{k}='{v}'" for k, v in {
        "REPO_DIR": repo, "RELEASES_DIR": releases, "CURRENT_LINK": current,
        "DATA_DIR": data, "SERVICE": "offline-workbench.service",
        "PYTHON_BIN": commands / "python", "HTTPS_URL": "https://example.invalid/quant",
        "AUTH_CURL_CONFIG": auth, "LOCAL_HEALTH_URL": "http://127.0.0.1:8513/quant/_stcore/health",
    }.items()))
    config.chmod(0o600)
    # One executable handles command doubles; no real sudo, network or service calls.
    driver = commands / "driver"
    driver.write_text(f"#!{sys.executable}\n" + r'''
import os, pathlib, subprocess, sys
name=pathlib.Path(sys.argv[0]).name
a=sys.argv[1:]
root=pathlib.Path(os.environ["DEPLOY_TEST_ROOT"])
current=root/"current"
with (root/"calls").open("a") as f: f.write(name+" "+" ".join(a)+"\n")
if name == "sudo":
    sys.exit(subprocess.call(a[1:]))
elif name == "systemctl":
    if a[0] in {"is-enabled", "is-active", "stop", "restart"}: pass
    elif a[0] == "cat":
        print(f"ExecStart={current}/.venv/bin/python 127.0.0.1\nEnvironment=AI_TRADE_WORKBENCH_ROOT={root}/persistent\nEnvironment=PYTHONPATH={current}/src\nEnvironment=AI_TRADE_READ_ONLY=1")
    elif "MemoryMax" in a: print(251658240)
    elif "CPUQuotaPerSecUSec" in a: print("200ms")
    elif "MainPID" in a: print(987654321)
elif name == "curl":
    if "--config" in a: print("maintenance" if os.environ.get("FAULT_AUTH") else "ok")
    elif any(v.startswith("https:") for v in a): print("401", end="")
    else: print("ok")
elif name == "git":
    if "fetch" not in a: sys.exit(subprocess.call([os.environ["REAL_GIT"], *a]))
elif name == "readlink":
    if a[-1] == "/proc/987654321/cwd": print(current.resolve())
    else: print(pathlib.Path(a[-1]).resolve())
elif name == "df": print("Filesystem 1024-blocks Used Available Capacity Mounted\nfixture 9999999 0 9999999 0% /")
elif name == "awk":
    if a[-1] == "/proc/meminfo": print(100 if os.environ.get("FAULT_MEMORY") else 1048576)
    else: sys.exit(subprocess.call(["/usr/bin/awk", *a]))
elif name == "python":
    if "venv" in a:
        target=pathlib.Path(a[-1])/"bin"
        target.mkdir(parents=True)
        (target/"python").symlink_to(root/"bin/driver")
    elif "inventory" in a: print('{"database":"stable content"}')
elif name in {"nginx", "sleep"}: pass
else: raise RuntimeError(name)
''')
    driver.chmod(0o755)
    for name in ("sudo", "systemctl", "curl", "git", "readlink", "df", "awk", "python", "nginx", "sleep"):
        (commands / name).symlink_to(driver)
    old_python = previous / ".venv/bin"
    old_python.mkdir(parents=True)
    (old_python / "python").symlink_to(driver)
    env = dict(os.environ, PATH=str(commands)+os.pathsep+os.environ["PATH"],
               DEPLOY_TEST_ROOT=str(tmp_path), REAL_GIT=git)
    return tmp_path, current, previous, data, sha, env, SCRIPT, config


@pytest.mark.parametrize("fault", [False, True])
def test_health_body_failure_rolls_back_and_never_reports_success(deployment, fault):
    root, current, previous, data, sha, env, script, config = deployment
    if fault:
        env["FAULT_AUTH"] = "1"
    result = subprocess.run(["bash", str(script), sha, str(config)], env=env, text=True, capture_output=True)
    if fault:
        assert result.returncode != 0
        assert current.resolve() == previous
        assert "Deployment healthy:" not in result.stdout
        assert "previous release link restored" in result.stderr
        assert sum(line.startswith("systemctl restart") for line in (root / "calls").read_text().splitlines()) == 2
    else:
        assert result.returncode == 0, result.stderr
        assert current.resolve().name == sha
        assert "Deployment healthy:" in result.stdout
    assert (data / "workbench.sqlite3").read_bytes() == b"unchanged store sentinel"


def test_low_memory_keeps_old_release_and_restores_service(deployment):
    root, current, previous, data, sha, env, script, config = deployment
    env["FAULT_MEMORY"] = "1"
    result = subprocess.run(["bash", str(script), sha, str(config)], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert "Less than 256 MiB" in result.stderr
    assert current.resolve() == previous
    assert "Deployment healthy:" not in result.stdout
    assert "Previous service loopback health restored" in result.stderr
