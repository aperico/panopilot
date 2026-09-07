from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def _requirements():
    text=(ROOT/'docs'/'03_system_requirements.md').read_text(); matches=list(re.finditer(r'^##\s+(SYS-[A-Z0-9-]+)\s+—\s+(.+)$',text,re.M)); return text,matches

def test_normative_requirement_ids_are_unique_and_have_verification():
    text,matches=_requirements(); ids=[m.group(1) for m in matches]; assert len(ids)==len(set(ids))
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(text); assert '**Verification:**' in text[m.end():end],m.group(1)

def test_traceability_matrix_covers_every_requirement_exactly_once():
    _,matches=_requirements(); required=[m.group(1) for m in matches]
    trace=(ROOT/'docs'/'06_requirements_traceability.md').read_text(); rows=re.findall(r'^\|\s*(SYS-[A-Z0-9-]+)\s*\|',trace,re.M)
    assert sorted(rows)==sorted(required) and len(rows)==len(set(rows))

def test_pass_traceability_rows_have_verification_evidence():
    trace=(ROOT/'docs'/'06_requirements_traceability.md').read_text()
    for line in trace.splitlines():
        if not line.startswith('| SYS-'): continue
        cells=[c.strip() for c in line.strip('|').split('|')]; assert len(cells)==5
        assert cells[2] in {'PASS','PARTIAL','OPEN'}
        if cells[2]=='PASS': assert 'tests/' in cells[4]
