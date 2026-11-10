// Copyright (C) 2026 openQ4 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENQ4_SOUND_VORBIS_STREAM_H
#define OPENQ4_SOUND_VORBIS_STREAM_H

#include <algorithm>
#include <cstring>
#include <memory>
#include <new>
#define STB_VORBIS_HEADER_ONLY
#include "stb_vorbis.c"
#undef STB_VORBIS_HEADER_ONLY

// No complete compressed file or PCM track is retained. The fixed arena also
// bounds Vorbis codebooks and scratch; an oversized setup fails without a heap
// fallback. Each playing voice has its own cursor, including overlapping lines.
class SoundVorbisStream {
public:
	static constexpr int ArenaBytes = 2 * 1024 * 1024;
	static constexpr int InputBytes = 64 * 1024;
	static constexpr int ChunkFrames = 4096;
	using ReadAt = int (*)(void*, unsigned int, void*, int);

	SoundVorbisStream() = default;
	SoundVorbisStream(const SoundVorbisStream&) = delete;
	SoundVorbisStream& operator=(const SoundVorbisStream&) = delete;
	~SoundVorbisStream() { Close(); }

	bool Open(ReadAt input, void* user, unsigned int bytes) {
		Close();
		if (!input || !bytes) return false;
		readAt = input; inputUser = user; length = bytes;
		arena.reset(new (std::nothrow) char[ArenaBytes]);
		if (!arena) return false;
		stb_vorbis_alloc alloc = {arena.get(), ArenaBytes};
		const stb_vorbis_callbacks callbacks = {ReadCallback, SeekCallback, TellCallback};
		decoder = stb_vorbis_open_callbacks(&callbacks, this, length, &error, &alloc);
		if (!decoder) { Close(); return false; }
		info = stb_vorbis_get_info(decoder);
		if (info.channels < 1 || info.channels > 2 || info.sample_rate < 8000 || info.sample_rate > 192000) {
			Close(); return false;
		}
		frames = stb_vorbis_stream_length_in_samples(decoder);
		return true;
	}
	void Close() {
		if (decoder) stb_vorbis_close(decoder);
		decoder = nullptr; arena.reset();
		position = 0; cachedStart = 0; cachedBytes = 0; frames = 0;
	}
	int Read(short* output, int capacityFrames) {
		if (!decoder || !output || capacityFrames < 1 || capacityFrames > ChunkFrames) return 0;
		return stb_vorbis_get_samples_short_interleaved(decoder, info.channels, output, capacityFrames * info.channels);
	}
	bool Seek(unsigned int sample) { return decoder && stb_vorbis_seek(decoder, sample) != 0; }
	// A stream without length metadata (Frames() is 0) cannot seek until a complete
	// decode has counted it. Find the last page that carries a position once, then
	// give each decoder of the stream that page and the counted length.
	bool FindLastGranulePage(stb_vorbis_openq4_granule_page& page) {
		return decoder && stb_vorbis_openq4_find_last_granule(decoder, &page) != 0;
	}
	bool SetCountedLength(unsigned int counted, const stb_vorbis_openq4_granule_page& page) {
		if (!decoder || frames || !stb_vorbis_openq4_set_length(decoder, counted, &page)) return false;
		frames = counted;
		return true;
	}
	unsigned int Frames() const { return frames; }
	int Channels() const { return info.channels; }
	int Rate() const { return static_cast<int>(info.sample_rate); }
	int Error() const { return error; }
	bool IsOpen() const { return decoder != nullptr; }

private:
	static int ReadCallback(void* user, unsigned char* output, int bytes) {
		auto& self = *static_cast<SoundVorbisStream*>(user);
		int copied = 0;
		while (copied < bytes && self.position < self.length) {
			if (self.position < self.cachedStart || self.position - self.cachedStart >= self.cachedBytes) {
				self.cachedStart = self.position;
				const int requested = static_cast<int>((std::min)(static_cast<unsigned int>(InputBytes), self.length - self.position));
				const int got = self.readAt(self.inputUser, self.position, self.cache, requested);
				self.cachedBytes = got > 0 && got <= requested ? got : 0;
				if (!self.cachedBytes) break;
			}
			const unsigned int offset = self.position - self.cachedStart;
			const int count = (std::min)(bytes - copied, static_cast<int>(self.cachedBytes - offset));
			std::memcpy(output + copied, self.cache + offset, count);
			self.position += count; copied += count;
		}
		return copied;
	}
	static int SeekCallback(void* user, unsigned int offset) {
		auto& self = *static_cast<SoundVorbisStream*>(user);
		if (offset > self.length) return 0;
		self.position = offset;
		return 1;
	}
	static unsigned int TellCallback(void* user) { return static_cast<SoundVorbisStream*>(user)->position; }

	std::unique_ptr<char[]> arena;
	stb_vorbis* decoder = nullptr;
	stb_vorbis_info info = {};
	ReadAt readAt = nullptr;
	void* inputUser = nullptr;
	unsigned int length = 0, position = 0, cachedStart = 0, cachedBytes = 0, frames = 0;
	int error = 0;
	unsigned char cache[InputBytes];
};
#endif
