// Copyright (C) 2026 DarkMatter Productions
//

#include "tr_local.h"
#include "ClassicSubviewDomain.h"
#include "ClassicCinematicPostDomain.h"

#include <cstring>

static_assert( static_cast<int>( CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL )
		== static_cast<int>( CLASSIC_CINEMATIC_POST_BACKEND_GL ),
	"classic subview and cinematic/post GL backend ordinals must match" );
static_assert( static_cast<int>( CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN )
		== static_cast<int>( CLASSIC_CINEMATIC_POST_BACKEND_VULKAN ),
	"classic subview and cinematic/post Vulkan backend ordinals must match" );
static_assert( static_cast<int>( CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT )
		== static_cast<int>( CLASSIC_CINEMATIC_POST_BACKEND_COUNT ),
	"classic subview and cinematic/post backend counts must match" );

namespace {

const std::uint64_t HASH_OFFSET = 1469598103934665603ull;
const std::uint64_t HASH_PRIME = 1099511628211ull;

typedef struct classicSubviewDomainState_s {
	classicSubviewDomainView_t views[CLASSIC_SUBVIEW_DOMAIN_MAX_VIEWS];
	classicSubviewDomainStats_t stats;
	int viewCount;
} classicSubviewDomainState_t;

classicSubviewDomainState_t domain;

static void HashByte( std::uint64_t &hash, unsigned int value ) {
	hash ^= value & 0xffu;
	hash *= HASH_PRIME;
}

static void HashU32( std::uint64_t &hash, std::uint32_t value ) {
	for ( int i = 0; i < 4; ++i ) {
		HashByte( hash, value >> ( i * 8 ) );
	}
}

static void HashInt( std::uint64_t &hash, int value ) {
	HashU32( hash, static_cast<std::uint32_t>( value ) );
}

static void HashBool( std::uint64_t &hash, bool value ) {
	HashByte( hash, value ? 1u : 0u );
}

static void HashFloat( std::uint64_t &hash, float value ) {
	std::uint32_t bits = 0;
	std::memcpy( &bits, &value, sizeof( bits ) );
	HashU32( hash, bits );
}

static bool SameFloat( float a, float b ) {
	std::uint32_t aBits = 0;
	std::uint32_t bBits = 0;
	std::memcpy( &aBits, &a, sizeof( aBits ) );
	std::memcpy( &bBits, &b, sizeof( bBits ) );
	return aBits == bBits;
}

static void HashVec3( std::uint64_t &hash, const idVec3 &value ) {
	for ( int component = 0; component < 3; ++component ) {
		HashFloat( hash, value[component] );
	}
}

static bool SameVec3( const idVec3 &a, const idVec3 &b ) {
	for ( int component = 0; component < 3; ++component ) {
		if ( !SameFloat( a[component], b[component] ) ) {
			return false;
		}
	}
	return true;
}

static void HashPlane( std::uint64_t &hash, const idPlane &value ) {
	for ( int component = 0; component < 4; ++component ) {
		HashFloat( hash, value[component] );
	}
}

static bool SamePlane( const idPlane &a, const idPlane &b ) {
	for ( int component = 0; component < 4; ++component ) {
		if ( !SameFloat( a[component], b[component] ) ) {
			return false;
		}
	}
	return true;
}

static void HashScreenRect( std::uint64_t &hash, const idScreenRect &value ) {
	HashInt( hash, value.x1 );
	HashInt( hash, value.y1 );
	HashInt( hash, value.x2 );
	HashInt( hash, value.y2 );
}

static bool SameScreenRect( const idScreenRect &a, const idScreenRect &b ) {
	return a.x1 == b.x1 && a.y1 == b.y1 && a.x2 == b.x2 && a.y2 == b.y2;
}

static void InitView( classicSubviewDomainView_t &view,
		const viewDef_t *viewDef, int scenePacketIndex ) {
	std::memset( &view, 0, sizeof( view ) );
	view.viewDef = viewDef;
	view.scenePacketIndex = scenePacketIndex;
	view.parentScenePacketIndex = -1;
	view.parentViewIndex = -1;
	view.rootViewIndex = -1;
	view.nestingDepth = 0;
	view.subtreeViewCount = 1;
	view.capturePacketIndex = -1;
	view.firstPassPacket = -1;
	view.firstDrawPacket = -1;
	view.captureTextureType = TT_DISABLED;
	view.captureTextureFormat = FMT_NONE;
	view.captureType = CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE;
	view.failure = CLASSIC_SUBVIEW_DOMAIN_FAILURE_NONE;
}

static void CaptureViewSemantics( classicSubviewDomainView_t &view,
		const viewDef_t &viewDef ) {
	view.semanticViewID = viewDef.renderView.viewID;
	view.semanticRenderTime = viewDef.renderView.time;
	view.semanticFloatTime = viewDef.floatTime;
	view.semanticViewOrigin = viewDef.renderView.vieworg;
	view.semanticViewAxis = viewDef.renderView.viewaxis;
	view.semanticInitialViewAreaOrigin = viewDef.initialViewAreaOrigin;
	view.semanticViewport = viewDef.viewport;
	view.semanticScissor = viewDef.scissor;
	view.semanticClipPlaneCount = viewDef.numClipPlanes;
	view.semanticIsMirror = viewDef.isMirror;
	view.semanticIsXraySubview = viewDef.isXraySubview;
	for ( int plane = 0; plane < MAX_CLIP_PLANES; ++plane ) {
		view.semanticClipPlanes[plane] = viewDef.clipPlanes[plane];
	}
}

static bool ViewSemanticsMatch( const classicSubviewDomainView_t &view,
		const viewDef_t &viewDef ) {
	if ( view.semanticViewID != viewDef.renderView.viewID
			|| view.semanticRenderTime != viewDef.renderView.time
			|| !SameFloat( view.semanticFloatTime, viewDef.floatTime )
			|| !SameVec3( view.semanticViewOrigin, viewDef.renderView.vieworg )
			|| !SameVec3( view.semanticInitialViewAreaOrigin,
				viewDef.initialViewAreaOrigin )
			|| !SameScreenRect( view.semanticViewport, viewDef.viewport )
			|| !SameScreenRect( view.semanticScissor, viewDef.scissor )
			|| view.semanticClipPlaneCount != viewDef.numClipPlanes
			|| view.semanticIsMirror != viewDef.isMirror
			|| view.semanticIsXraySubview != viewDef.isXraySubview ) {
		return false;
	}
	for ( int axis = 0; axis < 3; ++axis ) {
		if ( !SameVec3( view.semanticViewAxis[axis],
				viewDef.renderView.viewaxis[axis] ) ) {
			return false;
		}
	}
	for ( int plane = 0; plane < MAX_CLIP_PLANES; ++plane ) {
		if ( !SamePlane( view.semanticClipPlanes[plane], viewDef.clipPlanes[plane] ) ) {
			return false;
		}
	}
	return true;
}

static int ViewIndex( const classicSubviewDomainView_t *view ) {
	if ( view == NULL || view < domain.views
			|| view >= domain.views + domain.viewCount ) {
		return -1;
	}
	return static_cast<int>( view - domain.views );
}

static classicSubviewDomainView_t *FindMutableView( const viewDef_t *viewDef ) {
	for ( int i = 0; i < domain.viewCount; ++i ) {
		if ( domain.views[i].viewDef == viewDef ) {
			return &domain.views[i];
		}
	}
	return NULL;
}

static int FindViewIndex( const viewDef_t *viewDef ) {
	return ViewIndex( FindMutableView( viewDef ) );
}

static bool FailView( classicSubviewDomainView_t &view,
		classicSubviewDomainFailure_t failure, int detail ) {
	if ( !view.ready && view.failure != CLASSIC_SUBVIEW_DOMAIN_FAILURE_NONE ) {
		return false;
	}
	view.ready = false;
	view.failure = failure;
	view.failureDetail = detail;
	view.hash = 0;
	domain.stats.fallbackViews++;
	if ( failure >= CLASSIC_SUBVIEW_DOMAIN_FAILURE_NONE
			&& failure < CLASSIC_SUBVIEW_DOMAIN_FAILURE_COUNT ) {
		domain.stats.failureCounts[failure]++;
	}
	return false;
}

static int FindScenePacket( const idScenePacketFrame &packetFrame,
		const viewDef_t *viewDef ) {
	for ( int i = 0; i < packetFrame.NumScenes(); ++i ) {
		if ( packetFrame.Scene(i).viewDef == viewDef ) {
			return i;
		}
	}
	return -1;
}

static bool ParentContainsSurface( const viewDef_t *parent,
		const drawSurf_t *surface ) {
	if ( parent == NULL || surface == NULL || parent->drawSurfs == NULL
			|| parent->numDrawSurfs <= 0 ) {
		return false;
	}
	for ( int i = 0; i < parent->numDrawSurfs; ++i ) {
		if ( parent->drawSurfs[i] == surface ) {
			return true;
		}
	}
	return false;
}

static bool FindDirectKind( const drawSurf_t *surface,
		classicSubviewDomainKind_t &kind ) {
	kind = CLASSIC_SUBVIEW_DOMAIN_KIND_NONE;
	if ( surface == NULL || surface->material == NULL
			|| !surface->material->HasSubview()
			|| surface->material->GetSort() != SS_SUBVIEW ) {
		return false;
	}
	// SS_SUBVIEW is the classic direct mirror path: it publishes its child view
	// straight into the parent target and deliberately has no copy command.
	kind = CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR;
	return true;
}

static bool FindCaptureKind( const drawSurf_t *surface,
		const idImage *captureImage, classicSubviewDomainKind_t &kind ) {
	kind = CLASSIC_SUBVIEW_DOMAIN_KIND_NONE;
	if ( surface == NULL || surface->material == NULL || captureImage == NULL
			|| !surface->material->HasSubview() ) {
		return false;
	}
	int matchingStages = 0;
	const int stageCount = surface->material->GetNumStages();
	for ( int i = 0; i < stageCount; ++i ) {
		const shaderStage_t *stage = surface->material->GetStage(i);
		if ( stage == NULL ) {
			return false;
		}
		classicSubviewDomainKind_t stageKind = CLASSIC_SUBVIEW_DOMAIN_KIND_NONE;
		switch ( stage->texture.dynamic ) {
		case DI_REMOTE_RENDER:
			stageKind = CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA;
			break;
		case DI_MIRROR_RENDER:
			stageKind = CLASSIC_SUBVIEW_DOMAIN_KIND_MIRROR;
			break;
		case DI_REFLECTION_RENDER:
			stageKind = CLASSIC_SUBVIEW_DOMAIN_KIND_REFLECTION;
			break;
		case DI_REFRACTION_RENDER:
			stageKind = CLASSIC_SUBVIEW_DOMAIN_KIND_REFRACTION;
			break;
		case DI_XRAY_RENDER:
			stageKind = CLASSIC_SUBVIEW_DOMAIN_KIND_XRAY;
			break;
		case DI_STATIC:
			continue;
		default:
			// Other dynamic images are not subview capture producers.
			return false;
		}
		if ( stage->texture.image != captureImage || matchingStages != 0 ) {
			return false;
		}
		kind = stageKind;
		matchingStages++;
	}
	return matchingStages == 1;
}

static bool ClassifyCaptureTargetOptions( textureType_t textureType,
		textureFormat_t textureFormat, int cubeFace, bool copyDepth,
		classicSubviewDomainCaptureType_t &type ) {
	// The packet must retain both transfer aspect and layer identity exactly.
	type = CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE;
	const bool isCube = textureType == TT_CUBIC;
	if ( ( textureType != TT_2D && !isCube )
			|| ( isCube && ( cubeFace < 0 || cubeFace >= 6 ) )
			|| ( !isCube && cubeFace != 0 ) ) {
		return false;
	}
	const bool isDepth = textureFormat == FMT_DEPTH
		|| textureFormat == FMT_DEPTH_STENCIL;
	if ( copyDepth != isDepth ) {
		return false;
	}
	if ( copyDepth ) {
		type = isCube ? CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP
			: CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_2D;
	} else {
		type = isCube ? CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_CUBEMAP
			: CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_2D;
	}
	return true;
}

static bool ClassifyCaptureTarget( const sceneSubviewCapture_t &capture,
		classicSubviewDomainCaptureType_t &type ) {
	if ( capture.image == NULL || capture.width <= 0 || capture.height <= 0 ) {
		type = CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE;
		return false;
	}
	const idImageOpts &opts = capture.image->GetOpts();
	return ClassifyCaptureTargetOptions( opts.textureType, opts.format,
		capture.cubeFace, capture.copyDepth, type );
}

static bool HasSupportedSpecialSemantics( const viewDef_t &viewDef,
		classicSubviewDomainKind_t kind ) {
	if ( viewDef.numClipPlanes < 0 || viewDef.numClipPlanes > MAX_CLIP_PLANES ) {
		return false;
	}
	switch ( kind ) {
	case CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR:
	case CLASSIC_SUBVIEW_DOMAIN_KIND_MIRROR:
	case CLASSIC_SUBVIEW_DOMAIN_KIND_REFLECTION:
		// The final cull parity may be false for a nested mirror, so the
		// captured isMirror bit is authoritative rather than an eligibility
		// requirement. The single portal plane is the required camera boundary.
		return !viewDef.isXraySubview && viewDef.numClipPlanes == 1;
	case CLASSIC_SUBVIEW_DOMAIN_KIND_XRAY:
		return viewDef.isXraySubview && viewDef.numClipPlanes == 0;
	case CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA:
	case CLASSIC_SUBVIEW_DOMAIN_KIND_REFRACTION:
		return !viewDef.isMirror && !viewDef.isXraySubview
			&& viewDef.numClipPlanes == 0;
	case CLASSIC_SUBVIEW_DOMAIN_KIND_NONE:
	case CLASSIC_SUBVIEW_DOMAIN_KIND_COUNT:
	default:
		return false;
	}
}

static std::uint64_t HashView( const classicSubviewDomainView_t &view ) {
	std::uint64_t hash = HASH_OFFSET;
	HashInt( hash, view.scenePacketIndex );
	HashInt( hash, view.parentScenePacketIndex );
	HashInt( hash, view.parentViewIndex );
	HashInt( hash, view.rootViewIndex );
	HashInt( hash, view.nestingDepth );
	HashInt( hash, view.subtreeViewCount );
	HashInt( hash, view.capturePacketIndex );
	HashInt( hash, view.firstPassPacket );
	HashInt( hash, view.passPacketCount );
	HashInt( hash, view.firstDrawPacket );
	HashInt( hash, view.drawPacketCount );
	HashInt( hash, view.captureX );
	HashInt( hash, view.captureY );
	HashInt( hash, view.captureWidth );
	HashInt( hash, view.captureHeight );
	HashInt( hash, view.captureCubeFace );
	HashInt( hash, view.captureTextureType );
	HashInt( hash, view.captureTextureFormat );
	HashBool( hash, view.captureCopyDepth );
	HashInt( hash, view.kind );
	HashInt( hash, view.captureType );
	HashInt( hash, view.semanticViewID );
	HashInt( hash, view.semanticRenderTime );
	HashFloat( hash, view.semanticFloatTime );
	HashVec3( hash, view.semanticViewOrigin );
	for ( int axis = 0; axis < 3; ++axis ) {
		HashVec3( hash, view.semanticViewAxis[axis] );
	}
	HashVec3( hash, view.semanticInitialViewAreaOrigin );
	HashScreenRect( hash, view.semanticViewport );
	HashScreenRect( hash, view.semanticScissor );
	HashInt( hash, view.semanticClipPlaneCount );
	HashBool( hash, view.semanticIsMirror );
	HashBool( hash, view.semanticIsXraySubview );
	for ( int plane = 0; plane < MAX_CLIP_PLANES; ++plane ) {
		HashPlane( hash, view.semanticClipPlanes[plane] );
	}
	if ( view.viewDef != NULL ) {
		HashInt( hash, view.viewDef->viewport.x1 );
		HashInt( hash, view.viewDef->viewport.y1 );
		HashInt( hash, view.viewDef->viewport.x2 );
		HashInt( hash, view.viewDef->viewport.y2 );
		HashInt( hash, view.viewDef->scissor.x1 );
		HashInt( hash, view.viewDef->scissor.y1 );
		HashInt( hash, view.viewDef->scissor.x2 );
		HashInt( hash, view.viewDef->scissor.y2 );
		HashBool( hash, view.viewDef->isSubview );
		HashBool( hash, view.viewDef->isMirror );
		HashBool( hash, view.viewDef->isXraySubview );
	}
	return hash;
}

static bool PrepareView( const idScenePacketFrame &packetFrame,
		const scenePacket_t &scene, classicSubviewDomainView_t &view ) {
	const viewDef_t *viewDef = view.viewDef;
	view.parentViewDef = viewDef != NULL ? viewDef->superView : NULL;
	view.parentSurface = viewDef != NULL ? viewDef->subviewSurface : NULL;
	if ( viewDef == NULL || scene.packetCategory != SCENE_PACKET_CATEGORY_SUBVIEW
			|| !viewDef->isSubview || viewDef->viewEntitys == NULL
			|| viewDef->renderWorld == NULL || viewDef->isEditor
			|| viewDef->renderView.viewID < 0
			|| viewDef->renderView.globalMaterial != NULL
			|| viewDef->superView == NULL || viewDef->subviewSurface == NULL ) {
		return FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_VIEW, 0 );
	}
	view.parentScenePacketIndex = FindScenePacket( packetFrame, view.parentViewDef );
	if ( view.parentScenePacketIndex < 0 ) {
		return FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_PARENT_SCENE, 0 );
	}
	if ( !ParentContainsSurface( view.parentViewDef, view.parentSurface ) ) {
		return FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_PARENT_SURFACE, 0 );
	}
	classicSubviewDomainKind_t directKind = CLASSIC_SUBVIEW_DOMAIN_KIND_NONE;
	const bool isDirect = FindDirectKind( view.parentSurface, directKind );
	int captureIndex = -1;
	for ( int i = 0; i < packetFrame.NumSubviewCaptures(); ++i ) {
		const sceneSubviewCapture_t &candidate = packetFrame.SubviewCapture(i);
		if ( candidate.viewScenePacketIndex != view.scenePacketIndex ) {
			continue;
		}
		if ( captureIndex >= 0 ) {
			return FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_DUPLICATE_CAPTURE, i );
		}
		captureIndex = i;
	}
	if ( isDirect ) {
		if ( captureIndex >= 0 ) {
			return FailView( view,
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNEXPECTED_CAPTURE, captureIndex );
		}
		view.kind = directKind;
	} else {
		if ( captureIndex < 0 ) {
			return FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_CAPTURE, 0 );
		}
		const sceneSubviewCapture_t &capture = packetFrame.SubviewCapture(captureIndex);
		if ( capture.viewDef != viewDef || capture.image == NULL
				|| capture.width <= 0 || capture.height <= 0 ) {
			return FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_INVALID_CAPTURE,
				captureIndex );
		}
		if ( !ClassifyCaptureTarget( capture, view.captureType ) ) {
			return FailView( view,
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_CAPTURE_TARGET,
				captureIndex );
		}
		view.captureImage = capture.image;
		view.capturePacketIndex = captureIndex;
		view.captureX = capture.x;
		view.captureY = capture.y;
		view.captureWidth = capture.width;
		view.captureHeight = capture.height;
		view.captureCubeFace = capture.cubeFace;
		view.captureTextureType = capture.image->GetOpts().textureType;
		view.captureTextureFormat = capture.image->GetOpts().format;
		view.captureCopyDepth = capture.copyDepth;
		if ( capture.x != viewDef->viewport.x1 || capture.y != viewDef->viewport.y1
				|| capture.width != viewDef->viewport.x2 - viewDef->viewport.x1 + 1
				|| capture.height != viewDef->viewport.y2 - viewDef->viewport.y1 + 1 ) {
			return FailView( view,
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_VIEWPORT_MISMATCH, captureIndex );
		}
		if ( !FindCaptureKind( view.parentSurface, capture.image, view.kind ) ) {
			return FailView( view,
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_SURFACE_MISMATCH, captureIndex );
		}
	}
	if ( !HasSupportedSpecialSemantics( *viewDef, view.kind ) ) {
		return FailView( view,
			CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_SPECIAL_SEMANTICS,
			static_cast<int>( view.kind ) );
	}
	CaptureViewSemantics( view, *viewDef );
	view.firstPassPacket = scene.firstPassPacket;
	view.passPacketCount = scene.passPacketCount;
	view.firstDrawPacket = scene.firstDrawPacket;
	view.drawPacketCount = scene.drawPacketCount;
	view.ready = true;
	return true;
}

