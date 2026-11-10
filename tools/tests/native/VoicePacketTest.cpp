// Copyright (C) 2026 openQ4 contributors. SPDX-License-Identifier: GPL-3.0-or-later
#include "src/sound/VoicePacket.h"
#include "src/framework/async/VoiceTransport.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>

#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "voice check line %d: %s\n", __LINE__, #x); return 1; } } while (0)

int main() {
	using namespace oq4voice;
	CHECK( Compress(0) == 255 && Expand(255) == 0 && Expand(127) == 0 );
	CHECK( Expand(0) == -32124 && Expand(128) == 32124 );
	for ( int sample = -32768; sample <= 32767; ++sample ) {
		const int decoded = Expand(Compress(int16_t(sample)));
		CHECK( std::abs(decoded - sample) <= 644 );
		CHECK( (sample < 0 ? decoded <= 0 : decoded >= 0) );
	}
	int16_t pcm[Samples], decoded[Samples];
	for ( int i = 0; i < Samples; ++i ) pcm[i] = int16_t(15000 * std::sin(i * 6.283185307 * 400 / Rate));
	uint8_t packet[PacketBytes];
	Encode(pcm, 0x12345678, 0xabcdef01, packet);
	CHECK( Read32(packet + 1) == 0x12345678 && Read32(packet + 5) == 0xabcdef01 );
	CHECK( Decode(packet, sizeof(packet), decoded) );
	double signal = 0, noise = 0;
	for ( int i = 0; i < Samples; ++i ) { signal += double(pcm[i]) * pcm[i]; noise += double(pcm[i] - decoded[i]) * (pcm[i] - decoded[i]); }
	CHECK( 10 * std::log10(signal / noise) > 35 );
	for ( int length = 0; length < PacketBytes; ++length ) CHECK(!Decode(packet, length, decoded));
	CHECK( !Valid(nullptr, PacketBytes) && !Valid(packet, PacketBytes + 1) );
	for ( int version = 0; version <= 255; ++version ) { packet[0] = uint8_t(version); CHECK(Valid(packet, PacketBytes) == (version == Version)); }

	Admission admission;
	Encode(pcm, 1, 9000, packet); CHECK(admission.Accept(packet, PacketBytes, 1000));
	CHECK(!admission.Accept(packet, PacketBytes, 1001)); // duplicate
	Encode(pcm, 0, 8980, packet); CHECK(!admission.Accept(packet, PacketBytes, 1001)); // reordered
	Encode(pcm, 2, 9020, packet); CHECK(admission.Accept(packet, PacketBytes, 1000));
	Encode(pcm, 3, 9040, packet); CHECK(admission.Accept(packet, PacketBytes, 1000));
	Encode(pcm, 4, 9060, packet); CHECK(!admission.Accept(packet, PacketBytes, 1000)); // bounded burst
	CHECK(admission.Accept(packet, PacketBytes, 1020));
	Encode(pcm, 5, 9080, packet); CHECK(!admission.Accept(packet, PacketBytes, 1300)); // added delay >120 ms
	Encode(pcm, 6, 9340, packet); CHECK(admission.Accept(packet, PacketBytes, 1300)); // recovers toward live
	Encode(pcm, 7, 12000, packet); CHECK(admission.Accept(packet, PacketBytes, 4000)); // idle restart
	Encode(pcm, 8, 12500, packet); CHECK(!admission.Accept(packet, PacketBytes, 5000)); // idle does not forgive backlog
	Encode(pcm, 9, 13040, packet); CHECK(admission.Accept(packet, PacketBytes, 5000));
	admission = {};
	Encode(pcm, 0xffffffffu, 0xfffffff0u, packet); CHECK(admission.Accept(packet, PacketBytes, 0xfffffff0u));
	Encode(pcm, 0, 4, packet); CHECK(admission.Accept(packet, PacketBytes, 4)); // clock and sequence wrap

	// Independent monotonic clocks must not permanently silence a healthy peer.
	// Simulate a day at +/-1,000 ppm, including jitter, loss, PTT gaps, sequence
	// and millisecond wrap. A late frame must still fail after hours of tracking.
	for ( const int driftPpm : {-1000, -100, 0, 100, 1000} ) {
		admission = {};
		uint32_t serial = 0xffff0000u;
		for ( int64_t elapsed = 0; elapsed < 24LL * 60 * 60 * 1000; elapsed += FrameMsec ) {
			if ( (elapsed / FrameMsec) % 17 == 16 || elapsed % 60000 >= 59000 ) continue;
			const uint32_t sender = 9000u + uint32_t(elapsed + elapsed * driftPpm / 1000000);
			const uint32_t arrival = 0xffff0000u + uint32_t(elapsed) + uint32_t((elapsed / 1000) % 4) * 5;
			Write32(packet + 1, ++serial);
			Write32(packet + 5, sender);
			CHECK(admission.Accept(packet, PacketBytes, arrival));
			if ( elapsed % 60000 == 0 ) {
				Write32(packet + 1, ++serial);
				Write32(packet + 5, sender - 250);
				CHECK(!admission.Accept(packet, PacketBytes, arrival));
			}
		}
	}
	admission = {};
	Encode(pcm, 0, 0, packet); CHECK(admission.Accept(packet, PacketBytes, 0));
	for ( uint32_t elapsed = 1000; elapsed <= 60000; elapsed += FrameMsec ) {
		Write32(packet + 1, elapsed);
		Write32(packet + 5, elapsed - 250);
		CHECK(!admission.Accept(packet, PacketBytes, elapsed));
	}
	CHECK(admission.clockOffset == 0); // rejected backlog cannot train the clock
	Write32(packet + 1, 60001); Write32(packet + 5, 60000);
	CHECK(admission.Accept(packet, PacketBytes, 60000));

	admission = {};
	int accepted = 0;
	for ( int i = 0; i < 100000; ++i ) {
		Encode(pcm, i, i / 100, packet);
		accepted += admission.Accept(packet, PacketBytes, i / 100) ? 1 : 0;
	}
	CHECK(accepted <= 53); // hostile sender cannot turn sequence numbers into bandwidth

	// Soak reporting observes admission without changing it: added delay stays
	// inside the bound, the interval maximum is per report, rejected frames are
	// counted without training, and baseline shift reports tracked drift.
	admission = {};
	AdmissionStats stats;
	uint32_t serial = 0;
	for ( uint32_t now = 1000; now < 1000 + 600000; now += FrameMsec ) {
		const uint32_t sender = 50000u + (now - 1000) + (now - 1000) / 10000; // +100 ppm
		const uint32_t jitter = (now / FrameMsec) % 4 * 10;
		Write32(packet + 1, ++serial); Write32(packet + 5, sender - jitter);
		const bool ok = admission.Accept(packet, PacketBytes, now);
		stats.Record(admission, packet, PacketBytes, now, ok);
		CHECK(ok && stats.lastAdded <= uint32_t(MaxAgeMsec));
	}
	CHECK(stats.accepted == 30000 && stats.rejected == 0 && stats.maxAdded <= 40 && stats.intervalMaxAdded == stats.maxAdded);
	CHECK(stats.BaselineShift(admission) <= -70 && stats.BaselineShift(admission) >= -85); // 60 ms fast plus first-frame jitter
	stats.intervalMaxAdded = 0;
	const uint32_t trained = admission.clockOffset;
	Write32(packet + 1, ++serial); Write32(packet + 5, 50000u + 602000u + 60u - 250u); // 250 ms backlog after a 2 s gap
	const bool late = admission.Accept(packet, PacketBytes, 1000 + 600000 + 2000);
	stats.Record(admission, packet, PacketBytes, 1000 + 600000 + 2000, late);
	CHECK(!late && stats.rejected == 1 && stats.intervalMaxAdded == 0 && admission.clockOffset == trained);
	stats.Record(admission, packet, PacketBytes - 1, 0, true); // malformed input is never an accept
	CHECK(stats.rejected == 2 && stats.accepted == 30000);
	CaptureQueue capture;
	for ( int i = 0; i < 10000; ++i ) { Frame frame; frame.time = i * FrameMsec; frame.pcm[0] = int16_t(i); capture.Push(frame); }
	CHECK(capture.count == MaxQueuedFrames && capture.dropped == 10000 - MaxQueuedFrames);
	Frame frame;
	CHECK(capture.Pop(frame, 9999 * FrameMsec) && frame.pcm[0] == 9996);
	CHECK(!capture.Pop(frame, 10020 * FrameMsec)); // stale capture is never released after a stall
	CHECK(capture.count == 0);
	Mailbox mailbox;
	uint8_t wire[MaxWireFrame] = {}, batch[MaxBatch];
	for ( int i = 0; i < MaxTalkers; ++i ) { wire[0] = uint8_t(i); CHECK(mailbox.Push(wire, sizeof(wire), 100)); }
	wire[0] = 3; CHECK(!mailbox.Push(wire, sizeof(wire), 100));
	wire[0] = 1; wire[1] = 42; CHECK(mailbox.Push(wire, sizeof(wire), 101)); // replaces only this speaker
	const int batchSize = mailbox.Take(batch, 150);
	CHECK(batchSize == MaxBatch && ValidBatch(batch, batchSize) && mailbox.count == 0);
	CHECK(batch[1 + 2 + MaxWireFrame + 2 + 1] == 42);
	for ( int size = 0; size < batchSize; ++size ) CHECK(!ValidBatch(batch, size));
	batch[0] = 4; CHECK(!ValidBatch(batch, batchSize));
	batch[0] = 3; batch[1] = 0; batch[2] = 0; CHECK(!ValidBatch(batch, batchSize));
	CHECK(mailbox.Push(wire, sizeof(wire), 200));
	CHECK(mailbox.Take(batch, 301) == 0 && mailbox.count == 0); // no stale send after a stall
	CHECK(!mailbox.Push(nullptr, 1, 400) && !mailbox.Push(wire, MaxWireFrame + 1, 400));
	wire[0] = 32; CHECK(!mailbox.Push(wire, 1, 400));
	std::printf("voice codec, malformed frames, 24-hour clock drift/jitter/loss, sequence/clock wrap, late drops, flood limits and bounded capture pass; SNR %.2f dB\n", 10 * std::log10(signal / noise));
	return 0;
}
