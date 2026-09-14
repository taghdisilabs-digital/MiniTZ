// Biella terrace: world-centimetre coating wear, oxide and pooled rainwater.
// No opacity, displacement or gameplay state changes. Derivative-filtered grain.
struct FTerraceNoise
{
    float Hash(float3 p) {p=frac(p*.1031);p+=dot(p,p.yzx+33.33);return frac((p.x+p.y)*p.z);}
    float Value(float3 p) {
        float3 i=floor(p),f=frac(p),u=f*f*(3-2*f);
        return lerp(lerp(lerp(Hash(i),Hash(i+float3(1,0,0)),u.x),lerp(Hash(i+float3(0,1,0)),Hash(i+float3(1,1,0)),u.x),u.y),
                    lerp(lerp(Hash(i+float3(0,0,1)),Hash(i+float3(1,0,1)),u.x),lerp(Hash(i+float3(0,1,1)),Hash(i+float3(1,1,1)),u.x),u.y),u.z);
    }
    float Filtered(float3 p) {return (Value(p)-.5)*(1-smoothstep(.2,.7,max(length(ddx(p)),length(ddy(p)))));}
};
FTerraceNoise noise;
float3 P=Position-float3(10000,3000,0), N=normalize(SurfaceNormal);
float broad=noise.Value(P*.006+float3(2,7,3));
float medium=noise.Value(P*.021)*.65+noise.Value(P*.075+17)*.35;
float grain=noise.Filtered(P*.85);
float upward=smoothstep(.6,.96,N.z);
float wet=Wetness*saturate((broad-.34)*3.8)*lerp(.28,1.0,upward);
float oxide=Wear*.3*smoothstep(.57,.88,medium*.7+broad*.3);
float3 coating=BaseColor*lerp(.65,1.22,broad);
OutColor=lerp(coating,float3(.055,.023,.012),oxide)*lerp(1,.55,wet);
OutMetal=saturate(Metallic)*(1-oxide);
OutRough=clamp(lerp(Roughness+oxide*.25+grain*.12,.115,wet),.105,.94);
float height=.022*noise.Filtered(P*.18)+.007*grain;
float3 dx=ddx(Position),dy=ddy(Position),rx=cross(dy,N),ry=cross(N,dx);
float det=dot(dx,rx);
float3 gradient=(ddx(height)*rx+ddy(height)*ry)*sign(det)/max(abs(det),.00001);
OutNormal=normalize(N-gradient);
return 0.;