static void ResolveNestedOwnership( void ) {
	// R_RenderView emits descendants before their parent command. Recover that
	// order from the immutable scene packet indices and make every nested chain
	// one transaction. A child must never be admitted independently merely
	// because its local camera and capture edge happened to validate.
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		classicSubviewDomainView_t &view = domain.views[viewIndex];
		view.parentViewIndex = -1;
		view.rootViewIndex = viewIndex;
		view.nestingDepth = 0;
		view.subtreeViewCount = 1;
		if ( view.parentViewDef == NULL || !view.parentViewDef->isSubview ) {
			continue;
		}
		const int parentIndex = FindViewIndex( view.parentViewDef );
		view.parentViewIndex = parentIndex;
		if ( parentIndex < 0 ) {
			FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_NESTED_PARENT,
				view.parentScenePacketIndex );
			continue;
		}
		const classicSubviewDomainView_t &parent = domain.views[parentIndex];
		if ( parent.scenePacketIndex != view.parentScenePacketIndex
				|| view.scenePacketIndex >= parent.scenePacketIndex ) {
			FailView( view, CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_COMMAND_ORDER,
				parent.scenePacketIndex );
		}
	}

	// Resolve the root/depth only across strict depth-first links. The packet
	// ordering check above bounds this walk by the fixed view arena and rejects
	// malformed cycles before a backend can consume any record.
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		classicSubviewDomainView_t &view = domain.views[viewIndex];
		if ( !view.ready ) {
			continue;
		}
		int rootIndex = viewIndex;
		int depth = 0;
		for ( int parentIndex = view.parentViewIndex; parentIndex >= 0;
				parentIndex = domain.views[parentIndex].parentViewIndex ) {
			if ( parentIndex >= domain.viewCount || depth >= domain.viewCount ) {
				FailView( view,
					CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_COMMAND_ORDER, parentIndex );
				break;
			}
			rootIndex = parentIndex;
			++depth;
		}
		if ( view.ready ) {
			view.rootViewIndex = rootIndex;
			view.nestingDepth = depth;
		}
	}

	// A rejected nested link invalidates its entire parent/child component.
	// Iterate to cover a malformed sibling and every ancestor/descendant without
	// relying on front-end allocation order beyond the validated packet edge.
	for ( int pass = 0; pass < domain.viewCount; ++pass ) {
		bool changed = false;
		for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
			classicSubviewDomainView_t &view = domain.views[viewIndex];
			if ( view.ready && view.parentViewIndex >= 0
					&& !domain.views[view.parentViewIndex].ready ) {
				FailView( view,
					CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_PARENT_FALLBACK,
					view.parentViewIndex );
				changed = true;
			}
		}
		for ( int parentIndex = domain.viewCount - 1; parentIndex >= 0;
				--parentIndex ) {
			classicSubviewDomainView_t &parent = domain.views[parentIndex];
			if ( !parent.ready ) {
				continue;
			}
			for ( int childIndex = 0; childIndex < domain.viewCount; ++childIndex ) {
				if ( domain.views[childIndex].parentViewIndex == parentIndex
						&& !domain.views[childIndex].ready ) {
					FailView( parent,
						CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_CHILD_FALLBACK,
						childIndex );
					changed = true;
					break;
				}
			}
		}
		if ( !changed ) {
			break;
		}
	}

	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		classicSubviewDomainView_t &view = domain.views[viewIndex];
		view.subtreeViewCount = view.ready ? 1 : 0;
	}
	// Descendants precede parents in an admitted chain, so this pass gives every
	// root its complete sealed component size without dynamic allocation.
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		const classicSubviewDomainView_t &view = domain.views[viewIndex];
		if ( view.ready && view.parentViewIndex >= 0
				&& domain.views[view.parentViewIndex].ready ) {
			domain.views[view.parentViewIndex].subtreeViewCount +=
				view.subtreeViewCount;
		}
	}
}

