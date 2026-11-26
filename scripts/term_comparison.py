"""Compare independent occurrences within the same recorded voice and reading."""
from collections import defaultdict
from statistics import median


def _spacing(windows):
    if len(windows) != 2:
        return None
    first, second = (w['times'] for w in windows)
    if len(first) < 2 or len(first) != len(second):
        return None
    if any(abs(a-b) > .12 for a,b in zip(first, second)):
        return None
    # Onset spacing is observable with cue-level timing too. It is a clue to listen,
    # not a claim that the intervening sound was silent.
    return [round(1000 * ((b-a)+(d-c))/2) for a,b,c,d in zip(first,first[1:],second,second[1:])]


def review_repetitions(results, rows):
    by_id = {row['id']:row for row in rows}
    groups = defaultdict(list)
    reasons = defaultdict(list)
    for hit in results:
        row = by_id[hit['id']]
        groups[row.get('speaker') or '本片未标音色',hit['term'],hit['expected']].append(hit)
        if hit['status'] != 'supports_target':
            reasons[hit['id']].append(hit['status'])
        for flag in ('pause_candidate','length_candidate','possible_restart'):
            if row.get(flag):
                reasons[hit['id']].append(flag)
        if row.get('flow') == 'broken':
            reasons[hit['id']].append('heard_broken')
    comparisons = []
    for (speaker,term,sound), hits in groups.items():
        if len(hits) < 2:
            continue
        flagged = []
        usable = [(hit,spacing) for hit in hits
                  if (spacing := _spacing(hit['heard_windows'])) is not None]
        if len(usable) >= 4 and len({len(s) for _,s in usable}) == 1:
            for j, column in enumerate(zip(*(s for _,s in usable))):
                middle = median(column)
                deviation = median(abs(ms-middle) for ms in column)
                for (hit,_),ms in zip(usable,column):
                    if ms > middle + max(120, 3*deviation, .55*middle):
                        flagged.append(dict(id=hit['id'],after_character=j+1,spacing_ms=ms,median_ms=middle))
                        if 'unusual_spacing' not in reasons[hit['id']]:
                            reasons[hit['id']].append('unusual_spacing')
        # Prefer a reviewed natural reference. Unreviewed matches remain machine references.
        anchor = next((h for h in hits if h['heard_in_final'] and not reasons[h['id']]), None)
        if anchor is None:
            anchor = next((h for h in hits if h['status']=='supports_target' and not reasons[h['id']]), None)
        comparisons.append(dict(term=term,expected=sound,speaker=speaker,occurrences=[h['id'] for h in hits],
                                reference=anchor['id'] if anchor else None,
                                reference_heard=bool(anchor and anchor['heard_in_final']),spacing_outliers=flagged))
    queue = {}
    for hit in results:
        ident=hit['id']
        if not reasons[ident] or hit['heard_in_final']:
            continue
        row=by_id[ident]
        key=tuple(ident.split('.')[:2])
        sentence=queue.setdefault(key,dict(page=row['page'],cue=row['cue'],text=row['text'],
                                           start=row['cue_start'],end=row['cue_end'],targets=[]))
        sentence['targets'].append(dict(id=ident,term=hit['term'],expected=hit['expected'],
                                        offset=row.get('offset'),time=hit.get('time'),
                                        decoded=[w.get('syllables',[]) for w in hit['heard_windows']],
                                        reasons=reasons[ident]))
    def rank(sentence):
        flags={reason for target in sentence['targets'] for reason in target['reasons']}
        return (0 if 'heard_broken' in flags else 1 if 'possible_mismatch' in flags else
                2 if flags-{'needs_listening'} else 3, sentence['start'])
    return dict(repeated_terms=comparisons,producer_review=sorted(queue.values(),key=rank))
