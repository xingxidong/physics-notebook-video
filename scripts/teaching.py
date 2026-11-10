"""Structural evidence for problem recognition, real motion and explicit derivations.

This checks source completeness and display links, not mathematical truth. Physics
and derivation reasoning still require an independent calculation and visual review.
"""
import hashlib,json
from pathlib import Path

def audit(project,lesson,pages):
    project=Path(project).resolve();required=lesson.get('kind')=='problem';errors=[];warnings=[];step_count=0;motion_count=0
    def error(code,message):errors.append({'code':code,'message':message})
    def local_file(value):
        if not isinstance(value,str) or not value:return False
        path=(project/value).resolve()
        return path.is_relative_to(project) and path.is_file() and path.stat().st_size>0
    if required:
        value=lesson.get('input_manifest','input-manifest.json')
        if not local_file(value):error('input-manifest','Register problem and solution sources with intake.py')
        else:
            manifest=json.loads((project/value).read_text())
            if not manifest.get('recognition_reviewed') or not local_file(manifest.get('statement_file')):error('recognition-review','Transcribe and review the problem in statement_file')
            if manifest.get('formula_format')!='latex' or not manifest.get('formulas_reviewed'):error('formula-review','Transcribe all formulas in LaTeX and compare each formula with the original source before narration')
            if not manifest.get('solution_reviewed') or not local_file(manifest.get('solution_file')):error('solution-review','Complete and review the reference-based or self-solved derivation')
            if manifest.get('solution_origin') not in ('reference','self_solved'):error('solution-origin','Record whether the solution is reference-based or independently solved')
            if manifest.get('solution_origin')=='reference' and not manifest.get('solution_sources'):error('reference-source','A reference-based solution needs registered solution sources')
            for record in manifest.get('problem_sources',[])+manifest.get('solution_sources',[]):
                if not local_file(record.get('file')):error('source-file','A registered source file is missing or outside the project')
                elif record.get('sha256')!=hashlib.sha256((project/record['file']).read_bytes()).hexdigest():error('source-changed','A registered source changed; review and update its source record')
            if not manifest.get('problem_sources'):error('problem-source','Register the actual problem source')
            diagram=manifest.get('diagram',{})
            if diagram.get('mode') not in ('redrawn','cropped','mixed'):error('diagram-mode','Record redrawn, cropped or mixed diagram production')
            if diagram.get('mode') in ('cropped','mixed') and not diagram.get('sources'):error('diagram-source','Cropped diagrams need source and crop records')
    groups={}
    if required:
        for p in pages:
            pid=p.get('problem_id')
            if not isinstance(pid,str) or not pid.strip():
                error('problem-id',f'{p["id"]}: assign a stable problem_id');continue
            if pid not in groups:
                groups[pid]={'motion_scenes':0,'derivation_steps':0}
                if not p.get('problem_card'):error('problem-on-screen',f'{pid}: display the recognized problem text on its first page')
    for raw,page in zip(lesson.get('pages',[]),pages):
        group=groups.get(page.get('problem_id'))
        card=page.get('problem_card')
        if required and card and card.get('renderer')!='xelatex':error('problem-typesetting',f'{page["id"]}: typeset the problem statement with XeLaTeX')
        if required and card:
            for cue in page['cues']:
                for block in cue['blocks']:
                    if any(card['x']<x<card['x']+card['w'] and card['y']<y<card['y']+card['h'] for s in block['strokes'] for x,y in s['points']):error('problem-overlap',f'{page["id"]}: handwriting overlaps the problem statement')
        if page.get('demonstration'):
            from models import motion_report
            motion=motion_report(page['demonstration'])
            if motion['moving']:
                motion_count+=1
                if group is not None:group['motion_scenes']+=1
            elif required:error('scenario-motion',f'{page["id"]}: demonstration does not move the physical objects')
        if raw.get('native_scenes'):
            if raw.get('motion_reviewed') and str(raw.get('motion_description','')).strip():
                motion_count+=1
                if group is not None:group['motion_scenes']+=1
            elif required:error('native-motion-review',f'{page["id"]}: inspect the native scene and record motion_description and motion_reviewed')
        cues={c['id']:c for c in page['cues']};known=set()
        # Raw action ids are stable references to the actual visible math.
        actions={a.get('id'):a for c in raw.get('cues',[]) for a in c.get('actions',[]) if a.get('id')}
        for step in raw.get('derivation_steps',[]):
            step_count+=1;sid=step.get('id');deps=step.get('depends_on',[])
            if group is not None:group['derivation_steps']+=1
            if not sid or sid in known:error('step-id',f'{page["id"]}: derivation step ids must be unique')
            if not isinstance(deps,list) or any(d not in known for d in deps):error('step-order',f'{page["id"]}:{sid}: dependencies must refer to earlier steps')
            if not str(step.get('reason','')).strip():error('step-reason',f'{page["id"]}:{sid}: explain the modeling or algebra operation')
            cue=cues.get(step.get('cue_id'));action=actions.get(step.get('action_id'))
            if cue is None:error('step-cue',f'{page["id"]}:{sid}: link to an existing spoken cue')
            if action is None or action.get('type')!='math':error('step-visible',f'{page["id"]}:{sid}: link to a visible math action')
            elif not cue or not any(a.get('id')==step.get('action_id') for a in cue.get('actions',[])):error('step-cue-action',f'{page["id"]}:{sid}: math action must be in the linked cue')
            elif action.get('latex')!=step.get('result'):error('step-result',f'{page["id"]}:{sid}: recorded result differs from the on-screen formula')
            if sid:known.add(sid)
    if required:
        for pid,group in groups.items():
            if not group['motion_scenes']:error('motion-required',f'{pid}: animate its physical scenario with a model or a reviewed native engine scene')
            if not group['derivation_steps']:error('derivation-required',f'{pid}: record and display its complete derivation_steps chain')
        if not groups:error('problems-required','Assign a problem_id and show each problem before explaining it')
    return {'status':'pass' if not errors and not warnings else 'attention','required':required,'structural_checks_only':True,
            'recognized_problem_pages':sum(bool(p.get('problem_card')) for p in pages),'problem_checks':groups,
            'motion_scenes':motion_count,'derivation_steps':step_count,'errors':errors,'warnings':warnings}
