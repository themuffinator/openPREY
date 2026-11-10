/*
===========================================================================

openQ4 GPL Source Code
Copyright (C) 2026 the openQ4 contributors.

This file is part of the openQ4 Source Code. See docs/legal for details.

===========================================================================
*/

#ifndef __REMOTECVARPOLICY_H__
#define __REMOTECVARPOLICY_H__

// This small, dependency-free policy is shared with the native safety test.
// The caller supplies the engine's concrete CVar flag mask, keeping this
// header independent of the large CVarSystem interface and game-module ABI.
namespace idRemoteCVarPolicy {

inline bool IsSingleAllowedAuthority( int requiredFlag, int allowedRemoteFlags ) {
	return requiredFlag != 0 &&
		( requiredFlag & allowedRemoteFlags ) == requiredFlag &&
		( requiredFlag & ( requiredFlag - 1 ) ) == 0;
}

inline bool CanApply( int variableFlags, int requiredFlag, int allowedRemoteFlags,
		int forbiddenFlags ) {
	return IsSingleAllowedAuthority( requiredFlag, allowedRemoteFlags ) &&
		( variableFlags & requiredFlag ) != 0 &&
		( variableFlags & forbiddenFlags ) == 0;
}

} // namespace idRemoteCVarPolicy

#endif /* !__REMOTECVARPOLICY_H__ */
