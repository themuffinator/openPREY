// Exercise the production worker with storage faults, without a GPU or VFS.
#include <chrono>
#include <cstdio>
#include <memory>
#include <string>

struct idJobList {};
struct idJobContext { void *data; };
static std::string inputBytes, writtenBytes;
static int reads, writes;
enum Fault { None, Missing, FirstRead, Persist, SecondRead, ReadbackMismatch };
static Fault fault;
namespace openq4 {
enum class DurableReadResult { Missing, Present, Failed };
static DurableReadResult DurableReadExact(const std::string &path, size_t maxBytes,
    std::string &bytes, std::string &error) {
    ++reads;
    if (path != "preview.tga.tmp" || maxBytes != 307218) return DurableReadResult::Failed;
    if (reads == 1 && fault == Missing) return DurableReadResult::Missing;
    if ((reads == 1 && fault == FirstRead) || (reads == 2 && fault == SecondRead)) {
        error = "injected read failure";
        return DurableReadResult::Failed;
    }
    bytes = reads == 1 ? inputBytes : writtenBytes;
    if (reads == 2 && fault == ReadbackMismatch) bytes.back() ^= 1;
    return DurableReadResult::Present;
}
static bool DurableReplaceExact(const std::string &path, const std::string &bytes, std::string &error) {
    ++writes;
    if (path != "preview.tga.tmp") return false;
    if (fault == Persist) { error = "injected sync failure"; return false; }
    writtenBytes = bytes;
    return true;
}
}
#include "CheckpointPreviewUnderTest.inc"

static bool Check(const std::string &bytes, Fault injected, bool expected, int expectedWrites) {
    inputBytes = bytes;
    writtenBytes.clear();
    reads = writes = 0;
    fault = injected;
    sessionSavePreviewJob_t preview;
    preview.path = "preview.tga.tmp";
    Session_PersistCheckpointPreview({ &preview });
    return preview.success == expected && writes == expectedWrites &&
        (!expected || (reads == 2 && writtenBytes == inputBytes)) &&
        (expected || !preview.error.empty());
}
int main() {
    std::string valid(307218, '\0');
    valid[2] = 2; valid[12] = 64; valid[13] = 1;
    valid[14] = static_cast<char>(240); valid[16] = 32;
    for (size_t i = 18; i < valid.size(); ++i) valid[i] = static_cast<char>(i * 37);
    if (!Check(valid, None, true, 1)) return 1;
    for (Fault failure : { Missing, FirstRead, Persist, SecondRead, ReadbackMismatch }) {
        if (!Check(valid, failure, false, failure == Missing || failure == FirstRead ? 0 : 1)) return 2;
    }
    for (size_t length : { size_t(0), size_t(17), size_t(18), size_t(307217), size_t(307219) }) {
        std::string resized = valid;
        resized.resize(length);
        if (!Check(resized, None, false, 0)) return 3;
    }
    // Reject alternate TGA formats, orientation, dimensions and color maps;
    // only the renderer's fixed thumbnail may carry the no-second-sync proof.
    for (int offset : { 0, 1, 2, 12, 13, 14, 15, 16, 17 }) {
        std::string malformed = valid;
        malformed[offset] ^= 1;
        if (!Check(malformed, None, false, 0)) return 4;
    }
    std::puts("Checkpoint preview: exact persistence, failed sync/readback and malformed image controls passed");
}
