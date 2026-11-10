// Test the production checkpoint worker and handoff against independent bytes
// and controlled scheduler/storage failures, without game state or a VFS.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <memory>
#include <string>

static void Check(bool valid) { if (!valid) std::abort(); }
static int liveFiles, completedJobs;
struct idFile {
    std::string bytes;
    explicit idFile(std::string data) : bytes(std::move(data)) { ++liveFiles; }
    virtual ~idFile() { --liveFiles; }
    int Length() const { return static_cast<int>(bytes.size()); }
    const char *GetDataPtr() const { return bytes.data(); }
};
struct idJobContext { void *data; };
enum class idJobPriority { LOW };
enum class idJobSubmitResult { ACCEPTED, EXECUTED_SYNCHRONOUSLY, QUEUE_FULL };
enum class Schedule { Deferred, Immediate, NoList, NoJob, Rejected };
static Schedule schedule;
struct idJobList {
    void (*callback)(const idJobContext&) = nullptr;
    void *data = nullptr;
    bool queued = false;
    bool AddJob(void (*fn)(const idJobContext&), void *ptr) {
        callback = fn; data = ptr; return schedule != Schedule::NoJob;
    }
    idJobSubmitResult Submit() {
        if (schedule == Schedule::Rejected) return idJobSubmitResult::QUEUE_FULL;
        queued = true;
        if (schedule == Schedule::Immediate) { Wait(); return idJobSubmitResult::EXECUTED_SYNCHRONOUSLY; }
        return idJobSubmitResult::ACCEPTED;
    }
    void Wait() {
        if (queued) { Check(liveFiles == 1); queued = false; callback({data}); ++completedJobs; }
    }
    ~idJobList() { Wait(); }
};
struct JobSystem {
    std::unique_ptr<idJobList> CreateJobList(const char*, int, int, idJobPriority) {
        return schedule == Schedule::NoList ? nullptr : std::make_unique<idJobList>();
    }
} jobSystem;
static constexpr unsigned SESSION_OPENQ4_SAVEGAME_INTEGRITY_MAGIC = 0x4934514f;
static constexpr unsigned SESSION_OPENQ4_SAVEGAME_INTEGRITY_VERSION = 1;
// The CRC implementation has its own native test. This oracle checks the
// worker hashes exactly the source bytes, then appends its little-endian value.
static const std::string sourceBytes("snapshot\0with binary\xff", 21);
static unsigned CRC32_BlockChecksum(const void *data, int size) {
    Check(size == static_cast<int>(sourceBytes.size()));
    Check(std::string(static_cast<const char*>(data), size) == sourceBytes);
    return 0x98765432;
}
enum class StorageFault { None, WritePayload, ReadPayload, PayloadMismatch,
    WriteDescription, ReadDescription, DescriptionMismatch };
static StorageFault fault;
static std::map<std::string, std::string> disk;
namespace openq4 {
enum class DurableReadResult { Missing, Present, Failed };
static bool DurableReplaceExact(const std::string &path, const std::string &bytes, std::string &error) {
    Check(path == "payload" || path == "description");
    if ((path == "payload" && fault == StorageFault::WritePayload) ||
        (path == "description" && fault == StorageFault::WriteDescription)) {
        error = "injected write failure"; return false;
    }
    disk[path] = bytes; return true;
}
static DurableReadResult DurableReadExact(const std::string &path, size_t bound, std::string &bytes, std::string &error) {
    if ((path == "payload" && fault == StorageFault::ReadPayload) ||
        (path == "description" && fault == StorageFault::ReadDescription)) {
        error = "injected read failure"; return DurableReadResult::Failed;
    }
    Check(disk.at(path).size() == bound); bytes = disk.at(path);
    if ((path == "payload" && fault == StorageFault::PayloadMismatch) ||
        (path == "description" && fault == StorageFault::DescriptionMismatch)) bytes.back() ^= 1;
    return DurableReadResult::Present;
}
}
#include "CheckpointStorageUnderTest.inc"

int main() {
    std::string expected = sourceBytes;
    for (unsigned value : {SESSION_OPENQ4_SAVEGAME_INTEGRITY_MAGIC, 1u,
            static_cast<unsigned>(sourceBytes.size()), 0x98765432u})
        for (int shift = 0; shift < 32; shift += 8) expected.push_back(static_cast<char>(value >> shift));
    for (bool workerCopy : {false, true}) {
        for (Schedule mode : {Schedule::Deferred, Schedule::Immediate, Schedule::NoList, Schedule::NoJob, Schedule::Rejected}) {
            for (StorageFault failure : {StorageFault::None, StorageFault::WritePayload, StorageFault::ReadPayload,
                    StorageFault::PayloadMismatch, StorageFault::WriteDescription, StorageFault::ReadDescription,
                    StorageFault::DescriptionMismatch}) {
                schedule = mode; fault = failure; disk.clear(); completedJobs = 0;
                auto storage = std::make_unique<sessionSaveStorageJob_t>();
                storage->path = "payload"; storage->descriptionPath = "description"; storage->description = "description bytes";
                idFile *file = new idFile(sourceBytes);
                idFile *original = file;
                const char *originalBytes = file->GetDataPtr();
                const bool accepted = mode == Schedule::Deferred || mode == Schedule::Immediate;
                Check(Session_QueueCheckpointStorage(*storage, file, workerCopy) == accepted);
                Check(liveFiles == 1);
                if (!accepted) {
                    Check(file == original && file->bytes == sourceBytes && !storage->snapshot);
                    storage.reset(); Check(completedJobs == 0 && liveFiles == 1); delete file;
                } else {
                    Check(workerCopy ? file == nullptr && storage->snapshotData == originalBytes : file == original);
                    if (mode == Schedule::Deferred && workerCopy) Check(storage->payload.empty());
                    storage->jobs->Wait();
                    Check(completedJobs == 1 && storage->payload == expected);
                    Check(storage->success == (failure == StorageFault::None));
                    Check(storage->success || !storage->error.empty());
                    if (storage->success) Check(disk.at("payload") == expected && disk.at("description") == "description bytes");
                    storage.reset();
                    if (!workerCopy) delete file;
                }
                Check(liveFiles == 0);
            }
        }
    }
    // Destruction must join a queued reader before releasing its immutable source.
    schedule = Schedule::Deferred; fault = StorageFault::None; completedJobs = 0;
    {
        sessionSaveStorageJob_t storage; storage.path = "payload"; storage.descriptionPath = "description";
        storage.description = "description bytes";
        idFile *file = new idFile(sourceBytes);
        Check(Session_QueueCheckpointStorage(storage, file, true) && file == nullptr);
    }
    Check(completedJobs == 1 && liveFiles == 0);
    std::puts("Checkpoint storage: immutable handoff, join lifetime, rejection fallback and persistence faults passed");
}
