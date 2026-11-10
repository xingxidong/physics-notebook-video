#!/usr/bin/env python3
"""Register local problem/solution sources without pretending to transcribe them."""
import argparse,hashlib,json,shutil
from pathlib import Path

REMINDER='请同时提供题目和参考解答（图片、PDF 或文字均可）；只有题目时也可先独立求解，再补全推导。'

def register(project,problem_files,solution_files=(),self_solve=False):
    project=Path(project).resolve();project.mkdir(parents=True,exist_ok=True)
    target=project/'input-manifest.json'
    if target.exists():raise ValueError('input-manifest.json already exists; edit the existing registration to preserve review notes')
    if not problem_files:raise ValueError('Provide at least one problem source')
    def copy_files(values,role):
        records=[];folder=project/'inputs'/role;folder.mkdir(parents=True,exist_ok=True)
        for index,value in enumerate(values,1):
            source=Path(value).expanduser().resolve()
            if not source.is_file():raise ValueError(f'Missing {role} source: {source}')
            dest=folder/(f'{index:02d}-'+source.name);shutil.copy2(source,dest)
            records.append({'file':str(dest.relative_to(project)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
        return records
    # Resolve every source before writing a partially populated manifest.
    for value in [*problem_files,*solution_files]:
        if not Path(value).expanduser().is_file():raise ValueError(f'Missing input file: {value}')
    manifest={'version':1,'problem_sources':copy_files(problem_files,'problem'),
              'solution_sources':copy_files(solution_files,'solution'),'solution_origin':'reference' if solution_files else 'self_solved' if self_solve else 'not_supplied',
              'statement_file':None,'solution_file':None,'recognition_reviewed':False,'solution_reviewed':False,
              'formula_format':'latex','formulas_reviewed':False,
              'diagram':{'mode':None,'sources':[]},'reminder':REMINDER}
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return {'manifest':str(target),'problem_sources':len(problem_files),'solution_sources':len(solution_files),
            'recognition':'pending agent transcription and review','reminder':REMINDER}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--problem',action='append',required=True)
    p.add_argument('--solution',action='append',default=[]);p.add_argument('--self-solve',action='store_true');a=p.parse_args()
    try:print(json.dumps(register(a.project,a.problem,a.solution,a.self_solve),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as e:p.exit(1,f'ERROR: {e}\n')

if __name__=='__main__':main()
