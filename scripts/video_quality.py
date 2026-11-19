"""Inspect the delivered MP4 and extract notebook details at their native resolution."""
import json
import math
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path


def positive(value):
    try:
        number = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def probe(video):
    raw = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(video)], text=True)
    data = json.loads(raw)
    streams = data.get('streams', [])
    video_track = next((s for s in streams if s['codec_type'] == 'video'
                        and not s.get('disposition', {}).get('attached_pic')), {})
    audio = next((s for s in streams if s['codec_type'] == 'audio'), {})
    duration = positive(data.get('format', {}).get('duration'))
    if duration is None:
        raise ValueError('无法读取交付文件的有效时长。')
    size = Path(video).stat().st_size
    return {
        'file': str(Path(video).resolve()), 'duration_seconds': duration, 'size_bytes': size,
        'total_average_bps': round(size * 8 / duration),
        'video_codec': video_track.get('codec_name'), 'video_stream_index': video_track.get('index'),
        'video_average_bps': positive(video_track.get('bit_rate')),
        'width': video_track.get('width'), 'height': video_track.get('height'),
        'fps': positive(video_track.get('avg_frame_rate')) or positive(video_track.get('r_frame_rate')),
        'audio_codec': audio.get('codec_name'), 'audio_average_bps': positive(audio.get('bit_rate')),
    }


def review_points(pages, compiled):
    """Prefer actual formula completion and pen motion over evenly spaced samples."""
    by_id = {page['id']: page for page in compiled}
    formulas, writing, motion = [], [], []
    for page in pages:
        if page['id'] == 'opening-card':
            continue
        start = page.get('start', 0)
        strokes = [s for s in page.get('strokes', []) if s.get('end', 0) > max(0, s.get('start', 0))]
        by_action = {}
        for stroke in strokes:
            key = (stroke.get('cue'), stroke.get('action'))
            by_action.setdefault(key, []).append(stroke)
        for cue in by_id.get(page['id'], {}).get('cues', []):
            blocks = [block for block in cue.get('blocks', []) if not block.get('prewritten')]
            for index, block in enumerate(blocks):
                ink = by_action.get((cue['id'], index), [])
                if block.get('kind') == 'math' and ink:
                    end = max(s['end'] for s in ink)
                    formulas.append((block.get('size', 32), -len(ink), start + end, page['id']))
        if strokes:
            group = max(by_action.values(), key=len)
            middle = sorted(group, key=lambda s: s['start'])[len(group) // 2]
            writing.append((len(group), start + (middle['start'] + middle['end']) / 2, page['id']))
        for track in (page.get('scene_tracks') or {}).get('events', []):
            if track['end'] > track['start'] and track.get('from') != track.get('to'):
                motion.append((1, track['end'] - track['start'], start + (track['start'] + track['end']) / 2, page['id']))
        if page.get('native_scenes') or page.get('demonstration'):
            motion.append((0, page['duration'], start + page['duration'] / 2, page['id']))
    points = []
    if formulas:
        _, _, time, page_id = min(formulas)
        points.append(('formula', '公式写完后，查看上下标、负号和分式横线', time, page_id))
    if writing:
        _, time, page_id = max(writing)
        points.append(('writing', '落笔过程中，查看笔尖周围和新笔画的边缘', time, page_id))
    if motion:
        _, _, time, page_id = max(motion)
        points.append(('motion', '动画候选画面，播放前后两秒观察运动轮廓和细线', time, page_id))
    if not points:
        content = next((p for p in pages if p['id'] != 'opening-card'), None)
        if content:
            points.append(('board', '查看板书字迹和图中标注', content.get('start', 0) + content['duration'] / 2, content['id']))
    return points


def extract_samples(video, metadata, points, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    samples = []
    for key, purpose, time, page in points:
        # Leave a full frame before EOF even when a final stroke ends at the cut.
        time = max(0, min(time, metadata['duration_seconds'] - 2 / (metadata['fps'] or 24)))
        target = folder / (key + '.png')
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            frame = Path(tmp) / 'frame.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{time:.6f}', '-i', str(video),
                            '-map', f'0:{metadata["video_stream_index"]}', '-frames:v', '1', '-update', '1', str(frame)], check=True)
            if not frame.is_file() or not frame.stat().st_size:
                raise ValueError(f'无法在 {time:.2f} 秒处提取成片画面。')
            frame.replace(target)
        samples.append({'kind': key, 'page': page, 'seconds': round(time, 3),
                        'image': str(target.resolve()), 'look_for': purpose})
    return samples
