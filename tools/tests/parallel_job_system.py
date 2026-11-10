#!/usr/bin/env python3
"""Structural contract checks for the portable bounded job service."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def validate_public_contract() -> None:
    header = read("src/framework/ParallelJobSystem.h")
    for token in (
        "idJobPriority",
        "LOW",
        "NORMAL",
        "HIGH",
        "idJobSubmitResult",
        "QUEUE_FULL",
        "idJobShutdownMode",
        "CANCEL_PENDING",
        "idJobCancellationToken",
        "IsCancellationRequested",
        "maxQueuedLists",
        "maxJobs",
        "maxDependencies",
        "executionTimeMicroseconds",
        "queueHighWatermark",
        "priorityPromotions",
    ):
        require(header, token, "public job-system contract")


def validate_sleepable_bounded_scheduler() -> None:
    source = read("src/framework/ParallelJobSystem.cpp")
    require(source, "std::condition_variable workCondition", "sleepable worker scheduler")
    require(source, "workCondition.wait", "sleepable worker wait")
    require(source, "completionCondition.wait", "sleepable list wait")
    require(source, "activeLists.size() >= config.maxQueuedLists", "bounded active-list admission")
    require(source, "activeLists.reserve( impl->config.maxQueuedLists )", "preallocated active-list storage")
    require(source, "workers.reserve( impl->config.workerThreads )", "preallocated worker storage")
    require(source, "return idJobSubmitResult::QUEUE_FULL", "explicit saturation result")
    require(source, "state->status != idJobListStatus::BUILDING", "retryable saturation state")
    require(source, "MAX_JOBS_PER_LIST", "bounded per-list jobs")
    require(source, "MAX_DEPENDENCIES_PER_LIST", "bounded dependency lists")
    require(source, "candidate->schedulingAge", "starvation-safe priority aging")
    require(source, "JOB_LIST_STARVATION_THRESHOLD", "primary starvation selection class")
    require(source, "candidateIsStarved != selectedIsStarved", "starvation class precedence")
    require(source, "candidate->submitSequence", "deterministic scheduler tie-break")
    reject(source, "std::this_thread::yield", "job scheduler")
    reject(source, "Sys_Sleep", "job scheduler")
    reject(source, "snapshot = activeLists", "allocation-free waiting-list refresh")
    reject(source, "active = impl->activeLists", "allocation-free shutdown cancellation")


def validate_engine_lifecycle_and_policy() -> None:
    common = read("src/framework/Common.cpp")
    for token in (
        'jobs_enable( "jobs_enable", "1"',
        "0 preserves all work by executing job lists synchronously",
        "OPENQ4_JOBS_DETERMINISTIC_DEFAULT = \"1\"",
        'jobs_deterministic( "jobs_deterministic"',
        'jobs_numThreads( "jobs_numThreads", "0"',
        'jobs_queueCapacity( "jobs_queueCapacity", "64"',
        "!jobs_enable.GetBool() || jobs_deterministic.GetBool()",
        "jobSystem.Initialize( jobConfig )",
        "jobSystem.Shutdown( idJobShutdownMode::CANCEL_PENDING )",
        'AddCommand( "jobsStats"',
        'AddCommand( "jobsSelfTest"',
        "Job system initialized: mode=%s",
        "jobsSelfTest PASS v1",
        "jobsSelfTest FAILED v1",
        "jobsShutdown PASS v1 initialized=0 queued=0 running=0",
        "jobsShutdown FAILED v1",
    ):
        require(common, token, "engine job-service lifecycle")


def validate_native_coverage_and_build() -> None:
    native = read("tools/tests/native/ParallelJobSystemTest.cpp")
    for token in (
        "ExerciseSynchronousMode",
        "hard per-list job bound fails closed",
        "hard per-list dependency bound fails closed",
        "reinitialization refreshes bounded scheduler storage",
        "per-list job capacity rejects overflow",
        "self dependency fails closed",
        "unsubmitted dependency fails closed",
        "reverse dependency cycle fails closed",
        "ExerciseThreadedDependenciesAndFailure",
        "two worker threads execute one list concurrently",
        "QUEUE_FULL",
        "queue-full list remains retryable",
        "pending list cancellation accepted",
        "running cooperative job observes cancellation token",
        "initial high/normal/low priority order is enforced",
        "priority aging prevents low-list starvation",
        "oldest-age starvation class runs LOW before nine HIGH lists drain",
        "CANCEL_PENDING",
        "allocation-free shutdown iteration cancels every shifted pending list",
        "ExerciseSynchronousShutdownJoin",
        "synchronous in-flight list is visible to shutdown cancellation",
    ):
        require(native, token, "native job-system coverage")

    meson = read("meson.build")
    require(meson, "'openq4-job-system-test'", "native job-system target")
    require(meson, "'openq4-job-system'", "native job-system Meson test")
    require(meson, "tools/tests/native/ParallelJobSystemTest.cpp", "native job-system source wiring")
    require(meson, "src/framework/ParallelJobSystem.cpp", "production job-system source wiring")
    validator = read("tools/validation/openq4_validate.py")
    require(validator, "parallel_job_system.py", "default validation runner")
    for workflow_path in (
        ".github/workflows/push-verification.yml",
        ".github/workflows/commit-validation.yml",
    ):
        workflow = read(workflow_path)
        if workflow.count("tools/tests/parallel_job_system.py") < 2:
            raise AssertionError(
                f"parallel_job_system.py is not compiled and executed by {workflow_path}"
            )


def validate_documentation() -> None:
    roadmap = read("docs/dev/archive/2026-10-18/idtech5-modernization-roadmap.md")
    matrix = read("docs/dev/engine-capability-matrix.md")
    release = read("docs/dev/release-completion.md")
    require(roadmap, "portable bounded job service", "modernization roadmap")
    require(matrix, "Background job system for general engine work", "capability matrix")
    require(matrix, "ParallelJobSystem.cpp", "capability-matrix implementation evidence")
    require(release, "portable job service", "release completion notes")


def main() -> None:
    validate_public_contract()
    validate_sleepable_bounded_scheduler()
    validate_engine_lifecycle_and_policy()
    validate_native_coverage_and_build()
    validate_documentation()
    print("parallel_job_system: ok")


if __name__ == "__main__":
    main()
