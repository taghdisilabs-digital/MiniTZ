// Biella coated service steel. Real point-hit positions are mapped in panel
// local space so scuffs remain on the sheet during native debris simulation.
// Surface relief only: no WPO, opacity, extra collision or damage simulation.
struct FPanelSurface
{
    float Hash(float2 p)
    {
        uint2 c=asuint(int2(p));
        uint h=c.x*0x9e3779b9u ^ c.y*0x85ebca6bu;
        h^=h>>16; h*=0x7feb352du; h^=h>>15; h*=0x846ca68bu; h^=h>>16;
        return float(h & 0x00ffffffu)*(1.0/16777216.0);
    }
    float Noise(float2 p)
    {
        float2 i=floor(p),f=frac(p),u=f*f*f*(f*(f*6-15)+10);
        return lerp(lerp(Hash(i),Hash(i+float2(1,0)),u.x),
                    lerp(Hash(i+float2(0,1)),Hash(i+1),u.x),u.y);
    }
    float Mark(float2 delta,float aa)
    {
        // Irregular chipped coating around a small closed impact depression.
        // Neither the mark nor the normal creates a visual through-hole.
        float r=length(delta);
        float rim=r-(4.2+1.8*Noise(delta*.9)+.7*Noise(delta*2.3));
        return 1-smoothstep(-aa,aa,rim);
    }
};
FPanelSurface S;
float3 cm=LocalPosition*PanelSize*.01;
float2 p=cm.yz;
float aa=max(.06,.7*max(length(ddx(p)),length(ddy(p))));
float coarse=S.Noise(p*.055+float2(9.1,3.7));
float streak=S.Noise(p*float2(.23,.019));
float fine=lerp(S.Noise(p*2.5),.5,smoothstep(.25,.8,aa*2.5));
float edgeDistance=min(PanelSize.y*.5-abs(p.x),105-abs(p.y));
float edgeWear=(1-smoothstep(.5,3.2,edgeDistance))*smoothstep(.32,.7,coarse);
float oxide=smoothstep(.61,.83,streak)*(1-smoothstep(-98,-48,p.y))*.36;
float3 paint=float3(.055,.074,.08)*(.78+.35*coarse+.1*streak);
float3 color=lerp(paint,float3(.18,.19,.18),edgeWear*.65);
color=lerp(color,float3(.12,.059,.028),oxide);
float rough=clamp(.48+.17*coarse+.08*streak+.18*oxide,.42,.82);
float metal=lerp(.08,.82,edgeWear*.65);
float height=.003*(fine-.5);
float2 a=p-ImpactA.yz*PanelSize.yz*.01;
float2 b=p-ImpactB.yz*PanelSize.yz*.01;
float enabled=step(.001,DamageAmount);
float marks=max(S.Mark(a,aa),S.Mark(b,aa))*enabled;
float radius=min(length(a),length(b));
float depression=(1-smoothstep(.4,2.2,radius))*enabled;
float scuff=(1-smoothstep(5,10,radius))*(.15+.35*coarse)*enabled;
color=lerp(color,float3(.10,.115,.12),scuff);
color=lerp(color,float3(.31,.32,.30)*(.8+.32*fine),marks);
color=lerp(color,float3(.028,.034,.038),depression*.88);
metal=lerp(metal,.87,marks);
rough=lerp(rough,.34+.13*fine,marks);
height-=.055*marks+.12*depression;
float3 n=normalize(SurfaceNormal),dx=ddx(Position),dy=ddy(Position);
float3 rx=cross(dy,n),ry=cross(n,dx); float det=dot(dx,rx);
float3 gradient=(ddx(height)*rx+ddy(height)*ry)*sign(det)/max(abs(det),.00001);
OutColor=color;
OutMetal=metal;
OutRough=rough;
OutNormal=normalize(n-gradient);
return 0;
