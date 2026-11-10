/*
===========================================================================

openQ4 portable parallel job system

Copyright (C) 2026 openQ4 contributors

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

The scheduling model is informed by id Software's Doom 3 BFG
idParallelJobList, released under GPLv3.  This is an original implementation
using portable C++ condition variables and bounded openQ4-owned state.

===========================================================================
*/

#include "ParallelJobSystem.h"

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <exception>
#include <limits>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace {

const unsigned int MAX_JOB_WORKERS = 32;
const std::size_t MAX_JOB_LIST_CAPACITY = 1024;
const std::size_t MAX_JOBS_PER_LIST = 1024 * 1024;
const std::size_t MAX_DEPENDENCIES_PER_LIST = 256;
const std::size_t MAX_JOB_LIST_NAME = 63;
const std::uint64_t JOB_LIST_STARVATION_THRESHOLD = 8;

std::uint64_t JobClockMicroseconds() {
	return static_cast<std::uint64_t>( std::chrono::duration_cast<std::chrono::microseconds>(
		std::chrono::steady_clock::now().time_since_epoch() ).count() );
}

bool JobStatusIsTerminal( const idJobListStatus status ) {
	return status == idJobListStatus::COMPLETED ||
		status == idJobListStatus::CANCELLED ||
		status == idJobListStatus::FAILED;
}

bool JobStatusIsDependencyFailure( const idJobListStatus status ) {
	return status == idJobListStatus::CANCELLED || status == idJobListStatus::FAILED;
}

int JobPriorityRank( const idJobPriority priority ) {
	return static_cast<int>( priority );
}

struct idJobRecord {
	idJobFunction function;
	void *data;
};

struct idJobWork {
	std::shared_ptr<idJobListState> list;
	idJobRecord job;
	unsigned int workerIndex;
};

} // namespace

struct idJobListState {
	std::weak_ptr<idJobSystemImpl> owner;
	std::string name;
	std::size_t maxJobs;
	std::size_t maxDependencies;
	idJobPriority priority;
	std::vector<idJobRecord> jobs;
	std::vector<std::shared_ptr<idJobListState> > dependencies;
	std::shared_ptr<std::atomic<bool> > cancellationFlag;
	std::condition_variable completionCondition;
	idJobListStatus status;
	std::size_t nextJob;
	std::size_t runningJobs;
	std::uint64_t submitSequence;
	std::uint64_t submitTimeMicroseconds;
	std::uint64_t startTimeMicroseconds;
	std::uint64_t finishTimeMicroseconds;
	std::uint64_t waitTimeMicroseconds;
	std::uint64_t executionTimeMicroseconds;
	std::uint64_t executedJobs;
	std::uint64_t cancelledJobs;
	std::uint64_t failedJobs;
	std::uint64_t schedulingAge;
	bool failureObserved;

	idJobListState( const std::shared_ptr<idJobSystemImpl> &owner_, const char *name_,
		const std::size_t maxJobs_, const std::size_t maxDependencies_, const idJobPriority priority_ )
		: owner( owner_ )
		, name( name_ != nullptr ? name_ : "unnamed" )
		, maxJobs( maxJobs_ )
		, maxDependencies( maxDependencies_ )
		, priority( priority_ )
		, cancellationFlag( std::make_shared<std::atomic<bool> >( false ) )
		, status( idJobListStatus::BUILDING )
		, nextJob( 0 )
		, runningJobs( 0 )
		, submitSequence( 0 )
		, submitTimeMicroseconds( 0 )
		, startTimeMicroseconds( 0 )
		, finishTimeMicroseconds( 0 )
		, waitTimeMicroseconds( 0 )
		, executionTimeMicroseconds( 0 )
		, executedJobs( 0 )
		, cancelledJobs( 0 )
		, failedJobs( 0 )
		, schedulingAge( 0 )
		, failureObserved( false ) {
		if ( name.size() > MAX_JOB_LIST_NAME ) {
			name.resize( MAX_JOB_LIST_NAME );
		}
		jobs.reserve( maxJobs );
		dependencies.reserve( maxDependencies );
	}
};

struct idJobSystemImpl : public std::enable_shared_from_this<idJobSystemImpl> {
	mutable std::mutex mutex;
	std::condition_variable workCondition;
	std::condition_variable allDoneCondition;
	std::vector<std::thread> workers;
	std::vector<std::shared_ptr<idJobListState> > activeLists;
	idJobSystemConfig config;
	idJobSystemMetrics metrics;
	bool initialized;
	bool accepting;
	bool stopping;
	std::uint64_t nextSubmitSequence;

	idJobSystemImpl()
		: initialized( false )
		, accepting( false )
		, stopping( false )
		, nextSubmitSequence( 1 ) {
	}

