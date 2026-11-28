"""Configure the two animation engines for an installed lesson skill."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

from engine_render import install_motion_canvas, local_config, save_local_config, versions

MANIM_PACKAGE = 'manim==0.22.1'
MANIM_CHECK = """
import numpy as np
from manim import Camera, ImageMobject, __version__, tempconfig
with tempconfig({'pixel_width': 64, 'pixel_height': 36}):
    Camera().capture_mobjects([ImageMobject(np.zeros((4, 4, 3), dtype=np.uint8))])
print(__version__)
"""
BROWSER_CHECK = """
const {chromium} = require('playwright-core');
(async () => {
  const executablePath = process.argv[1] || chromium.executablePath();
  const browser = await chromium.launch({executablePath, headless: true, args: ['--disable-dev-shm-usage'], timeout: 20000});
  await browser.close();
  console.log(executablePath);
})().catch(error => { console.error(error.message); process.exitCode = 1; });
"""


def run(command, *, cwd=None, timeout=600):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-2200:]
        raise ValueError(detail or f'{Path(command[0]).name} returned {result.returncode}')
    return result.stdout.strip()


def default_runtime(skill_root):
    identity = hashlib.sha256(os.fsencode(skill_root)).hexdigest()[:12]
    base = Path.home() / '.cache'
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        base = Path(os.environ['LOCALAPPDATA'])
    return base / 'physics-notebook-video' / 'animation-engines' / identity


def python_for_venv():
    if sys.version_info >= (3, 11):
        return sys.executable
    for name in ('python3.13', 'python3.12', 'python3.11', 'python3.14', 'python3'):
        binary = shutil.which(name)
        if binary and run([binary, '-c', 'import sys;print(int(sys.version_info >= (3, 11)))'], timeout=10) == '1':
            return binary
    raise ValueError('创建 Manim 环境需要 Python 3.11 或更新版本。')


def manim_env(config, runtime):
    overrides = [os.environ.get('PHYSICS_MANIM_PYTHON'), config.get('manim_python')]
    for entry in dict.fromkeys([*overrides, sys.executable]):
        if entry:
            executable = str(Path(entry).expanduser())
            try:
                found = run([executable, '-c', MANIM_CHECK], timeout=60).splitlines()[-1]
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                if entry == overrides[0]:
                    raise ValueError(f'PHYSICS_MANIM_PYTHON 指向的环境未通过检查。{exc}') from exc
            else:
                return executable, found, True
    venv = runtime / 'manim'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        run([python_for_venv(), '-m', 'venv', str(venv)], timeout=120)
    try:
        found = run([str(python), '-c', MANIM_CHECK], timeout=60).splitlines()[-1]
        return str(python), found, True
    except (OSError, ValueError, subprocess.TimeoutExpired):
        run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', MANIM_PACKAGE])
        found = run([str(python), '-c', MANIM_CHECK], timeout=60).splitlines()[-1]
        return str(python), found, False


def system_browser():
    common = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
              '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']
    for env in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        if os.environ.get(env):
            common.append(str(Path(os.environ[env]) / 'Google/Chrome/Application/chrome.exe'))
    candidates = [*(shutil.which(name) for name in ('chromium', 'chromium-browser', 'google-chrome')), *common]
    return next((path for path in candidates if path and Path(path).is_file()), '')


def check_motion_packages(node, location):
    found = versions('motion-canvas', location)
    run([node, '-e', "require('playwright-core'); import('vite').catch(error => { throw error; });"],
        cwd=location, timeout=20)
    return found


def motion_env(skill_root, config, runtime):
    node = shutil.which('node')
    if not node or int(run([node, '-p', "process.versions.node.split('.')[0]"], timeout=10)) < 20:
        raise ValueError('Motion Canvas 需要 Node.js 20 或更新版本。')
    override = os.environ.get('PHYSICS_ANIMATION_RUNTIME')
    recorded = override or config.get('motion_canvas_runtime')
    location = Path(recorded).expanduser().resolve() if recorded else runtime / 'motion-canvas'
    try:
        found = check_motion_packages(node, location)
        reused = True
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        if override:
            raise ValueError(f'PHYSICS_ANIMATION_RUNTIME 指向的环境未通过检查。{exc}') from exc
        managed = runtime / 'motion-canvas'
        if location != managed:
            try:
                found = check_motion_packages(node, managed)
                reused = True
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                reused = False
        else:
            reused = False
        location = managed
        if not reused:
            try:
                found = install_motion_canvas(location, skill_root)
            except subprocess.CalledProcessError as exc:
                raise ValueError('Motion Canvas 的 npm 依赖安装失败，请查看上面的 npm 输出。') from exc
    override_browser = os.environ.get('CHROME_PATH')
    browser = override_browser or config.get('chrome_path') or system_browser()
    if browser and not Path(browser).is_file() and not override_browser:
        browser = system_browser()
    try:
        executable = run([node, '-e', BROWSER_CHECK, '--', browser], cwd=location, timeout=35).splitlines()[-1]
    except (ValueError, subprocess.TimeoutExpired):
        if override_browser:
            raise
        cli = location / 'node_modules/playwright-core/cli.js'
        run([node, str(cli), 'install', 'chromium'], cwd=location)
        executable = run([node, '-e', BROWSER_CHECK, '--', ''], cwd=location, timeout=35).splitlines()[-1]
        reused = False
    return location, executable, found, reused


def configure(skill_root, runtime=None):
    skill_root = Path(skill_root).resolve()
    runtime = Path(runtime).expanduser().resolve() if runtime else default_runtime(skill_root)
    config = local_config(skill_root)
    report = {}
    changes = {}
    try:
        python, version, reused = manim_env(config, runtime)
        changes['manim_python'] = python
        report['manim'] = {'status': 'ready', 'version': version, 'reused': reused, 'python': python}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report['manim'] = {'status': 'setup-needed', 'reason': str(exc)}
    try:
        location, chrome, details, reused = motion_env(skill_root, config, runtime)
        changes.update(motion_canvas_runtime=str(location), chrome_path=chrome)
        report['motion-canvas'] = {'status': 'ready', 'reused': reused, 'versions': details,
                                   'runtime': str(location), 'chrome': chrome}
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        report['motion-canvas'] = {'status': 'setup-needed', 'reason': str(exc)}
    if changes:
        save_local_config(changes, skill_root)
    missing = [name for name in ('ffmpeg', 'ffprobe') if not shutil.which(name)]
    ok = not missing and all(item['status'] == 'ready' for item in report.values())
    result = {'ok': ok, 'engines': report, 'missing_tools': missing}
    if not ok:
        result['retry'] = 'python3 scripts/platform_install.py animation-engines'
    return result
