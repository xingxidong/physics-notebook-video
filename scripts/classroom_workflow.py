"""Enforce the reviewed classroom production sequence for new lessons."""

import json
import math
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from handout_bundle import digest
from production_workflow import read, save
from term_inventory import script_text

ROOT = Path(__file__).resolve().parents[1]
EDIT_ROLES = ('lesson_plan', 'board', 'handout', 'script')


def enabled(lesson):
    return lesson.get('classroom_workflow_version') == 1


def start(project, kind, source_type=None):
    from feedback_bank import applicable_issues, lesson_catalog, preparation
    from final_review import invalidate, token
    project.mkdir(parents=True, exist_ok=True)
    context = {'kind': kind, 'source_type': source_type}
    rules = lesson_catalog(context)
    previous = read(project / 'classroom-start.json')
    preparation(project, context)
    started = {'run': uuid4().hex, **context,
               'catalog_sha256': token(rules),
               'applicable_issues': applicable_issues(context, rules),
               'first_take': not previous}
    save(project / 'classroom-start.json', started)
    invalidate(project)
    return {'file': '备课提醒.md', 'run': started['run'],
            'prior_issues': len(started['applicable_issues'])}


def preflight(project, lesson):
    started = read(project / 'classroom-start.json')
    if (not started.get('run') or started.get('kind') != lesson.get('kind')
            or started.get('source_type') != lesson.get('source_type')):
        raise ValueError('缺少第 1 步。先运行 start-workflow 扫描自我成长包，再以对应课型从头备课。')
    if not lesson.get('review_required') or lesson.get('speech_review_version') != 1 or lesson.get('term_inventory_version', 0) < 2:
        raise ValueError('完整流程须启用教案审阅、逐次术语盘点及成片审音。')
    return started


def scoped_script(lesson):
    from production_workflow import cue_rows
    return [{'page': page, 'cue': cue['id'], 'tts': cue.get('tts', cue.get('say', cue.get('text', ''))),
              'spoken': script_text(cue)}
            for page, cue in cue_rows(lesson)]


def write_drafts(project, pages):
    script = []
    board = []
    for page in pages:
        script += ['### ' + page['title'], '']
        board += ['### ' + page['title'], '']
        for cue in page['cues']:
            script.extend([script_text(cue), ''])
            for action in cue.get('resolved_actions', []):
                if action['type'] == 'text':
                    board.extend([action['text'], ''])
                if action['type'] == 'math':
                    board.extend(['$' + action['latex'] + '$', ''])
    (project / '完整讲稿.md').write_text('\n'.join(script), encoding='utf-8')
    (project / '板书文字.md').write_text('\n'.join(board), encoding='utf-8')


def text_materials(project, lesson):
    from handout_bundle import main_source, source_files
    main = main_source(project, lesson)
    if main is None:
        raise ValueError('学生讲义需要可编辑的 LaTeX 主文件。')
    inputs = sorted(p for p in source_files(project, lesson) if p.suffix in ('.tex', '.tikz'))
    return dict(lesson_plan=[project / '教案.md'], board=[project / '板书文字.md'],
                handout=inputs, script=[project / '完整讲稿.md'])


def edit_sources(project, lesson):
    from lesson_review import current_review
    started = preflight(project, lesson)
    plan = current_review(project, lesson)
    if plan.get('workflow_run') != started['run']:
        raise ValueError('先为本轮课程生成 review-plan 草稿。')
    materials = text_materials(project, lesson)
    files = {role: {str(p.relative_to(project)): digest(p) for p in paths} for role, paths in materials.items()}
    return started, plan, materials, files


def humanize(project, lesson, notes):
    started, plan, materials, files = edit_sources(project, lesson)
    if set(notes) != set(EDIT_ROLES) or any(not isinstance(n, str) or not n.strip() for n in notes.values()):
        raise ValueError('分别写明教案、板书、讲义与完整讲稿实际改了什么，或复读后保留的理由。')
    checker = ROOT / 'assets/academic-humanizer/scripts/check_revision.py'
    reports = {role: {str(p.relative_to(project)): subprocess.run(
        [sys.executable, str(checker), 'audit', str(p)], cwd=project,
        capture_output=True, text=True, check=True).stdout for p in paths}
        for role, paths in materials.items()}
    result = dict(run=started['run'], source=plan['fingerprint'],
                  files=files, observations=notes, audit=reports)
    save(project / 'classroom-language-review.json', result)
    return {'file': 'classroom-language-review.json', 'materials': list(files)}