	bool DependenciesReadyLocked( const idJobListState &list ) const {
		for ( const std::shared_ptr<idJobListState> &dependency : list.dependencies ) {
			if ( dependency == nullptr || dependency->status != idJobListStatus::COMPLETED ) {
				return false;
			}
		}
		return true;
	}

	bool DependencyFailedLocked( const idJobListState &list ) const {
		for ( const std::shared_ptr<idJobListState> &dependency : list.dependencies ) {
			if ( dependency == nullptr || JobStatusIsDependencyFailure( dependency->status ) ) {
				return true;
			}
		}
		return false;
	}

	void RemoveActiveLocked( const std::shared_ptr<idJobListState> &list ) {
		const auto found = std::find( activeLists.begin(), activeLists.end(), list );
		if ( found != activeLists.end() ) {
			activeLists.erase( found );
		}
		metrics.queuedLists = activeLists.size();
		if ( activeLists.empty() ) {
			allDoneCondition.notify_all();
		}
	}

	void FinishLocked( const std::shared_ptr<idJobListState> &list, const idJobListStatus status ) {
		if ( list == nullptr || JobStatusIsTerminal( list->status ) ) {
			return;
		}
		list->status = status;
		list->finishTimeMicroseconds = JobClockMicroseconds();
		if ( status == idJobListStatus::COMPLETED ) {
			metrics.completedLists++;
		} else if ( status == idJobListStatus::CANCELLED ) {
			metrics.cancelledLists++;
		} else if ( status == idJobListStatus::FAILED ) {
			metrics.failedLists++;
		}
		RemoveActiveLocked( list );
		list->completionCondition.notify_all();
	}

	void RequestCancellationLocked( const std::shared_ptr<idJobListState> &list ) {
		if ( list == nullptr || JobStatusIsTerminal( list->status ) ) {
			return;
		}
		list->cancellationFlag->store( true, std::memory_order_release );
		if ( list->status == idJobListStatus::BUILDING ) {
			list->status = idJobListStatus::CANCELLED;
			list->finishTimeMicroseconds = JobClockMicroseconds();
			list->cancelledJobs = list->jobs.size();
			list->completionCondition.notify_all();
			return;
		}
		if ( list->nextJob < list->jobs.size() ) {
			const std::uint64_t cancelled = static_cast<std::uint64_t>( list->jobs.size() - list->nextJob );
			list->cancelledJobs += cancelled;
			metrics.cancelledJobs += cancelled;
			list->nextJob = list->jobs.size();
		}
		list->status = idJobListStatus::CANCELLING;
		if ( list->runningJobs == 0 ) {
			FinishLocked( list, idJobListStatus::CANCELLED );
		}
	}

	void RefreshWaitingListsLocked() {
		std::size_t index = 0;
		while ( index < activeLists.size() ) {
			const std::shared_ptr<idJobListState> list = activeLists[ index ];
			if ( list == nullptr || list->status != idJobListStatus::WAITING ) {
				index++;
				continue;
			}
			if ( DependencyFailedLocked( *list ) ) {
				RequestCancellationLocked( list );
			} else if ( DependenciesReadyLocked( *list ) ) {
				list->status = idJobListStatus::READY;
				if ( list->jobs.empty() ) {
					FinishLocked( list, idJobListStatus::COMPLETED );
				}
			}
			// FinishLocked erases the current element.  In that case, inspect the
			// element shifted into this slot without allocating a snapshot vector.
			if ( index < activeLists.size() && activeLists[ index ] == list ) {
				index++;
			}
		}
	}

	bool HasRunnableWorkLocked() {
		RefreshWaitingListsLocked();
		for ( const std::shared_ptr<idJobListState> &list : activeLists ) {
			if ( list != nullptr &&
				( list->status == idJobListStatus::READY || list->status == idJobListStatus::RUNNING ) &&
				list->nextJob < list->jobs.size() ) {
				return true;
			}
		}
		return false;
	}

