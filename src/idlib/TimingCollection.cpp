



#if !defined(__TIMINGCOLLECTION_H_)
	#include "TimingCollection.h"
#endif

#ifdef RV_TIMERCOLLECTION

//-----------------------------------------------------------------------------
//
//								rvSingleTiming::Clear
//
//-----------------------------------------------------------------------------

void rvSingleTiming::Clear( void )
{
	mTotalUpdates			= 0;
	mCurValue				= 0;
	mTotalValue				= 0;
	mPeakValue				= 0;
	mLimit					= 0;
	mLimitExceeded			= 0;
	mLimitExceededTimesFive	= 0;
	mDisplayLevel			= 0;
	mName					= "";
	mParentName				= "";

	mStartFile				= "";
	mStartLine				= 0;
	mEndFile				= "";
	mEndLine				= 0;
}

//-----------------------------------------------------------------------------
//
//								rvSingleTiming::rvSingleTiming
//
//-----------------------------------------------------------------------------

rvSingleTiming::rvSingleTiming()
{
	Clear();
}

//-----------------------------------------------------------------------------
//
//								rvSingleTiming::rvSingleTiming
//
//-----------------------------------------------------------------------------

rvSingleTiming::rvSingleTiming( idStr &newName )
{
	Clear();
	mName = newName;
}

//-----------------------------------------------------------------------------
//
//								rvSingleTiming::OutputDataToFile
//
//-----------------------------------------------------------------------------

void rvSingleTiming::OutputDataToFile( idFile *file, int framesRecorded )
{
	idStr	outputName = "";

	for( int i = 0; i < mDisplayLevel; i++ )
	{
		outputName += "**";
	}
	outputName += mName;

	const float invFrames = framesRecorded > 0 ? 1.0f / framesRecorded : 0.0f;
	idStr buffer;
	sprintf( buffer, "%-36s %-9.3f %-9.3f %-9.3f %-9.3f %-9i %-9i %-9.3f\n", outputName.c_str(),
		(float)mTotalValue, (float)mTotalValue * invFrames, (float)mPeakValue,
		(float)mLimit, mLimitExceeded, mLimitExceededTimesFive, (float)mTotalUpdates * invFrames );
	file->Write ( buffer.c_str(), buffer.Length() );
}

//-----------------------------------------------------------------------------
//
//								rvSingleTiming::OutputInfoToFile
//
//-----------------------------------------------------------------------------

void rvSingleTiming::OutputInfoToFile( idFile *file )
{
	idStr	buffer;

	sprintf( buffer, "Name: %s\nParent: %s\n", mName.c_str(), mParentName.c_str() );
	file->Write ( buffer.c_str(), buffer.Length() );

	sprintf( buffer, "Starting at %s(%d)\nEnding at %s(%d)\n\n", mStartFile.c_str(), mStartLine, mEndFile.c_str(), mEndLine );
	file->Write ( buffer.c_str(), buffer.Length() );
}














//-----------------------------------------------------------------------------
//
//								rvTimingCollection::Clear
//
//-----------------------------------------------------------------------------