def estimate(plan):
    value = plan.get('estimated_seconds')
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError('教案须给出可回查的全课预计时长。')
    return value


def pilot_pace(project):
    from final_review import token
    from trial_materials import lesson_stamp
    trials = read(project / 'voice-trial/trial-results.json')
    source = trials.get('source_plan', {})
    if source.get('project') != str(project) or source.get('lesson_files') != lesson_stamp(project):
        return None, None
    samples = [(row.get('audio_sha256'), row.get('text', ''), row.get('duration'))
               for row in trials['items'] if row.get('origin') == 'lesson']
    measured = [(sample, sum(ch.isalnum() for ch in sample[1])) for sample in samples
                if sample[2] and sample[2] > 0]
    if not measured:
        return None, None
    units = sum(n for _, n in measured)
    duration = sum(sample[2] for sample, _ in measured)
    return units / duration if units else None, token(samples)


def materials_for_review(project, lesson, plan):
    from final_review import token
    from handout_bundle import verified
    from lesson_review import local_file, native_preview
    from trial_review import require_target_voice
    started, _, _, files = edit_sources(project, lesson)
    edited = read(project / 'classroom-language-review.json')
    if (edited.get('run') != started['run'] or edited.get('source') != plan['fingerprint']
            or edited.get('files') != files or set(edited.get('audit', {})) != set(EDIT_ROLES)):
        raise ValueError('先用内置文案技能处理四份材料，再用 review-language 登记本轮改稿。')
    animation = native_preview(project, lesson)
    if not animation:
        raise ValueError('需附当前版本可播放的动画预览。请先运行 preview。')
    if not verified(project, lesson):
        raise ValueError('送审前请用当前 LaTeX/TikZ 源码编译学生讲义。')
    _, voice = require_target_voice(project, lesson.get('speech', {}))
    pace, trial_sha = pilot_pace(project)
    if not pace or plan.get('pilot_sha256') != trial_sha:
        raise ValueError('请用这次本课实录试音运行 review-plan，更新送审的预计时长。')
    trial = read(project / 'voice-trial/trial-results.json')
    sample_files = ['voice-trial/' + row['audio'] for row in trial['items']]
    reviewed = {'教案': '教案.md', '板书': 'review-preview/boards.pdf', '完整讲稿': '完整讲稿.md',
                '动画预览': animation, '学生讲义': 'handout-delivery/学生讲义.pdf'}
    reviewed.update({f'试音 {i}': name for i, name in enumerate(sample_files, 1)})
    evidence = {label: {'file': name, 'sha256': digest(local_file(project, name))}
                for label, name in reviewed.items()}
    result = dict(run=started['run'], source=plan['fingerprint'], files=evidence,
                  language_sha256=digest(project / 'classroom-language-review.json'),
                  script_sha256=token(scoped_script(lesson)), trial=voice,
                  estimated_seconds=estimate(plan))
    result['packet_sha256'] = token(result)
    return result


def packet(project, lesson):
    from lesson_review import current_review
    result = materials_for_review(project, lesson, current_review(project, lesson))
    save(project / 'classroom-review-packet.json', result)
    return result


def require_packet(project, lesson, plan):
    current = materials_for_review(project, lesson, plan)
    if read(project / 'classroom-review-packet.json') != current:
        raise ValueError('先运行 review-packet 并把这一整套材料发给作者确认。')
    return current