	bool AcquireWorkLocked( const unsigned int workerIndex, idJobWork &work ) {
		RefreshWaitingListsLocked();
		std::shared_ptr<idJobListState> selected;
		bool selectedIsStarved = false;
		for ( const std::shared_ptr<idJobListState> &candidate : activeLists ) {
			if ( candidate == nullptr ||
				( candidate->status != idJobListStatus::READY && candidate->status != idJobListStatus::RUNNING ) ||
				candidate->nextJob >= candidate->jobs.size() ) {
				continue;
			}
			// Once any runnable list reaches the starvation threshold, scheduling
			// switches to a primary oldest-waiter class.  Base priority is ignored
			// inside that class so a ring of earlier HIGH lists cannot permanently
			// pin a later LOW list at a tied, capped score.
			const bool candidateIsStarved = candidate->schedulingAge >= JOB_LIST_STARVATION_THRESHOLD;
			bool preferCandidate = selected == nullptr;
			if ( selected != nullptr ) {
				if ( candidateIsStarved != selectedIsStarved ) {
					preferCandidate = candidateIsStarved;
				} else if ( candidateIsStarved ) {
					preferCandidate = candidate->schedulingAge > selected->schedulingAge ||
						( candidate->schedulingAge == selected->schedulingAge &&
							candidate->submitSequence < selected->submitSequence );
				} else {
					const int candidatePriority = JobPriorityRank( candidate->priority );
					const int selectedPriority = JobPriorityRank( selected->priority );
					preferCandidate = candidatePriority > selectedPriority ||
						( candidatePriority == selectedPriority &&
							( candidate->schedulingAge > selected->schedulingAge ||
								( candidate->schedulingAge == selected->schedulingAge &&
									candidate->submitSequence < selected->submitSequence ) ) );
				}
			}
			if ( preferCandidate ) {
				selected = candidate;
				selectedIsStarved = candidateIsStarved;
			}
		}
		if ( selected == nullptr ) {
			return false;
		}
		for ( const std::shared_ptr<idJobListState> &candidate : activeLists ) {
			if ( candidate == nullptr || candidate == selected ||
				( candidate->status != idJobListStatus::READY && candidate->status != idJobListStatus::RUNNING ) ||
				candidate->nextJob >= candidate->jobs.size() ) {
				continue;
			}
			if ( candidate->schedulingAge != ( std::numeric_limits<std::uint64_t>::max )() ) {
				candidate->schedulingAge++;
			}
		}
		if ( selectedIsStarved ) {
			metrics.priorityPromotions++;
		}
		selected->schedulingAge = 0;

		work.list = selected;
		work.job = selected->jobs[ selected->nextJob++ ];
		work.workerIndex = workerIndex;
		selected->runningJobs++;
		metrics.runningJobs++;
		if ( selected->startTimeMicroseconds == 0 ) {
			selected->startTimeMicroseconds = JobClockMicroseconds();
		}
		selected->status = idJobListStatus::RUNNING;
		return true;
	}

	void CompleteWorkLocked( const idJobWork &work, const std::uint64_t elapsedMicroseconds, const bool failed ) {
		const std::shared_ptr<idJobListState> &list = work.list;
		if ( list == nullptr ) {
			return;
		}
		if ( list->runningJobs > 0 ) {
			list->runningJobs--;
		}
		if ( metrics.runningJobs > 0 ) {
			metrics.runningJobs--;
		}
		list->executionTimeMicroseconds += elapsedMicroseconds;
		metrics.totalExecutionMicroseconds += elapsedMicroseconds;
		list->executedJobs++;
		metrics.executedJobs++;
		if ( failed ) {
			list->failureObserved = true;
			list->failedJobs++;
			metrics.failedJobs++;
			list->cancellationFlag->store( true, std::memory_order_release );
			if ( list->nextJob < list->jobs.size() ) {
				const std::uint64_t cancelled = static_cast<std::uint64_t>( list->jobs.size() - list->nextJob );
				list->cancelledJobs += cancelled;
				metrics.cancelledJobs += cancelled;
				list->nextJob = list->jobs.size();
			}
			list->status = idJobListStatus::CANCELLING;
		}

		if ( list->runningJobs == 0 && list->nextJob >= list->jobs.size() ) {
			if ( list->failureObserved ) {
				FinishLocked( list, idJobListStatus::FAILED );
			} else if ( list->cancellationFlag->load( std::memory_order_acquire ) ) {
				FinishLocked( list, idJobListStatus::CANCELLED );
			} else {
				FinishLocked( list, idJobListStatus::COMPLETED );
			}
		}
		RefreshWaitingListsLocked();
		workCondition.notify_all();
	}

	void WorkerMain( const unsigned int workerIndex ) {
		for ( ;; ) {
			idJobWork work = {};
			{
				std::unique_lock<std::mutex> lock( mutex );
				metrics.sleepingWorkers++;
				workCondition.wait( lock, [this]() {
					return stopping || HasRunnableWorkLocked();
				} );
				metrics.sleepingWorkers--;
				metrics.workerWakeups++;
				if ( stopping && !HasRunnableWorkLocked() ) {
					return;
				}
				if ( !AcquireWorkLocked( workerIndex, work ) ) {
					continue;
				}
			}

			const std::uint64_t start = JobClockMicroseconds();
			bool failed = false;
			try {
				idJobContext context = {};
				context.data = work.job.data;
				context.workerIndex = workerIndex;
				context.cancellation = idJobCancellationToken( work.list->cancellationFlag );
				work.job.function( context );
			} catch ( ... ) {
				failed = true;
			}
			const std::uint64_t elapsed = JobClockMicroseconds() - start;

			std::lock_guard<std::mutex> lock( mutex );
			CompleteWorkLocked( work, elapsed, failed );
		}
	}

