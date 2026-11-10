#include "src/framework/ParallelJobSystem.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

namespace {

int failures = 0;

void Expect( const bool condition, const char *label ) {
	if ( !condition ) {
		std::fprintf( stderr, "ParallelJobSystemTest failed: %s\n", label );
		failures++;
	}
}

bool SubmitSucceeded( const idJobSubmitResult result ) {
	return result == idJobSubmitResult::ACCEPTED ||
		result == idJobSubmitResult::EXECUTED_SYNCHRONOUSLY;
}

struct AppendData {
	std::vector<int> *values;
	int value;
};

void AppendJob( const idJobContext &context ) {
	AppendData *data = static_cast<AppendData *>( context.data );
	data->values->push_back( data->value );
	Expect( context.workerIndex == 0, "synchronous jobs must use deterministic worker index zero" );
}

void RecordJob( const idJobContext &context ) {
	AppendData *data = static_cast<AppendData *>( context.data );
	data->values->push_back( data->value );
}

void IncrementAtomicJob( const idJobContext &context ) {
	std::atomic<int> *value = static_cast<std::atomic<int> *>( context.data );
	value->fetch_add( 1, std::memory_order_relaxed );
}

struct DependencyData {
	std::atomic<int> *phase;
	std::atomic<bool> *failed;
	int expected;
	int replacement;
};

void DependencyJob( const idJobContext &context ) {
	DependencyData *data = static_cast<DependencyData *>( context.data );
	if ( data->phase->load( std::memory_order_acquire ) != data->expected ) {
		data->failed->store( true, std::memory_order_release );
	}
	data->phase->store( data->replacement, std::memory_order_release );
}

struct BlockingData {
	std::mutex mutex;
	std::condition_variable condition;
	bool started = false;
	bool release = false;
};

struct ParallelGateData {
	std::mutex mutex;
	std::condition_variable condition;
	int started = 0;
	bool release = false;
};

void ParallelGateJob( const idJobContext &context ) {
	ParallelGateData *data = static_cast<ParallelGateData *>( context.data );
	std::unique_lock<std::mutex> lock( data->mutex );
	data->started++;
	data->condition.notify_all();
	data->condition.wait( lock, [&data, &context]() {
		return data->release || context.IsCancellationRequested();
	} );
}

void BlockingJob( const idJobContext &context ) {
	BlockingData *data = static_cast<BlockingData *>( context.data );
	std::unique_lock<std::mutex> lock( data->mutex );
	data->started = true;
	data->condition.notify_all();
	while ( !data->release && !context.IsCancellationRequested() ) {
		data->condition.wait_for( lock, std::chrono::milliseconds( 10 ) );
	}
}

bool WaitForStarted( BlockingData &data ) {
	std::unique_lock<std::mutex> lock( data.mutex );
	return data.condition.wait_for( lock, std::chrono::seconds( 2 ), [&data]() {
		return data.started;
	} );
}

void ReleaseBlockingJob( BlockingData &data ) {
	{
		std::lock_guard<std::mutex> lock( data.mutex );
		data.release = true;
	}
	data.condition.notify_all();
}

void ThrowingJob( const idJobContext & ) {
	throw std::runtime_error( "intentional job failure" );
}

struct ObservePriorityData {
	std::atomic<int> *highCompleted;
	std::atomic<int> *observedHighCompleted;
};

void ObservePriorityJob( const idJobContext &context ) {
	ObservePriorityData *data = static_cast<ObservePriorityData *>( context.data );
	data->observedHighCompleted->store(
		data->highCompleted->load( std::memory_order_acquire ),
		std::memory_order_release );
}

void ExerciseConfigurationBounds() {
	idJobSystem system;
	idJobSystemConfig config;
	config.maxQueuedLists = 0;
	Expect( !system.Initialize( config ), "zero active-list capacity fails closed" );
	config.maxQueuedLists = 1025;
	Expect( !system.Initialize( config ), "oversized active-list capacity fails closed" );
	config.maxQueuedLists = 1;
	config.workerThreads = 33;
	Expect( !system.Initialize( config ), "oversized worker count fails closed" );
	config.synchronous = true;
	config.workerThreads = 0;
	Expect( system.Initialize( config ), "system initializes after rejected configurations" );
	Expect( system.CreateJobList( "zero-jobs", 0 ) == nullptr,
		"zero per-list job capacity fails closed" );
	Expect( system.CreateJobList( "oversized-jobs", 1024 * 1024 + 1 ) == nullptr,
		"hard per-list job bound fails closed" );
	Expect( system.CreateJobList( "oversized-dependencies", 1, 257 ) == nullptr,
		"hard per-list dependency bound fails closed" );
	system.Shutdown();
	config.synchronous = false;
	config.workerThreads = 2;
	config.maxQueuedLists = 4;
	Expect( system.Initialize( config ),
		"reinitialization refreshes bounded scheduler storage" );
	Expect( system.GetWorkerThreadCount() == 2,
		"reinitialized scheduler exposes its reserved worker count" );
	system.Shutdown();
}

void ExerciseSynchronousMode() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = true;
	config.workerThreads = 8;
	config.maxQueuedLists = 2;
	Expect( system.Initialize( config ), "synchronous system initializes" );
	Expect( system.IsSynchronous(), "synchronous policy is observable" );
	Expect( system.GetWorkerThreadCount() == 0, "synchronous policy creates no workers" );