static int TransactionRootIndex( const classicSubviewDomainView_t *view ) {
	const int viewIndex = ViewIndex( view );
	if ( viewIndex < 0 ) {
		return -1;
	}
	return view->rootViewIndex >= 0 && view->rootViewIndex < domain.viewCount
		? view->rootViewIndex : viewIndex;
}

static bool IsTransactionMember( const classicSubviewDomainView_t &view,
		int rootIndex ) {
	return rootIndex >= 0 && view.ready
		&& ( view.rootViewIndex == rootIndex
			|| ( view.rootViewIndex < 0 && ViewIndex( &view ) == rootIndex ) );
}

static void RecordSingleFallback( classicSubviewDomainView_t &view,
		classicSubviewDomainBackend_t backend, classicSubviewDomainFailure_t failure,
		int detail ) {
	classicSubviewDomainBackendCoverage_t &coverage = domain.stats.backend[backend];
	if ( view.backendOutcome[backend] != CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED ) {
		return;
	}
	const int index = ViewIndex( &view );
	view.backendOutcome[backend] = CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK;
	view.backendFailure[backend] = failure;
	view.backendFailureDetail[backend] = detail;
	if ( index >= 0 ) {
		coverage.fallbackViewMask |= 1ull << index;
	}
	coverage.fallbackViews++;
	if ( view.nestingDepth > 0 ) {
		coverage.fallbackNestedViews++;
	}
}