	idJobSubmitResult SubmitSynchronous( const std::shared_ptr<idJobListState> &list ) {
		std::unique_lock<std::mutex> admissionLock( mutex );
		if ( !initialized || !accepting ) {
			metrics.rejectedSubmissions++;
			return idJobSubmitResult::SYSTEM_UNAVAILABLE;
		}
		if ( list == nullptr || list->status != idJobListStatus::BUILDING ) {
			metrics.rejectedSubmissions++;
			return idJobSubmitResult::INVALID_STATE;
		}
		for ( const std::shared_ptr<idJobListState> &dependency : list->dependencies ) {
			if ( dependency == nullptr || dependency->owner.lock().get() != this ||
				dependency->status == idJobListStatus::BUILDING ) {
				metrics.rejectedSubmissions++;
				return idJobSubmitResult::INVALID_DEPENDENCY;
			}
			if ( JobStatusIsDependencyFailure( dependency->status ) ) {
				metrics.rejectedSubmissions++;
				return idJobSubmitResult::DEPENDENCY_FAILED;
			}
		}
		if ( activeLists.size() >= config.maxQueuedLists ) {
			metrics.rejectedSubmissions++;
			return idJobSubmitResult::QUEUE_FULL;
		}

		list->submitSequence = nextSubmitSequence++;
		list->submitTimeMicroseconds = JobClockMicroseconds();
		list->status = idJobListStatus::WAITING;
		metrics.submittedLists++;
		metrics.submittedJobs += list->jobs.size();
		activeLists.push_back( list );
		metrics.queuedLists = activeLists.size();
		metrics.queueHighWatermark = ( std::max )( metrics.queueHighWatermark, metrics.queuedLists );
		workCondition.notify_all();

		// Synchronous lists still participate in the global active/quiescence
		// contract.  Concurrent callers sleep until their deterministic submit
		// sequence reaches the front; shutdown and CancelAll can therefore observe,
		// cancel, and join every inline job just like worker-owned work.
		workCondition.wait( admissionLock, [this, &list]() {
			return JobStatusIsTerminal( list->status ) ||
				( !activeLists.empty() && activeLists.front() == list );
		} );
		if ( JobStatusIsTerminal( list->status ) ) {
			return idJobSubmitResult::EXECUTED_SYNCHRONOUSLY;
		}
		if ( DependencyFailedLocked( *list ) ) {
			RequestCancellationLocked( list );
			workCondition.notify_all();
			return idJobSubmitResult::DEPENDENCY_FAILED;
		}
		if ( !DependenciesReadyLocked( *list ) ) {
			// Dependencies are admitted before dependents.  Reaching the head while
			// one is still non-terminal would violate that ordering contract.
			list->failureObserved = true;
			FinishLocked( list, idJobListStatus::FAILED );
			workCondition.notify_all();
			return idJobSubmitResult::INVALID_DEPENDENCY;
		}
		list->status = idJobListStatus::RUNNING;
		list->startTimeMicroseconds = JobClockMicroseconds();
		list->runningJobs = 1;
		metrics.runningJobs++;
		admissionLock.unlock();

		for ( std::size_t jobIndex = 0; jobIndex < list->jobs.size(); ++jobIndex ) {
			if ( list->cancellationFlag->load( std::memory_order_acquire ) ) {
				break;
			}
			const idJobRecord &job = list->jobs[ jobIndex ];
			{
				std::lock_guard<std::mutex> lock( mutex );
				// Mark the job acquired before invoking user work so a concurrent
				// cancellation accounts only jobs that have not started.
				list->nextJob = jobIndex + 1;
			}
			const std::uint64_t start = JobClockMicroseconds();
			bool failed = false;
			try {
				idJobContext context = {};
				context.data = job.data;
				context.workerIndex = 0;
				context.cancellation = idJobCancellationToken( list->cancellationFlag );
				job.function( context );
			} catch ( ... ) {
				failed = true;
			}
			const std::uint64_t elapsed = JobClockMicroseconds() - start;
			std::lock_guard<std::mutex> lock( mutex );
			list->executionTimeMicroseconds += elapsed;
			metrics.totalExecutionMicroseconds += elapsed;
			list->executedJobs++;
			metrics.executedJobs++;
			if ( failed ) {
				list->failureObserved = true;
				list->cancellationFlag->store( true, std::memory_order_release );
				list->failedJobs++;
				metrics.failedJobs++;
				const std::uint64_t cancelled = static_cast<std::uint64_t>( list->jobs.size() - list->nextJob );
				list->cancelledJobs += cancelled;
				metrics.cancelledJobs += cancelled;
				list->nextJob = list->jobs.size();
				break;
			}
		}

		{
			std::lock_guard<std::mutex> lock( mutex );
			list->runningJobs = 0;
			if ( metrics.runningJobs > 0 ) {
				metrics.runningJobs--;
			}
			if ( list->failureObserved ) {
				FinishLocked( list, idJobListStatus::FAILED );
			} else if ( list->cancellationFlag->load( std::memory_order_acquire ) ) {
				FinishLocked( list, idJobListStatus::CANCELLED );
			} else {
				FinishLocked( list, idJobListStatus::COMPLETED );
			}
			RefreshWaitingListsLocked();
			workCondition.notify_all();
		}
		return idJobSubmitResult::EXECUTED_SYNCHRONOUSLY;
	}

