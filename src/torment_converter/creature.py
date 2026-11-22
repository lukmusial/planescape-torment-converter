"""Creature (CRE) conversion: original PST CRE V1.2 -> PST:EE CRE V1.0.

Field mapping was derived by comparing every creature shipped with the original
game against the copy Beamdog converted for the Enhanced Edition, and checked
against the IESDP and Near Infinity format descriptions. See docs/how-it-works.md.
"""
import struct

u32 = lambda d, o: struct.unpack_from('<I', d, o)[0]

V12_HEADER = 0x378
V10_HEADER = 0x2D4
EFF_V1_SIZE = 48
EFF_V2_SIZE = 264          # CRE-embedded EFF v2 (no 8-byte signature)

# Original proficiency byte (offset 0x6E + index) -> PST:EE proficiency stat.
# The EE stores proficiencies as opcode 233 effects instead of header bytes.
PROFICIENCY_STAT = {0: 89, 1: 96, 2: 97, 3: 92, 4: 115, 5: 103}   # fist, edged, hammer, axe, club, bow

# Slot table sizes in words. The EE writes 56 into the header count byte (0x7C) for party
# members and stores 57 words; non-party creatures use 0 (= the 40-word default).
PARTY_SLOTS = 57           # 55 item slots + selected weapon + selected ability
PARTY_SLOT_COUNT = 56      # value of header byte 0x7C for party members
NONPARTY_SLOTS = 40        # 38 item slots + selected weapon + selected ability

# Original 48-word slot table index -> (party index, non-party index) in the EE table.
# None: the EE has no such slot (the item stays in the creature's item list but unequipped).
SLOT_MAP = {}
for _i in range(17):                     # equipment 0-8, weapons 9-12, quiver 1-4
    SLOT_MAP[_i] = (_i, _i)
SLOT_MAP[17] = (38, None)                # quiver 5
SLOT_MAP[18] = (None, None)              # quiver 6 (not reachable from the GUI)
SLOT_MAP[19] = (17, 17)                  # right tattoo (upper)
for _k in range(3):
    SLOT_MAP[20 + _k] = (18 + _k, 18 + _k)   # quick items 1-3
SLOT_MAP[23] = (40, None)                # quick item 4
SLOT_MAP[24] = (41, None)                # quick item 5
for _k in range(16):
    SLOT_MAP[25 + _k] = (21 + _k, 21 + _k)   # inventory 1-16
for _k in range(4):
    SLOT_MAP[41 + _k] = (42 + _k, None)  # inventory 17-20
SLOT_MAP[45] = (37, 37)                  # magic weapon


def _eff_v2(opcode, target, power, p1, p2, timing, duration, prob1, prob2,
            resource=b'\0' * 8, dice=(0, 0), save=(0, 0), special=0, resist=0):
    out = bytearray(EFF_V2_SIZE)
    struct.pack_into('<IIIIIH', out, 0x08, opcode, target, power, p1, p2, timing)
    struct.pack_into('<IHH', out, 0x20, duration, prob1, prob2)
    out[0x28:0x30] = resource
    struct.pack_into('<IIIII', out, 0x30, dice[0], dice[1], save[0], save[1], special)
    struct.pack_into('<I', out, 0x54, resist)
    struct.pack_into('<iiii', out, 0x78, -1, -1, -1, -1)    # caster / target coordinates: unset
    struct.pack_into('<i', out, 0x9C, -1)
    return bytes(out)


def eff_v1_to_v2(e):
    """Convert a 48-byte EFF v1 record to the 264-byte CRE-embedded EFF v2 record."""
    op, tgt, pw, p1, p2, tm, resist, dur, pr1, pr2 = struct.unpack_from('<HBBIIBBIBB', e, 0)
    dthrown, dsides, stype, sbonus, special = struct.unpack_from('<IIIII', e, 0x1C)
    return _eff_v2(op, tgt, pw, p1, p2, tm, dur, pr1, pr2, e[0x14:0x1C],
                   (dthrown, dsides), (stype, sbonus), special, resist)


def proficiency_effect(stat, stars):
    return _eff_v2(233, 1, 0, stars, stat, 9, 0, 100, 0)


