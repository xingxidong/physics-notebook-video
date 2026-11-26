"""Move a skill's teaching feedback and the short clips used in its listening decisions."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

DB_REL = Path('assets/learning/feedback.sqlite3')
ROOT = Path(__file__).resolve().parents[1]
REPORTS = '''CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
    lesson TEXT NOT NULL, location TEXT NOT NULL, received TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kind,key,payload,lesson,location))'''
DECISIONS = '''CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY, selector TEXT NOT NULL, payload TEXT NOT NULL,
    received TEXT DEFAULT CURRENT_TIMESTAMP, event_uid TEXT)'''
TRIAL_REVIEWS = '''CREATE TABLE IF NOT EXISTS voice_trial_reviews (
    event_uid TEXT PRIMARY KEY, case_id TEXT NOT NULL, payload TEXT NOT NULL,
    received TEXT DEFAULT CURRENT_TIMESTAMP)'''
RETESTS = '''CREATE TABLE IF NOT EXISTS classroom_retests (
    event_uid TEXT PRIMARY KEY, decision_hash TEXT NOT NULL, payload TEXT NOT NULL)'''


def prepare_decisions(db):
    db.execute(DECISIONS)
    if 'event_uid' not in {row[1] for row in db.execute('PRAGMA table_info(decisions)')}:
        db.execute('ALTER TABLE decisions ADD COLUMN event_uid TEXT')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS decision_event_uid ON decisions(event_uid)')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def resolve_sample(db_path, value):
    p = Path(value)
    if p.is_absolute():  # older local databases
        return p
    if '..' in p.parts or len(p.parts)!=2 or p.parts[0]!='samples':
        raise ValueError('试听片段的相对路径无效。')
    return db_path.parent/p


def keep_sample(db_path, sample, expected):
    if not re.fullmatch('[0-9a-f]{64}',expected):
        raise ValueError('试听片段缺少有效的 SHA256。')
    suffix = sample.suffix.lower()
    if suffix not in {'.wav','.mp3','.m4a','.aac','.flac','.ogg','.opus','.aiff','.mp4'}:
        raise ValueError('请选择课堂试听用的音视频片段。')
    rel = Path('samples')/(expected+suffix)
    dest = db_path.parent/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_file() and sha(dest)==expected:
        return rel.as_posix()
    with tempfile.NamedTemporaryFile(dir=dest.parent,prefix='.learning-',delete=False) as f:
        tmp=Path(f.name)
    try:
        shutil.copyfile(sample,tmp)
        if sha(tmp)!=expected:
            raise ValueError(f'试听片段与登记时的声音不同：{sample.name}')
        os.replace(tmp,dest)
    finally:
        tmp.unlink(missing_ok=True)
    return rel.as_posix()


def clean_note(text):
    # Older observations sometimes included an absolute path to a disposable WAV.
    return re.sub(r'(?:/Users/|/private/|/Volumes/)[^\n，。；、]*?\.(?:wav|mp3|m4a|mp4)\b',
                  '已登记的试听片段',text,flags=re.I)


def merge(source, dest):
    """Idempotent across installs and retries, preserving trials, adoptions and withdrawals."""
    source, dest = Path(source).resolve(), Path(dest).resolve()
    if source==dest or not source.is_file():
        return {'reports_added':0,'decisions_added':0}
    dest.parent.mkdir(parents=True,exist_ok=True)
    reports=choices=0
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=30)) as src, \
         closing(sqlite3.connect(dest,timeout=30)) as out, out:
        src.execute('BEGIN')
        tables={row[0] for row in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables.intersection({'reports','decisions','voice_trial_reviews','classroom_retests'}):
            raise ValueError('选择的文件没有教学反馈或试听记录。')
        out.execute('BEGIN IMMEDIATE')
        out.execute(REPORTS)
        prepare_decisions(out)
        if 'reports' in tables:
            for kind,key,payload,lesson,at,received in src.execute('SELECT kind,key,payload,lesson,location,received FROM reports ORDER BY received,id'):
                values=json.loads(payload)
                if 'observed' in values:
                    values['observed']=clean_note(values['observed'])
                encoded=json.dumps(values,ensure_ascii=False,sort_keys=True)
                reports+=out.execute('INSERT OR IGNORE INTO reports(kind,key,payload,lesson,location,received) VALUES(?,?,?,?,?,?)',
                                     (kind,key,encoded,lesson,at,received)).rowcount
        if 'decisions' in tables:
            uid='event_uid' if 'event_uid' in {r[1] for r in src.execute('PRAGMA table_info(decisions)')} else 'NULL'
            for seq,sel,payload,received,event in src.execute(f'SELECT id,selector,payload,received,{uid} FROM decisions ORDER BY received,id'):
                row=json.loads(payload)
                if row.get('sample'):
                    sample=resolve_sample(source,row['sample'])
                    row['sample']=keep_sample(dest,sample,row['sample_sha256'])
                encoded=json.dumps(row,ensure_ascii=False,sort_keys=True)
                if not event:
                    identity=json.dumps([sel,encoded,received,seq],ensure_ascii=False)
                    event=hashlib.sha256(identity.encode()).hexdigest()
                choices+=out.execute('INSERT OR IGNORE INTO decisions(selector,payload,received,event_uid) VALUES(?,?,?,?)',
                                     (sel,encoded,received,event)).rowcount
        trial_reviews = 0
        retests = 0
        if 'classroom_retests' in tables:
            out.execute(RETESTS)
            for event, decision_hash, payload in src.execute('SELECT event_uid,decision_hash,payload FROM classroom_retests'):
                row = json.loads(payload)
                if row.get('sample'):
                    row['sample'] = keep_sample(dest,resolve_sample(source,row['sample']),row['sample_sha256'])
                retests += out.execute('INSERT OR IGNORE INTO classroom_retests VALUES (?,?,?)',
                    (event,decision_hash,json.dumps(row,ensure_ascii=False,sort_keys=True))).rowcount
        if 'voice_trial_reviews' in tables:
            out.execute(TRIAL_REVIEWS)
            for event, case_id, payload, received in src.execute('SELECT event_uid,case_id,payload,received FROM voice_trial_reviews'):
                row = json.loads(payload)
                row['sample'] = keep_sample(dest, resolve_sample(source,row['sample']),row['sample_sha256'])
                trial_reviews += out.execute('INSERT OR IGNORE INTO voice_trial_reviews(event_uid,case_id,payload,received) VALUES(?,?,?,?)',
                    (event,case_id,json.dumps(row,ensure_ascii=False,sort_keys=True),received)).rowcount
    result = {'reports_added':reports,'decisions_added':choices}
    if 'classroom_retests' in tables:
        result['retests_added'] = retests
    if 'voice_trial_reviews' in tables:
        result['trial_reviews_added'] = trial_reviews
    return result


def snapshot(source, dest):
    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True,timeout=30)) as src, \
         closing(sqlite3.connect(dest)) as out:
        src.backup(out)


def sync_cards(source, dest, *, prefer_incoming=True):
    """Preserve learned vocabulary in both archives during an install or checkout export."""
    from classroom_terms import saved_cards
    incoming=saved_cards(source)
    lock_key=hashlib.sha256(str(dest.resolve()).encode()).hexdigest()
    lock=Path(tempfile.gettempdir())/f'physics-classroom-cards-{lock_key}.sqlite3'
    with closing(sqlite3.connect(lock,timeout=45)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        original=saved_cards(dest)
        cards=dict(original)
        for term,new in incoming.items():
            old=cards.get(term,{})
            combined={**old,**new} if prefer_incoming else {**new,**old}
            for key in ('readings','contexts'):
                values=[*old.get(key,[]),*new.get(key,[])]
                if values:
                    combined[key]=list(dict.fromkeys(values))
            cards[term]=combined
        if cards!=original:
            dest.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=dest.parent,delete=False) as out:
                rows=(json.dumps(k,ensure_ascii=False)+': '+json.dumps(v,ensure_ascii=False) for k,v in sorted(cards.items()))
                out.write('{"schema":1,"cards":{\n'+',\n'.join(rows)+'\n}}\n')
            os.replace(out.name,dest)


def reference_files(root):
    return {p.relative_to(root).as_posix():p for p in (root/'references').rglob('*.md') if p.is_file()}


def reference_history(root):
    path=root/'assets/learning/reference-versions.json'
    return json.loads(path.read_text()).get('files',{}) if path.is_file() else {}


def write_reference_history(root, known=None):
    history=reference_history(root)
    for name, values in (known or {}).items():
        history[name]=list(dict.fromkeys([*history.get(name,[]),*values]))
    for name,path in reference_files(root).items():
        history[name]=list(dict.fromkeys([*history.get(name,[]),sha(path)]))
    path=root/'assets/learning/reference-versions.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'schema':1,'files':history},ensure_ascii=False,indent=2)+'\n')


def sync_references(source, dest, *, prefer_incoming=True):
    """Three-way update; keep both independently edited notes instead of losing either."""
    source,dest=Path(source),Path(dest)
    incoming=reference_files(source)
    known=reference_history(dest)
    for name, hashes in reference_history(source).items():
        known[name]=list(dict.fromkeys([*known.get(name,[]),*hashes]))
    index=dest/'assets/learning/reference-conflicts.json'
    conflicts=json.loads(index.read_text()) if index.is_file() else []
    source_index=source/'assets/learning/reference-conflicts.json'
    if source_index.is_file():
        for row in json.loads(source_index.read_text()):
            if row not in conflicts:conflicts.append(row)
    added=0
    for name,path in incoming.items():
        target=dest/name
        if (not prefer_incoming and target.is_file() and sha(target)!=sha(path)
                and sha(target) in known.get(name,[]) and sha(path) in known.get(name,[])):
            continue  # Exporting from an installation must not roll back a published checkout.
        if target.is_file() and sha(target)!=sha(path) and sha(target) not in known.get(name,[]):
            if sha(path) in known.get(name,[]):
                continue  # Only the destination changed since the shared published version.
            # Leave the edited note at its existing link. The incoming variant also travels.
            variant=dest/'references/term-glossaries/merged'/(path.stem+'-'+sha(path)[:16]+'.md')
            variant.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,variant)
            row={'file':name,'retained_sha256':sha(target),'incoming_sha256':sha(path),
                 'incoming_file':variant.relative_to(dest).as_posix(),'status':'pending'}
            if row not in conflicts:conflicts.append(row);added+=1
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
    if conflicts:
        index.parent.mkdir(parents=True,exist_ok=True)
        index.write_text(json.dumps(conflicts,ensure_ascii=False,indent=2)+'\n')
    # Only published source versions are bases; an unreviewed local edit remains an edit.
    for name,path in incoming.items():
        known[name]=list(dict.fromkeys([*known.get(name,[]),sha(path)]))
    history=dest/'assets/learning/reference-versions.json'
    history.parent.mkdir(parents=True,exist_ok=True)
    history.write_text(json.dumps({'schema':1,'files':known},ensure_ascii=False,indent=2)+'\n')
    return {'notes':len(incoming),'new_conflicts':added}


def verify_contents(archive, prefix):
    """Verify the actual portable index and the clips referenced from it, within the ZIP."""
    cards=json.loads(archive.read(prefix+'/assets/classroom-cards.json'))
    if cards.get('schema')!=1 or not isinstance(cards.get('cards'),dict):
        raise ValueError('读音卡文件格式有误。')
    checked=set()
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/DB_REL.name
        path.write_bytes(archive.read(prefix+'/'+DB_REL.as_posix()))
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                raise ValueError('随行包的学习库损坏。')
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            count=db.execute('SELECT count(*) FROM reports').fetchone()[0] if 'reports' in tables else 0
            records=list(db.execute('SELECT payload FROM decisions')) if 'decisions' in tables else []
            trials=list(db.execute('SELECT payload FROM voice_trial_reviews')) if 'voice_trial_reviews' in tables else []
            retests=list(db.execute('SELECT payload FROM classroom_retests')) if 'classroom_retests' in tables else []
            for payload, in [*records, *trials, *retests]:
                row=json.loads(payload)
                if not row.get('sample'):
                    continue
                clip=row['sample']
                value=resolve_sample(path,clip)
                if Path(clip).is_absolute() or not value.is_relative_to(path.parent/'samples'):
                    raise ValueError('随行包的试听位置应在包内。')
                identity=(clip,row['sample_sha256'])
                if identity in checked:
                    continue
                audio=archive.read(prefix+'/'+(DB_REL.parent/clip).as_posix())
                if hashlib.sha256(audio).hexdigest()!=identity[1]:
                    raise ValueError('随行包的试听片段与登记时不同。')
                checked.add(identity)
    result = dict(cards=len(cards['cards']),reports=count,decisions=len(records),samples=len(checked))
    if retests:
        result['classroom_retests'] = len(retests)
    if trials:
        result['trial_reviews'] = len(trials)
    return result