	idJobSubmitResult SubmitThreaded( const std::shared_ptr<idJobListState> &list ) {
		std::lock_guard<std::mutex> lock( mutex );
		if ( !initialized || !accepting ) {
			metrics.rejectedSubmissions++;
			return idJobSubmitResult::SYSTEM_UNAVAILABLE;
		}
		if ( list == nullptr || list->status != idJobListStatus::BUILDING ) {
			metrics.rejectedSubmissions++;
			return idJobSubmitResult::INVALID_STATE;
		}
		for ( const std::shared_ptr<idJobListState> &dependency : list->dependencies ) {
			if ( dependency == nullptr || dependency->owner.lock().get() != this ||
				dependency->status == idJobListStatus::BUILDING ) {
				metrics.rejectedSubmissions++;
				return idJobSubmitResult::INVALID_DEPENDENCY;
			}
			if ( JobStatusIsDependencyFailure( dependency->status ) ) {
				metrics.rejectedSubmissions++;
				return idJobSubmitResult::DEPENDENCY_FAILED;
			}
		}
		if ( activeLists.size() >= config.maxQueuedLists ) {
			metrics.rejectedSubmissions++;
			return idJobSubmitResult::QUEUE_FULL;
		}

		list->submitSequence = nextSubmitSequence++;
		list->submitTimeMicroseconds = JobClockMicroseconds();
		list->status = DependenciesReadyLocked( *list ) ? idJobListStatus::READY : idJobListStatus::WAITING;
		metrics.submittedLists++;
		metrics.submittedJobs += list->jobs.size();
		activeLists.push_back( list );
		metrics.queuedLists = activeLists.size();
		metrics.queueHighWatermark = ( std::max )( metrics.queueHighWatermark, metrics.queuedLists );

		if ( list->jobs.empty() && list->status == idJobListStatus::READY ) {
			FinishLocked( list, idJobListStatus::COMPLETED );
			RefreshWaitingListsLocked();
		}
		workCondition.notify_all();
		return idJobSubmitResult::ACCEPTED;
	}
};

idJobCancellationToken::idJobCancellationToken() {
}

idJobCancellationToken::idJobCancellationToken( const std::shared_ptr<std::atomic<bool> > &flag_ )
	: flag( flag_ ) {
}

bool idJobCancellationToken::IsCancellationRequested() const {
	return flag != nullptr && flag->load( std::memory_order_acquire );
}

idJobCancellationToken::operator bool() const {
	return flag != nullptr;
}

idJobSystemConfig::idJobSystemConfig()
	: workerThreads( 0 )
	, maxQueuedLists( 64 )
	, synchronous( false ) {
}

idJobListMetrics::idJobListMetrics()
	: status( idJobListStatus::BUILDING )
	, jobCapacity( 0 )
	, dependencyCapacity( 0 )
	, submittedJobs( 0 )
	, executedJobs( 0 )
	, cancelledJobs( 0 )
	, failedJobs( 0 )
	, submitTimeMicroseconds( 0 )
	, startTimeMicroseconds( 0 )
	, finishTimeMicroseconds( 0 )
	, waitTimeMicroseconds( 0 )
	, executionTimeMicroseconds( 0 ) {
}

idJobSystemMetrics::idJobSystemMetrics()
	: submittedLists( 0 )
	, rejectedSubmissions( 0 )
	, completedLists( 0 )
	, cancelledLists( 0 )
	, failedLists( 0 )
	, submittedJobs( 0 )
	, executedJobs( 0 )
	, cancelledJobs( 0 )
	, failedJobs( 0 )
	, workerWakeups( 0 )
	, priorityPromotions( 0 )
	, totalExecutionMicroseconds( 0 )
	, totalWaitMicroseconds( 0 )
	, queuedLists( 0 )
	, queueHighWatermark( 0 )
	, runningJobs( 0 )
	, sleepingWorkers( 0 )
	, workerThreads( 0 )
	, synchronous( false )
	, accepting( false ) {
}

idJobSystem::idJobSystem()
	: impl( std::make_shared<idJobSystemImpl>() ) {
}

idJobSystem::~idJobSystem() {
	Shutdown( idJobShutdownMode::CANCEL_PENDING );
	impl.reset();
}