	std::vector<int> values;
	AppendData data[] = { { &values, 1 }, { &values, 2 }, { &values, 3 } };
	std::unique_ptr<idJobList> first = system.CreateJobList( "deterministic-first", 2, 1 );
	std::unique_ptr<idJobList> second = system.CreateJobList( "deterministic-second", 1, 1 );
	Expect( first != nullptr && second != nullptr, "bounded synchronous lists allocate" );
	Expect( first->AddJob( AppendJob, &data[0] ), "first deterministic job added" );
	Expect( first->AddJob( AppendJob, &data[1] ), "second deterministic job added" );
	Expect( !first->AddJob( AppendJob, &data[2] ), "per-list job capacity rejects overflow" );
	Expect( !second->AddDependency( *second ), "self dependency fails closed" );
	Expect( !second->AddDependency( *first ), "unsubmitted dependency fails closed" );
	Expect( first->Submit() == idJobSubmitResult::EXECUTED_SYNCHRONOUSLY,
		"first list executes synchronously" );
	Expect( second->AddDependency( *first ), "submitted dependency is accepted" );
	Expect( !first->AddDependency( *second ), "reverse dependency cycle fails closed" );
	Expect( second->AddJob( AppendJob, &data[2] ), "dependent job added" );
	Expect( second->Submit() == idJobSubmitResult::EXECUTED_SYNCHRONOUSLY,
		"dependent list executes synchronously" );
	Expect( values == std::vector<int>( { 1, 2, 3 } ), "synchronous insertion and dependency order is deterministic" );
	Expect( first->Wait() && second->Wait(), "completed synchronous lists wait successfully" );
	Expect( first->GetMetrics().executedJobs == 2, "per-list synchronous execution metrics" );

	const idJobSystemMetrics metrics = system.GetMetrics();
	Expect( metrics.submittedLists == 2 && metrics.completedLists == 2,
		"synchronous list counters are exact" );
	Expect( metrics.submittedJobs == 3 && metrics.executedJobs == 3,
		"synchronous job counters are exact" );
	system.Shutdown();
}

