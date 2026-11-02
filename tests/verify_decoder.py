"""Exercise the firmware ProbeDecoder: deferred frame decision, cadence and contact rules,
and check that the Python reference decoder makes the same decisions."""
from pathlib import Path
import json
import random
import sys
import wasmtime

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO/'build/tests'
sys.path.insert(0, str(REPO/'protocol/reference'))
from protocol_dsp import PulseMessageDecoder  # noqa: E402
FREE, CONTACT = 1, 2
PERIOD = 16250
WRAP = 2**32
store = exports = None


def load(path=ROOT/'decoder.wasm'):
    global store, exports
    engine = wasmtime.Engine()
    store = wasmtime.Store(engine)
    exports = wasmtime.Instance(store, wasmtime.Module.from_file(engine, str(path)), []).exports(store)


def call(name, *args):
    return exports[name](store, *args)


def u32(n):
    return n % WRAP


def last_message():
    return u32(call('lastMessageAt'))  # i32 results arrive signed.


def edge(active, at):
    return call('edge', active, u32(at))


def poll(at):
    return call('poll', u32(at))


def pulses(start, items, check=None):
    """Feed (offset, width) pulses; returns 1 if any edge accepted a frame."""
    accepted = 0
    for offset, width in sorted(items):
        accepted |= edge(1, start+offset)
        if check: check()
        accepted |= edge(0, start+offset+width)
        if check: check()
    return accepted


def frame(start, contact=False, extra=(), check=None):
    """One frame of 260 us pulses; `extra` adds pulse offsets or (offset, width) pairs."""
    items = [(offset, 260) for offset in (0, 1040, 1560, 3120 if contact else 3640)]
    items += [e if isinstance(e, tuple) else (e, 260) for e in extra]
    return pulses(start, items, check)


def acquire_free(base):
    """Two-frame acquisition on a FREE stream; returns the next on-cadence frame start."""
    call('reset')
    assert frame(base) == 0 and call('state') == 0
    assert frame(base+PERIOD) == 1 and call('state') == FREE
    assert frame(base+2*PERIOD) == 1 and call('state') == FREE
    assert call('link', u32(base+2*PERIOD+3900))
    return base+3*PERIOD


def immediate_contact_while_linked(base=1000):
    acquire_free(base)
    touch = base+2*PERIOD+6320  # Off-cadence, as the probe sends at a touch (contact-on.cs8).
    assert frame(touch, contact=True) == 0
    assert call('state') == FREE  # Undecided until the FREE slot has closed.
    assert poll(touch+3760) == 0 and call('state') == FREE
    assert poll(touch+3761) == 1 and call('state') == CONTACT
    assert call('link', u32(touch+3761)) and last_message() == u32(touch+3760)
    # The touch frame is the new cadence reference; the release FREE is then on cadence.
    assert frame(touch+PERIOD, contact=True) == 0 and poll(touch+PERIOD+3761) == 1
    assert call('state') == CONTACT
    assert frame(touch+2*PERIOD) == 1 and call('state') == FREE
    # Not linked: an off-cadence CONTACT cannot acquire, nor re-acquire after link loss.
    call('reset')
    assert frame(base) == 0 and frame(base+PERIOD+6320, contact=True) == 0
    assert poll(base+PERIOD+6320+3761) == 0 and call('state') == 0
    start = acquire_free(base)
    assert poll(start+4*PERIOD) == 0 and not call('link', u32(start+4*PERIOD))
    late = start+4*PERIOD+6320
    assert frame(late, contact=True) == 0 and poll(late+3761) == 0
    assert call('state') == FREE and not call('link', u32(late+3761))


def off_cadence_free_not_accepted(base=1000):
    acquire_free(base)
    touch = base+2*PERIOD+6320
    frame(touch, contact=True)
    assert poll(touch+3761) == 1 and call('state') == CONTACT
    stamp = last_message()
    early = touch+8000  # A FREE frame half a period after the touch frame.
    assert frame(early) == 0 and poll(early+4000) == 0
    assert call('state') == CONTACT and last_message() == stamp
    # It re-anchors the cadence; the next FREE on that cadence closes the loop again.
    assert frame(early+PERIOD) == 1 and call('state') == FREE
    # In a FREE stream an off-cadence FREE does not refresh the link either.
    stamp = last_message()
    assert frame(early+PERIOD+9000) == 0 and last_message() == stamp


