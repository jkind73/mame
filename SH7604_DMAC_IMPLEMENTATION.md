# SH7604 DMAC implementation — 2026-10-11

The chapter-9 remainder is implemented in the active SH7604 device. The normal
Saturn configuration continues to use the CD HLE; no executing SH-1 was added.

## Request and peripheral interfaces

`dreq0_w`, `dreq1_w` and `dma_request_w` accept raw physical pin levels.
CHCR selects active high/low level or rising/falling edge, with separate edge
latches for both channels. An edge supplies one cycle-steal unit; an edge burst
continues to its transfer end. Level bursts drain requests already accepted
before deassertion (three single-address units, two dual-address units), then
release the bus until requested again. External requests have a three-clock
minimum detection/start delay and cycle-steal edge recovery follows chapter 9.

DRCR selects external, SCI RX, SCI TX or the reserved no-request selection;
CHCR AR selects auto request. SCI acknowledgement remains through the actual
RDR/TDR access paths and does not depend on the CPU interrupt mask. The legacy
32X FIFO callback remains a board adapter when no physical DREQ is connected.
Its notification now also starts a channel that initially saw an empty FIFO;
an unavailable FIFO cannot trap the arbiter in a zero-time retry loop.

`dma_ack_handler<Channel>()` binds DACK. AL selects polarity and AM selects
the read or write phase. Each acknowledgement starts with its bus address and
ends half a clock before that address phase ends; bus waits extend it. Narrow
memory buses produce individual acknowledgements, while an SDRAM burst read
holds the read acknowledgement through the burst.

`dma_read_handler<Channel>()` and `dma_write_handler<Channel>()` bind the
single-address device ports. Byte, word and longword input/output use the
appropriate masks. Memory-to-device uses SAR; device-to-memory uses DAR.
Ignored address registers neither advance nor generate alignment errors.
Prohibited single-address request/size configurations do not start a transfer.
Debugger DREQ/DACK and external data-latch states also expose the interfaces.

## Arbitration, progress and lifecycle

One shared owner serializes the two channels at complete transfer-unit
boundaries. Fixed priority grants channel 0 first, alternates cycle-steal
requests, retains channel-0 burst tenure and lets channel 0 preempt a channel-1
burst after its accepted unit finishes. Round robin gives the next grant to
the previous winner's peer and retains that priority across idle periods.

DMA bus tenure uses its own CPU suspension reason. Only actual changes to that
reason suspend/resume execution, avoiding artificial scheduler yields and
preserving an external HALT asserted by another device. Waiting for an external
request releases DMA tenure, allowing CPU execution to continue.

The existing driver bus-cost hooks supply wait durations. Connected peripheral
interfaces execute individual bus beats; unconnected pins retain the cheaper
unit event path used by Saturn. A 16-byte unit reads all four source longwords,
even when the final count is shorter, and writes only the remaining count.
Programmer-visible address/count registers follow completed payload units.

AE alignment/on-chip-width checks and NMI inhibition are retained. DE, DME,
AE and NMI stop new grants; an already accepted valid read/write unit finishes.
A non-final aborted transfer does not set TE. A final completed unit can set TE
when AE/NMI/DME stops it, as specified in 9.3.8; a DE forced stop does not.

All active addresses/counts, request latches, priority, owner, payload words,
bus-beat and DACK timelines are serialized. MSTP4 pauses a live unit and its
pins, then shifts its deadlines on resume. Full standby resets controller
transients and priority. Postload restores the peripheral output level.

## Validation

The connected fixture uses the real device, mapped RAM and bound peripheral
ports, and runs under both DRC and interpreter. It checks both request levels
and edges, both DACK polarities/phases, measured acknowledgement durations,
single-address widths/directions, narrow-bus beats, fixed/round-robin/mixed
priority, burst preemption, accepted-ahead requests, short final bursts,
SDRAM acknowledgement, module-stop resume, DME/NMI aborts and external HALT.
A scheduled save/load during a live read with both channels pending reproduces
the complete subsequent timestamped pin/data/arbitration trace.

Connected results: `/private/tmp/sh7604-dma-pins-c-20261011`.
The actual-method SCI/standby/FIFO/max-width fixture passes ASan/UBSan:
`/private/tmp/sh7604-dmac-sanitizer-final.log`.

The rebuilt normal Saturn passes all 34 full-device cases (17 per CPU engine),
including SCI/standby, reset, UBC, DMA errors, WDT, refresh, FRT and seven burst
counts: `/private/tmp/sh7604-dmac-suite-final-20261011`.
The FAQ fixture validates all nine payloads per core; current rates and their
hardware differences are recorded in `SATURN_DMA_AUDIT.md`, with artifacts in
`/private/tmp/sh7604-dmac-rate-final-20261011`.

Normal HLE Saturn runs PAL VF2 for 40 emulated seconds without a freeze, reaching
its title/attract animation. The first five captured images match the preceding
build byte-for-byte; the final two have a small animation-position difference
with the changed DMA scheduling, rather than an image-parity result. Headless
speed was 193.51%, versus 195.13% in the preceding smoke run; this single run
is not a controlled performance benchmark. Artifacts:
`/private/tmp/sh7604-dmac-vf2-final-20261011`.

ST-V Golden Axe Duel also completes a 12-second isolated startup smoke run
without a process failure or hang:
`/private/tmp/sh7604-dmac-gaxeduel-final-20261011.log`.
The preserved CD LLE re-enable patch still passes `git apply --check`.
Only the original DMAC checklist marker changes to `[x]`; its text and every
other checklist byte are preserved against the pre-change copy.

## References and limits

Implementation follows the local SH7604 hardware manual, chapter 9 (including
9.3.7 request/pin timing diagrams and 9.3.8 transfer-end conditions), table 4.6
and the standby chapter. MiSTer DMAC RTL corroborates per-unit priority changes.
Table 9.5 supplies DL polarity where surrounding prose is inconsistent.

No real-hardware verification has been performed. Software tests establish
functional behavior and the specified relationships between events. Absolute
Saturn bus timing still uses the existing bus-cost model; completion of this
request/handshake/arbitration item does not claim hardware-exact transfer rates.
