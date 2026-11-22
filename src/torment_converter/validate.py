"""Check the creature converter against Beamdog's own conversion of the game's creatures."""
import collections

from . import creature
from .convert import SaveConverter
from .resources import CRE

SECTIONS = ('known', 'meminfo', 'memorized', 'items', 'slots', 'selected', 'effects')


def validate_creatures(original, ee):
    """Convert each CRE V1.2 shipped with the original game; compare with the EE's CRE V1.0.

    Uses the same path as save conversion (including the EE-side fix-ups), so what remains
    are differences Beamdog introduced in the EE content itself.
    """
    converter = SaveConverter(ee)
    header = collections.Counter()
    sections = collections.Counter()
    total = identical = 0
    for name in sorted(original.names(CRE) & ee.names(CRE)):
        a, b = original.get(name, CRE), ee.get(name, CRE)
        if not a or not b or a[:8] != b'CRE V1.2' or b[:8] != b'CRE V1.0':
            continue
        total += 1
        mine = creature.summarize_v10(converter.creature(a, party=False, reference=name))
        theirs = creature.summarize_v10(b)
        same = True
        for i, (x, y) in enumerate(zip(mine['header'], theirs['header'])):
            if x != y:
                header[hex(i) if i < 0x2A0 else 'dialog'] += 1
                same = False
        for key in SECTIONS:
            if mine[key] != theirs[key]:
                sections[key] += 1
                same = False
        identical += same
    return {'total': total, 'identical': identical,
            'header': header.most_common(), 'sections': dict(sections)}
