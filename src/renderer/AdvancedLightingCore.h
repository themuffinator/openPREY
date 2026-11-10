// Copyright (C) 2026 DarkMatter Productions
//


#ifndef __ADVANCED_LIGHTING_CORE_H__
#define __ADVANCED_LIGHTING_CORE_H__

#include <cmath>
#include <cstdint>

/*
===============================================================================

	Device-independent ownership rules for Milestone F lighting records.

	The GL clustered implementation supplies the storage and raster work, but the
	transaction, generation, volume, and deterministic probe-selection rules stay
	free of renderer and graphics-API types.  That keeps malformed, overflow, and
	stale-generation behaviour testable on every build host.

===============================================================================
*/

const int ADVANCED_LIGHTING_PROBES_PER_CLUSTER = 2;

typedef enum advancedLightingRecordKind_e {
	ADVANCED_LIGHTING_RECORD_PROBE = 0,
	ADVANCED_LIGHTING_RECORD_DECAL
} advancedLightingRecordKind_t;

typedef enum advancedLightingReject_e {
	ADVANCED_LIGHTING_REJECT_NONE = 0,
	ADVANCED_LIGHTING_REJECT_DISABLED,
	ADVANCED_LIGHTING_REJECT_INVALID_GENERATION,
	ADVANCED_LIGHTING_REJECT_INVALID_IDENTITY,
	ADVANCED_LIGHTING_REJECT_INVALID_VOLUME,
	ADVANCED_LIGHTING_REJECT_INVALID_KIND,
	ADVANCED_LIGHTING_REJECT_CAPACITY,
	ADVANCED_LIGHTING_REJECT_REFERENCE_CAPACITY,
	ADVANCED_LIGHTING_REJECT_RESOURCES
} advancedLightingReject_t;

typedef struct advancedLightingVolume_s {
	float		origin[3];
	float		extents[3];
	std::uint32_t	generation;
	int		stableId;
} advancedLightingVolume_t;

typedef struct advancedLightingTransaction_s {
	bool		enabled;
	bool		sealed;
	bool		complete;
	std::uint32_t	generation;
	int		probeCapacity;
	int		decalCapacity;
	int		referenceCapacity;
	int		probeCount;
	int		decalCount;
	int		probeReferences;
	int		decalReferences;
	int		rejectedRecords;
	advancedLightingReject_t firstReject;
} advancedLightingTransaction_t;

typedef struct advancedLightingProbeCandidate_s {
	int		probeIndex;
	int		priority;
	int		stableId;
	float		weight;
} advancedLightingProbeCandidate_t;

inline bool AdvancedLightingCore_Finite( float value ) {
	return std::isfinite( value );
}

inline bool AdvancedLightingCore_ValidateVolume(
		const advancedLightingVolume_t &volume, std::uint32_t generation,
		advancedLightingReject_t &reject ) {
	if ( volume.generation == 0 || volume.generation != generation ) {
		reject = ADVANCED_LIGHTING_REJECT_INVALID_GENERATION;
		return false;
	}
	if ( volume.stableId < 0 ) {
		reject = ADVANCED_LIGHTING_REJECT_INVALID_IDENTITY;
		return false;
	}
	for ( int axis = 0; axis < 3; ++axis ) {
		if ( !AdvancedLightingCore_Finite( volume.origin[axis] )
				|| !AdvancedLightingCore_Finite( volume.extents[axis] )
				|| volume.extents[axis] <= 0.0f ) {
			reject = ADVANCED_LIGHTING_REJECT_INVALID_VOLUME;
			return false;
		}
	}
	reject = ADVANCED_LIGHTING_REJECT_NONE;
	return true;
}

