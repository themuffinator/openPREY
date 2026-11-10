// Copyright (C) 2026 DarkMatter Productions
#ifndef OPENQ4_CONTENT_IDENTITY_H
#define OPENQ4_CONTENT_IDENTITY_H

class idContentObserver;

// One optional observer for mutable, single-thread-owned content. No allocation,
// counter wrap or retained source data: mutation and destruction detach both ends.
// Copying content never copies its identity or an observer registration.
class idContentIdentity {
public:
	idContentIdentity() = default;
	idContentIdentity( const idContentIdentity& ) {}
	idContentIdentity& operator=( const idContentIdentity& ) { Invalidate(); return *this; }
	~idContentIdentity() { Invalidate(); }
	void Invalidate();
private:
	friend class idContentObserver;
	mutable idContentObserver *observer = nullptr;
};

class idContentObserver {
public:
	idContentObserver() = default;
	idContentObserver( const idContentObserver& ) = delete;
	idContentObserver& operator=( const idContentObserver& ) = delete;
	~idContentObserver() { Clear(); }
	void Attach( const idContentIdentity &content ) {
		Clear();
		// Replacing an observer invalidates the previous registration too.
		if ( content.observer ) content.observer->Clear();
		source = &content;
		content.observer = this;
	}
	void Clear() {
		if ( source ) source->observer = nullptr;
		source = nullptr;
	}
	bool Matches( const idContentIdentity &content ) const { return source == &content; }
	// Check this before dereferencing a deferred source pointer. Destruction and
	// every mutation clear the registration while the source is still alive.
	bool IsAttached() const { return source != nullptr; }
private:
	friend class idContentIdentity;
	const idContentIdentity *source = nullptr;
};

inline void idContentIdentity::Invalidate() {
	if ( observer ) observer->Clear();
}
#endif