def verify_timeline(project, lesson, timeline):
    from final_review import token
    from lesson_review import current_review
    plan = current_review(project, lesson)
    packet = require_packet(project, lesson, plan)
    if timeline.get('classroom_run') != packet['run'] or timeline.get('classroom_packet') != packet['packet_sha256']:
        raise ValueError('正式时间轴须来自当前已审的课程和试音。')
    scope = dict(pages=[page for page in timeline['pages'] if page['id'] != 'opening-card'])
    cue_list = scoped_script(scope)
    if token(cue_list) != packet['script_sha256']:
        raise ValueError('实际配音时间轴与送审完整讲稿不一致。')
    if any(cue.get('timing') != 'measured' or cue['end'] <= cue['start']
           for page in scope['pages'] for cue in page['cues']):
        raise ValueError('正式落笔须使用每个完整语段的实测时间。')
    evidence = timeline.get('pronunciation_packages', {})
    if not all(evidence.get(key) for key in ('pronunciation_cards', 'target_voice')):
        raise ValueError('这次正式配音缺少两套读音材料的落实记录。')
    guide=project/'classroom-pronunciation-plan.json'
    if not guide.is_file() or digest(guide)!=timeline.get('pronunciation_plan_sha256'):
        raise ValueError('缺少与这次正式配音对应的逐句读音计划。')
    if token(retake_plan(project,packet))!=timeline.get('retake_sha256'):
        raise ValueError('最新标记的语段仍需整段重录并更新正式时间轴。')
    voice = timeline.get('target_voice', {})
    if (not voice.get('matched_takes')
            or any(voice.get(key) != value for key, value in packet['trial'].items())):
        raise ValueError('正式录音缺少已确认试音的音色记录。')
    return packet


def duration_difference(estimated, measured):
    return abs(estimated - measured) > max(15, .08 * estimated)


def retake_plan(project, packet):
    revision = read(project / 'revision-plan.json')
    if revision.get('workflow_run') == packet['run']:
        return revision.get('takes', {})
    return {}


def before_finalize(project, lesson, video):
    """An attempted delivery with a missing stage invalidates the current run."""
    from final_review import binding
    from lesson_review import local_file, require
    try:
        media=local_file(project,video)
        require(project, lesson)
        timeline = read(project / 'timeline.json')
        packet = verify_timeline(project, lesson, timeline)
        report = read(project / 'quality-report.json')
        if report.get('stage') != 'final' or report.get('review_binding') != binding(project, lesson, media):
            raise ValueError('缺少与准备交付的 MP4 对应的第 7 步成片审查。')
    except (ValueError, OSError, KeyError) as exc:
        run = read(project / 'classroom-start.json').get('run')
        save(project / 'classroom-restart.json', {'run': run, 'reason': str(exc)})
        raise ValueError('交付前发现流程遗漏。用 start-workflow 从第 1 步完整重做。' + str(exc)) from exc
    measured=report.get('coverage',{}).get('media',{}).get('duration_seconds')
    if not measured or duration_difference(packet['estimated_seconds'], measured):
        raise ValueError('实测全课时长与已确认的预计时长相差较大。请调整教学内容或编排并重新送审。')
    return {'run':packet['run'],'packet_sha256':packet['packet_sha256'],
            'estimated_seconds':packet['estimated_seconds'],'measured_seconds':measured}


def require_active(project, lesson):
    state = preflight(project, lesson)
    if read(project / 'classroom-restart.json').get('run') == state['run']:
        raise ValueError('当前制作流程有遗漏。请用 start-workflow 从第 1 步重新制作。')
    return state


def register(subs):
    parser = subs.add_parser('start-workflow', help='Start with the portable self-growth library')
    parser.add_argument('project')
    parser.add_argument('--kind', choices=('concept', 'problem'), required=True)
    parser.add_argument('--source-type')
    parser = subs.add_parser('review-language', help='Record the four classroom edits and audit their exact texts')
    parser.add_argument('project')
    for role in EDIT_ROLES:
        parser.add_argument('--' + role.replace('_', '-'), required=True)
    parser = subs.add_parser('review-packet', help='Bind the review materials, animation and real voice samples')
    parser.add_argument('project')


def dispatch(args):
    from production_workflow import effective
    project = Path(args.project).resolve()
    if args.command == 'start-workflow':
        return start(project, args.kind, args.source_type)
    lesson = effective(project)
    require_active(project, lesson)
    if args.command == 'review-language':
        return humanize(project, lesson, {role: getattr(args, role) for role in EDIT_ROLES})
    return packet(project, lesson)
