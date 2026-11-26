"""Local acoustic evidence for a timed occurrence. Both decoding windows preserve natural rate."""
import argparse
from functools import lru_cache
import itertools
import json
from pathlib import Path
import re
import os
import subprocess

from feedback_bank import save_report
from term_flow import RATE, acoustic_gap
from tone_review import _digest


# Entire aligned letter name, including a single vowel nucleus for Q.
LETTER_PATTERNS={key:re.compile(pattern) for key,pattern in {
    'Q':r'(?:k|kh) (?:j (?:uː?|u5|ʉː?|ʊ)|ju)',
    'U':r'(?:j (?:uː?|ʉː?)|ju)', 'V':r'v iː?', 'Z':r'z iː?',
    'W':r'd (?:ʌ|ə|a) b (?:ə l|əl|l) (?:j uː?|ju)',
    'X':r'(?:ɛ|e) k s', 'A':r'eɪ', 'M':r'(?:ɛ|e) m', 'F':r'(?:ɛ|e) f',
    'B':r'b iː?', 'C':r's iː?', 'D':r'd iː?', 'E':r'iː?',
    'G':r'(?:dʒ|d ʒ) iː?', 'H':r'eɪ (?:tʃ|t ʃ)', 'I':r'aɪ', 'J':r'(?:dʒ|d ʒ) eɪ',
    'K':r'(?:k|kh) eɪ', 'L':r'(?:ɛ|e) l', 'N':r'(?:ɛ|e) n', 'O':r'oʊ',
    'P':r'(?:p|ph) iː?', 'R':r'(?:ɑːɹ|ɑː? (?:r|ɹ)|ɑː)', 'S':r'(?:ɛ|e) s',
    'T':r'(?:t|th) iː?', 'Y':r'w aɪ',
}.items()}


class Mandarin:
    def __init__(self, folder):
        import numpy as np
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.net = ort.InferenceSession(str(folder/'sv.onnx'), options, providers=['CPUExecutionProvider'])
        self.output = next(out.name for out in self.net.get_outputs() if 'pinyin' in out.name)
        self.tokens = {i:k for k,i in json.loads((folder/'vocab.json').read_text()).items()}
        self.norm = [np.fromstring(m,sep=' ',dtype='float32') for m in
                     re.findall(r'\[\s*([-\d.\s]+?)\s*\]',(folder/'am.mvn').read_text()) if len(m)>80]
        if len(self.norm)!=2 or any(len(v)!=560 for v in self.norm):
            raise ValueError('拼音模型的归一化参数应各有 560 项。')

    def decode(self, samples):
        import numpy as np
        import torch
        from torchaudio.compliance.kaldi import fbank
        samples = np.pad(samples,1920)
        samples *= 26000 / max(.001,abs(samples).max())
        frames = fbank(torch.from_numpy(samples[None]),num_mel_bins=80,dither=0,window_type='hamming').numpy()
        ix = np.clip(np.arange(0,len(frames),6)[:,None]+np.arange(-3,4),0,len(frames)-1)
        feats = (frames[ix].reshape(-1,560)+self.norm[0])*self.norm[1]
        logits = self.net.run([self.output],{'feats':feats[None],'feats_lens':np.array([len(feats)],'int32')})[0]
        ids = logits.reshape(-1,len(self.tokens)).argmax(-1)
        return [(self.tokens[int(k)],i*.06-.12) for i,k in enumerate(ids) if k and (not i or k!=ids[i-1])]


class English:
    def __init__(self,folder):
        import torch
        torch.set_num_threads(min(2,torch.get_num_threads()))
        from transformers import Wav2Vec2ForCTC
        self.model=Wav2Vec2ForCTC.from_pretrained(str(folder),local_files_only=True).eval()
        self.tokens={i:k for k,i in json.loads((folder/'vocab.json').read_text()).items()}

    def decode(self,samples):
        import numpy as np
        import torch
        samples=np.pad(samples,1600)
        samples=(samples-samples.mean())/(samples.std()+1e-7)
        with torch.inference_mode():
            ids=self.model(torch.from_numpy(samples[None])).logits[0].argmax(-1).tolist()
        hop=self.model.config.inputs_to_logits_ratio/RATE
        tokens=[]
        frame=0
        for k, repeats in itertools.groupby(ids):
            count=sum(1 for _ in repeats)
            if k!=self.model.config.pad_token_id:
                tokens.append((self.tokens[k],(frame+count/2)*hop-.10))
            frame+=count
        return tokens