inline void AdvancedLightingCore_Begin( advancedLightingTransaction_t &state,
		bool enabled, std::uint32_t generation, int probeCapacity,
		int decalCapacity, int referenceCapacity ) {
	state.enabled = enabled;
	state.sealed = false;
	state.complete = false;
	state.generation = generation;
	state.probeCapacity = probeCapacity > 0 ? probeCapacity : 0;
	state.decalCapacity = decalCapacity > 0 ? decalCapacity : 0;
	state.referenceCapacity = referenceCapacity > 0 ? referenceCapacity : 0;
	state.probeCount = 0;
	state.decalCount = 0;
	state.probeReferences = 0;
	state.decalReferences = 0;
	state.rejectedRecords = 0;
	state.firstReject = enabled
		? ADVANCED_LIGHTING_REJECT_NONE
		: ADVANCED_LIGHTING_REJECT_DISABLED;
}

inline void AdvancedLightingCore_Reject( advancedLightingTransaction_t &state,
		advancedLightingReject_t reject ) {
	state.rejectedRecords++;
	if ( state.firstReject == ADVANCED_LIGHTING_REJECT_NONE ) {
		state.firstReject = reject;
	}
}

inline bool AdvancedLightingCore_Admit( advancedLightingTransaction_t &state,
		advancedLightingRecordKind_t kind,
		const advancedLightingVolume_t &volume ) {
	if ( !state.enabled || state.sealed ) {
		AdvancedLightingCore_Reject( state, ADVANCED_LIGHTING_REJECT_DISABLED );
		return false;
	}
	if ( kind != ADVANCED_LIGHTING_RECORD_PROBE
			&& kind != ADVANCED_LIGHTING_RECORD_DECAL ) {
		AdvancedLightingCore_Reject( state, ADVANCED_LIGHTING_REJECT_INVALID_KIND );
		return false;
	}
	advancedLightingReject_t reject = ADVANCED_LIGHTING_REJECT_NONE;
	if ( !AdvancedLightingCore_ValidateVolume( volume, state.generation, reject ) ) {
		AdvancedLightingCore_Reject( state, reject );
		return false;
	}
	int *count = kind == ADVANCED_LIGHTING_RECORD_PROBE
		? &state.probeCount : &state.decalCount;
	const int capacity = kind == ADVANCED_LIGHTING_RECORD_PROBE
		? state.probeCapacity : state.decalCapacity;
	if ( *count >= capacity ) {
		AdvancedLightingCore_Reject( state, ADVANCED_LIGHTING_REJECT_CAPACITY );
		return false;
	}
	( *count )++;
	return true;
}

inline bool AdvancedLightingCore_AddReference(
		advancedLightingTransaction_t &state,
		advancedLightingRecordKind_t kind ) {
	if ( !state.enabled || state.sealed ) {
		AdvancedLightingCore_Reject( state, ADVANCED_LIGHTING_REJECT_DISABLED );
		return false;
	}
	if ( kind != ADVANCED_LIGHTING_RECORD_PROBE
			&& kind != ADVANCED_LIGHTING_RECORD_DECAL ) {
		AdvancedLightingCore_Reject( state, ADVANCED_LIGHTING_REJECT_INVALID_KIND );
		return false;
	}
	const int total = state.probeReferences + state.decalReferences;
	if ( total >= state.referenceCapacity ) {
		AdvancedLightingCore_Reject(
			state, ADVANCED_LIGHTING_REJECT_REFERENCE_CAPACITY );
		return false;
	}
	if ( kind == ADVANCED_LIGHTING_RECORD_PROBE ) {
		state.probeReferences++;
	} else {
		state.decalReferences++;
	}
	return true;
}

inline bool AdvancedLightingCore_Seal( advancedLightingTransaction_t &state,
		bool resourcesReady ) {
	state.sealed = true;
	if ( !resourcesReady && state.firstReject == ADVANCED_LIGHTING_REJECT_NONE ) {
		state.firstReject = ADVANCED_LIGHTING_REJECT_RESOURCES;
	}
	state.complete = state.enabled && resourcesReady
		&& state.firstReject == ADVANCED_LIGHTING_REJECT_NONE;
	return state.complete;
}