bool idJobSystem::Initialize( const idJobSystemConfig &requestedConfig ) {
	if ( impl == nullptr ) {
		impl = std::make_shared<idJobSystemImpl>();
	}
	if ( requestedConfig.maxQueuedLists == 0 || requestedConfig.maxQueuedLists > MAX_JOB_LIST_CAPACITY ||
		requestedConfig.workerThreads > MAX_JOB_WORKERS ) {
		return false;
	}

	std::unique_lock<std::mutex> lock( impl->mutex );
	if ( impl->initialized ) {
		return false;
	}
	if ( !impl->activeLists.empty() || !impl->workers.empty() ) {
		return false;
	}
	impl->config = requestedConfig;
	if ( impl->config.workerThreads == 0 ) {
		impl->config.workerThreads = ResolveWorkerThreadCount( 0 );
	}
	impl->config.synchronous = requestedConfig.synchronous;
	try {
		// All scheduler-owned vectors are reserved before admission or worker
		// creation begins.  Accepted submissions and teardown therefore require
		// no container growth and allocation failure remains an Initialize error.
		impl->activeLists.reserve( impl->config.maxQueuedLists );
		if ( !impl->config.synchronous ) {
			impl->workers.reserve( impl->config.workerThreads );
		}
	} catch ( ... ) {
		return false;
	}
	impl->metrics = idJobSystemMetrics();
	impl->metrics.synchronous = impl->config.synchronous;
	impl->metrics.workerThreads = impl->config.synchronous ? 0 : impl->config.workerThreads;
	impl->metrics.accepting = true;
	impl->accepting = true;
	impl->stopping = false;
	impl->initialized = true;
	impl->nextSubmitSequence = 1;

	if ( !impl->config.synchronous ) {
		try {
			for ( unsigned int workerIndex = 0; workerIndex < impl->config.workerThreads; ++workerIndex ) {
				const std::shared_ptr<idJobSystemImpl> workerImpl = impl;
				impl->workers.emplace_back( [workerImpl, workerIndex]() {
					workerImpl->WorkerMain( workerIndex );
				} );
			}
		} catch ( ... ) {
			impl->accepting = false;
			impl->metrics.accepting = false;
			impl->stopping = true;
			impl->workCondition.notify_all();
			std::vector<std::thread> startedWorkers = std::move( impl->workers );
			impl->initialized = false;
			lock.unlock();
			for ( std::thread &worker : startedWorkers ) {
				if ( worker.joinable() ) {
					worker.join();
				}
			}
			return false;
		}
	}
	return true;
}

void idJobSystem::Shutdown( const idJobShutdownMode mode ) {
	if ( impl == nullptr ) {
		return;
	}
	std::vector<std::thread> workers;
	{
		std::unique_lock<std::mutex> lock( impl->mutex );
		if ( !impl->initialized ) {
			return;
		}
		impl->accepting = false;
		impl->metrics.accepting = false;
		if ( mode == idJobShutdownMode::CANCEL_PENDING ) {
			std::size_t index = 0;
			while ( index < impl->activeLists.size() ) {
				const std::shared_ptr<idJobListState> list = impl->activeLists[ index ];
				impl->RequestCancellationLocked( list );
				if ( index < impl->activeLists.size() && impl->activeLists[ index ] == list ) {
					index++;
				}
			}
		}
		impl->workCondition.notify_all();
		impl->allDoneCondition.wait( lock, [this]() {
			return impl->activeLists.empty();
		} );
		impl->stopping = true;
		impl->workCondition.notify_all();
		workers = std::move( impl->workers );
		impl->initialized = false;
	}
	for ( std::thread &worker : workers ) {
		if ( worker.joinable() ) {
			worker.join();
		}
	}
}

void idJobSystem::CancelAll() {
	if ( impl == nullptr ) {
		return;
	}
	std::lock_guard<std::mutex> lock( impl->mutex );
	std::size_t index = 0;
	while ( index < impl->activeLists.size() ) {
		const std::shared_ptr<idJobListState> list = impl->activeLists[ index ];
		impl->RequestCancellationLocked( list );
		if ( index < impl->activeLists.size() && impl->activeLists[ index ] == list ) {
			index++;
		}
	}
	impl->RefreshWaitingListsLocked();
	impl->workCondition.notify_all();
}

void idJobSystem::WaitAll() {
	if ( impl == nullptr ) {
		return;
	}
	const std::uint64_t start = JobClockMicroseconds();
	std::unique_lock<std::mutex> lock( impl->mutex );
	impl->allDoneCondition.wait( lock, [this]() {
		return impl->activeLists.empty();
	} );
	impl->metrics.totalWaitMicroseconds += JobClockMicroseconds() - start;
}

bool idJobSystem::IsInitialized() const {
	if ( impl == nullptr ) {
		return false;
	}
	std::lock_guard<std::mutex> lock( impl->mutex );
	return impl->initialized;
}

bool idJobSystem::IsSynchronous() const {
	if ( impl == nullptr ) {
		return true;
	}
	std::lock_guard<std::mutex> lock( impl->mutex );
	return !impl->initialized || impl->config.synchronous;
}