@lru_cache(maxsize=2)
def model(root,language):
    factory, subdir = (Mandarin,'mandarin-syllables') if language=='zh' else (English,'english-phonemes')
    return factory(root/subdir)


def measure(media, start, end, *, language, root, expected=None, accepted_surface=None):
    """Report agreement of independent context windows. An uncertain result stays in review."""
    import numpy as np
    if not 0 <= start < end:
        raise ValueError('目标音节或字母的起止秒数无效。')
    net=model(root,language)
    findings=[]
    for padding in (.16,.42):
        left=max(0,start-padding)
        raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-ss',str(left),'-i',str(media),
            '-t',str(end+padding-left),'-map','0:a:0','-ac','1','-ar',str(RATE),'-f','s16le','pipe:1'])
        if len(raw)/2 < round((end-left)*RATE):
            raise ValueError('所选位置超出音轨。')
        decoded=net.decode(np.frombuffer(raw,dtype='<i2').astype('float32')/32768)
        phones=[token for token,t in decoded if start-.035 <= left+t <= end+.035]
        findings.append(phones)
    status='inspect_phones'
    if language=='zh' and expected:
        forms=[phonetic_form(p) for p in expected.split()]
        from pronunciation import classroom_syllables
        observed=[]
        for group in findings:
            seq=[phonetic_form(p) for p in group]
            spans=[seq[i:i+len(forms)] for i in range(len(seq)-len(forms)+1)
                   if [v.rstrip('12345') for v in seq[i:i+len(forms)]]==[v.rstrip('12345') for v in forms]]
            observed.append(spans[0] if len(spans)==1 else [])
        if all(observed):
            matches=[all(classroom_syllables('字'*len(forms),' '.join(forms),' '.join(group))) or
                     (accepted_surface is not None and group==[accepted_surface]) for group in observed]
            status='supports_target' if all(matches) else 'possible_mismatch' if observed[0]==observed[1] else 'uncertain'
        else:
            status='uncertain'
    if language=='en' and expected:
        letter=expected.split()[0].upper()
        if letter in LETTER_PATTERNS:
            flags=[bool(LETTER_PATTERNS[letter].fullmatch(' '.join(phones))) for phones in findings]
            status='supports_target' if all(flags) else 'uncertain'
            if not any(flags) and findings[0]==findings[1] and findings[0]:
                # A matching name plus a neighbouring Mandarin consonant can straddle alignment.
                group=findings[0]
                contains=any(LETTER_PATTERNS[letter].fullmatch(' '.join(group[i:j]))
                             for i in range(len(group)) for j in range(i+1,len(group)+1))
                extra_vowel=letter in ('Q','U') and sum(p in ('u','uː','u5','ju','ʉ','ʉː') for p in group)>1
                # The multilingual phone inventory can emit Mandarin tone labels on
                # vowels in otherwise English names, e.g. z i5 in a Chinese sentence.
                # This is ambiguous acoustic evidence, not a confirmed extra vowel.
                untoned = [re.sub(r'[1-5]$', '', phone) for phone in group]
                mixed = (untoned != group and LETTER_PATTERNS[letter].fullmatch(' '.join(untoned)))
                if (not contains and not mixed) or extra_vowel:
                    status='possible_mismatch'
    gap=acoustic_gap(raw[2*round((start-left)*RATE):2*round((end-left)*RATE)])
    return dict(windows=findings,expected=expected,interior_quiet_ms=gap,status=status)


def phonetic_form(token):
    return token.casefold().replace('ü','v').replace('u:','v').replace('0','5')