void ExerciseThreadedDependenciesAndFailure() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = false;
	config.workerThreads = 1;
	config.maxQueuedLists = 4;
	Expect( system.Initialize( config ), "threaded dependency system initializes" );

	std::atomic<int> phase( 0 );
	std::atomic<bool> dependencyFailed( false );
	DependencyData firstData = { &phase, &dependencyFailed, 0, 1 };
	DependencyData secondData = { &phase, &dependencyFailed, 1, 2 };
	std::unique_ptr<idJobList> first = system.CreateJobList( "dependency-root", 1, 0 );
	std::unique_ptr<idJobList> second = system.CreateJobList( "dependency-leaf", 1, 1 );
	Expect( first->AddJob( DependencyJob, &firstData ), "root dependency job added" );
	Expect( SubmitSucceeded( first->Submit() ), "root dependency list submitted" );
	Expect( second->AddDependency( *first ), "threaded dependency added" );
	Expect( second->AddJob( DependencyJob, &secondData ), "leaf dependency job added" );
	Expect( SubmitSucceeded( second->Submit() ), "leaf dependency list submitted" );
	Expect( second->Wait(), "leaf dependency list completes" );
	Expect( first->Wait(), "root dependency list completes" );
	Expect( !dependencyFailed.load( std::memory_order_acquire ) && phase.load() == 2,
		"dependency execution order is enforced" );

	std::atomic<int> shouldNotRun( 0 );
	std::unique_ptr<idJobList> throwing = system.CreateJobList( "throwing", 2, 0 );
	Expect( throwing->AddJob( ThrowingJob, nullptr ), "throwing job added" );
	Expect( throwing->AddJob( IncrementAtomicJob, &shouldNotRun ), "post-failure job added" );
	Expect( SubmitSucceeded( throwing->Submit() ), "throwing list submitted" );
	Expect( !throwing->Wait(), "throwing list reports failure" );
	Expect( throwing->GetStatus() == idJobListStatus::FAILED, "throwing list has failed terminal state" );
	Expect( shouldNotRun.load() == 0, "failure cancels jobs not yet acquired" );
	Expect( throwing->GetMetrics().failedJobs == 1, "failure counter records thrown job" );

	system.Shutdown();
}

void ExerciseParallelWorkers() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = false;
	config.workerThreads = 2;
	config.maxQueuedLists = 2;
	Expect( system.Initialize( config ), "parallel worker system initializes" );
	ParallelGateData gate;
	std::unique_ptr<idJobList> list = system.CreateJobList( "parallel-workers", 2, 0 );
	Expect( list->AddJob( ParallelGateJob, &gate ), "first parallel gate job added" );
	Expect( list->AddJob( ParallelGateJob, &gate ), "second parallel gate job added" );
	Expect( SubmitSucceeded( list->Submit() ), "parallel gate list submitted" );
	{
		std::unique_lock<std::mutex> lock( gate.mutex );
		Expect( gate.condition.wait_for( lock, std::chrono::seconds( 2 ), [&gate]() {
			return gate.started == 2;
		} ), "two worker threads execute one list concurrently" );
		gate.release = true;
	}
	gate.condition.notify_all();
	Expect( list->Wait(), "parallel gate list completes" );
	Expect( list->GetMetrics().executedJobs == 2, "parallel execution metrics are exact" );
	system.Shutdown();
}

void ExerciseBoundedSaturationAndCancellation() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = false;
	config.workerThreads = 1;
	config.maxQueuedLists = 1;
	Expect( system.Initialize( config ), "bounded system initializes" );

	BlockingData blocker;
	std::atomic<int> overflowRuns( 0 );
	std::unique_ptr<idJobList> occupied = system.CreateJobList( "occupied-slot", 1, 0 );
	std::unique_ptr<idJobList> overflow = system.CreateJobList( "overflow-slot", 1, 0 );
	Expect( occupied->AddJob( BlockingJob, &blocker ), "blocking job added" );
	Expect( overflow->AddJob( IncrementAtomicJob, &overflowRuns ), "overflow job added" );
	Expect( SubmitSucceeded( occupied->Submit() ), "blocking list submitted" );
	Expect( WaitForStarted( blocker ), "blocking job starts" );
	Expect( overflow->Submit() == idJobSubmitResult::QUEUE_FULL,
		"saturated list admission fails immediately and explicitly" );
	Expect( overflow->GetStatus() == idJobListStatus::BUILDING,
		"queue-full list remains retryable" );
	ReleaseBlockingJob( blocker );
	Expect( occupied->Wait(), "blocking list drains" );
	Expect( SubmitSucceeded( overflow->Submit() ), "queue-full list can retry after capacity drains" );
	Expect( overflow->Wait() && overflowRuns.load() == 1, "retried list executes once" );
	const idJobSystemMetrics saturationMetrics = system.GetMetrics();
	Expect( saturationMetrics.queueHighWatermark == 1, "queue high-water mark respects configured bound" );
	Expect( saturationMetrics.rejectedSubmissions >= 1, "saturation is observable" );
	system.Shutdown();

	idJobSystem cancellationSystem;
	config.maxQueuedLists = 3;
	Expect( cancellationSystem.Initialize( config ), "cancellation system initializes" );
	BlockingData cancellationBlocker;
	std::atomic<int> cancelledRuns( 0 );
	std::unique_ptr<idJobList> running = cancellationSystem.CreateJobList( "running-cancel", 1, 0 );
	std::unique_ptr<idJobList> pending = cancellationSystem.CreateJobList( "pending-cancel", 1, 0 );
	Expect( running->AddJob( BlockingJob, &cancellationBlocker ), "cooperative running job added" );
	Expect( pending->AddJob( IncrementAtomicJob, &cancelledRuns ), "pending cancellation job added" );
	Expect( SubmitSucceeded( running->Submit() ), "cooperative running list submitted" );
	Expect( WaitForStarted( cancellationBlocker ), "cooperative running job starts" );
	Expect( SubmitSucceeded( pending->Submit() ), "pending cancellation list submitted" );
	Expect( pending->Cancel(), "pending list cancellation accepted" );
	Expect( !pending->Wait() && pending->GetStatus() == idJobListStatus::CANCELLED,
		"pending cancellation reaches terminal state" );
	Expect( cancelledRuns.load() == 0, "cancelled pending job never executes" );
	Expect( running->Cancel(), "running cooperative cancellation accepted" );
	cancellationBlocker.condition.notify_all();
	Expect( !running->Wait() && running->GetStatus() == idJobListStatus::CANCELLED,
		"running cooperative job observes cancellation token" );
	cancellationSystem.Shutdown();
}