unsigned int idJobSystem::GetWorkerThreadCount() const {
	if ( impl == nullptr ) {
		return 0;
	}
	std::lock_guard<std::mutex> lock( impl->mutex );
	return impl->initialized && !impl->config.synchronous ? impl->config.workerThreads : 0;
}

idJobSystemMetrics idJobSystem::GetMetrics() const {
	if ( impl == nullptr ) {
		return idJobSystemMetrics();
	}
	std::lock_guard<std::mutex> lock( impl->mutex );
	idJobSystemMetrics snapshot = impl->metrics;
	snapshot.queuedLists = impl->activeLists.size();
	snapshot.workerThreads = impl->initialized && !impl->config.synchronous ? impl->config.workerThreads : 0;
	snapshot.synchronous = impl->config.synchronous;
	snapshot.accepting = impl->accepting;
	return snapshot;
}

std::unique_ptr<idJobList> idJobSystem::CreateJobList( const char *name,
		const std::size_t maxJobs, const std::size_t maxDependencies,
		const idJobPriority priority ) {
	if ( impl == nullptr || maxJobs == 0 || maxJobs > MAX_JOBS_PER_LIST ||
		maxDependencies > MAX_DEPENDENCIES_PER_LIST ) {
		return std::unique_ptr<idJobList>();
	}
	{
		std::lock_guard<std::mutex> lock( impl->mutex );
		if ( !impl->initialized || !impl->accepting ) {
			return std::unique_ptr<idJobList>();
		}
	}
	try {
		return std::unique_ptr<idJobList>( new idJobList( std::make_shared<idJobListState>(
			impl, name, maxJobs, maxDependencies, priority ) ) );
	} catch ( ... ) {
		return std::unique_ptr<idJobList>();
	}
}

unsigned int idJobSystem::ResolveWorkerThreadCount( const int requestedThreads ) {
	if ( requestedThreads > 0 ) {
		return ( std::min )( static_cast<unsigned int>( requestedThreads ), MAX_JOB_WORKERS );
	}
	const unsigned int hardwareThreads = std::thread::hardware_concurrency();
	if ( hardwareThreads <= 1 ) {
		return 1;
	}
	return ( std::min )( hardwareThreads - 1, MAX_JOB_WORKERS );
}

idJobList::idJobList( const std::shared_ptr<idJobListState> &state_ )
	: state( state_ ) {
}

idJobList::~idJobList() {
	if ( state != nullptr ) {
		Cancel();
		Wait();
	}
}

idJobList::idJobList( idJobList &&other ) noexcept
	: state( std::move( other.state ) ) {
}

idJobList &idJobList::operator=( idJobList &&other ) noexcept {
	if ( this != &other ) {
		if ( state != nullptr ) {
			Cancel();
			Wait();
		}
		state = std::move( other.state );
	}
	return *this;
}

bool idJobList::AddJob( const idJobFunction function, void *data ) {
	if ( state == nullptr || function == nullptr ) {
		return false;
	}
	const std::shared_ptr<idJobSystemImpl> owner = state->owner.lock();
	if ( owner == nullptr ) {
		return false;
	}
	std::lock_guard<std::mutex> lock( owner->mutex );
	if ( state->status != idJobListStatus::BUILDING || state->jobs.size() >= state->maxJobs ) {
		return false;
	}
	state->jobs.push_back( { function, data } );
	return true;
}

bool idJobList::AddDependency( const idJobList &dependency ) {
	if ( state == nullptr || dependency.state == nullptr || state == dependency.state ) {
		return false;
	}
	const std::shared_ptr<idJobSystemImpl> owner = state->owner.lock();
	const std::shared_ptr<idJobSystemImpl> dependencyOwner = dependency.state->owner.lock();
	if ( owner == nullptr || owner != dependencyOwner ) {
		return false;
	}
	std::lock_guard<std::mutex> lock( owner->mutex );
	if ( state->status != idJobListStatus::BUILDING ||
		state->dependencies.size() >= state->maxDependencies ||
		dependency.state->status == idJobListStatus::BUILDING ) {
		return false;
	}
	if ( std::find( state->dependencies.begin(), state->dependencies.end(), dependency.state ) != state->dependencies.end() ) {
		return false;
	}
	state->dependencies.push_back( dependency.state );
	return true;
}

idJobSubmitResult idJobList::Submit() {
	if ( state == nullptr ) {
		return idJobSubmitResult::INVALID_STATE;
	}
	const std::shared_ptr<idJobSystemImpl> owner = state->owner.lock();
	if ( owner == nullptr ) {
		return idJobSubmitResult::SYSTEM_UNAVAILABLE;
	}
	bool synchronous = false;
	{
		std::lock_guard<std::mutex> lock( owner->mutex );
		synchronous = owner->config.synchronous;
	}
	if ( synchronous ) {
		return owner->SubmitSynchronous( state );
	}
	return owner->SubmitThreaded( state );
}