@lru_cache(maxsize=2)
def model_signature(root,language):
    folder=root/('english-phonemes' if language=='en' else 'mandarin-syllables')
    files=('config.json','vocab.json') if language=='en' else ('am.mvn','vocab.json','sv.onnx')
    if language=='en':
        files+=tuple(p.name for p in sorted(folder.iterdir()) if p.suffix in ('.bin','.safetensors') or p.name.endswith('.index.json'))
    from speech_context import digest
    from inspect import getsource
    from pronunciation import classroom_syllables
    # Vocabulary additions in other lessons do not change this acoustic model.
    return digest([_digest(Path(__file__)),getsource(classroom_syllables),*[(name,_digest(folder/name)) for name in files]])


def probe_targets(project,report,model_root, *, select=None):
    media=Path(report['file'])
    if report['sha256']!=_digest(media):
        raise ValueError('交付件已更换，先刷新整句清单。')
    results=[]
    review_folder=project/'review-audio'
    for row in report['items']:
        if row['status']=='reviewed' and not select:
            continue
        for target in row['targets']:
            if select and (row['id'],target['id'])!=select:
                continue
            item=dict(cue=row['id'],target=target['id'],text=target['text'],token=row['token'])
            results.append(item)
            if not target.get('window'):
                item['status']='needs_timing'
                continue
            language='en' if target['kind']=='symbol' else 'zh'
            if language=='en' and not target['text'][0].isascii():
                item['status']='listen_in_context'
                continue
            signature=model_signature(model_root,language)
            path=review_folder/f"probe-{row['token']}-{target['id']}.json"
            result=json.loads(path.read_text()) if path.is_file() else {}
            if result.get('model_sha256')!=signature:
                expected=target.get('reading') if target['kind']=='flow' else target['expected']
                result=measure(media,*target['window'],language=language,expected=expected,root=model_root,accepted_surface=target.get('accepted_surface'))
                result.update(token=row['token'],target=target['id'],window=target['window'],model_sha256=signature)
                save_report(path,result)
            item.update(status=result['status'],evidence=str(path))
    if select and not results:
        raise ValueError('请从本版清单选择一个实际出现的位置。')
    results.sort(key=lambda r:r['status']!='possible_mismatch')
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path)
    opts=parser.add_mutually_exclusive_group(required=True)
    opts.add_argument('--id',help='final-speech-context.json 中的句号，如 2.3')
    opts.add_argument('--terms',action='store_true',help='检查成片术语清单中的每一次出现')
    opts.add_argument('--pending',action='store_true',help='逐处复测待审整句，有字词定位时核对音节或音素')
    parser.add_argument('--target',help='句内编号，如 symbol@8')
    parser.add_argument('--model-root',type=Path,default=Path(os.environ.get('PHYSICS_NOTEBOOK_PHONEME_MODELS',Path.home()/'.cache/physics-notebook-video')))
    args=parser.parse_args()
    if bool(args.id)!=bool(args.target):
        parser.error('--id 与 --target 配合使用')
    if args.terms or args.pending:
        from classroom_probe import probe_terms
        term_path=args.project/'final-term-flow.json'
        if args.terms or term_path.is_file():
            terms=json.loads(term_path.read_text())
            if not terms.get('file'):
                parser.error('需先生成完整的 final-term-flow.json')
            media=Path(terms['file'])
            if args.pending:
                context=json.loads((args.project/'final-speech-context.json').read_text())
                media=Path(context['file'])
            result=probe_terms(args.project,terms,media,args.model_root)
            save_report(args.project/'final-physics-term-probes.json',result)
            if args.terms:
                print(f"已检查 {result['terms']} 种物理术语、{result['total']} 个位置。")
                return
    report=json.loads((args.project/'final-speech-context.json').read_text())
    output=probe_targets(args.project,report,args.model_root,select=(args.id,args.target) if args.id else None)
    if args.pending:
        path=args.project/'final-speech-probes.json'
        save_report(path,dict(sha256=report['sha256'],items=output))
        print(path)
    else:
        print(json.dumps(output,ensure_ascii=False))


if __name__=='__main__':
    main()