void ExercisePriorityAging() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = false;
	config.workerThreads = 1;
	config.maxQueuedLists = 2;
	Expect( system.Initialize( config ), "priority system initializes" );

	BlockingData firstHigh;
	std::atomic<int> highCompleted( 0 );
	std::atomic<int> observedHighCompleted( -1 );
	ObservePriorityData lowData = { &highCompleted, &observedHighCompleted };
	std::unique_ptr<idJobList> high = system.CreateJobList( "high-stream", 40, 0, idJobPriority::HIGH );
	std::unique_ptr<idJobList> low = system.CreateJobList( "low-starvation-guard", 1, 0, idJobPriority::LOW );
	Expect( high->AddJob( BlockingJob, &firstHigh ), "priority blocker added" );
	for ( int index = 1; index < 40; ++index ) {
		Expect( high->AddJob( IncrementAtomicJob, &highCompleted ), "high-priority stream job added" );
	}
	Expect( low->AddJob( ObservePriorityJob, &lowData ), "low-priority observation job added" );
	Expect( SubmitSucceeded( high->Submit() ), "high-priority stream submitted" );
	Expect( WaitForStarted( firstHigh ), "high-priority blocker starts" );
	Expect( SubmitSucceeded( low->Submit() ), "low-priority list submitted while high work remains" );
	ReleaseBlockingJob( firstHigh );
	Expect( low->Wait(), "aged low-priority list completes" );
	Expect( observedHighCompleted.load( std::memory_order_acquire ) >= 0 &&
		observedHighCompleted.load( std::memory_order_acquire ) < 39,
		"priority aging prevents low-list starvation" );
	Expect( high->Wait(), "high-priority stream completes" );
	Expect( system.GetMetrics().priorityPromotions > 0, "priority aging promotion is observable" );
	system.Shutdown();
}

