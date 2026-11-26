"""Install the tested local Qwen voice stack once per Apple Silicon Mac."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit'
REVISION = '50f45ef0047cde7e84c2ef04326acb8ada2436a7'
MODEL_FILES = (
    'config.json', 'generation_config.json', 'merges.txt', 'model.safetensors',
    'model.safetensors.index.json', 'preprocessor_config.json', 'tokenizer_config.json', 'vocab.json',
    'speech_tokenizer/config.json', 'speech_tokenizer/configuration.json',
    'speech_tokenizer/model.safetensors', 'speech_tokenizer/preprocessor_config.json',
)
RUNTIME = 'mlx-audio-0.5.0'


def supported():
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        return False
    return int(platform.mac_ver()[0].split('.')[0] or 0) >= 26


def data_home():
    return Path.home() / 'Library/Application Support/physics-notebook-video/qwen'


def complete(model):
    return all((p := model / name).is_file() and p.stat().st_size > 0 for name in MODEL_FILES)


def managed_config():
    """Use paths produced by the installer. Preserve per-user/lesson overrides elsewhere."""
    if not supported():
        return {}
    try:
        data = json.loads((data_home() / 'installation.json').read_text())
        if data['revision'] != REVISION or not Path(data['python']).is_file() or not complete(Path(data['model'])):
            return {}
    except (OSError, KeyError, TypeError, ValueError):
        return {}
    return {key: data[key] for key in ('python', 'model')}


def public_reference():
    folder = ROOT / 'assets/starter-kit/voice-trial'
    reference = json.loads((folder / 'public-reference.json').read_text())
    return {'reference_audio': str(folder / reference['file']), 'reference_text': reference['text']}


def checked_run(cmd, purpose, env=None):
    try:
        subprocess.run(cmd, check=True, env=env, stdout=sys.stderr)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f'{purpose}失败。修复上述原因后可重新运行 platform_install.py local-voice。') from exc


def download_model(output):
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    kwargs = dict(repo_id=MODEL, revision=REVISION, allow_patterns=MODEL_FILES, token=False)
    try:
        model = Path(snapshot_download(**kwargs, local_files_only=True))
    except LocalEntryNotFoundError:
        model = None
    if model is None or not complete(model):
        model = Path(snapshot_download(**kwargs))
    if not complete(model):
        raise ValueError('千问模型文件不完整。')
    output.write_text(str(model.resolve()))


def install():
    if not supported():
        raise ValueError('该本地 Qwen 配音安装器需要 macOS 26 或更新版本，以及 Apple Silicon Mac 的原生 arm64 Python。')
    if sys.version_info < (3, 11):
        raise ValueError('请用 Python 3.11 或更新版本运行本地配音安装。')

    import fcntl
    home = data_home()
    home.mkdir(parents=True, exist_ok=True)
    with (home / 'install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = managed_config()
        if previous:
            return {'status': 'ready', 'model_repo': MODEL, 'revision': REVISION, 'reused': True}
        runtime = home / f'{RUNTIME}-py{sys.version_info.major}.{sys.version_info.minor}'
        python = runtime / 'bin/python'
        if not python.exists():
            checked_run([sys.executable, '-m', 'venv', str(runtime)], '创建本地配音环境')
        req = ROOT / 'assets/requirements-qwen.txt'
        offline = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
        probe = ['-c', 'import mlx.core; from mlx_audio.tts.models.qwen3_tts import Model']
        if subprocess.run([str(python), *probe], env=offline, capture_output=True).returncode:
            checked_run([str(python), '-m', 'pip', 'install', '-r', str(req)], '安装本地配音依赖')
            checked_run([str(python), *probe], '检查 MLX 配音环境', env=offline)
        with tempfile.TemporaryDirectory(dir=home) as tmp:
            folder = Path(tmp)
            model_file = folder / 'model.txt'
            env = {**os.environ, 'HF_HUB_DISABLE_TELEMETRY': '1'}
            checked_run([str(python), __file__, str(model_file)], '下载或复用千问模型', env=env)
            model = model_file.read_text()
            record = {'status': 'ready', 'model_repo': MODEL, 'revision': REVISION, 'reused': False,
                      'python': str(python), 'model': model}
            receipt = folder / 'installation.json'
            receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            receipt.replace(home / receipt.name)
        return {key: record[key] for key in ('status', 'model_repo', 'revision', 'reused')}


if __name__ == '__main__':
    download_model(Path(sys.argv[1]))