bool idJobList::Cancel() {
	if ( state == nullptr ) {
		return false;
	}
	const std::shared_ptr<idJobSystemImpl> owner = state->owner.lock();
	if ( owner == nullptr ) {
		state->cancellationFlag->store( true, std::memory_order_release );
		return false;
	}
	std::lock_guard<std::mutex> lock( owner->mutex );
	if ( JobStatusIsTerminal( state->status ) ) {
		return false;
	}
	owner->RequestCancellationLocked( state );
	owner->RefreshWaitingListsLocked();
	owner->workCondition.notify_all();
	return true;
}

bool idJobList::Wait() {
	if ( state == nullptr ) {
		return false;
	}
	const std::shared_ptr<idJobSystemImpl> owner = state->owner.lock();
	if ( owner == nullptr ) {
		return state->status == idJobListStatus::COMPLETED;
	}
	const std::uint64_t start = JobClockMicroseconds();
	std::unique_lock<std::mutex> lock( owner->mutex );
	if ( state->status == idJobListStatus::BUILDING ) {
		return false;
	}
	state->completionCondition.wait( lock, [this]() {
		return JobStatusIsTerminal( state->status );
	} );
	const std::uint64_t waited = JobClockMicroseconds() - start;
	state->waitTimeMicroseconds += waited;
	owner->metrics.totalWaitMicroseconds += waited;
	return state->status == idJobListStatus::COMPLETED;
}

bool idJobList::TryWait() const {
	return state != nullptr && JobStatusIsTerminal( GetStatus() );
}

idJobListStatus idJobList::GetStatus() const {
	if ( state == nullptr ) {
		return idJobListStatus::FAILED;
	}
	const std::shared_ptr<idJobSystemImpl> owner = state->owner.lock();
	if ( owner == nullptr ) {
		return state->status;
	}
	std::lock_guard<std::mutex> lock( owner->mutex );
	return state->status;
}

idJobListMetrics idJobList::GetMetrics() const {
	idJobListMetrics snapshot;
	if ( state == nullptr ) {
		snapshot.status = idJobListStatus::FAILED;
		return snapshot;
	}
	const std::shared_ptr<idJobSystemImpl> owner = state->owner.lock();
	std::unique_lock<std::mutex> lock;
	if ( owner != nullptr ) {
		lock = std::unique_lock<std::mutex>( owner->mutex );
	}
	snapshot.status = state->status;
	snapshot.jobCapacity = state->maxJobs;
	snapshot.dependencyCapacity = state->maxDependencies;
	snapshot.submittedJobs = state->submitTimeMicroseconds != 0 ? state->jobs.size() : 0;
	snapshot.executedJobs = state->executedJobs;
	snapshot.cancelledJobs = state->cancelledJobs;
	snapshot.failedJobs = state->failedJobs;
	snapshot.submitTimeMicroseconds = state->submitTimeMicroseconds;
	snapshot.startTimeMicroseconds = state->startTimeMicroseconds;
	snapshot.finishTimeMicroseconds = state->finishTimeMicroseconds;
	snapshot.waitTimeMicroseconds = state->waitTimeMicroseconds;
	snapshot.executionTimeMicroseconds = state->executionTimeMicroseconds;
	return snapshot;
}

idJobCancellationToken idJobList::GetCancellationToken() const {
	return state != nullptr ? idJobCancellationToken( state->cancellationFlag ) : idJobCancellationToken();
}

const char *idJobList::GetName() const {
	return state != nullptr ? state->name.c_str() : "<invalid>";
}

const char *idJobListStatusName( const idJobListStatus status ) {
	switch ( status ) {
		case idJobListStatus::BUILDING: return "building";
		case idJobListStatus::WAITING: return "waiting";
		case idJobListStatus::READY: return "ready";
		case idJobListStatus::RUNNING: return "running";
		case idJobListStatus::COMPLETED: return "completed";
		case idJobListStatus::CANCELLING: return "cancelling";
		case idJobListStatus::CANCELLED: return "cancelled";
		case idJobListStatus::FAILED: return "failed";
	}
	return "unknown";
}

const char *idJobSubmitResultName( const idJobSubmitResult result ) {
	switch ( result ) {
		case idJobSubmitResult::ACCEPTED: return "accepted";
		case idJobSubmitResult::EXECUTED_SYNCHRONOUSLY: return "executed-synchronously";
		case idJobSubmitResult::QUEUE_FULL: return "queue-full";
		case idJobSubmitResult::INVALID_STATE: return "invalid-state";
		case idJobSubmitResult::INVALID_DEPENDENCY: return "invalid-dependency";
		case idJobSubmitResult::DEPENDENCY_FAILED: return "dependency-failed";
		case idJobSubmitResult::SYSTEM_UNAVAILABLE: return "system-unavailable";
	}
	return "unknown";
}

idJobSystem jobSystem;