def convert(a, party=False):
    """Convert a CRE V1.2 (bytes) to CRE V1.0 (bytes). `party` selects the 57-slot inventory."""
    if a[:8] != b'CRE V1.2':
        raise ValueError('not a CRE V1.2: %r' % a[:8])
    h = bytearray(V10_HEADER)
    h[0:8] = b'CRE V1.0'
    h[0x08:0x2C] = a[0x08:0x2C]                   # names, flags, XP, gold, state, HP, animation
    for k in range(4):                            # colour indices (stored as words in V1.2)
        h[0x2C + k] = a[0x2E4 + 2 * k]
    h[0x30:0x33] = a[0x30:0x33]
    h[0x33] = 1                                   # effects stored as EFF v2
    h[0x34:0x44] = a[0x34:0x44]                   # portraits
    h[0x44] = min(a[0x44], 255)                   # reputation (word -> byte)
    h[0x45] = a[0x68]                             # hide in shadows <- stealth
    h[0x46:0x64] = a[0x46:0x64]                   # AC, THAC0, attacks, saves, resistances
    h[0x65:0x6E] = a[0x65:0x6E]                   # skills, fatigue, intoxication, luck
    h[0x7B] = a[0x64]                             # unspent proficiencies
    h[0x7C] = PARTY_SLOT_COUNT if party else 0    # item slot count (0 = default)
    h[0x7F] = a[0x2BB]                            # MURDER increment
    h[0x82:0x84] = a[0x82:0x84]                   # turn undead, tracking
    h[0x84:0x88] = a[0x29C:0x2A0]                 # thief XP
    h[0x88:0x8C] = a[0x2A0:0x2A4]                 # mage XP
    h[0x8C:0x8F] = a[0x2B8:0x2BB]                 # GOOD / LAW / LADY increments
    h[0x8F] = a[0x313]                            # faction
    h[0x90] = a[0x312]                            # team
    h[0x91] = a[0x311]                            # species
    h[0x92:0x94] = a[0x2DC:0x2DE]                 # dialog range, selection circle
    h[0x95] = a[0x30E]                            # field of vision
    h[0x96:0x9A] = a[0x2E0:0x2E4]                 # attribute flags
    h[0xA4:0x270] = a[0xA4:0x270]                 # sounds, levels, abilities, kit, scripts
    h[0x270:0x276] = a[0x314:0x31A]               # EA, general, race, class, specific, gender
    h[0x276:0x27B] = a[0x31A:0x31F]               # OBJECT.IDS refs
    h[0x27B] = a[0x31F]                           # alignment
    h[0x27C:0x280] = a[0x320:0x324]               # actor enumeration
    h[0x280:0x2A0] = a[0x324:0x344]               # death variable
    h[0x2CC:0x2D4] = a[0x370:0x378]               # dialog

    ks, kc, ms, mc, mm, mmc, sl, it, ic, ef, ec = [u32(a, 0x344 + 4 * i) for i in range(11)]
    known = a[ks:ks + 12 * kc]
    meminfo = a[ms:ms + 16 * mc]
    memorized = a[mm:mm + 12 * mmc]
    items = a[it:it + 20 * ic]
    old_slots = struct.unpack_from('<48H', a, sl)

    nslots = PARTY_SLOTS if party else NONPARTY_SLOTS
    slots = [0xFFFF] * (nslots - 2)
    for i in range(46):
        v = old_slots[i]
        if v == 0xFFFF:
            continue
        dst = SLOT_MAP.get(i, (None, None))[0 if party else 1]
        if dst is not None:
            slots[dst] = v
    if party:                                     # the EE resets this on load; store 'none'
        slots += [0xFFFF, 0]
    else:                                         # selected weapon, selected ability
        slots += [old_slots[46], old_slots[47]]

    effects = []
    for k in range(ec):
        if a[0x33] == 0:
            effects.append(eff_v1_to_v2(a[ef + EFF_V1_SIZE * k:ef + EFF_V1_SIZE * (k + 1)]))
        else:
            effects.append(a[ef + EFF_V2_SIZE * k:ef + EFF_V2_SIZE * (k + 1)])
    present = {u32(e, 0x18) for e in effects if u32(e, 0x08) == 233}
    for idx, stat in PROFICIENCY_STAT.items():
        stars = a[0x6E + idx]
        if stars and stat not in present:
            effects.append(proficiency_effect(stat, stars))

    body = bytearray()
    offsets = []
    for blob in (known, meminfo, memorized, items, b''.join(effects),
                 struct.pack('<%dH' % nslots, *slots)):
        offsets.append(V10_HEADER + len(body))
        body += blob
    o_ks, o_ms, o_mm, o_it, o_ef, o_sl = offsets
    struct.pack_into('<11I', h, 0x2A0, o_ks, kc, o_ms, mc, o_mm, mmc, o_sl, o_it, ic, o_ef, len(effects))
    return bytes(h) + bytes(body)


def summarize_v10(b):
    """Comparable view of a CRE V1.0 (used by validation and tests)."""
    ks, kc, ms, mc, mm, mmc, sl, it, ic, ef, ec = [u32(b, 0x2A0 + 4 * i) for i in range(11)]
    items = [b[it + 20 * k:it + 20 * (k + 1)] for k in range(ic)]
    n = b[0x7C] + 1 if b[0x7C] else NONPARTY_SLOTS
    slots = struct.unpack_from('<%dH' % n, b, sl)
    equipped = [(i, items[v][:8] if v < ic else v) for i, v in enumerate(slots[:-2]) if v != 0xFFFF]
    return {
        'header': bytes(b[:0x2A0] + b[0x2CC:0x2D4]),
        'known': bytes(b[ks:ks + 12 * kc]),
        'meminfo': bytes(b[ms:ms + 16 * mc]),
        'memorized': bytes(b[mm:mm + 12 * mmc]),
        'items': sorted(items),
        'slots': equipped,
        'selected': slots[-2:],
        'effects': sorted(b[ef + EFF_V2_SIZE * k:ef + EFF_V2_SIZE * (k + 1)] for k in range(ec)),
    }
