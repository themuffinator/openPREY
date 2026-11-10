// Copyright (C) 2026 DarkMatter Productions
// Exact sRGB filtering for explicitly authored colour textures; alpha is linear.
#ifndef OPENQ4_SRGB_H
#define OPENQ4_SRGB_H
#include <array>
#include <cmath>
namespace openq4SRGB {
inline float Decode(float x) {
    return x <= 0.04045f ? x/12.92f : std::pow((x+0.055f)/1.055f, 2.4f);
}
inline float Encode(float x) {
    return x <= 0.0031308f ? x*12.92f : 1.055f*std::pow(x, 1.0f/2.4f)-0.055f;
}
inline void Downsample(const unsigned char *input, int width, int height, unsigned char *output) {
    static const std::array<float,256> linear = [] {
        std::array<float,256> values{};
        for (int i=0; i<256; ++i) { values[i]=Decode(i/255.0f); }
        return values;
    }();
    const int w=width>1 ? width/2 : 1, h=height>1 ? height/2 : 1;
    const int nx=width>1 ? 2 : 1, ny=height>1 ? 2 : 1;
    for (int y=0; y<h; ++y) for (int x=0; x<w; ++x) {
        float sum[3]={0,0,0}; int alpha=0;
        for (int dy=0; dy<ny; ++dy) for (int dx=0; dx<nx; ++dx) {
            const unsigned char *p=input+((y*ny+dy)*width+x*nx+dx)*4;
            for (int c=0; c<3; ++c) { sum[c]+=linear[p[c]]; }
            alpha+=p[3];
        }
        unsigned char *p=output+(y*w+x)*4;
        for (int c=0; c<3; ++c) {
            const int encoded=int(255.0f*Encode(sum[c]/(nx*ny))+0.5f);
            p[c]=static_cast<unsigned char>(encoded<0 ? 0 : (encoded>255 ? 255 : encoded));
        }
        p[3]=static_cast<unsigned char>((alpha+nx*ny/2)/(nx*ny));
    }
}
}
#endif
