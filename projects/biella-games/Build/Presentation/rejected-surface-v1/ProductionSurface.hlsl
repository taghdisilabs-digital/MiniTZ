// Biella D03: static masonry/asphalt microrelief, in world centimetres.
// Editable shader source is embedded verbatim in M_ProductionSurface.
// No time, camera-relative UVs, displacement, emission or gameplay state.
// Smoothly remove each frequency before it becomes smaller than two pixels.
float3 P = Position * clamp(DetailScale, 0.25, 4.0);
float3 q = float3(dot(P, float3(0.037, 0.051, 0.043)),
                  dot(P, float3(0.311, -0.271, 0.293)),
                  dot(P, float3(-1.137, 1.213, 0.973)));
float3 weight = saturate(1.0 - fwidth(q) / 3.14159265);
weight *= weight * (3.0 - 2.0 * weight);
float height = dot(sin(q), weight * float3(0.50, 0.32, 0.18));

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