def spurious_pulse_in_free_frame(base=1000):
    start = acquire_free(base)
    for spur in (3000, 3060, 3120, 3180, 3240):
        for width in (120, 150, 260, 400):
            if spur+width >= 3640:
                continue
            stamp = last_message()
            def never_contact():
                assert call('state') == FREE, (spur, width)
            assert frame(start, extra=[(spur, width)], check=never_contact) == 0
            poll(start+4100); never_contact()
            assert last_message() == stamp  # Discarded, not accepted as FREE either.
            assert call('link', u32(start+4100))
            # The discarded frame is not a cadence reference; the next frame is accepted.
            assert frame(start+PERIOD, check=never_contact) == 1
            start += 2*PERIOD
    # Polled between the spurious pulse and the real FREE pulse, as loop() does.
    stamp = last_message()
    pulses(start, [(0, 260), (1040, 260), (1560, 260), (3100, 200)])
    for at in range(3300, 3640, 20):
        assert poll(start+at) == 0 and call('state') == FREE
    pulses(start, [(3640, 260)])
    assert poll(start+4000) == 0 and call('state') == FREE and last_message() == stamp


def ambiguous_frame_discarded(base=1000):
    start = acquire_free(base)
    stamp = last_message()
    # Pulses in both the CONTACT and the FREE slot.
    assert frame(start, contact=True, extra=[3640]) == 0 and poll(start+4100) == 0
    assert call('state') == FREE and last_message() == stamp
    assert frame(start+PERIOD) == 1
    # Any other extra pulse inside the frame.
    for extra in (500, 2300, 3400):
        start += 2*PERIOD
        stamp = last_message()
        assert frame(start, contact=True, extra=[extra]) == 0 and poll(start+4100) == 0
        assert call('state') == FREE and last_message() == stamp
        assert frame(start+PERIOD) == 1
    # Noise before the first pulse does not hide a valid frame.
    start += 2*PERIOD
    pulses(start, [(-600, 200)])
    assert frame(start) == 1 and call('state') == FREE
    # While in CONTACT, an ambiguous frame is not accepted either.
    touch = start+6320
    frame(touch, contact=True)
    assert poll(touch+3761) == 1 and call('state') == CONTACT
    stamp = last_message()
    assert frame(touch+PERIOD, contact=True, extra=[3640]) == 0 and poll(touch+PERIOD+4100) == 0
    assert call('state') == CONTACT and last_message() == stamp


def poll_commit_timing(base=1000):
    start = acquire_free(base)
    assert frame(start, contact=True) == 0 and call('state') == FREE  # Fourth pulse ended at +3380.
    assert poll(start+3500) == 0 and poll(start+3760) == 0 and call('state') == FREE
    assert poll(start+3761) == 1 and call('state') == CONTACT
    assert last_message() == u32(start+3760)
    assert u32(last_message()-(start+3120+260)) <= 400  # Latency over the end of the CONTACT pulse.
    # FREE: the fourth pulse is still active at the deadline, so the decision waits for its end.
    start += PERIOD
    for offset, active in ((0, 1), (260, 0), (1040, 1), (1300, 0), (1560, 1), (1820, 0), (3640, 1)):
        assert edge(active, start+offset) == 0
    assert poll(start+3761) == 0 and poll(start+3899) == 0 and call('state') == CONTACT
    assert edge(0, start+3900) == 1 and call('state') == FREE
    assert last_message() == u32(start+3900)
    # A poll older than the last edge (edges drained after the poll time was read) is ignored.
    assert poll(start+3800) == 0 and call('link', u32(start+3900)) and call('state') == FREE
    # A fourth pulse that is still active beyond the maximum width discards the frame.
    start += PERIOD
    stamp = last_message()
    for offset, active in ((0, 1), (260, 0), (1040, 1), (1300, 0), (1560, 1), (1820, 0), (3640, 1)):
        edge(active, start+offset)
    assert poll(start+3640+401) == 0
    assert edge(0, start+3640+450) == 0 and last_message() == stamp
    # Without poll(), the next edge after the deadline commits; the stamp is the deadline.
    start += PERIOD
    frame(start, contact=True)
    assert call('state') == FREE
    assert edge(1, start+PERIOD) == 1 and call('state') == CONTACT
    assert last_message() == u32(start+3760)


def invalid_pulse_discards_open_frames(base=1000):
    """A CONTACT pulse that is mis-sliced must not leave the first three pulses of the frame
    to pair with a later pulse in the FREE slot (closing the loop while touched)."""
    start = acquire_free(base)
    head = ((0, 1), (260, 0), (1040, 1), (1300, 0), (1560, 1), (1820, 0))
    tails = {
        'missed falling edge': ((3120, 1), (3640, 1), (3900, 0)),
        'too wide': ((3120, 1), (3570, 0), (3640, 1), (3900, 0)),
        'too narrow': ((3120, 1), (3220, 0), (3640, 1), (3900, 0)),
        # Rise and fall merged into one interrupt that reads the inactive level.
        'missed rising edge': ((3180, 0), (3650, 1), (3900, 0)),
    }
    for name, tail in tails.items():
        assert frame(start, contact=True) == 0 and poll(start+3761) == 1 and call('state') == CONTACT
        stamp = last_message()
        start += PERIOD  # On cadence.
        for offset, active in head+tail:
            assert edge(active, start+offset) == 0 and call('state') == CONTACT, name
        assert poll(start+4100) == 0 and call('state') == CONTACT and last_message() == stamp, name
        assert call('link', u32(start+4100)), name
        # Not a cadence reference either: the next clean FREE on cadence closes the loop.
        start += PERIOD
        assert frame(start) == 1 and call('state') == FREE, name
        start += PERIOD


