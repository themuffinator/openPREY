#!/usr/bin/env python3
"""Independent reference for the PBR shading kernel (src/renderer/PBRMath.h).

Laboratory oracles evaluate the equations the shaders evaluate, written out
again here in NumPy so that a regression in the shared C++/GLSL source cannot
hide in the oracle. The fitted polynomials are definitions, not derivations:
their coefficients are copied and their accuracy is tested in
tools/tests/native/PBRMathTest.cpp against the integrated split-sum table.

It also models the laboratory's specimen sphere as the sampling camera sees
it, so oracles can predict view-dependent terms pixel by pixel.
"""
from __future__ import annotations

import numpy as np

# The sampling camera (pbr-lab.json 'sampling') sits 400 units in front of the
# specimen sphere (radius 72, generate_pbr_validation_map.sphere_ase) on its
# axis. The 1280x800 view uses Quake 4's 4:3-base field of view widened for
# 16:10: tan(fov_y / 2) = 0.75, a focal length of 400 / 0.75 pixels.
SAMPLING_WIDTH, SAMPLING_HEIGHT = 1280, 800
SAMPLING_FOCAL = 400.0 / 0.75
SAMPLING_DISTANCE = 400.0
SPECIMEN_RADIUS = 72.0


def decode(x):
    """sRGB decode, continued above one (PBRSRGBToLinearExtended)."""
    x = np.maximum(np.asarray(x, dtype=np.float64), 0.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def encode(x):
    """sRGB encode, continued above one (PBRLinearToSRGBExtended)."""
    x = np.maximum(np.asarray(x, dtype=np.float64), 0.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def byte_decode(value):
    """A stored sRGB colour byte as linear light."""
    return decode(np.asarray(value, dtype=np.float64) / 255.0)


def roughness(r):
    return np.clip(r, 0.045, 1.0)


def filtered_roughness(r, normal_variance):
    alpha = roughness(r) ** 2
    kernel = np.clip(2.0 * normal_variance, 0.0, 0.18)
    return np.sqrt(np.sqrt(np.clip(alpha * alpha + kernel, 0.0, 1.0)))


def shading_nov(nov):
    return np.clip(nov, 1.0e-4, 1.0)


def fresnel_weight(x):
    return (1.0 - np.clip(x, 0.0, 1.0)) ** 5


def specular_albedo(nov, r):
    r = roughness(r)
    u = np.sqrt(np.clip(nov, 0.1, 1.0))
    c0 = 1.30429459 + u * (-0.93026197 + u * 0.659094632)
    c1 = -4.92084694 + u * (15.8142557 + u * (-11.6078072))
    c2 = 14.91817 + u * (-55.1149101 + u * 44.208828)
    c3 = -15.5533714 + u * (63.1911125 + u * (-55.7175789))
    c4 = 5.33295727 + u * (-24.152729 + u * 22.883503)
    return np.clip(c0 + r * (c1 + r * (c2 + r * (c3 + r * c4))), 0.3, 1.0)


def specular_bias(nov, r):
    rr = roughness(r)
    u = np.sqrt(np.clip(nov, 0.1, 1.0))
    c0 = 1.86122463 + u * (-5.8115519 + u * (6.04423784 + u * (-2.09929099 + u * 0.00579774298)))
    c1 = -10.18743 + u * (89.0484333 + u * (-235.623025 + u * (248.992105 + u * (-92.3278808))))
    c2 = 5.56878037 + u * (-249.036709 + u * (878.661836 + u * (-1056.69664 + u * 422.086637)))
    c3 = 44.7441308 + u * (190.739295 + u * (-1169.02785 + u * (1638.08811 + u * (-705.807224))))
    c4 = -78.0086265 + u * (56.2170228 + u * (581.732087 + u * (-1066.83411 + u * 508.070166)))
    c5 = 36.1835707 + u * (-81.8335126 + u * (-60.7151143 + u * (237.799529 + u * (-131.834229))))
    bias = c0 + rr * (c1 + rr * (c2 + rr * (c3 + rr * (c4 + rr * c5))))
    return np.clip(bias, 0.0, specular_albedo(nov, r))


def energy_compensation(f0, albedo):
    return 1.0 + np.clip(f0, 0.0, 1.0) * (1.0 / np.clip(albedo, 0.3, 1.0) - 1.0)


def specular_occlusion(nov, ao, r):
    r = roughness(r)
    a = np.clip(ao, 0.0, 1.0)
    lobe = np.exp2(-16.0 * r * r - 1.0)
    return np.clip(np.power(np.clip(nov, 0.0, 1.0) + a, lobe) - 1.0 + a, 0.0, 1.0)


def multi_bounce_ao(visibility, albedo):
    v = np.clip(visibility, 0.0, 1.0)
    x = np.clip(albedo, 0.0, 1.0)
    bounced = ((v * (2.0404 * x - 0.3324) + (0.6417 - 4.7951 * x)) * v + (2.7552 * x + 0.6903)) * v
    return np.clip(bounced, v, 1.0)


def uniform_environment_specular(f0, nov, r):
    albedo = specular_albedo(nov, r)
    f = np.clip(f0, 0.0, 1.0)
    return (f * albedo + (1.0 - f) * specular_bias(nov, r)) * energy_compensation(f, albedo)


def uniform_environment(radiance, albedo, metallic, r, ao, nov, horizon=1.0):
    """Linear radiance an authored ambient light leaves: a uniform environment
    of radiance `radiance` (E / pi, per channel). Arrays broadcast; the colour
    axis is last."""
    radiance = np.asarray(radiance, dtype=np.float64)
    albedo = np.asarray(albedo, dtype=np.float64)
    nov = shading_nov(np.asarray(nov, dtype=np.float64))[..., None]
    r = np.asarray(r, dtype=np.float64)
    r = r[..., None] if r.ndim else r
    f0 = 0.04 * (1.0 - metallic) + albedo * metallic
    diffuse_color = albedo * (1.0 - metallic)
    fresnel = f0 + (np.maximum(1.0 - r, f0) - f0) * fresnel_weight(nov)
    specular = (uniform_environment_specular(f0, nov, r)
                * multi_bounce_ao(specular_occlusion(nov, ao, r), f0) * horizon)
    diffuse = (1.0 - fresnel) * diffuse_color * multi_bounce_ao(ao, diffuse_color)
    return (diffuse + specular) * radiance


def sampling_sphere(width=SAMPLING_WIDTH, height=SAMPLING_HEIGHT, focal=SAMPLING_FOCAL,
                    distance=SAMPLING_DISTANCE, radius=SPECIMEN_RADIUS):
    """Per-pixel N.V and normal variance of the specimen sphere.

    Returns (nov, variance), NaN outside the sphere. The variance is the
    shaders' 0.5 * (|dN/dx|^2 + |dN/dy|^2) of the final normal, from finite
    differences between neighbouring pixels' analytic normals.
    """
    xs = (np.arange(width) + 0.5 - width / 2.0) / focal
    ys = (height / 2.0 - (np.arange(height) + 0.5)) / focal
    dx, dy = np.meshgrid(xs, ys)
    direction = np.stack([dx, dy, np.ones_like(dx)], axis=-1)
    direction /= np.linalg.norm(direction, axis=-1, keepdims=True)
    centre = np.array([0.0, 0.0, distance])
    b = direction @ centre
    disc = b * b - (distance * distance - radius * radius)
    hit = disc >= 0.0
    t = np.where(hit, b - np.sqrt(np.where(hit, disc, 0.0)), np.nan)
    point = direction * t[..., None]
    normal = (point - centre) / radius
    nov = np.where(hit, np.einsum('ijk,ijk->ij', normal, -direction), np.nan)
    ddx = np.zeros_like(normal)
    ddy = np.zeros_like(normal)
    ddx[:, :-1] = normal[:, 1:] - normal[:, :-1]
    ddx[:, -1] = ddx[:, -2]
    ddy[:-1] = normal[1:] - normal[:-1]
    ddy[-1] = ddy[-2]
    variance = 0.5 * (np.einsum('ijk,ijk->ij', ddx, ddx) + np.einsum('ijk,ijk->ij', ddy, ddy))
    return nov, np.where(hit, variance, np.nan)
