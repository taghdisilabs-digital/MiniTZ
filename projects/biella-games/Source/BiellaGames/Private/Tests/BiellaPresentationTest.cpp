// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "Components/MeshComponent.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "InputKeyEventArgs.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstance.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "DynamicRHI.h"
#include "UnrealClient.h"

namespace
{
class FPresentationScenario : public IAutomationLatentCommand
{
public:
    FPresentationScenario(FAutomationTestBase* InTest, FString Out)
        : Test(InTest), Output(Out), Started(FPlatformTime::Seconds())
    {
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FPresentationScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FPresentationScenario::Frame);
        Csv=TEXT("frame,wall_ms,sim_ms,gpu_ms,phase,shot_requested,x,y,z,yaw,ready,aa,screen_percentage,motion_blur_quality,dynamic_res,vsync,frame_cap\n");
    }
    ~FPresentationScenario()
    {
        FWorldDelegates::OnWorldTickStart.Remove(TickHandle);
        FCoreDelegates::OnEndFrame.Remove(FrameHandle);
        if (PC.IsValid()) { Key(false); }
    }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>150) { return Finish(false,TEXT("timeout")); }
        if (Test->HasAnyErrors()) { return Finish(false,TEXT("assertion_failed")); }
        if (!bReload)
        {
            for (const auto& C:GEngine->GetWorldContexts())
            {
                auto* W=C.World();
                if (W && W->IsGameWorld() && W->HasBegunPlay())
                { OldWorld=W; bReload=true; UGameplayStatics::OpenLevel(W,TEXT("/Game/Maps/BiellaOpenWorldMap")); break; }
            }
            return false;
        }
        if (!World.IsValid())
        {
            for (const auto& C:GEngine->GetWorldContexts())
            {
                auto* W=C.World();
                if (W && W!=OldWorld.Get() && W->IsGameWorld() && W->HasBegunPlay()) { World=W; break; }
            }
            if (!World.IsValid()) { return false; }
            PC=World->GetFirstPlayerController();
            Player=PC.IsValid() ? Cast<ABiellaStreamingCharacter>(PC->GetPawn()) : nullptr;
            if (!Player.IsValid()) { return Finish(false,TEXT("missing_player")); }
            if (!Player->RequestRelocation(FVector(6000,-1000,90))) { return Finish(false,TEXT("relocation_rejected")); }
            Next(1);
        }
        const double Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1 && Ready() && Age>3)
        {
            Player->SetActorRotation(FRotator::ZeroRotator);
            TSet<FString> Materials;
            for (TActorIterator<AActor> It(World.Get()); It; ++It)
            {
                TInlineComponentArray<UMeshComponent*> Meshes; It->GetComponents(Meshes);
                for (auto* Mesh:Meshes) for (int32 Slot=0; Slot<Mesh->GetNumMaterials(); ++Slot)
                {
                    auto* Mat=Mesh->GetMaterial(Slot);
                    if (Mat && Mat->GetPathName().StartsWith(TEXT("/Game/OpenWorld/Materials/MI_")))
                    {
                        Materials.Add(Mat->GetPathName());
                        Test->TestEqual(TEXT("Live world surface uses authored master"),Mat->GetMaterial()->GetPathName(),
                            FString(TEXT("/Game/OpenWorld/Materials/M_ProductionSurface.M_ProductionSurface")));
                    }
                }
            }
            SurfaceCount=Materials.Num();
            Test->TestTrue(TEXT("Loaded playable world uses multiple production surfaces"),SurfaceCount>=3);
            Next(2);
        }
        else if (Phase==2 && Age>4) { Next(3); }
        else if (Phase==3)
        {
            Sequence(TEXT("static"),10,0.15);
            if (ShotIndex==10 && !FScreenshotRequest::IsScreenshotRequested())
            { Player->SetActorRotation(FRotator(0,-25,0)); Next(4); }
        }
        else if (Phase==4)
        {
            Player->SetActorRotation(FRotator(0,-25+12.5*FMath::Min(Age,4.0),0));
            if (Age>4) { Player->SetActorRotation(FRotator(0,-25,0)); Next(5); }
        }
        else if (Phase==5 && Age>2) { Next(6); }
        else if (Phase==6)
        {
            Player->SetActorRotation(FRotator(0,-25+12.5*FMath::Min(Age,4.0),0));
            Sequence(TEXT("pan"),32,0.125);
            if (ShotIndex==32 && !FScreenshotRequest::IsScreenshotRequested())
            { Player->SetActorRotation(FRotator::ZeroRotator); WalkStart=Player->GetActorLocation(); Key(true); Next(7); }
        }
        else if (Phase==7 && Age>2)
        {
            Key(false); WalkDistance=FVector::Dist2D(WalkStart,Player->GetActorLocation());
            Test->TestTrue(TEXT("Real W input traverses rendered world"),WalkDistance>200);
            Capture(TEXT("walk_end")); Next(8);
        }
        else if (Phase==8 && Age>1 && !FScreenshotRequest::IsScreenshotRequested()) { return Finish(true,TEXT("")); }
        return false;
    }
