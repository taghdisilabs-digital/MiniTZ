// Biella D17: fine coated-metal grain. World centimeters; derivative filtered.
// Separate from accepted masonry/asphalt: no displacement or state mutation.
struct FServiceNoise
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
        float3 u = f*f*f*(f*(f*6.0 - 15.0) + 10.0);
        return lerp(lerp(lerp(Hash(i), Hash(i+float3(1,0,0)), u.x),
                         lerp(Hash(i+float3(0,1,0)), Hash(i+float3(1,1,0)), u.x), u.y),
                    lerp(lerp(Hash(i+float3(0,0,1)), Hash(i+float3(1,0,1)), u.x),
                         lerp(Hash(i+float3(0,1,1)), Hash(i+float3(1,1,1)), u.x), u.y), u.z);
    }
    float Filtered(float3 p)
    {
        float footprint = max(length(ddx(p)), length(ddy(p)));
        return (Value(p)*2.0-1.0) * (1.0-smoothstep(.20,.50,footprint));
    }
};
FServiceNoise Grain;
float3 P = Position * clamp(DetailScale,.25,4.0);
float height = .12*Grain.Filtered(P*.055)
             + .26*Grain.Filtered(P*.70+float3(11.1,3.7,8.9))
             + .16*Grain.Filtered(P*2.8+float3(2.3,7.1,4.9));
float3 N = normalize(SurfaceNormal);
float3 dx = ddx(Position), dy = ddy(Position);
float3 rx = cross(dy,N), ry = cross(N,dx);
float det = dot(dx,rx);
float3 gradient = (ddx(height)*rx+ddy(height)*ry)*sign(det)/max(abs(det),.00001);
ReliefNormal = normalize(N-clamp(ReliefCm,0.0,.20)*gradient);
return .5+.5*height;