inline bool AdvancedLightingCore_ProbeBefore(
		const advancedLightingProbeCandidate_t &a,
		const advancedLightingProbeCandidate_t &b ) {
	if ( a.priority != b.priority ) {
		return a.priority > b.priority;
	}
	if ( a.weight != b.weight ) {
		return a.weight > b.weight;
	}
	if ( a.stableId != b.stableId ) {
		return a.stableId < b.stableId;
	}
	return a.probeIndex < b.probeIndex;
}

inline void AdvancedLightingCore_SelectProbe(
		advancedLightingProbeCandidate_t selected[ADVANCED_LIGHTING_PROBES_PER_CLUSTER],
		const advancedLightingProbeCandidate_t &candidate ) {
	if ( candidate.probeIndex < 0 || candidate.stableId < 0
			|| !AdvancedLightingCore_Finite( candidate.weight )
			|| candidate.weight <= 0.0f ) {
		return;
	}
	for ( int index = 0; index < ADVANCED_LIGHTING_PROBES_PER_CLUSTER; ++index ) {
		if ( selected[index].probeIndex == candidate.probeIndex ) {
			if ( AdvancedLightingCore_ProbeBefore( candidate, selected[index] ) ) {
				selected[index] = candidate;
			}
			return;
		}
	}
	for ( int index = 0; index < ADVANCED_LIGHTING_PROBES_PER_CLUSTER; ++index ) {
		if ( selected[index].probeIndex < 0
				|| AdvancedLightingCore_ProbeBefore( candidate, selected[index] ) ) {
			for ( int move = ADVANCED_LIGHTING_PROBES_PER_CLUSTER - 1;
					move > index; --move ) {
				selected[move] = selected[move - 1];
			}
			selected[index] = candidate;
			return;
		}
	}
}

inline float AdvancedLightingCore_ProbeWeight(
		const advancedLightingVolume_t &volume, const float position[3],
		float blendDistance ) {
	if ( !AdvancedLightingCore_Finite( blendDistance ) || blendDistance <= 0.0f ) {
		blendDistance = 0.001f;
	}
	float edgeDistance = volume.extents[0];
	for ( int axis = 0; axis < 3; ++axis ) {
		if ( !AdvancedLightingCore_Finite( position[axis] ) ) {
			return 0.0f;
		}
		const float normalized = std::fabs( position[axis] - volume.origin[axis] )
			/ volume.extents[axis];
		if ( normalized >= 1.0f ) {
			return 0.0f;
		}
		const float axisEdgeDistance = ( 1.0f - normalized ) * volume.extents[axis];
		edgeDistance = axis == 0 || axisEdgeDistance < edgeDistance
			? axisEdgeDistance : edgeDistance;
	}
	const float weight = edgeDistance / blendDistance;
	return weight < 0.0f ? 0.0f : ( weight > 1.0f ? 1.0f : weight );
}

inline float AdvancedLightingCore_SphericalProbeWeight(
		const float origin[3], float radius, const float position[3],
		float blendDistance ) {
	if ( !AdvancedLightingCore_Finite( radius ) || radius <= 0.0f
			|| !AdvancedLightingCore_Finite( blendDistance )
			|| blendDistance <= 0.0f ) {
		return 0.0f;
	}
	float distanceSquared = 0.0f;
	for ( int axis = 0; axis < 3; ++axis ) {
		if ( !AdvancedLightingCore_Finite( origin[axis] )
				|| !AdvancedLightingCore_Finite( position[axis] ) ) {
			return 0.0f;
		}
		const float delta = position[axis] - origin[axis];
		distanceSquared += delta * delta;
	}
	if ( !AdvancedLightingCore_Finite( distanceSquared )
			|| distanceSquared >= radius * radius ) {
		return 0.0f;
	}
	const float distance = std::sqrt( distanceSquared );
	const float weight = ( radius - distance ) / blendDistance;
	return weight < 0.0f ? 0.0f : ( weight > 1.0f ? 1.0f : weight );
}

#endif /* !__ADVANCED_LIGHTING_CORE_H__ */
