// Biella service isolator face. Object coordinates retain the existing cube,
// component transform and interaction collider. No WPO or state simulation.
struct FSwitchSurface
{
    float Hash(float2 p)
    {
        uint2 cell=asuint(int2(p));
        uint h=cell.x*0x9e3779b9u ^ cell.y*0x85ebca6bu;
        h^=h>>16; h*=0x7feb352du; h^=h>>15; h*=0x846ca68bu; h^=h>>16;
        return float(h & 0x00ffffffu)*(1.0/16777216.0);
    }
    float Noise(float2 p)
    {
        float2 i=floor(p), f=frac(p), u=f*f*f*(f*(f*6-15)+10);
        return lerp(lerp(Hash(i),Hash(i+float2(1,0)),u.x),
                    lerp(Hash(i+float2(0,1)),Hash(i+1),u.x),u.y);
    }
    float Box(float2 p,float2 size,float radius)
    {
        float2 d=abs(p)-size+radius;
        return length(max(d,0))+min(max(d.x,d.y),0)-radius;
    }
    float Mask(float distance,float aa) { return 1-smoothstep(-aa,aa,distance); }
};
FSwitchSurface S;
// The -X face is the existing cabinet approach face; local mapping survives
// actor translation/rotation and does not repeat controls on the cube sides.
float2 p=float2(-LocalPosition.y*.42,LocalPosition.z*.55);
float aa=max(.055,.65*max(length(ddx(p)),length(ddy(p))));
float front=1-smoothstep(-49.95,-49.5,LocalPosition.x);
float coarse=S.Noise(p*.28+float2(7.3,1.9));
float fine=lerp(S.Noise(p*3.2),.5,smoothstep(.2,.65,aa*3.2));
float edge=1-S.Mask(S.Box(p,float2(19.4,25.9),.5),aa);
float recess=S.Mask(S.Box(p-float2(0,-1),float2(15.8,20.5),1.1),aa);
float gasket=S.Mask(S.Box(p-float2(0,-1),float2(16.3,21),1.2),aa)-recess;
float wear=smoothstep(.56,.76,coarse)*(edge*.75+.10);
float3 color=lerp(float3(.068,.083,.087),float3(.19,.20,.19),wear);
float metal=lerp(.12,.78,wear), rough=.52+.12*coarse;
color=lerp(color,float3(.025,.033,.036)*( .8+.4*coarse),recess);
color=lerp(color,float3(.009,.012,.012),gasket);
rough=lerp(rough,.70,gasket);
float height=-.035*recess-.02*gasket+.004*(fine-.5);
// Four recessed, slotted fixings. Detail integrates into the faceplate rather
// than adding non-colliding silhouettes beyond the original switch envelope.
float2 fastener=abs(p)-float2(18,24);
float bolt=S.Mask(length(fastener)-1.02,aa);
float socket=S.Mask(length(fastener)-1.25,aa)-bolt;
float slot=S.Mask(S.Box(float2(fastener.x+fastener.y,fastener.x-fastener.y)*.7071,float2(.7,.13),.04),aa)*bolt;
color=lerp(color,float3(.008,.010,.011),socket);
color=lerp(color,float3(.23,.24,.23)*( .85+.3*fine),bolt);
color=lerp(color,float3(.009,.012,.013),slot);
metal=lerp(metal,.88,bolt*(1-slot)); rough=lerp(rough,.36,bolt);
height+=.035*bolt-.025*slot;
// Recessed isolator grip and enamel index marks, fixed like the old switch.
float2 k=p-float2(0,-4);
float ring=S.Mask(length(k)-6.8,aa);
float rubber=S.Mask(length(k)-5.9,aa);
float grip=S.Mask(S.Box(k,float2(1.35,4.6),.6),aa);
color=lerp(color,float3(.22,.24,.24),ring);
color=lerp(color,float3(.010,.014,.017),rubber);
color=lerp(color,float3(.05,.061,.067)*( .8+.4*fine),grip);
metal=lerp(metal,.82,ring); metal=lerp(metal,0,rubber);
rough=lerp(rough,.36,ring); rough=lerp(rough,.65,rubber);
height+=.018*ring+.045*grip;
float ticks=S.Mask(S.Box(abs(k)-float2(0,8.2),float2(.22,1.05),.08),aa);
float arrow=S.Mask(S.Box(k-float2(0,2.7),float2(.33,.8),.1),aa)*grip;
color=lerp(color,float3(.51,.53,.47),saturate(ticks+arrow)*.75);
// Worn caution triangle and lightning notch are original generic symbols.
float2 t=(p-float2(-9,14))/3.2;
float cautionMask=S.Mask(max(abs(t.x)*.866+t.y*.5-.46,-t.y-.52)*3.2,aa);
float boltMark=S.Mask(S.Box(p-float2(-9,14),float2(.22,1.2),.05),aa)*cautionMask;
color=lerp(color,float3(.44,.29,.065),cautionMask*(.62+.2*coarse));
color=lerp(color,float3(.014,.018,.018),boltMark);
// Only the lens consumes the native safe/live color and emission. Steel,
// rubber, oxide and dirt retain their material class through the power change.
float lensFrame=S.Mask(S.Box(p-float2(3.5,14),float2(6.9,2.25),.75),aa);
float lens=S.Mask(S.Box(p-float2(3.5,14),float2(5.8,1.15),.55),aa);
color=lerp(color,float3(.16,.18,.18),lensFrame);
color=lerp(color,BaseColor*.65,lens);
metal=lerp(metal,.7,lensFrame); metal=lerp(metal,0,lens);
rough=lerp(rough,.22,lens);
height+=.025*lensFrame+.02*lens;
float3 side=float3(.055,.067,.071)*( .8+.25*coarse);
OutColor=lerp(side,color,front);
OutMetal=lerp(.1,metal,front);
OutRough=lerp(.6,clamp(rough,.22,.84),front);
OutEmission=BaseColor*Emission*5*front*lens;
float3 n=normalize(SurfaceNormal), dx=ddx(Position),dy=ddy(Position);
float3 rx=cross(dy,n), ry=cross(n,dx); float det=dot(dx,rx);
float3 gradient=(ddx(height)*rx+ddy(height)*ry)*sign(det)/max(abs(det),.00001);
OutNormal=normalize(n-front*gradient);
return 0;