static void RecordFallback( classicSubviewDomainView_t *view,
		classicSubviewDomainBackend_t backend, classicSubviewDomainFailure_t failure,
		int detail ) {
	if ( backend < CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL
			|| backend >= CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT ) {
		return;
	}
	classicSubviewDomainBackendCoverage_t &coverage = domain.stats.backend[backend];
	if ( view == NULL ) {
		coverage.untrackedFallbacks++;
		return;
	}
	if ( view->backendOutcome[backend] != CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED ) {
		coverage.duplicateReports++;
		return;
	}
	const int rootIndex = TransactionRootIndex( view );
	const bool nestedTransaction = rootIndex >= 0
		&& domain.views[rootIndex].subtreeViewCount > 1;
	if ( nestedTransaction ) {
		coverage.fallbackNestedTransactions++;
	}
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		classicSubviewDomainView_t &member = domain.views[viewIndex];
		if ( IsTransactionMember( member, rootIndex ) ) {
			RecordSingleFallback( member, backend, failure,
				viewIndex == ViewIndex( view ) ? detail : rootIndex );
		}
	}
	if ( rootIndex >= 0 ) {
		R_ClassicCinematicPostDomain_RecordSubviewTransactionFallback(
			domain.views[rootIndex].viewDef,
			static_cast<classicCinematicPostDomainBackend_t>( backend ),
			CLASSIC_CINEMATIC_POST_FAILURE_SPECIAL_VIEW_TRANSACTION_REJECTED,
			detail );
	}
}

