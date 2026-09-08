// Biella service floor. Coordinates are centimeters relative to the site.
// Static material response only: no displacement, collision, or game state.
struct FGroundNoise
{
    float Hash(float2 p) { return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453); }
    float Value(float2 p) {
        float2 i=floor(p), f=frac(p); f=f*f*(3.0-2.0*f);
        return lerp(lerp(Hash(i),Hash(i+float2(1,0)),f.x),
                    lerp(Hash(i+float2(0,1)),Hash(i+1),f.x),f.y);
    }
    float Detail(float2 p) {
        return (Value(p)-.5)*(1.0-smoothstep(.20,.50,max(length(ddx(p)),length(ddy(p)))));
    }
};
FGroundNoise Grain;
float2 p=(Position-SiteOrigin).xy;
float age=Grain.Value(p*.025+11.7);
float grit=Grain.Detail(p*1.6)+.42*Grain.Detail(p*5.3);
float low=Grain.Value(p*.014)+.24*Grain.Value(p*.049+37.1);
// Separated low spots collect water; intervening rough aggregate stays visible.
float puddle=smoothstep(.63,.72,low);
float damp=smoothstep(.34,.69,low);
float inside=step(45.0,p.x)*step(p.x,495.0)*step(abs(p.y),215.0);
float edge=min(min(p.x-45.0,495.0-p.x),215.0-abs(p.y));
float painted=inside*(1.0-smoothstep(8.0,8.8,edge));
float stripePhase=(p.x+p.y)*.04;
float stripeAA=max(fwidth(stripePhase),.015);
float stripe=smoothstep(.5-stripeAA,.5+stripeAA,frac(stripePhase));
float eroded=smoothstep(.25,.38,age+.16*grit);
float3 concrete=float3(.12,.132,.14)*lerp(.62,1.2,age)+grit*.026;
float3 steel=float3(.16,.185,.20)*lerp(.60,1.05,age)+grit*.012;
float3 paint=lerp(float3(.016,.022,.025),float3(.46,.29,.058),stripe);
float wear=painted*eroded;
OutColor=lerp(lerp(concrete,steel,inside),paint,wear)*lerp(1.0,.42,damp);
OutMetal=inside*.78*(1.0-wear)*(1.0-.35*age);
OutRough=lerp(lerp(.83,.40,inside)+grit*.08,.065,puddle);
// Tiny repeated amber lenses on the inner boundary are controlled by the
// existing native power boolean. No broad status tint or autonomous animation.
float lens=inside*step(13.0,edge)*step(edge,15.0)*step(.72,frac((p.x+p.y)*.025));
OutColor=lerp(OutColor,float3(.065,.029,.007),lens);
OutEmission=lens*saturate(Powered)*float3(2.8,.43,.012);
float height=(.10*Grain.Detail(p*.19)+.032*grit)*(1.0-puddle);
float3 N=normalize(SurfaceNormal),dx=ddx(Position),dy=ddy(Position);
float3 rx=cross(dy,N),ry=cross(N,dx);
float det=dot(dx,rx);
float3 gradient=(ddx(height)*rx+ddy(height)*ry)*sign(det)/max(abs(det),.00001);
OutNormal=normalize(N-gradient);
return 0.0;
