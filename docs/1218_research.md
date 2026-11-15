# UNIVAC 1218 — first research notes

Sources: the 2-page repertoire card (`UNIVAC_1218_Repertoire_of_Instructions_2pages.pdf`)
unless noted; VIP Club chapter 53 for history. To be checked against PX 2910.

## The machine

- US Navy designation **CP-789**; military version of the UNIVAC **418-I** (VIP Club / Wikipedia).
- **18-bit word**, ones' complement arithmetic; 36-bit double-length operands.
- Memory **4K to 32K words**, **4 µs** cycle (MO 5262 says 4 µs; VIP Club gives 98 instructions).
- Up to **8 I/O channels**, -15 V interface; odd/even channels can pair into a 36-bit channel.
- History: project start Oct 1962, first CP-789 delivered Apr 1963. Uses: Navy shipboard
  Management Information System, USMC Landing Approach System-3, U1500 inventory system
  (MARS-class stores ships), ARTS I (1965), JPL Apollo telemetry, Honeysuckle Creek station.
- Family: 1219 / 1219B (CP-848), 32-65K words, 2 µs, 102 instructions, 16 channels
  (TARTAR, TALOS, TERRIER MK-152). AN/UYK-5 "Moonbeam" variant with more memory.

## Registers (from the card)

| Register | Width | Notes |
|---|---|---|
| A = AU:AL | 36 | accumulator; AU upper 18, AL lower 18 |
| B | 18 | the current index register (index registers live in memory 001-010) |
| ICR | 3 | index control register: selects which index register is B |
| SR | 4 | "special register": memory bank / address extension (`u_SR` in Y) |
| P | | program address |
| designators | | overflow, borrow, resume, comparison designator |

## Instruction formats

```
Format I   | 17 - f - 12 | 11 ------ u ------ 0 |       (6-bit function, 12-bit address)
Format II  | 17 - f - 12 | 11 - m - 6 | 5 - k - 0 |    (function 50: m = sub-function, k = count/channel)
```

- Operand address: `Y = y + B`, with `y = u_p ⊕ u_SR ⊕ u` (page/bank from P and SR).
- `*` instructions: "B modification requested" — add suffix B to the symbol and 1 to the
  f code (e.g. ENTAL 12 / ENTALB 13), +4 µs.
- `#` instructions are SR-sensitive.

## Repertoire groups (card)

- Logical: CMAL, CMSK, SLSU (selective substitute), SLSET, SLCL, SLCP, CPAL/CPAU/CPA
- Shift: RSHAU/RSHAL/RSHA, LSHAU/LSHAL/LSHA (circular), SF (scale factor)
- Skip: SKPNBO, SKPOV, SKPNOV, SKPODD, SKPEVN, SKPIIN/OIN/FIN (I/O), SKP (console key k), SKPNR
- I/O: IN, OUT, EXF, INSTP/OUTSTP/EXFSTP, SRSM, OUTOV, EXFOV, RIL/RXL/SIL/SXL
- Misc: WTFI (wait for interrupt), STOP (stop on key setting k)
- Enter: ENTAU, ENTAL, ENTB, ENTBK, ENTALK, ENTICR, ENTSR
- Store: CL, STRB, STRAL, STRAU, STRICR, STRADR, STRSR
- Arithmetic: ADDAL, SUBAL, ADDA, SUBA (36-bit), MULAL, DIVA, ADDALK, RND
- Modifying: ENTBKB, BSK (B skip), ISK (index skip), BJP (B jump)
- Jumps: IRJP, JP, IJPEI, IJP, RJP; conditional JPAUZ ... JPALNG, JPEQ/JPNOT/JPMLEQ/JPMGR
- Fault: function codes 00, 01, 77 and 50 00, 50 01, 50 77

## Assigned memory locations (octal)

000 fault entrance · 001-010 index registers · 016 synchronization interrupt entrance ·
017 scale-factor shift count · 020-037 external function buffer control ·
040-057 output buffer control · 060-077 input buffer control · 100-117 external interrupt
entrance · 120-137 ext. function termination · 140-157 output termination ·
160-177 input termination · 200-237 **bootstrap program**

## Console keys

The card refers to **console key settings k** (SKP skips, STOP stops when k matches) —
the 1218 equivalent of the UYK-7 jump/stop switches.

## Still to find

- A photo or drawing of the **1218 operator/maintenance console** (needed for the panel).
- PX 2910 details: exact adder behaviour (-0), SR / paging rules, interrupt sequencing,
  timing of shifts and multiply, the bootstrap.