static void PublishOwned( classicSubviewDomainView_t &view,
		classicSubviewDomainBackend_t backend ) {
	const int index = ViewIndex( &view );
	classicSubviewDomainBackendCoverage_t &coverage = domain.stats.backend[backend];
	view.backendOutcome[backend] = CLASSIC_SUBVIEW_DOMAIN_BACKEND_OWNED;
	if ( index >= 0 ) {
		coverage.ownedViewMask |= 1ull << index;
	}
	coverage.ownedViews++;
	if ( view.nestingDepth > 0 ) {
		coverage.ownedNestedViews++;
	}
	if ( view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR ) {
		coverage.ownedDirectMirrorViews++;
	} else if ( view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA ) {
		coverage.ownedRemoteCameraViews++;
	} else if ( view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_MIRROR ) {
		coverage.ownedMirrorViews++;
	} else if ( view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_REFLECTION ) {
		coverage.ownedReflectionViews++;
	} else if ( view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_REFRACTION ) {
		coverage.ownedRefractionViews++;
	} else if ( view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_XRAY ) {
		coverage.ownedXrayViews++;
	}
	switch ( view.captureType ) {
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_CUBEMAP:
		coverage.ownedColorCubemapCaptures++;
		break;
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_2D:
		coverage.ownedDepth2DCaptures++;
		break;
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP:
		coverage.ownedDepthCubemapCaptures++;
		break;
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE:
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_2D:
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COUNT:
	default:
		break;
	}
}

static bool FinalizeTransaction( classicSubviewDomainView_t &view,
		classicSubviewDomainBackend_t backend ) {
	const int rootIndex = TransactionRootIndex( &view );
	if ( rootIndex < 0 ) {
		return false;
	}
	int memberCount = 0;
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		const classicSubviewDomainView_t &member = domain.views[viewIndex];
		if ( !IsTransactionMember( member, rootIndex ) ) {
			continue;
		}
		++memberCount;
		if ( member.backendOutcome[backend]
				== CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK ) {
			return false;
		}
		if ( !member.backendCompleted[backend] ) {
			RecordFallback( &view, backend,
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTING_INCOMPLETE,
				viewIndex );
			return false;
		}
	}
	if ( memberCount != domain.views[rootIndex].subtreeViewCount ) {
		RecordFallback( &view, backend,
			CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTING_INCOMPLETE,
			memberCount );
		return false;
	}
	if ( !R_ClassicCinematicPostDomain_SubviewTransactionCompleted(
			domain.views[rootIndex].viewDef,
			static_cast<classicCinematicPostDomainBackend_t>( backend ) ) ) {
		RecordFallback( &view, backend,
			CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTED_CINEMATIC_POST_INCOMPLETE,
			rootIndex );
		return false;
	}
	if ( !R_ClassicCinematicPostDomain_PublishSubviewTransactionOwned(
			domain.views[rootIndex].viewDef,
			static_cast<classicCinematicPostDomainBackend_t>( backend ) ) ) {
		RecordFallback( &view, backend,
			CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTED_CINEMATIC_POST_INCOMPLETE,
			rootIndex );
		return false;
	}
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		classicSubviewDomainView_t &member = domain.views[viewIndex];
		if ( IsTransactionMember( member, rootIndex ) ) {
			PublishOwned( member, backend );
		}
	}
	if ( memberCount > 1 ) {
		domain.stats.backend[backend].ownedNestedTransactions++;
	}
	return true;
}

} // namespace

void R_ClassicSubviewDomain_ResetFrame( void ) {
	std::memset( &domain.stats, 0, sizeof( domain.stats ) );
	domain.viewCount = 0;
	idStr::Copynz( domain.stats.status, "empty", sizeof( domain.stats.status ) );
}

void R_ClassicSubviewDomain_PrepareFrame( const idScenePacketFrame &packetFrame ) {
	R_ClassicSubviewDomain_ResetFrame();
	domain.stats.prepared = true;
	domain.stats.sourceScenes = packetFrame.NumScenes();
	domain.stats.capturePackets = packetFrame.NumSubviewCaptures();
	domain.stats.overflow = packetFrame.Stats().overflow;
	if ( packetFrame.Stats().overflow ) {
		domain.stats.failureCounts[CLASSIC_SUBVIEW_DOMAIN_FAILURE_SCENE_PACKET_OVERFLOW]++;
	}
	for ( int sceneIndex = 0; sceneIndex < packetFrame.NumScenes(); ++sceneIndex ) {
		const scenePacket_t &scene = packetFrame.Scene(sceneIndex);
		if ( scene.packetCategory != SCENE_PACKET_CATEGORY_SUBVIEW ) {
			continue;
		}
		domain.stats.subviewScenes++;
		if ( domain.viewCount >= CLASSIC_SUBVIEW_DOMAIN_MAX_VIEWS ) {
			domain.stats.overflow = true;
			domain.stats.fallbackViews++;
			domain.stats.failureCounts[CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_POOL_OVERFLOW]++;
			continue;
		}
		classicSubviewDomainView_t &view = domain.views[domain.viewCount++];
		InitView( view, scene.viewDef, sceneIndex );
		PrepareView( packetFrame, scene, view );
	}
	ResolveNestedOwnership();
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		classicSubviewDomainView_t &view = domain.views[viewIndex];
		if ( view.ready ) {
			view.hash = HashView( view );
			domain.stats.readyViews++;
			if ( view.nestingDepth > 0 ) {
				domain.stats.nestedViews++;
				domain.stats.maxNestingDepth = Max( domain.stats.maxNestingDepth,
					view.nestingDepth );
			}
			if ( view.rootViewIndex == viewIndex && view.subtreeViewCount > 1 ) {
				domain.stats.nestedTransactions++;
			}
			switch ( view.kind ) {
			case CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR:
				domain.stats.directMirrorViews++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA:
				domain.stats.remoteCameraViews++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_KIND_MIRROR:
				domain.stats.mirrorViews++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_KIND_REFLECTION:
				domain.stats.reflectionViews++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_KIND_REFRACTION:
				domain.stats.refractionViews++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_KIND_XRAY:
				domain.stats.xrayViews++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_KIND_NONE:
			case CLASSIC_SUBVIEW_DOMAIN_KIND_COUNT:
			default:
				break;
			}
			switch ( view.captureType ) {
			case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_CUBEMAP:
				domain.stats.colorCubemapCaptures++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_2D:
				domain.stats.depth2DCaptures++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP:
				domain.stats.depthCubemapCaptures++;
				break;
			case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE:
			case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_2D:
			case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COUNT:
			default:
				break;
			}
		}
	}
	domain.stats.frameValid = !domain.stats.overflow
		&& domain.stats.fallbackViews == 0;
	std::uint64_t hash = HASH_OFFSET;
	HashInt( hash, domain.stats.subviewScenes );
	HashInt( hash, domain.stats.capturePackets );
	HashInt( hash, domain.stats.nestedViews );
	HashInt( hash, domain.stats.nestedTransactions );
	HashInt( hash, domain.stats.maxNestingDepth );
	for ( int i = 0; i < domain.viewCount; ++i ) {
		HashBool( hash, domain.views[i].ready );
		HashInt( hash, domain.views[i].failure );
		HashInt( hash, domain.views[i].failureDetail );
		HashInt( hash, domain.views[i].kind );
		HashInt( hash, static_cast<int>( domain.views[i].hash ) );
		HashInt( hash, static_cast<int>( domain.views[i].hash >> 32 ) );
	}
	domain.stats.hash = hash;
	if ( domain.stats.subviewScenes == 0 ) {
		idStr::Copynz( domain.stats.status, "empty", sizeof( domain.stats.status ) );
	} else if ( domain.stats.frameValid ) {
		idStr::Copynz( domain.stats.status, "ready", sizeof( domain.stats.status ) );
	} else if ( domain.stats.readyViews == 0 ) {
		idStr::Copynz( domain.stats.status, "fallback", sizeof( domain.stats.status ) );
	} else {
		idStr::Copynz( domain.stats.status, "mixed-view-fallback", sizeof( domain.stats.status ) );
	}
}

