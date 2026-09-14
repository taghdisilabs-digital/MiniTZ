// Biella service floor. Coordinates are centimeters relative to the site.
// Static material response only: no displacement, collision, or game state.
struct FGroundNoise
{
    // Integer lattice hashing avoids transcendental/large-multiplier rounding
    // in the moisture field. Neighboring cells share exactly the same corners.
    float Hash(float2 p) {
        uint2 cell=asuint(int2(p));
        uint h=cell.x*0x9e3779b9u ^ cell.y*0x85ebca6bu;
        h^=h>>16; h*=0x7feb352du; h^=h>>15; h*=0x846ca68bu; h^=h>>16;
        return float(h & 0x00ffffffu)*(1.0/16777216.0);
    }
    float Value(float2 p) {
        float2 i=floor(p), f=frac(p); f=f*f*f*(f*(f*6.0-15.0)+10.0);
        return lerp(lerp(Hash(i),Hash(i+float2(1,0)),f.x),
                    lerp(Hash(i+float2(0,1)),Hash(i+1),f.x),f.y);
    }
    float2 Turn(float2 p) { return float2(.8*p.x-.6*p.y,.6*p.x+.8*p.y); }
    float Field(float2 p) {
        return .57*Value(p)+.29*Value(Turn(p)*2.07+17.3)+.14*Value(Turn(p)*4.31-8.1);
    }
    float Detail(float2 p) {
        return (Value(p)-.5)*(1.0-smoothstep(.20,.50,max(length(ddx(p)),length(ddy(p)))));
    }
};
FGroundNoise Grain;
float2 p=(Position-SiteOrigin).xy;
float age=Grain.Field(p*.018+11.7);
float grit=Grain.Detail(p*1.6)+.42*Grain.Detail(p*5.3);
// Smooth warped low spots avoid the former axis-aligned value-noise islands.
float2 warp=float2(Grain.Field(p*.004+7.1),Grain.Field(p*.004-31.6))-.5;
float low=Grain.Field(Grain.Turn(p)*.007+warp*1.9);
float puddle=smoothstep(.40,.68,low);
float damp=smoothstep(.25,.68,low);
float inside=step(45.0,p.x)*step(p.x,495.0)*step(abs(p.y),215.0);
// The authored apron ends at these surveyed mesh bounds. Moisture drains away
// before that edge instead of clipping a reflective rectangle onto the street.
// Vary the drying width in world space; retain the inset conductive plates and
// their exact native hazard footprint. This mask changes shading only.
float apronEdge=min(min(p.x+521.4,532.0-p.x),365.4-abs(p.y));
float dryingWidth=lerp(85.0,145.0,Grain.Field(Grain.Turn(p)*.009+43.7));
float apron=max(inside,smoothstep(0.0,dryingWidth,max(0.0,apronEdge)));
puddle*=apron;
damp*=apron;
float edge=min(min(p.x-45.0,495.0-p.x),215.0-abs(p.y));
float painted=inside*(1.0-smoothstep(8.0,8.8,edge));
float stripePhase=(p.x+p.y)*.04;
float stripeAA=max(fwidth(stripePhase),.015);
float stripe=smoothstep(.5-stripeAA,.5+stripeAA,frac(stripePhase));
float eroded=smoothstep(.25,.38,age+.16*grit);
float3 concrete=float3(.082,.091,.098)*lerp(.88,1.12,age)+grit*.012;
float3 steel=float3(.16,.185,.20)*lerp(.85,1.05,age)+grit*.009;
float3 paint=lerp(float3(.016,.022,.025),float3(.46,.29,.058),stripe);
float wear=painted*eroded;
// Match the adjoining MI_Street's dry material class at the outer edge;
// preserve the physical slab joints rather than fading geometry or opacity.
float3 dryEdge=float3(.08,.10,.12)*.97;
OutColor=lerp(dryEdge,lerp(lerp(concrete,steel,inside),paint,wear),apron)*lerp(1.0,.72,damp);
OutMetal=inside*.78*(1.0-wear)*(1.0-.35*age);
OutRough=lerp(lerp(.88,lerp(.78,.39,inside)+grit*.025,apron),.095,puddle);
// Tiny repeated amber lenses on the inner boundary are controlled by the
// existing native power boolean. No broad status tint or autonomous animation.
float lens=inside*step(13.0,edge)*step(edge,15.0)*step(.72,frac((p.x+p.y)*.025));
OutColor=lerp(OutColor,float3(.065,.029,.007),lens);
OutEmission=lens*saturate(Powered)*float3(2.8,.43,.012);
// Object-stable small aggregate relief. Sample the smooth height field directly,
// fading detail with pixel footprint. G-buffer diagnostics distinguish moisture
// discontinuities from normals instead of inferring their cause from lit views.
float2 detail=p*.14;
float filtered=1.0-smoothstep(.20,.50,max(length(ddx(detail)),length(ddy(detail))));
float2 slope=float2(
    Grain.Field(detail+float2(.07,0))-Grain.Field(detail-float2(.07,0)),
    Grain.Field(detail+float2(0,.07))-Grain.Field(detail-float2(0,.07)));
float3 N=normalize(SurfaceNormal);
float3 gradient=float3(slope,0)*.018*filtered*(1.0-puddle)*apron;
gradient-=N*dot(N,gradient);
OutNormal=normalize(N-gradient);
return 0.0;
