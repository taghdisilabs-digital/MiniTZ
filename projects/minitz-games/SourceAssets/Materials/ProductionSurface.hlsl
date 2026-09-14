// Biella D03: static masonry/asphalt microrelief, in world centimetres.
// Editable shader source is embedded verbatim in M_ProductionSurface.
// No time, camera-relative UVs, displacement, emission or gameplay state.
// Smoothly remove each frequency before it becomes smaller than two pixels.
struct FSurfaceNoise
{
    float Hash(float3 p)
    {
        p = frac(p * 0.1031);
        p += dot(p, p.yzx + 33.33);
        return frac((p.x + p.y) * p.z);
    }
    float Value(float3 p)
    {
        float3 i = floor(p), f = frac(p);
        // Quintic interpolation keeps gradients continuous at cell boundaries.
        float3 u = f*f*f*(f*(f*6.0 - 15.0) + 10.0);
        return lerp(lerp(lerp(Hash(i), Hash(i+float3(1,0,0)), u.x),
                         lerp(Hash(i+float3(0,1,0)), Hash(i+float3(1,1,0)), u.x), u.y),
                    lerp(lerp(Hash(i+float3(0,0,1)), Hash(i+float3(1,0,1)), u.x),
                         lerp(Hash(i+float3(0,1,1)), Hash(i+float3(1,1,1)), u.x), u.y), u.z);
    }
    float Filtered(float3 p)
    {
        float footprint = max(length(ddx(p)), length(ddy(p)));
        float weight = 1.0 - smoothstep(0.20, 0.50, footprint);
        return (Value(p) * 2.0 - 1.0) * weight;
    }
};
FSurfaceNoise Grain;
float3 P = Position * clamp(DetailScale, 0.25, 4.0);
float height = 0.28 * Grain.Filtered(P * 0.022)
             + 0.42 * Grain.Filtered(P * 0.17 + float3(11.1,3.7,8.9))
             + 0.30 * Grain.Filtered(P * 0.95 + float3(2.3,7.1,4.9));

// Surface-gradient bump mapping in world space, with a guarded grazing case.
// Pixel derivatives include the same filtered height used for albedo/roughness.
float3 N = normalize(SurfaceNormal);
float3 dx = ddx(Position), dy = ddy(Position);
float3 rx = cross(dy, N), ry = cross(N, dx);
float det = dot(dx, rx);
float3 gradient = (ddx(height) * rx + ddy(height) * ry)
                  * sign(det) / max(abs(det), 0.00001);
ReliefNormal = normalize(N - clamp(ReliefCm, 0.0, 0.20) * gradient);
return 0.5 + 0.5 * height;
