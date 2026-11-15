# UNIVAC 1218 control panel — label transcription

From `1218_panel.jpg` (900x1200), enhanced to `1218_improved_panel.jpg` (3600x4800) with
`tools/enhance_photo.py` (4x Lanczos, denoise, CLAHE, unsharp mask — no AI upscaling, so no
invented characters). `?` = not readable yet; *italic* = inferred from the manuals.

MO 5262: "front panel display of all registers, manual alteration of all registers, and switches
for operation stepping, sequence stepping, or phase stepping, at a manually controlled variable
clock speed. Test points ... thirty-four 104-pin test blocks on the front panels."

## Top strip

ELAPSED TIME meter (Haydon, hours and tenths) · POWER: COMPUTER lamp + ON/OFF, BLOWER ON/OFF + lamp ·
RUN lamp · FAULT lamp (red) + DISCONNECT/CLEAR · OVER-TEMP DISCONNECT/CLEAR + lamp · HORN ·
INDICATE/SET – OFF – INDICATE toggle.

## Right drawer ("T.S. 746") — CPU

Registers are lamp grids of 3 columns (one octal digit per row), MSB at top; each has a white
pushbutton at top right (*clear*?).

| Block | Label | Bits |
|---|---|---|
| top left | A? (*AU*) | 17-0 |
| top right | A? (*AL*) | 17-0 |
| middle left | ? (looks like D; PX 2910: D arithmetic exchange register) | 17-0 |
| middle right | X (PX 2910: exchange register) | 17-0 |
| lower left | ? (looks like S) | 14-0 |
| lower right | ? (looks like P) | 14-0 |

- SEQUENCE: I, B?, R?, W, SQ?, HC?, RW, WAIT
- F (bracket, read as U before; PX 2910: 7-bit function register): FORMAT II lamp + FUNCTION CODE lamps (6) + white button
- MODE: ? (*OPER STEP*?), PHASE STEP, SEQ STEP, ? (4 lamps)
- PHASE: 4 lamps + white button
- Switches, row 1: I/O CLEAR / CLEAR · ? / PHASE REPEAT · SEQ STOP / ? · RESTART / STEP
- Switches, row 2: FUNCTION REPEAT · ? RECOVERY (*AUTO RECOVERY*: up → 00200 bootstrap,
  down → 00000 fault entrance, PX 2910 I-B) · ADV P · rotary knob (*variable clock speed*)

## Left drawer — I/O

- Two 18-bit registers, C_O and C_E: output buffers for odd and even channels (PX 2910 3.5.2)
- ID ACKNOWLEDGE 7-0 (input data) · EF/OD ACKNOWLEDGE 7-0
- EF/OD: EF · ACTIVE: ID OD EF · MONITOR: ID OD EF
- CHANNEL PRIORITY 7-0
- FUNCTION PRIORITY: SYNC, ?, ?, ?, EXT INT, MON INT
- SCAN SEQ 0 1 2 · CHANNEL TRANSLATOR 4? 2? 1? ODD
- Switches: INTERFACE FAST/? · SYNC ON, EXT
- IC 7 6 5 4 / NORMAL · IC 3 2 1 0 / NORMAL (*intercomputer* mode per channel)
- ESI 7 5 3 1 / NORMAL (externally specified indexing, PX 2910 §4.3)
- DUAL 7 5 3 1 / SINGLE (odd/even channel pairs → 36-bit channel)

## Both edges

Test blocks TB1-TB10, columns A-N — decorative only.

## Not on this photo

PX 2910 refers to MASTER CLEAR, LOAD and START at the computer control panel — probably on
another drawer (the cabinet has 4 or 6).