void ExercisePriorityStarvationClass() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = false;
	config.workerThreads = 1;
	config.maxQueuedLists = 11;
	Expect( system.Initialize( config ), "starvation-class system initializes" );

	BlockingData gate;
	std::unique_ptr<idJobList> blocker = system.CreateJobList( "starvation-class-gate", 1, 0 );
	Expect( blocker->AddJob( BlockingJob, &gate ), "starvation-class gate job added" );
	Expect( SubmitSucceeded( blocker->Submit() ), "starvation-class gate submitted" );
	Expect( WaitForStarted( gate ), "starvation-class gate starts" );

	const int highListCount = 9;
	const int jobsPerHighList = 32;
	std::atomic<int> highCompleted( 0 );
	std::atomic<int> observedHighCompleted( -1 );
	ObservePriorityData lowData = { &highCompleted, &observedHighCompleted };
	std::vector<std::unique_ptr<idJobList> > highLists;
	highLists.reserve( highListCount );
	for ( int listIndex = 0; listIndex < highListCount; ++listIndex ) {
		std::unique_ptr<idJobList> high = system.CreateJobList(
			"long-running-high", jobsPerHighList, 0, idJobPriority::HIGH );
		Expect( high != nullptr, "long-running high-priority list created" );
		for ( int jobIndex = 0; jobIndex < jobsPerHighList; ++jobIndex ) {
			Expect( high->AddJob( IncrementAtomicJob, &highCompleted ),
				"long-running high-priority job added" );
		}
		Expect( SubmitSucceeded( high->Submit() ),
			"long-running high-priority list submitted" );
		highLists.push_back( std::move( high ) );
	}

	std::unique_ptr<idJobList> low = system.CreateJobList(
		"starvation-class-low", 1, 0, idJobPriority::LOW );
	Expect( low->AddJob( ObservePriorityJob, &lowData ),
		"starvation-class low-priority job added" );
	Expect( SubmitSucceeded( low->Submit() ),
		"starvation-class low-priority list submitted after high lists" );

	ReleaseBlockingJob( gate );
	Expect( blocker->Wait(), "starvation-class gate drains" );
	Expect( low->Wait(), "starvation-class low-priority list completes" );
	const int observed = observedHighCompleted.load( std::memory_order_acquire );
	Expect( observed >= 0 && observed <= highListCount,
		"oldest-age starvation class runs LOW before nine HIGH lists drain" );
	for ( const std::unique_ptr<idJobList> &high : highLists ) {
		Expect( high->Wait(), "long-running high-priority list drains" );
	}
	Expect( highCompleted.load( std::memory_order_acquire ) == highListCount * jobsPerHighList,
		"all long-running high-priority work completes" );
	Expect( system.GetMetrics().priorityPromotions > 0,
		"starvation-class dispatch is observable as a promotion" );
	system.Shutdown();
}

void ExercisePriorityOrdering() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = false;
	config.workerThreads = 1;
	config.maxQueuedLists = 4;
	Expect( system.Initialize( config ), "priority ordering system initializes" );

	BlockingData gate;
	std::vector<int> order;
	AppendData lowData = { &order, 1 };
	AppendData normalData = { &order, 2 };
	AppendData highData = { &order, 3 };
	std::unique_ptr<idJobList> blocker = system.CreateJobList( "priority-order-blocker", 1, 0 );
	std::unique_ptr<idJobList> low = system.CreateJobList( "priority-order-low", 1, 0, idJobPriority::LOW );
	std::unique_ptr<idJobList> normal = system.CreateJobList( "priority-order-normal", 1, 0, idJobPriority::NORMAL );
	std::unique_ptr<idJobList> high = system.CreateJobList( "priority-order-high", 1, 0, idJobPriority::HIGH );
	Expect( blocker->AddJob( BlockingJob, &gate ), "priority ordering blocker added" );
	Expect( SubmitSucceeded( blocker->Submit() ), "priority ordering blocker submitted" );
	Expect( WaitForStarted( gate ), "priority ordering blocker starts" );
	Expect( low->AddJob( RecordJob, &lowData ) && SubmitSucceeded( low->Submit() ),
		"low-priority ordering list submitted" );
	Expect( normal->AddJob( RecordJob, &normalData ) && SubmitSucceeded( normal->Submit() ),
		"normal-priority ordering list submitted" );
	Expect( high->AddJob( RecordJob, &highData ) && SubmitSucceeded( high->Submit() ),
		"high-priority ordering list submitted" );
	ReleaseBlockingJob( gate );
	Expect( blocker->Wait() && low->Wait() && normal->Wait() && high->Wait(),
		"priority ordering lists complete" );
	Expect( order == std::vector<int>( { 3, 2, 1 } ),
		"initial high/normal/low priority order is enforced" );
	system.Shutdown();
}

