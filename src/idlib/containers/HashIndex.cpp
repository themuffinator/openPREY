



int idHashIndex::INVALID_INDEX[1] = { -1 };

/*
================
idHashIndex::NormalizeHashSize
================
*/
int idHashIndex::NormalizeHashSize( const int hashSize ) {
	if ( hashSize <= 0 ) {
		return DEFAULT_HASH_SIZE;
	}
	if ( idMath::IsPowerOfTwo( hashSize ) ) {
		return hashSize;
	}
	if ( hashSize > ( 1 << 30 ) ) {
		return ( 1 << 30 );
	}
	return idMath::CeilPowerOfTwo( hashSize );
}

/*
================
idHashIndex::NormalizeIndexSize
================
*/
int idHashIndex::NormalizeIndexSize( const int indexSize ) {
	return Max( 0, indexSize );
}

/*
================
idHashIndex::Init
================
*/
void idHashIndex::Init( const int initialHashSize, const int initialIndexSize ) {
	const int normalizedHashSize = NormalizeHashSize( initialHashSize );
	assert( idMath::IsPowerOfTwo( normalizedHashSize ) );

	hashSize = normalizedHashSize;
	hash = INVALID_INDEX;
	indexSize = NormalizeIndexSize( initialIndexSize );
	indexChain = INVALID_INDEX;
	granularity = DEFAULT_HASH_GRANULARITY;
	hashMask = hashSize - 1;
	lookupMask = 0;
// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
	allocatorHeap = 0;
#endif
// RAVEN END
}

/*
================
idHashIndex::Allocate
================
*/
void idHashIndex::Allocate( const int newHashSize, const int newIndexSize ) {
	const int normalizedHashSize = NormalizeHashSize( newHashSize );
	const int normalizedIndexSize = Max( 1, NormalizeIndexSize( newIndexSize ) );
	assert( idMath::IsPowerOfTwo( normalizedHashSize ) );

	Free();

// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
	if(allocatorHeap)
	{
		RV_PUSH_HEAP_PTR(allocatorHeap);
	}
#endif
// RAVEN END

	hashSize = normalizedHashSize;
	hash = new int[hashSize];
	memset( hash, 0xff, hashSize * sizeof( hash[0] ) );
	indexSize = normalizedIndexSize;
	indexChain = new int[indexSize];
	memset( indexChain, 0xff, indexSize * sizeof( indexChain[0] ) );
	hashMask = hashSize - 1;
	lookupMask = -1;

// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
	if(allocatorHeap)
	{
		RV_POP_HEAP();
	}
#endif
// RAVEN END
}

/*
================
idHashIndex::Free
================
*/
void idHashIndex::Free( void ) {
	if ( hash != INVALID_INDEX ) {
		delete[] hash;
		hash = INVALID_INDEX;
	}
	if ( indexChain != INVALID_INDEX ) {
		delete[] indexChain;
		indexChain = INVALID_INDEX;
	}
	lookupMask = 0;
}

/*
================
idHashIndex::ResizeIndex
================
*/
void idHashIndex::ResizeIndex( const int newIndexSize ) {
	int *oldIndexChain, mod, newSize;

	if ( newIndexSize <= indexSize ) {
		return;
	}

	granularity = Max( 1, granularity );
	mod = newIndexSize % granularity;
	if ( !mod ) {
		newSize = newIndexSize;
	} else if ( newIndexSize > idMath::INT_MAX - ( granularity - mod ) ) {
		newSize = newIndexSize;
	} else {
		newSize = newIndexSize + granularity - mod;
	}
	newSize = NormalizeIndexSize( newSize );

	if ( indexChain == INVALID_INDEX ) {
		indexSize = newSize;
		return;
	}

	oldIndexChain = indexChain;

// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
	if(allocatorHeap)
	{
		RV_PUSH_HEAP_PTR(allocatorHeap);
	}
#endif
// RAVEN END

	indexChain = new int[newSize];

// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
		if(allocatorHeap)
		{
			RV_POP_HEAP();
		}
#endif
// RAVEN END

	memcpy( indexChain, oldIndexChain, indexSize * sizeof(int) );
	memset( indexChain + indexSize, 0xff, (newSize - indexSize) * sizeof(int) );
	delete[] oldIndexChain;
	indexSize = newSize;
}

/*
================
idHashIndex::GetSpread
================
*/
int idHashIndex::GetSpread( void ) const {
	int i, index, totalItems, *numHashItems, average, error, e;

	if ( hash == INVALID_INDEX || indexChain == INVALID_INDEX || hashSize <= 0 || indexSize <= 0 ) {
		return 100;
	}

	totalItems = 0;

// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
	if(allocatorHeap)
	{
		RV_PUSH_HEAP_PTR(allocatorHeap);
	}
#endif
// RAVEN END

	numHashItems = new int[hashSize];

// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
	if(allocatorHeap)
	{
		RV_POP_HEAP();
	}
#endif
// RAVEN END

	for ( i = 0; i < hashSize; i++ ) {
		numHashItems[i] = 0;
		for ( index = hash[i]; index >= 0; index = indexChain[index] ) {
			if ( index >= indexSize ) {
				break;
			}
			numHashItems[i]++;
		}
		totalItems += numHashItems[i];
	}
	// if no items in hash
	if ( totalItems <= 1 ) {
		delete[] numHashItems;
		return 100;
	}
	average = totalItems / hashSize;
	error = 0;
	for ( i = 0; i < hashSize; i++ ) {
		e = abs( numHashItems[i] - average );
		if ( e > 1 ) {
			error += e - 1;
		}
	}
	delete[] numHashItems;
	return idMath::ClampInt( 0, 100, 100 - (error * 100 / totalItems) );
}

// RAVEN BEGIN
// mwhitlock: Dynamic memory consolidation
#if defined(_RV_MEM_SYS_SUPPORT)
void idHashIndex::SetAllocatorHeap ( rvHeap* heap )
{
	assert(heap);
	allocatorHeap = heap;
}
#endif
// RAVEN END
