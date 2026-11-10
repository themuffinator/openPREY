
#ifndef __MATH_RANDOM_H__
#define __MATH_RANDOM_H__

/*
===============================================================================

	Random number generator

===============================================================================
*/

class idRandom {
public:
						idRandom( int seed = 0 );

	void				SetSeed( int seed );
	int					GetSeed( void ) const;

	int					RandomInt( void );			// random integer in the range [0, MAX_RAND]
	int					RandomInt( int max );		// random integer in the range [0, max[
	float				RandomFloat( void );		// random number in the range [0.0f, 1.0f]
	float				CRandomFloat( void );		// random number in the range [-1.0f, 1.0f]

	static const int	MAX_RAND = 0x7fff;

private:
	int					seed;
};

ID_INLINE idRandom::idRandom( int seed ) {
	this->seed = seed;
}

ID_INLINE void idRandom::SetSeed( int seed ) {
	this->seed = seed;
}

ID_INLINE int idRandom::GetSeed( void ) const {
	return seed;
}

ID_INLINE int idRandom::RandomInt( void ) {
	const unsigned int nextSeed = 69069u * static_cast<unsigned int>( seed ) + 1u;
	seed = ( nextSeed & 0x80000000u )
		? -1 - static_cast<int>( ~nextSeed )
		: static_cast<int>( nextSeed );
	return static_cast<int>( nextSeed & static_cast<unsigned int>( idRandom::MAX_RAND ) );
}

ID_INLINE int idRandom::RandomInt( int max ) {
	if ( max == 0 ) {
		return 0;			// avoid divide by zero error
	}
	return RandomInt() % max;
}

ID_INLINE float idRandom::RandomFloat( void ) {
	return ( RandomInt() / ( float )( idRandom::MAX_RAND + 1 ) );
}

ID_INLINE float idRandom::CRandomFloat( void ) {
	return ( 2.0f * ( RandomFloat() - 0.5f ) );
}


/*
===============================================================================

	Random number generator

===============================================================================
*/

class idRandom2 {
public:
							idRandom2( unsigned int seed = 0 );

	void					SetSeed( unsigned int seed );
	unsigned int			GetSeed( void ) const;

	int						RandomInt( void );			// random integer in the range [0, MAX_RAND]
	int						RandomInt( int max );		// random integer in the range [0, max]
	float					RandomFloat( void );		// random number in the range [0.0f, 1.0f]
	float					CRandomFloat( void );		// random number in the range [-1.0f, 1.0f]

	static const int		MAX_RAND = 0x7fff;

private:
	unsigned int			seed;

	static const unsigned int	IEEE_ONE = 0x3f800000u;
	static const unsigned int	IEEE_MASK = 0x007fffffu;
};

ID_INLINE idRandom2::idRandom2( unsigned int seed ) {
	this->seed = seed;
}

ID_INLINE void idRandom2::SetSeed( unsigned int seed ) {
	this->seed = seed;
}

ID_INLINE unsigned int idRandom2::GetSeed( void ) const {
	return seed;
}

ID_INLINE int idRandom2::RandomInt( void ) {
	seed = 1664525u * seed + 1013904223u;
	return ( (int) seed & idRandom2::MAX_RAND );
}

ID_INLINE int idRandom2::RandomInt( int max ) {
	if ( max == 0 ) {
		return 0;		// avoid divide by zero error
	}
	return ( RandomInt() >> ( 16 - idMath::BitsForInteger( max ) ) ) % max;
}

ID_INLINE float idRandom2::RandomFloat( void ) {
	unsigned int i;
	seed = 1664525u * seed + 1013904223u;
	i = idRandom2::IEEE_ONE | ( seed & idRandom2::IEEE_MASK );
	return idMath_FloatFromBits( i ) - 1.0f;
}

ID_INLINE float idRandom2::CRandomFloat( void ) {
	unsigned int i;
	seed = 1664525u * seed + 1013904223u;
	i = idRandom2::IEEE_ONE | ( seed & idRandom2::IEEE_MASK );
	return 2.0f * idMath_FloatFromBits( i ) - 3.0f;
}

#endif /* !__MATH_RANDOM_H__ */
