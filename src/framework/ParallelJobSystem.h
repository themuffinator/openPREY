/*
===========================================================================

openQ4 portable parallel job system

The job-list architecture is informed by id Software's GPLv3 Doom 3 BFG
idParallelJobList design.  This implementation is original openQ4 code: it
uses portable C++ sleepable synchronization, explicit bounds and cooperative
cancellation instead of carrying over BFG's platform-specific worker code or
spin-wait behavior.

===========================================================================
*/

#ifndef __PARALLEL_JOB_SYSTEM_H__
#define __PARALLEL_JOB_SYSTEM_H__

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>

class idJobList;
struct idJobListState;
struct idJobSystemImpl;

class idJobCancellationToken {
public:
	idJobCancellationToken();

	bool				IsCancellationRequested() const;
	explicit			operator bool() const;

private:
	explicit idJobCancellationToken( const std::shared_ptr<std::atomic<bool> > &flag );

	std::shared_ptr<std::atomic<bool> > flag;

	friend class idJobList;
	friend class idJobSystem;
	friend struct idJobListState;
	friend struct idJobSystemImpl;
};

struct idJobContext {
	void *				data;
	unsigned int		workerIndex;
	idJobCancellationToken cancellation;

	bool IsCancellationRequested() const {
		return cancellation.IsCancellationRequested();
	}
};

typedef void ( *idJobFunction )( const idJobContext &context );

enum class idJobPriority {
	LOW = 0,
	NORMAL,
	HIGH
};

enum class idJobListStatus {
	BUILDING = 0,
	WAITING,
	READY,
	RUNNING,
	COMPLETED,
	CANCELLING,
	CANCELLED,
	FAILED
};

enum class idJobSubmitResult {
	ACCEPTED = 0,
	EXECUTED_SYNCHRONOUSLY,
	QUEUE_FULL,
	INVALID_STATE,
	INVALID_DEPENDENCY,
	DEPENDENCY_FAILED,
	SYSTEM_UNAVAILABLE
};

enum class idJobShutdownMode {
	DRAIN = 0,
	CANCEL_PENDING
};

struct idJobSystemConfig {
	unsigned int		workerThreads;
	std::size_t		maxQueuedLists;
	bool				synchronous;

	idJobSystemConfig();
};

struct idJobListMetrics {
	idJobListStatus		status;
	std::size_t		jobCapacity;
	std::size_t		dependencyCapacity;
	std::uint64_t		submittedJobs;
	std::uint64_t		executedJobs;
	std::uint64_t		cancelledJobs;
	std::uint64_t		failedJobs;
	std::uint64_t		submitTimeMicroseconds;
	std::uint64_t		startTimeMicroseconds;
	std::uint64_t		finishTimeMicroseconds;
	std::uint64_t		waitTimeMicroseconds;
	std::uint64_t		executionTimeMicroseconds;

	idJobListMetrics();
};

struct idJobSystemMetrics {
	std::uint64_t		submittedLists;
	std::uint64_t		rejectedSubmissions;
	std::uint64_t		completedLists;
	std::uint64_t		cancelledLists;
	std::uint64_t		failedLists;
	std::uint64_t		submittedJobs;
	std::uint64_t		executedJobs;
	std::uint64_t		cancelledJobs;
	std::uint64_t		failedJobs;
	std::uint64_t		workerWakeups;
	std::uint64_t		priorityPromotions;
	std::uint64_t		totalExecutionMicroseconds;
	std::uint64_t		totalWaitMicroseconds;
	std::size_t		queuedLists;
	std::size_t		queueHighWatermark;
	std::size_t		runningJobs;
	std::size_t		sleepingWorkers;
	unsigned int		workerThreads;
	bool				synchronous;
	bool				accepting;

	idJobSystemMetrics();
};

class idJobSystem {
public:
	idJobSystem();
	~idJobSystem();

	idJobSystem( const idJobSystem & ) = delete;
	idJobSystem &operator=( const idJobSystem & ) = delete;

	bool				Initialize( const idJobSystemConfig &config );
	void				Shutdown( idJobShutdownMode mode = idJobShutdownMode::DRAIN );
	void				CancelAll();
	void				WaitAll();

	bool				IsInitialized() const;
	bool				IsSynchronous() const;
	unsigned int		GetWorkerThreadCount() const;
	idJobSystemMetrics	GetMetrics() const;

	std::unique_ptr<idJobList> CreateJobList( const char *name,
		std::size_t maxJobs, std::size_t maxDependencies = 0,
		idJobPriority priority = idJobPriority::NORMAL );

	static unsigned int ResolveWorkerThreadCount( int requestedThreads );

private:
	std::shared_ptr<idJobSystemImpl> impl;

	friend class idJobList;
};

class idJobList {
public:
	~idJobList();

	idJobList( const idJobList & ) = delete;
	idJobList &operator=( const idJobList & ) = delete;
	idJobList( idJobList &&other ) noexcept;
	idJobList &operator=( idJobList &&other ) noexcept;

	bool				AddJob( idJobFunction function, void *data );
	bool				AddDependency( const idJobList &dependency );
	idJobSubmitResult	Submit();
	bool				Cancel();
	bool				Wait();
	bool				TryWait() const;

	idJobListStatus		GetStatus() const;
	idJobListMetrics		GetMetrics() const;
	idJobCancellationToken GetCancellationToken() const;
	const char *		GetName() const;

private:
	explicit idJobList( const std::shared_ptr<idJobListState> &state );

	std::shared_ptr<idJobListState> state;

	friend class idJobSystem;
};

extern idJobSystem jobSystem;

const char *idJobListStatusName( idJobListStatus status );
const char *idJobSubmitResultName( idJobSubmitResult result );

#endif