void rvTimingCollection::Clear( void )
{
	mUpdates			= 0;
	mCurTimer			= 0;
	mFramesRecorded		= 0;
	mCurrentlyUpdating	= 0;
	mTimings.Clear();
	mTimingsIndex.Clear();
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::rvTimingCollection
//
//-----------------------------------------------------------------------------

rvTimingCollection::rvTimingCollection()
{
	Clear();
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::GetTiming
//
//-----------------------------------------------------------------------------

rvSingleTiming *rvTimingCollection::GetTiming( idStr &timingName )
{
	int *handle = NULL;

	if( mTimingsIndex.Get( timingName, &handle ) ) 
	{	
		return( &mTimings[*handle] );
	}

	rvSingleTiming	newTiming( timingName );
	int				index = mTimings.Num();
	
	mTimingsIndex.Set( timingName, index );
	mTimings.Append( newTiming );
	return &mTimings[index];
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::DisplayTimingValues
//
//-----------------------------------------------------------------------------

void rvTimingCollection::DisplayTimingValues( void ) {
	// Fixme: the display resulting from this is really, really a mess - quite unreadable.
	common->Printf ( "Timer: \n" );
	for( int i = 0; i < mTimings.Num(); i++ ) {
		if ( (int)(mTimings[i].mCurValue) ) {
			common->Printf( "\t%s %3i\n", mTimings[i].mName.c_str(), (int)(mTimings[i].mCurValue) );
		}
	}
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::OutputToFile
//
//-----------------------------------------------------------------------------

void rvTimingCollection::OutputToFile( void )
{
	idFile	*file	= NULL;
	idStr	name;

	// Fixme: Do we have any good information for building a better file name here?

	name = "Timings/output.txt";

	file = fileSystem->OpenFileWrite ( name );
	if ( !file )
	{
		return;
	}

	file->Printf( "Total frames = %d\n\n", mFramesRecorded );

	file->Printf( "%-36s %-9s %-9s %-9s %-9s %-9s %-9s %-9s\n\n",
		"Name", "Total", "Average", "Peak", "Limit", "Exceeded", "Exceed*5", "Calls" );

	for( int i = 0; i < mTimings.Num(); i++ )
	{
		mTimings[i].OutputDataToFile( file, mFramesRecorded );
		if( !( ( i + 1 )%3) )	// break up the prints into groups of 3 to make scanning visually easier.
		{
			file->Printf( "\n" );
		}
	}

	file->Printf( "\n\nInformation about categories\n\n" );

	for( int i = 0; i < mTimings.Num(); i++ )
	{
		mTimings[i].OutputInfoToFile( file );
	}

	fileSystem->CloseFile ( file );
	file = NULL;
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::AppendToDict
//
//-----------------------------------------------------------------------------

void rvTimingCollection::AppendToDict( idDict *dict )
{
	if( !mCurrentlyUpdating )
	{
		return;
	}

	for( int i = 0; i < mTimings.Num(); i++ )
	{
		dict->Set ( mTimings[i].mName.c_str(), va( "%0.3g\t%0.3g\t", mTimings[i].mCurValue, mTimings[i].mTotalValue ) );
	}
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::InitFrame
//
//-----------------------------------------------------------------------------

void rvTimingCollection::InitFrame( bool inUse, bool displayText, bool outputFileWhenDone )
{
	// Do our quick reject test to ensure this is quick when not in use.

	if( !inUse )
	{
		if( mCurrentlyUpdating )
		{
			if( outputFileWhenDone )
			{
				OutputToFile();
			}
			mCurrentlyUpdating = 0;
		}
		return;
	}

	mCurrentlyUpdating = 1;
	mUpdates++;
	mFramesRecorded++;

	if( mUpdates >= 10 && displayText )
	{
		// ??  If we display output every single frame, we get REALLY bogged down.  It is bad.

		DisplayTimingValues();

		mUpdates = 0;

		return;
	}

	// Clear only the curValues and record information.

	for( int i = 0; i < mTimings.Num(); i++ )
	{
		if( mTimings[i].mCurValue > mTimings[i].mPeakValue )
		{
			mTimings[i].mPeakValue = mTimings[i].mCurValue;
		}

		if( mTimings[i].mLimit > 0.0 && mTimings[i].mCurValue > mTimings[i].mLimit )
		{
			mTimings[i].mLimitExceeded++;
		}

		if( mTimings[i].mLimit > 0.0 && mTimings[i].mCurValue > mTimings[i].mLimit * 5 )
		{
			mTimings[i].mLimitExceededTimesFive++;
		}

		mTimings[i].mCurValue = 0.0f;
	}
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::TimingStart
//
//-----------------------------------------------------------------------------

void rvTimingCollection::_TimingStart( const char *timingName, const char *fileName, const int lineNum )
{
	// Do our quick reject test to ensure this is quick when not in use.

	if( !mCurrentlyUpdating )
	{
		return;
	}

	// Go up the timer list.

	mCurTimer++; 
	assert( mCurTimer < MAX_TIMERS );

	// Keep track of the current function being timed in case we nest and need to know our parent.

	mTimerName[mCurTimer] = timingName;

	// Set the information about this timer.

	rvSingleTiming *curTiming = GetTiming( mTimerName[mCurTimer] );
	
	if( mCurTimer == 0 )
	{
		curTiming->mParentName = "base";
	}
	else
	{
		curTiming->mParentName = mTimerName[mCurTimer - 1];
	}
	curTiming->mStartFile		= fileName;
	curTiming->mStartLine		= lineNum;
	curTiming->mDisplayLevel	= mCurTimer - 1;

	// Start the timer; do it last to avoid timing the rest of this function.

	mTimer[mCurTimer].Clear();
	mTimer[mCurTimer].Start();
}

//-----------------------------------------------------------------------------
//
//								rvTimingCollection::TimingEnd
//
//-----------------------------------------------------------------------------

void rvTimingCollection::_TimingStop( double msecLimit, const char *fileName, const int lineNum )
{
	// Do our quick reject test to ensure this is quick when not in use.

	if( !mCurrentlyUpdating )
	{
		return;
	}

	// Stop our timer first so that we don't log time from the rest of this function.

	mTimer[mCurTimer].Stop();

	// Update incidental information on the timer.

	rvSingleTiming *curTiming = GetTiming( mTimerName[mCurTimer] );
	
	curTiming->mEndFile = fileName;
	curTiming->mEndLine = lineNum;

	curTiming->mLimit	= msecLimit;

	// Add the actual timing values to the rvSingleTiming

	double	frameTime = mTimer[mCurTimer].Milliseconds();

	curTiming->mCurValue	+= frameTime;
	curTiming->mTotalValue	+= frameTime;

	curTiming->mTotalUpdates++;

	// Go back down the timer list.

	mCurTimer--;
	assert( mCurTimer >= 0 );
}

#endif