const classicSubviewDomainStats_t &R_ClassicSubviewDomain_Stats( void ) {
	return domain.stats;
}

int R_ClassicSubviewDomain_NumViews( void ) {
	return domain.viewCount;
}

const classicSubviewDomainView_t *R_ClassicSubviewDomain_ViewByIndex( int index ) {
	return index >= 0 && index < domain.viewCount ? &domain.views[index] : NULL;
}

const classicSubviewDomainView_t *R_ClassicSubviewDomain_FindView(
		const viewDef_t *viewDef ) {
	return FindMutableView(viewDef);
}

bool R_ClassicSubviewDomain_IsCaptureBacked(
		const classicSubviewDomainView_t &view ) {
	return view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA
		|| view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_MIRROR
		|| view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_REFLECTION
		|| view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_REFRACTION
		|| view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_XRAY;
}

bool R_ClassicSubviewDomain_IsDirect( const classicSubviewDomainView_t &view ) {
	return view.kind == CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR;
}

bool R_ClassicSubviewDomain_ViewSemanticsMatch(
		const classicSubviewDomainView_t &view ) {
	return view.ready && view.viewDef != NULL
		&& ViewSemanticsMatch( view, *view.viewDef );
}

bool R_ClassicSubviewDomain_ReadyForBackend(
		const classicSubviewDomainView_t &view,
		classicSubviewDomainBackend_t backend ) {
	if ( backend < CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL
			|| backend >= CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT
			|| !domain.stats.prepared || domain.stats.overflow
			|| !view.ready
			|| view.backendCompleted[backend]
			|| view.backendOutcome[backend]
				!= CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED
			|| !R_ClassicSubviewDomain_ViewSemanticsMatch( view ) ) {
		return false;
	}
	const int rootIndex = TransactionRootIndex( &view );
	for ( int viewIndex = 0; viewIndex < domain.viewCount; ++viewIndex ) {
		const classicSubviewDomainView_t &member = domain.views[viewIndex];
		if ( !IsTransactionMember( member, rootIndex ) ) {
			continue;
		}
		if ( member.backendOutcome[backend]
				!= CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED
			|| !R_ClassicSubviewDomain_ViewSemanticsMatch( member )
			|| ( R_ClassicSubviewDomain_IsCaptureBacked( member )
				&& ( member.captureImage == NULL
					|| !member.captureImage->IsLoaded() ) ) ) {
			return false;
		}
	}
	return R_ClassicCinematicPostDomain_SubviewTransactionReady( view.viewDef,
		static_cast<classicCinematicPostDomainBackend_t>( backend ) );
}

bool R_ClassicSubviewDomain_CaptureMatches(
		const classicSubviewDomainView_t &view, const idImage *image,
		int x, int y, int width, int height, int cubeFace, bool copyDepth ) {
	return R_ClassicSubviewDomain_IsCaptureBacked( view )
		&& R_ClassicSubviewDomain_ViewSemanticsMatch( view )
		&& image == view.captureImage && x == view.captureX
		&& y == view.captureY && width == view.captureWidth
		&& height == view.captureHeight && cubeFace == view.captureCubeFace
		&& copyDepth == view.captureCopyDepth;
}

bool R_ClassicSubviewDomain_RecordOwned( const viewDef_t *viewDef,
		classicSubviewDomainBackend_t backend, const idImage *image,
		int x, int y, int width, int height, int cubeFace, bool copyDepth ) {
	if ( backend < CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL
			|| backend >= CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT ) {
		return false;
	}
	classicSubviewDomainView_t *view = FindMutableView(viewDef);
	if ( view == NULL || !view->ready ) {
		RecordFallback( view, backend, CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NOT_READY, 0 );
		return false;
	}
	if ( view->backendOutcome[backend] != CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED
			|| view->backendCompleted[backend] ) {
		domain.stats.backend[backend].duplicateReports++;
		return view->backendOutcome[backend] != CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK
			&& R_ClassicSubviewDomain_CaptureMatches( *view, image, x, y, width,
				height, cubeFace, copyDepth );
	}
	if ( !R_ClassicSubviewDomain_ViewSemanticsMatch( *view ) ) {
		domain.stats.backend[backend].coverageMismatches++;
		RecordFallback( view, backend,
			CLASSIC_SUBVIEW_DOMAIN_FAILURE_VIEW_SEMANTICS_MISMATCH, 0 );
		return false;
	}
	if ( !R_ClassicSubviewDomain_CaptureMatches( *view, image, x, y, width,
			height, cubeFace, copyDepth ) ) {
		domain.stats.backend[backend].coverageMismatches++;
		RecordFallback( view, backend,
			CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_CAPTURE_MISMATCH, 0 );
		return false;
	}
	view->backendCompleted[backend] = true;
	return TransactionRootIndex( view ) != ViewIndex( view )
		|| FinalizeTransaction( *view, backend );
}

bool R_ClassicSubviewDomain_RecordDirectOwned( const viewDef_t *viewDef,
		classicSubviewDomainBackend_t backend ) {
	if ( backend < CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL
			|| backend >= CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT ) {
		return false;
	}
	classicSubviewDomainView_t *view = FindMutableView(viewDef);
	if ( view == NULL || !view->ready || !R_ClassicSubviewDomain_IsDirect( *view ) ) {
		RecordFallback( view, backend, CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NOT_READY, 0 );
		return false;
	}
	if ( view->backendOutcome[backend] != CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED
			|| view->backendCompleted[backend] ) {
		domain.stats.backend[backend].duplicateReports++;
		return view->backendOutcome[backend] != CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK
			&& R_ClassicSubviewDomain_ViewSemanticsMatch( *view );
	}
	if ( !R_ClassicSubviewDomain_ViewSemanticsMatch( *view ) ) {
		domain.stats.backend[backend].coverageMismatches++;
		RecordFallback( view, backend,
			CLASSIC_SUBVIEW_DOMAIN_FAILURE_VIEW_SEMANTICS_MISMATCH, 0 );
		return false;
	}
	view->backendCompleted[backend] = true;
	return TransactionRootIndex( view ) != ViewIndex( view )
		|| FinalizeTransaction( *view, backend );
}

void R_ClassicSubviewDomain_RecordBackendFallback( const viewDef_t *viewDef,
		classicSubviewDomainBackend_t backend, classicSubviewDomainFailure_t failure,
		int detail ) {
	RecordFallback( FindMutableView(viewDef), backend, failure, detail );
}