void ExerciseShutdownCancellation() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = false;
	config.workerThreads = 1;
	config.maxQueuedLists = 3;
	Expect( system.Initialize( config ), "shutdown system initializes" );
	BlockingData blocker;
	std::atomic<int> pendingRuns( 0 );
	std::unique_ptr<idJobList> running = system.CreateJobList( "shutdown-running", 1, 0 );
	std::unique_ptr<idJobList> pendingA = system.CreateJobList( "shutdown-pending-a", 1, 0 );
	std::unique_ptr<idJobList> pendingB = system.CreateJobList( "shutdown-pending-b", 1, 0 );
	Expect( running->AddJob( BlockingJob, &blocker ), "shutdown cooperative job added" );
	Expect( pendingA->AddJob( IncrementAtomicJob, &pendingRuns ) &&
		pendingB->AddJob( IncrementAtomicJob, &pendingRuns ),
		"multiple shutdown-pending jobs added" );
	Expect( SubmitSucceeded( running->Submit() ), "shutdown cooperative list submitted" );
	Expect( WaitForStarted( blocker ), "shutdown cooperative job starts" );
	Expect( SubmitSucceeded( pendingA->Submit() ) && SubmitSucceeded( pendingB->Submit() ),
		"multiple shutdown-pending lists submitted" );
	system.Shutdown( idJobShutdownMode::CANCEL_PENDING );
	Expect( running->GetStatus() == idJobListStatus::CANCELLED,
		"cancel-pending shutdown reaches a terminal list state" );
	Expect( pendingA->GetStatus() == idJobListStatus::CANCELLED &&
		pendingB->GetStatus() == idJobListStatus::CANCELLED && pendingRuns.load() == 0,
		"allocation-free shutdown iteration cancels every shifted pending list" );
	Expect( !system.IsInitialized(), "shutdown releases the service" );
	const idJobSystemMetrics metrics = system.GetMetrics();
	Expect( metrics.queuedLists == 0 && metrics.runningJobs == 0 && metrics.sleepingWorkers == 0,
		"shutdown joins workers and leaves stable quiescent counters" );
}

void ExerciseSynchronousShutdownJoin() {
	idJobSystem system;
	idJobSystemConfig config;
	config.synchronous = true;
	config.workerThreads = 0;
	config.maxQueuedLists = 2;
	Expect( system.Initialize( config ), "synchronous shutdown system initializes" );
	BlockingData blocker;
	std::unique_ptr<idJobList> running = system.CreateJobList( "synchronous-shutdown-running", 1, 0 );
	Expect( running->AddJob( BlockingJob, &blocker ), "synchronous shutdown job added" );
	std::atomic<int> submitResult( static_cast<int>( idJobSubmitResult::INVALID_STATE ) );
	std::thread submitter( [&running, &submitResult]() {
		submitResult.store( static_cast<int>( running->Submit() ), std::memory_order_release );
	} );
	Expect( WaitForStarted( blocker ), "synchronous inline job starts on submitting caller" );
	system.Shutdown( idJobShutdownMode::CANCEL_PENDING );
	submitter.join();
	Expect( submitResult.load( std::memory_order_acquire ) ==
		static_cast<int>( idJobSubmitResult::EXECUTED_SYNCHRONOUSLY ),
		"accepted synchronous submission returns after shutdown joins it" );
	Expect( running->GetStatus() == idJobListStatus::CANCELLED,
		"synchronous in-flight list is visible to shutdown cancellation" );
	const idJobSystemMetrics metrics = system.GetMetrics();
	Expect( metrics.queuedLists == 0 && metrics.runningJobs == 0,
		"synchronous shutdown leaves the shared quiescence contract clean" );
}

} // namespace

int main() {
	ExerciseConfigurationBounds();
	ExerciseSynchronousMode();
	ExerciseThreadedDependenciesAndFailure();
	ExerciseParallelWorkers();
	ExerciseBoundedSaturationAndCancellation();
	ExercisePriorityOrdering();
	ExercisePriorityAging();
	ExercisePriorityStarvationClass();
	ExerciseShutdownCancellation();
	ExerciseSynchronousShutdownJoin();

	if ( failures != 0 ) {
		std::fprintf( stderr, "ParallelJobSystemTest: %d failure(s)\n", failures );
		return 1;
	}
	std::printf( "ParallelJobSystemTest passed\n" );
	return 0;
}