def edge_bounce(base=1000):
    """The edge interrupt reports the level, so chatter at an edge arrives as a repeated
    event with the same level. A repeated inactive event up to 40 us after the falling edge,
    or a repeated active event up to 40 us after the rising edge, is bounce and keeps the
    frame and the time of the first edge; a later one is a missed edge and discards it."""
    def bounced(start, contact, extra):
        fourth = 3120 if contact else 3640
        events = sorted([(0, 1), (260, 0), (1040, 1), (1300, 0), (1560, 1), (1820, 0),
                         (fourth, 1), (fourth+260, 0)] + list(extra))
        accepted = 0
        for offset, active in events:
            accepted |= edge(active, start+offset)
        return accepted | poll(start+4100)
    # Falling-edge chatter: a second inactive event.
    start = acquire_free(base)
    for contact, bounce in ((False, 260+1), (True, 1300+40), (True, 3380+40), (False, 1820+25)):
        stamp = last_message()
        assert bounced(start, contact, [(bounce, 0)]) == 1, bounce
        assert call('state') == (CONTACT if contact else FREE) and last_message() != stamp, bounce
        start += PERIOD
    stamp = last_message()
    assert bounced(start, False, [(1300+41, 0)]) == 0 and last_message() == stamp
    assert frame(start+PERIOD) == 1 and call('state') == FREE
    # Rising-edge chatter: a second active event, on every pulse of FREE and CONTACT frames.
    start = acquire_free(base)
    for contact, bounce in ((True, 0+40), (False, 0+8), (True, 1040+8), (True, 1560+40), (True, 3120+25),
                            (False, 3640+1)):
        stamp = last_message()
        assert bounced(start, contact, [(bounce, 1)]) == 1, bounce
        assert call('state') == (CONTACT if contact else FREE) and last_message() != stamp, bounce
        # The pulse keeps its first rising edge: a CONTACT frame is decided at start+3760.
        assert not contact or last_message() == u32(start+3760), bounce
        start += PERIOD
    # A one-frame touch, off cadence, with rising-edge chatter still opens the loop.
    touch = start-PERIOD+6320
    assert bounced(touch, True, [(1040+8, 1)]) == 1 and call('state') == CONTACT
    assert last_message() == u32(touch+3760)
    assert bounced(touch+PERIOD, False, [(3640+8, 1)]) == 1 and call('state') == FREE
    # A second active event more than 40 us later is a missed falling edge.
    start = touch+2*PERIOD
    stamp = last_message()
    assert bounced(start, False, [(1040+41, 1)]) == 0 and last_message() == stamp
    assert frame(start+PERIOD) == 1 and call('state') == FREE
    stamp = last_message()
    assert bounced(start+2*PERIOD, True, [(3120+41, 1)]) == 0
    assert call('state') == FREE and last_message() == stamp


def late_frame_after_link_timeout(base=1000):
    """An off-cadence CONTACT completing after the 65 ms timeout is not accepted, even when
    no poll() latched the link loss before the frame was decided."""
    acquire_free(base)
    last = last_message()
    late = last+61300  # Last edge at +64680, decided at +65060.
    assert frame(late, contact=True) == 0
    assert poll(late+3800) == 0 and call('state') == FREE and last_message() == last
    assert not call('link', u32(late+3800))


