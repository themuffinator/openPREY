// SPDX-License-Identifier: GPL-3.0-or-later
#include "src/sound/SoundVorbisStream.h"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>

static void Check(bool ok, const char* reason) {
	if (!ok) { std::fprintf(stderr, "%s\n", reason); std::exit(1); }
}
struct Input {
	std::vector<unsigned char> data;
	unsigned maxRead = 0, calls = 0, shortLimit = 0;
	bool fail = false;
	static int Read(void* user, unsigned int at, void* output, int size) {
		auto& self = *static_cast<Input*>(user);
		self.maxRead = (std::max)(self.maxRead, static_cast<unsigned>(size));
		++self.calls;
		if (self.fail || at > self.data.size()) return 0;
		size = (std::min)(size, static_cast<int>(self.data.size() - at));
		if (self.shortLimit) size = (std::min)(size, static_cast<int>(self.shortLimit));
		std::memcpy(output, self.data.data() + at, size);
		return size;
	}
};

int main(int argc, char** argv) {
	Check(argc > 1, "provide Ogg fixtures");
	for (int arg = 1; arg < argc; ++arg) {
		std::ifstream file(argv[arg], std::ios::binary);
		Input input;
		input.data.assign(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
		int channels = 0, rate = 0;
		short* full = nullptr;
		const int frames = stb_vorbis_decode_memory(input.data.data(), static_cast<int>(input.data.size()), &channels, &rate, &full);
		Check(frames > 0 && full, "reference decoder");
		SoundVorbisStream stream;
		Check(stream.Open(Input::Read, &input, static_cast<unsigned>(input.data.size())), "stream open");
		// A fixture without length metadata: the final pages carry no position, or
		// the file ends in other bytes. LoadOggStream counts it, then every decoder
		// of the stream seeks with that count and the last positioned page.
		const bool lengthless = std::strstr(argv[arg], "-lengthless") != nullptr;
		stb_vorbis_openq4_granule_page page{};
		if (lengthless) {
			Check(stream.Frames() == 0, "lengthless fixture reports no length");
			Check(!stream.Seek(static_cast<unsigned>(frames) / 2), "an uncounted stream cannot seek");
			Check(stream.FindLastGranulePage(page) && page.granule <= static_cast<unsigned>(frames) &&
				page.page_end > page.page_start && page.page_end <= input.data.size(), "last positioned page");
			SoundVorbisStream counter;
			Check(counter.Open(Input::Read, &input, static_cast<unsigned>(input.data.size())), "counting open");
			short scratch[SoundVorbisStream::ChunkFrames * 2];
			unsigned counted = 0;
			while (int got = counter.Read(scratch, SoundVorbisStream::ChunkFrames)) counted += got;
			Check(counted == static_cast<unsigned>(frames), "counted length matches a complete decode");
			Check(!stream.SetCountedLength(0, page), "an empty count is refused");
			Check(stream.SetCountedLength(counted, page), "counted length accepted");
			Check(!stream.SetCountedLength(counted, page), "a length is supplied once");
		} else {
			Check(!stream.SetCountedLength(static_cast<unsigned>(frames), page), "a stream with a length keeps it");
		}
		Check(stream.Channels() == channels && stream.Rate() == rate && stream.Frames() == static_cast<unsigned>(frames), "metadata parity");
		short block[SoundVorbisStream::ChunkFrames * 2];
		int decoded = 0;
		while (int count = stream.Read(block, SoundVorbisStream::ChunkFrames)) {
			Check(count <= SoundVorbisStream::ChunkFrames && decoded + count <= frames, "bounded decode");
			Check(!std::memcmp(block, full + decoded * channels, count * channels * sizeof(short)), "PCM differs from full decoder");
			decoded += count;
		}
		Check(decoded == frames, "exact end of stream");
		for (int seek : {0, 1, frames / 2, frames - 1, frames / 4, 0}) {
			Check(stream.Seek(seek), "sample-exact seek");
			const int count = stream.Read(block, SoundVorbisStream::ChunkFrames);
			Check(count > 0 && count <= frames - seek, "seek read length");
			Check(!std::memcmp(block, full + seek * channels, count * channels * sizeof(short)), "seek PCM parity");
		}
		Check(!stream.Seek(static_cast<unsigned>(frames) + 1), "out-of-range seek rejected");
		Check(stream.Read(block, SoundVorbisStream::ChunkFrames + 1) == 0, "oversized output rejected");
		// A second voice must not move the first voice's decoder/cursor.
		SoundVorbisStream other;
		Check(other.Open(Input::Read, &input, static_cast<unsigned>(input.data.size())), "overlap open");
		if (lengthless) Check(other.SetCountedLength(static_cast<unsigned>(frames), page), "second decoder reuses the count");
		Check(stream.Seek(frames / 3) && other.Seek(frames / 5), "independent seeks");
		int count = stream.Read(block, SoundVorbisStream::ChunkFrames);
		Check(!std::memcmp(block, full + (frames / 3) * channels, count * channels * sizeof(short)), "overlap first voice");
		count = other.Read(block, SoundVorbisStream::ChunkFrames);
		Check(!std::memcmp(block, full + (frames / 5) * channels, count * channels * sizeof(short)), "overlap second voice");
		Check(input.maxRead <= SoundVorbisStream::InputBytes, "compressed read bound");
		stream.Close(); other.Close();
		input.shortLimit = 97; // VFS short reads must not lose bytes or spin.
		Check(stream.Open(Input::Read, &input, static_cast<unsigned>(input.data.size())), "short reads open");
		count = stream.Read(block, SoundVorbisStream::ChunkFrames);
		Check(count > 0 && !std::memcmp(block, full, count * channels * sizeof(short)), "short reads PCM");
		stream.Close();
		input.fail = true;
		Check(!stream.Open(Input::Read, &input, static_cast<unsigned>(input.data.size())), "read failure closes decoder");
		Check(!stream.IsOpen(), "failed stream releases arena");
		std::free(full);
		std::printf("PASS %s: %d Hz, %d channels, %d frames%s; PCM, seek, overlap, EOF and read failures\n", argv[arg], rate, channels, frames,
			lengthless ? " (counted, no length metadata)" : "");
	}
}
