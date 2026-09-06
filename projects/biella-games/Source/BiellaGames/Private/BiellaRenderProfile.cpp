// Copyright Biella Games. All Rights Reserved.
#include "BiellaRenderProfile.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RenderUtils.h"
#include "SceneInterface.h"
#include "SceneView.h"
#include "SceneViewExtension.h"

namespace
{
float CVar(const TCHAR* Name)
{
    const auto* Value=IConsoleManager::Get().FindConsoleVariable(Name);
    return Value ? Value->GetFloat():-1;
}
void Set(const TCHAR* Name,int32 Value)
{
    if (auto* Variable=IConsoleManager::Get().FindConsoleVariable(Name))
    { Variable->Set(Value,ECVF_SetByCode); }
}

// Opt-in game-thread observation of constructed native views, independent of
// the requested profile/cvar. It never edits a view or renderer state.
class FBiellaRenderReadback : public FSceneViewExtensionBase
{
public:
    FBiellaRenderReadback(const FAutoRegister& Register,UGameInstance* InInstance,FString InPath)
        : FSceneViewExtensionBase(Register),Instance(InInstance),Path(MoveTemp(InPath))
    {
        Csv=TEXT("frame,view,aa,requested_aa,screen_percentage,temporal_upsampling,dynamic_res,gi,reflections,vsm,nanite,ray_tracing,tsr_supported,external_upscaler,width,height\n");
    }
    ~FBiellaRenderReadback() override
    {
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);
        if (!FFileHelper::SaveStringToFile(Csv,*Path,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
        { UE_LOG(LogTemp,Error,TEXT("D03_RENDER_READBACK_SAVE_FAILED path=%s"),*Path); }
    }
    void BeginRenderViewFamily(FSceneViewFamily& Family) override
    {
        if (!Instance.IsValid() || !Family.Scene || !Family.Scene->GetWorld() || Family.Scene->GetWorld()->GetGameInstance()!=Instance.Get()) { return; }
        int32 Index=0;
        for (const FSceneView* View:Family.Views)
        {
            Csv+=FString::Printf(TEXT("%llu,%d,%d,%.0f,%.2f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%d,%d,%d,%d\n"),
                static_cast<unsigned long long>(GFrameCounter),Index++,int32(View->AntiAliasingMethod),
                CVar(TEXT("r.AntiAliasingMethod")),CVar(TEXT("r.ScreenPercentage")),CVar(TEXT("r.TemporalAA.Upsampling")),
                CVar(TEXT("r.DynamicRes.OperationMode")),CVar(TEXT("r.DynamicGlobalIlluminationMethod")),CVar(TEXT("r.ReflectionMethod")),
                CVar(TEXT("r.Shadow.Virtual.Enable")),CVar(TEXT("r.Nanite")),CVar(TEXT("r.RayTracing")),SupportsTSR(View->GetShaderPlatform()),
                Family.GetTemporalUpscalerInterface()!=nullptr,View->UnscaledViewRect.Width(),View->UnscaledViewRect.Height());
        }
    }
private:
    TWeakObjectPtr<UGameInstance> Instance;
    FString Path,Csv;
};
}

void BiellaRenderProfile::Configure()
{
    FString Requested;
    const bool Explicit=FParse::Value(FCommandLine::Get(),TEXT("BiellaRenderProfile="),Requested);
    const bool Supports=SupportsTSR(GMaxRHIShaderPlatform);
    if (!Explicit && (CVar(TEXT("r.AntiAliasingMethod"))!=4 || Supports)) { return; }
    FString Selected=Requested;
    if (!Explicit) { Selected=TEXT("ProductionTSR"); }
    if (Selected!=TEXT("ProductionTSR") && Selected!=TEXT("NativeTAA"))
    {
        UE_LOG(LogTemp,Warning,TEXT("D03_RENDER_PROFILE_INVALID requested=%s fallback=NativeTAA"),*Requested);
        Selected=TEXT("NativeTAA");
    }
    if (Selected==TEXT("ProductionTSR") && !Supports)
    {
        UE_LOG(LogTemp,Display,TEXT("D03_RENDER_TSR_UNAVAILABLE fallback=NativeTAA"));
        Selected=TEXT("NativeTAA");
    }
    Set(TEXT("r.AntiAliasingMethod"),Selected==TEXT("NativeTAA") ? 2:4);
    Set(TEXT("r.ScreenPercentage"),100);
    Set(TEXT("r.DynamicRes.OperationMode"),0);
    Set(TEXT("r.TemporalAA.Upsampling"),Selected==TEXT("NativeTAA") ? 0:1);
    UE_LOG(LogTemp,Display,TEXT("D03_RENDER_PROFILE version=1 requested=%s selected=%s supported_tsr=%d aa=%.0f percentage=%.0f"),
        Explicit ? *Requested:TEXT("ProjectDefault"),*Selected,Supports,CVar(TEXT("r.AntiAliasingMethod")),CVar(TEXT("r.ScreenPercentage")));
}

TSharedPtr<FSceneViewExtensionBase,ESPMode::ThreadSafe> BiellaRenderProfile::BeginReadback(UGameInstance* Instance)
{
    FString Path;
    if (!FParse::Value(FCommandLine::Get(),TEXT("BiellaRenderReadback="),Path) || Path.IsEmpty()) { return {}; }
    return FSceneViewExtensions::NewExtension<FBiellaRenderReadback>(Instance,Path);
}
