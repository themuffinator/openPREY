
#ifndef __STACK_H__
#define __STACK_H__

#include <stddef.h>

/*
===============================================================================

	Stack template

===============================================================================
*/

#define idStack( type, next )		idStackTemplate<type, offsetof( type, next )>

template< class type, size_t nextOffset >
class idStackTemplate {
public:
							idStackTemplate( void );

	void					Add( type *element );
	type *					Get( void );

private:
	type *					top;
	type *					bottom;
};

#define STACK_NEXT_PTR( element )		(*(type**)(((byte*)element)+nextOffset))

template< class type, size_t nextOffset >
idStackTemplate<type,nextOffset>::idStackTemplate( void ) {
	top = bottom = NULL;
}

template< class type, size_t nextOffset >
void idStackTemplate<type,nextOffset>::Add( type *element ) {
	STACK_NEXT_PTR(element) = top;
	top = element;
	if ( !bottom ) {
		bottom = element;
	}
}

template< class type, size_t nextOffset >
type *idStackTemplate<type,nextOffset>::Get( void ) {
	type *element;

	element = top;
	if ( element ) {
		top = STACK_NEXT_PTR(top);
		if ( bottom == element ) {
			bottom = NULL;
		}
		STACK_NEXT_PTR(element) = NULL;
	}
	return element;
}

#endif /* !__STACK_H__ */
