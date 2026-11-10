#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
using byte = unsigned char;
using int64 = long long;
template<class T> T Min(T a, T b) { return std::min(a,b); }
template<class T> T Max(T a, T b) { return std::max(a,b); }
static void *R_StaticAlloc(size_t size) { return std::malloc(size); }
#include "CaptureResampleUnderTest.inc"

int main() {
	for ( int width : { 1, 2, 3, 5, 17 } ) for ( int height : { 1, 2, 3, 7, 13 } ) {
		std::vector<byte> rgba(width*height*4), bgra(rgba.size());
		for ( int y=0; y<height; ++y ) for ( int x=0; x<width; ++x ) {
			const int i=(y*width+x)*4, j=((height-1-y)*width+x)*4;
			rgba[i]=byte(x*11+y); rgba[i+1]=byte(y*13+x); rgba[i+2]=byte(x+y*3); rgba[i+3]=byte(x*3+y*5);
			bgra[j]=rgba[i+2]; bgra[j+1]=rgba[i+1]; bgra[j+2]=rgba[i]; bgra[j+3]=rgba[i+3];
		}
		for ( int outWidth : { 1, 3, 8, 320 } ) for ( int outHeight : { 1, 3, 11, 240 } ) {
			byte *a=R_ResampleCaptureToAspectRGBA(rgba.data(),width,height,outWidth,outHeight);
			byte *b=R_ResampleCaptureToAspectRGBA(bgra.data(),width,height,outWidth,outHeight,true,true);
			if (std::memcmp(a,b,outWidth*outHeight*4)) return 1;
			if (outWidth==width && outHeight==height && std::memcmp(a,rgba.data(),rgba.size())) return 2;
			std::free(a); std::free(b);
		}
	}
	const byte fourPixels[16]={0,4,8,12, 4,8,12,16, 8,12,16,20, 12,16,20,24};
	byte *average=R_ResampleCaptureToAspectRGBA(fourPixels,2,2,1,1);
	const byte expected[4]={6,10,14,18};
	if (std::memcmp(average,expected,4)) return 3;
	std::free(average);
	std::puts("Capture resampling and GL/Vulkan orientation parity passed");
}