const classicSubviewDomainBackendCoverage_t &
		R_ClassicSubviewDomain_BackendCoverage( classicSubviewDomainBackend_t backend ) {
	static const classicSubviewDomainBackendCoverage_t empty = {};
	return backend >= CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL
		&& backend < CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT
		? domain.stats.backend[backend] : empty;
}

const char *ClassicSubviewDomainKind_Name( classicSubviewDomainKind_t kind ) {
	switch ( kind ) {
	case CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR: return "directMirror";
	case CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA: return "remoteCamera";
	case CLASSIC_SUBVIEW_DOMAIN_KIND_MIRROR: return "mirror";
	case CLASSIC_SUBVIEW_DOMAIN_KIND_REFLECTION: return "reflection";
	case CLASSIC_SUBVIEW_DOMAIN_KIND_REFRACTION: return "refraction";
	case CLASSIC_SUBVIEW_DOMAIN_KIND_XRAY: return "xray";
	case CLASSIC_SUBVIEW_DOMAIN_KIND_NONE:
	case CLASSIC_SUBVIEW_DOMAIN_KIND_COUNT:
	default: return "none";
	}
}

const char *ClassicSubviewDomainCaptureType_Name(
		classicSubviewDomainCaptureType_t type ) {
	switch ( type ) {
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_2D: return "color2D";
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_CUBEMAP: return "colorCubemap";
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_2D: return "depth2D";
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP: return "depthCubemap";
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE:
	case CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COUNT:
	default: return "none";
	}
}

const char *ClassicSubviewDomainFailure_Name( classicSubviewDomainFailure_t failure ) {
	switch ( failure ) {
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_NONE: return "none";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNAVAILABLE: return "unavailable";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_SCENE_PACKET_OVERFLOW: return "scenePacketOverflow";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_POOL_OVERFLOW: return "capturePoolOverflow";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_VIEW: return "unsupportedView";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_PARENT_SCENE: return "missingParentScene";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_PARENT_SURFACE: return "missingParentSurface";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_PARENT_MATERIAL: return "unsupportedParentMaterial";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_CAPTURE: return "missingCapture";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_DUPLICATE_CAPTURE: return "duplicateCapture";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_INVALID_CAPTURE: return "invalidCapture";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_SURFACE_MISMATCH: return "captureSurfaceMismatch";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_VIEWPORT_MISMATCH: return "captureViewportMismatch";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_CAPTURE_TARGET: return "unsupportedCaptureTarget";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNEXPECTED_CAPTURE: return "unexpectedCapture";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_SPECIAL_SEMANTICS: return "unsupportedSpecialSemantics";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_VIEW_SEMANTICS_MISMATCH: return "viewSemanticsMismatch";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_NESTED_PARENT: return "missingNestedParent";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_COMMAND_ORDER: return "nestedCommandOrder";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_PARENT_FALLBACK: return "nestedParentFallback";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_CHILD_FALLBACK: return "nestedChildFallback";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_CINEMATIC_POST_FALLBACK: return "nestedCinematicPostFallback";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NOT_READY: return "backendNotReady";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_REJECTED: return "backendRejected";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_CAPTURE_MISMATCH: return "backendCaptureMismatch";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTING_INCOMPLETE: return "backendNestingIncomplete";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTED_CINEMATIC_POST_INCOMPLETE: return "backendNestedCinematicPostIncomplete";
	case CLASSIC_SUBVIEW_DOMAIN_FAILURE_COUNT:
	default: return "unknown";
	}
}

const char *ClassicSubviewDomainBackend_Name( classicSubviewDomainBackend_t backend ) {
	switch ( backend ) {
	case CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL: return "GL";
	case CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN: return "Vulkan";
	case CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT:
	default: return "unknown";
	}
}