def random_stream(rng, frames=60):
    """Probe-like edge stream with timing faults; yields ('edge', active, t) and ('poll', 0, t)."""
    pulses = []
    t = rng.randint(0, 20000)
    contact = False
    for _ in range(frames):
        offsets = [0, 1040, 1560, 3120 if contact else 3640]
        offsets = [o+(rng.randint(-150, 150) if rng.random() < 0.2 else rng.randint(-30, 30)) for o in offsets]
        if rng.random() < 0.1:
            offsets.pop(rng.randrange(4))
        if rng.random() < 0.15:
            offsets.append(rng.choice([rng.randint(-800, 4500), 3120, 3640]))
        for offset in offsets:
            width = rng.randint(90, 460) if rng.random() < 0.15 else rng.randint(200, 300)
            pulses.append((t+offset, t+offset+width))
        if rng.random() < 0.15:
            contact = not contact
        r = rng.random()
        t += (PERIOD+rng.randint(-40, 40) if r < 0.70 else PERIOD+rng.randint(-400, 400) if r < 0.80 else
              rng.randint(2, 3)*PERIOD if r < 0.88 else rng.randint(2000, 40000) if r < 0.95 else
              rng.randint(50000, 150000))
    edges, last = [], -1
    for begin, end in sorted(pulses):
        if begin <= last:
            continue  # Overlapping pulses would merge into one on the data line.
        r = rng.random()  # Below 0.03 the rising edge is missed, from 0.03 to 0.08 the falling edge.
        if r >= 0.03:
            edges.append((1, begin))
            if rng.random() < 0.05:  # A second active event: bounce, or a missed falling edge just beyond 40 us.
                edges.append((1, begin+rng.randint(1, 60)))
        if not 0.03 <= r < 0.08:
            edges.append((0, end))
        last = end
        if rng.random() < 0.05:  # A second inactive event: bounce, or a lost pulse just beyond 40 us.
            last = end+rng.randint(1, 60)
            edges.append((0, last))
    poll_rate = rng.choice([0.0, 0.2, 0.7])
    for i, (active, at) in enumerate(edges):
        yield 'edge', active, at
        following = edges[i+1][1] if i+1 < len(edges) else at+100000
        if rng.random() < 0.03:
            yield 'poll', 0, at-rng.randint(1, 300)  # Stale: older than an edge already fed.
        polls = 1 if rng.random() < poll_rate else 0
        polls += (following-at)//5000 if rng.random() < poll_rate else 0
        for p in sorted(rng.randint(at, following-1) for _ in range(polls)):
            yield 'poll', 0, p


def reference_decoder_matches(sequences=120):
    """Same random streams through the C++ decoder (micros() wrapping) and the Python
    reference decoder: identical result, state, last-message time and link after every call."""
    states = {None: 0, 'free': FREE, 'contact': CONTACT}
    totals = {'free': 0, 'contact': 0, 'rejected': 0}
    for seed in range(sequences):
        rng = random.Random(seed)
        offset = rng.choice([0, WRAP-500000, WRAP-1000000])
        ref = PulseMessageDecoder()
        call('reset')
        now = 0
        for kind, active, at in random_stream(rng):
            if kind == 'edge':
                message, got = ref.edge(active, at/1e6), edge(active, at+offset)
            else:
                message, got = ref.poll(at/1e6), poll(at+offset)
            now = max(now, at)  # loop() reads micros() for link() after draining the edges.
            where = (seed, kind, active, at)
            assert got == bool(message and message['locked']), where
            assert call('state') == states[ref.state], where
            assert ref.state is None or last_message() == u32(ref.last_message_us+offset), where
            assert bool(call('link', u32(now+offset))) == ref.link(now/1e6), where
            if message:
                totals[message['state'] if message['locked'] else 'rejected'] += 1
    # The streams must reach every decision kind, not only clean FREE frames.
    assert min(totals.values()) > 500, totals
    return totals


def micros_rollover():
    # Wrap inside the touch frame, inside the poll window, between frames and in the link window.
    for base in (WRAP-2*PERIOD-6320-3500, WRAP-3*PERIOD-3700, WRAP-3*PERIOD-3300, WRAP-2*PERIOD-1000,
                 WRAP-20000):
        immediate_contact_while_linked(base)
        off_cadence_free_not_accepted(base)
        spurious_pulse_in_free_frame(base)
        ambiguous_frame_discarded(base)
        poll_commit_timing(base)
        invalid_pulse_discards_open_frames(base)
        edge_bounce(base)
        late_frame_after_link_timeout(base)
    # Link loss is latched by poll(): it cannot reappear one micros() period later.
    acquire_free(WRAP-40000)
    last = last_message()
    assert call('link', u32(last+64999))
    assert poll(last+65000) == 0 and not call('link', u32(last+65000))
    assert not call('link', u32(last+WRAP+1000))


TESTS = [immediate_contact_while_linked, off_cadence_free_not_accepted, spurious_pulse_in_free_frame,
         ambiguous_frame_discarded, poll_commit_timing, invalid_pulse_discards_open_frames,
         edge_bounce, late_frame_after_link_timeout, micros_rollover, reference_decoder_matches]


def main():
    load()
    for test in TESTS:
        test()
        print('  ok', test.__name__)
    result = {'passed': True, 'cases': [t.__name__ for t in TESTS],
              'scope': 'Exact C++ ProbeDecoder with synthetic edge timing, compared with the Python '
                       'reference decoder on seeded random streams; radio and GPIO not modelled.'}
    (ROOT/'decoder-validation.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('PASS: immediate contact, cadence, deferred decision, spurious/ambiguous frames, invalid pulses, '
          'missed edges, bounce, poll timing, link timeout, rollover and Python reference agreement.')


if __name__ == '__main__':
    main()