private:
    // Controlled repeatability fixture: population AI is frozen, geometry,
    // streaming, lighting, camera, movement and render paths remain native.
    void BeforeTick(UWorld* W,ELevelTick,float)
    {
        if (!bReload || !W || W==OldWorld.Get() || !W->IsGameWorld()) { return; }
        for (TActorIterator<ABiellaPopulationDirector> It(W);It;++It) { It->MaxActive=0; }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It)
        { if (!It->IsA<ABiellaStreamingCharacter>()) { It->SetActorTickEnabled(false); It->PawnMovement->SetComponentTickEnabled(false); } }
    }
    bool Ready() const { return Player->IsTraversalReady() && !Player->IsRelocationPending(); }
    void Key(bool Down)
    { PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),EKeys::W,Down ? IE_Pressed : IE_Released,FPlatformTime::Cycles64())); }
    void Next(int32 Value)
    { Phase=Value; PhaseStart=World->GetTimeSeconds(); ShotIndex=0; LastShot=-1; }
    void Capture(const FString& Name)
    {
        FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),Name+TEXT(".png")),true,false,false,FIntRect(),true);
        CaptureCsv+=FString::Printf(TEXT("%s,%llu,%.6f,%.6f\n"),*Name,static_cast<unsigned long long>(GFrameCounter),World->GetTimeSeconds(),Player->GetActorRotation().Yaw);
        bShotThisFrame=true;
    }
    void Sequence(const TCHAR* Prefix,int32 Count,double Interval)
    {
        const double Now=World->GetTimeSeconds();
        if (ShotIndex<Count && Now-LastShot>=Interval && !FScreenshotRequest::IsScreenshotRequested())
        { Capture(FString::Printf(TEXT("%s_%03d"),Prefix,ShotIndex++)); LastShot=Now; }
    }
    static float CVar(const TCHAR* Name)
    { const auto* V=IConsoleManager::Get().FindConsoleVariable(Name); return V ? V->GetFloat() : -1; }
    void Frame()
    {
        if (bFinished || !Player.IsValid()) { return; }
        const double Now=FPlatformTime::Seconds();
        if (LastWall>0)
        {
            const auto P=Player->GetActorLocation();
            Csv+=FString::Printf(TEXT("%llu,%.6f,%.6f,%.6f,%d,%d,%.4f,%.4f,%.4f,%.4f,%d,%.1f,%.2f,%.1f,%.1f,%.1f,%.1f\n"),
                static_cast<unsigned long long>(GFrameCounter),(Now-LastWall)*1000,FApp::GetDeltaTime()*1000,
                FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles()),Phase,bShotThisFrame,P.X,P.Y,P.Z,
                Player->GetActorRotation().Yaw,Ready(),CVar(TEXT("r.AntiAliasingMethod")),CVar(TEXT("r.ScreenPercentage")),
                CVar(TEXT("r.MotionBlurQuality")),CVar(TEXT("r.DynamicRes.OperationMode")),CVar(TEXT("r.VSync")),CVar(TEXT("t.MaxFPS")));
        }
        LastWall=Now; bShotThisFrame=false;
    }
    bool Finish(bool Good,const TCHAR* Error)
    {
        if (bFinished) { return true; } bFinished=true; Good &= !Test->HasAnyErrors();
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"rhi\":\"%s\",\"fixed_timestep\":%s,\"benchmark\":%s,\"surface_count\":%d,\"walk_cm\":%.3f,\"error\":\"%s\"}\n"),
            Good ? TEXT("true") : TEXT("false"),GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"),
            FApp::UseFixedTimeStep() ? TEXT("true") : TEXT("false"),FApp::IsBenchmarking() ? TEXT("true") : TEXT("false"),SurfaceCount,WalkDistance,Error);
        bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("frames.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(CaptureCsv,*FPaths::Combine(Output,TEXT("captures.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        if (!Good || !Saved) { Test->AddError(FString(TEXT("presentation_evidence_failed: "))+Error); }
        return true;
    }
    FAutomationTestBase* Test;
    FString Output,Csv,CaptureCsv=TEXT("name,frame,sim_time,yaw\n");
    double Started,PhaseStart=0,LastWall=0,LastShot=-1,WalkDistance=0;
    int32 Phase=0,ShotIndex=0,SurfaceCount=0;
    bool bReload=false,bFinished=false,bShotThisFrame=false;
    FVector WalkStart;
    FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld;
    TWeakObjectPtr<APlayerController> PC;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaPresentationTest,"BiellaGames.D03.Surfaces",EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaPresentationTest::RunTest(const FString&)
{
    FString Out; FParse::Value(FCommandLine::Get(),TEXT("BiellaPresentationOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaPresentationOutput is required")); return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FPresentationScenario(this,Out)); return true;
}
#endif