bool RendererClassicSubviewDomain_RunSelfTest( void ) {
	R_ClassicCinematicPostDomain_ResetFrame();
	if ( CLASSIC_SUBVIEW_DOMAIN_MAX_VIEWS != SCENE_PACKET_MAX_SUBVIEW_CAPTURES
			|| idStr::Cmp( ClassicSubviewDomainKind_Name(
				CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA ), "remoteCamera" ) != 0
			|| idStr::Cmp( ClassicSubviewDomainKind_Name(
				CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR ), "directMirror" ) != 0
			|| idStr::Cmp( ClassicSubviewDomainCaptureType_Name(
				CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP ),
				"depthCubemap" ) != 0
			|| idStr::Cmp( ClassicSubviewDomainFailure_Name(
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_CAPTURE_TARGET ),
				"unsupportedCaptureTarget" ) != 0
			|| idStr::Cmp( ClassicSubviewDomainFailure_Name(
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTING_INCOMPLETE ),
				"backendNestingIncomplete" ) != 0
			|| idStr::Cmp( ClassicSubviewDomainFailure_Name(
				CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTED_CINEMATIC_POST_INCOMPLETE ),
				"backendNestedCinematicPostIncomplete" ) != 0
			|| idStr::Cmp( ClassicSubviewDomainBackend_Name(
				CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN ), "Vulkan" ) != 0 ) {
		return false;
	}
	// Prepare a valid empty companion domain so standalone subview cases also
	// exercise the joint-domain vacuous-success contract, regardless of the
	// caller's live cinematic/post CVar state.
	idScenePacketFrame emptyCinematicFrame;
	emptyCinematicFrame.Clear();
	emptyCinematicFrame.MarkBackendDerived();
	R_ClassicCinematicPostDomain_PrepareFrame( emptyCinematicFrame );
	R_ClassicSubviewDomain_ResetFrame();
	viewDef_t viewDef;
	std::memset( &viewDef, 0, sizeof(viewDef) );
	InitView( domain.views[0], &viewDef, 7 );
	domain.viewCount = 1;
	classicSubviewDomainView_t &view = domain.views[0];
	view.ready = true;
	view.kind = CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA;
	view.captureImage = reinterpret_cast<idImage *>( static_cast<size_t>(0x1000) );
	view.captureX = 3;
	view.captureY = 4;
	view.captureWidth = 64;
	view.captureHeight = 32;
	view.captureCubeFace = 5;
	view.captureTextureType = TT_CUBIC;
	view.captureTextureFormat = FMT_DEPTH;
	view.captureCopyDepth = true;
	view.captureType = CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP;
	ResolveNestedOwnership();
	classicSubviewDomainCaptureType_t classifiedType =
		CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE;
	const bool cubeDepthTarget = ClassifyCaptureTargetOptions( TT_CUBIC,
		FMT_DEPTH, 5, true, classifiedType )
		&& classifiedType == CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP;
	const bool depthStencilTarget = ClassifyCaptureTargetOptions( TT_2D,
		FMT_DEPTH_STENCIL, 0, true, classifiedType )
		&& classifiedType == CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_2D;
	const bool invalidTargetRejected =
		!ClassifyCaptureTargetOptions( TT_CUBIC, FMT_DEPTH, 6, true,
			classifiedType )
		&& !ClassifyCaptureTargetOptions( TT_2D, FMT_RGBA8, 0, true,
			classifiedType );
	const std::uint64_t firstHash = HashView(view);
	view.captureWidth++;
	const bool hashSensitive = HashView(view) != firstHash;
	view.captureWidth--;
	std::memset( &domain.stats, 0, sizeof(domain.stats) );
	const bool owned = R_ClassicSubviewDomain_RecordOwned( &viewDef,
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL, view.captureImage, 3, 4, 64, 32,
		5, true );
	const bool duplicate = R_ClassicSubviewDomain_RecordOwned( &viewDef,
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL, view.captureImage, 3, 4, 64, 32,
		5, true );
	const bool mismatch = !R_ClassicSubviewDomain_RecordOwned( &viewDef,
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN, view.captureImage, 3, 4, 63, 32,
		5, true );
	const bool capturePassed = cubeDepthTarget && depthStencilTarget
		&& invalidTargetRejected && hashSensitive && owned && duplicate && mismatch
		&& view.backendOutcome[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			== CLASSIC_SUBVIEW_DOMAIN_BACKEND_OWNED
		&& view.backendOutcome[CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN]
			== CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL].ownedViews == 1
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			.ownedDepthCubemapCaptures == 1
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL].duplicateReports == 1
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN].coverageMismatches == 1;
	R_ClassicSubviewDomain_ResetFrame();
	std::memset( &viewDef, 0, sizeof(viewDef) );
	viewDef.isSubview = true;
	viewDef.numClipPlanes = 1;
	InitView( domain.views[0], &viewDef, 11 );
	domain.viewCount = 1;
	classicSubviewDomainView_t &directView = domain.views[0];
	directView.ready = true;
	directView.kind = CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR;
	CaptureViewSemantics( directView, viewDef );
	ResolveNestedOwnership();
	const bool directOwned = R_ClassicSubviewDomain_RecordDirectOwned( &viewDef,
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL );
	viewDef.scissor.x1++;
	const bool semanticMismatch = !R_ClassicSubviewDomain_ViewSemanticsMatch(
		directView );

	// A nested direct pair publishes neither member until the outer root returns.
	// The second run injects a root failure after the child completes and proves
	// that the pending child is rolled back with the same transaction.
	R_ClassicSubviewDomain_ResetFrame();
	domain.stats.prepared = true;
	viewDef_t nestedRootDef;
	viewDef_t nestedChildDef;
	std::memset( &nestedRootDef, 0, sizeof(nestedRootDef) );
	std::memset( &nestedChildDef, 0, sizeof(nestedChildDef) );
	nestedRootDef.isSubview = true;
	nestedChildDef.isSubview = true;
	nestedRootDef.numClipPlanes = 1;
	nestedChildDef.numClipPlanes = 1;
	nestedChildDef.superView = &nestedRootDef;
	InitView( domain.views[0], &nestedChildDef, 20 );
	InitView( domain.views[1], &nestedRootDef, 21 );
	domain.viewCount = 2;
	classicSubviewDomainView_t &nestedChild = domain.views[0];
	classicSubviewDomainView_t &nestedRoot = domain.views[1];
	nestedChild.ready = true;
	nestedChild.kind = CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR;
	nestedChild.parentViewDef = &nestedRootDef;
	nestedChild.parentScenePacketIndex = 21;
	CaptureViewSemantics( nestedChild, nestedChildDef );
	nestedRoot.ready = true;
	nestedRoot.kind = CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR;
	CaptureViewSemantics( nestedRoot, nestedRootDef );
	ResolveNestedOwnership();
	const bool nestedTopology = nestedChild.ready && nestedRoot.ready
		&& nestedChild.parentViewIndex == 1
		&& nestedChild.rootViewIndex == 1
		&& nestedChild.nestingDepth == 1
		&& nestedRoot.rootViewIndex == 1
		&& nestedRoot.subtreeViewCount == 2;
	const bool nestedChildReadyInitially = R_ClassicSubviewDomain_ReadyForBackend(
		nestedChild, CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL );
	const bool nestedChildCompleted = R_ClassicSubviewDomain_RecordDirectOwned(
		&nestedChildDef, CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL );
	const bool nestedDeferred = nestedChild.backendOutcome[
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
		== CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED;
	const bool nestedChildNotReadyTwice = !R_ClassicSubviewDomain_ReadyForBackend(
		nestedChild, CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL );
	const bool nestedChildDuplicate = R_ClassicSubviewDomain_RecordDirectOwned(
		&nestedChildDef, CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL );
	const bool nestedDuplicateSealed = nestedChildDuplicate
		&& nestedChild.backendCompleted[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
		&& nestedChild.backendOutcome[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			== CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			.duplicateReports == 1;
	const bool nestedRootOwned = R_ClassicSubviewDomain_RecordDirectOwned(
		&nestedRootDef, CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL );
	const bool nestedPublished = nestedRootOwned
		&& nestedChild.backendOutcome[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			== CLASSIC_SUBVIEW_DOMAIN_BACKEND_OWNED
		&& nestedRoot.backendOutcome[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			== CLASSIC_SUBVIEW_DOMAIN_BACKEND_OWNED
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			.ownedNestedViews == 1
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL]
			.ownedNestedTransactions == 1;

	R_ClassicSubviewDomain_ResetFrame();
	InitView( domain.views[0], &nestedChildDef, 20 );
	InitView( domain.views[1], &nestedRootDef, 21 );
	domain.viewCount = 2;
	classicSubviewDomainView_t &rejectedChild = domain.views[0];
	classicSubviewDomainView_t &rejectedRoot = domain.views[1];
	rejectedChild.ready = true;
	rejectedChild.kind = CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR;
	rejectedChild.parentViewDef = &nestedRootDef;
	rejectedChild.parentScenePacketIndex = 21;
	CaptureViewSemantics( rejectedChild, nestedChildDef );
	rejectedRoot.ready = true;
	rejectedRoot.kind = CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR;
	CaptureViewSemantics( rejectedRoot, nestedRootDef );
	ResolveNestedOwnership();
	const bool rejectedChildCompleted = R_ClassicSubviewDomain_RecordDirectOwned(
		&nestedChildDef, CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN );
	R_ClassicSubviewDomain_RecordBackendFallback( &nestedRootDef,
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN,
		CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_REJECTED, 9 );
	const bool nestedRollback = rejectedChildCompleted
		&& rejectedChild.backendOutcome[CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN]
			== CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK
		&& rejectedRoot.backendOutcome[CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN]
			== CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN]
			.fallbackNestedViews == 1
		&& domain.stats.backend[CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN]
			.fallbackNestedTransactions == 1;
	const bool passed = capturePassed && directOwned && semanticMismatch
		&& nestedTopology && nestedChildReadyInitially
		&& nestedChildCompleted && nestedDeferred
		&& nestedChildNotReadyTwice && nestedDuplicateSealed && nestedPublished
		&& nestedRollback;
	R_ClassicSubviewDomain_ResetFrame();
	R_ClassicCinematicPostDomain_ResetFrame();
	return passed;
}
