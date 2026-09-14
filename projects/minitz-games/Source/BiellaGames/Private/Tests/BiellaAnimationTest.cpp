// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaCharacterAnimInstance.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "BiellaVehicle.h"
#include "AnimationRuntime.h"
#include "Engine/SkeletalMesh.h"
#if WITH_EDITOR
#include "Rendering/SkeletalMeshModel.h"
#endif
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "InputKeyEventArgs.h"
#include "Kismet/GameplayStatics.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace
{
class FAnimationScenario : public IAutomationLatentCommand
{
public:
    FAnimationScenario(FAutomationTestBase* T, FString Out) : Test(T), Output(Out), Started(FPlatformTime::Seconds())
    {
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FAnimationScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FAnimationScenario::Frame);
    }
    ~FAnimationScenario()
    {
        FWorldDelegates::OnWorldTickStart.Remove(TickHandle);
        FCoreDelegates::OnEndFrame.Remove(FrameHandle);
        if (PC.IsValid()) for (auto K:{EKeys::W,EKeys::A,EKeys::S,EKeys::D,EKeys::SpaceBar}) { Key(K,false); }
    }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>120) { return Finish(false,TEXT("timeout")); }
        if (Test->HasAnyErrors()) { return Finish(false,TEXT("assertion_failed")); }
        if (!bReload)
        {
            for (const auto& C:GEngine->GetWorldContexts()) if (auto* W=C.World(); W && W->IsGameWorld() && W->HasBegunPlay())
            { OldWorld=W; bReload=true; UGameplayStatics::OpenLevel(W,TEXT("/Game/Maps/BiellaOpenWorldMap")); break; }
            return false;
        }
        if (!World.IsValid())
        {
            for (const auto& C:GEngine->GetWorldContexts()) if (auto* W=C.World(); W && W!=OldWorld.Get() && W->IsGameWorld() && W->HasBegunPlay()) { World=W; break; }
            if (!World.IsValid()) { return false; }
            PC=World->GetFirstPlayerController(); Player=PC.IsValid() ? Cast<ABiellaStreamingCharacter>(PC->GetPawn()) : nullptr;
            if (!Player.IsValid()) { return Finish(false,TEXT("missing_player")); }
            if (!Player->RequestRelocation(FVector(6000,-1000,90))) { return Finish(false,TEXT("relocation_rejected")); }
            Next(1);
        }
        const double Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1 && Player->IsTraversalReady() && !Player->IsRelocationPending() && Age>3)
        {
            Mesh=Player->FindComponentByClass<USkeletalMeshComponent>();
            if (!Mesh.IsValid() || !Mesh->GetSkeletalMeshAsset() || !Mesh->GetAnimInstance()) { return Finish(false,TEXT("missing_live_skeletal_presentation")); }
            Test->TestTrue(TEXT("On-foot rig is visible"),Mesh->IsVisible());
            Test->TestTrue(TEXT("Left foot is a real evaluated rig bone"),Mesh->GetBoneIndex(TEXT("foot_l"))>=0);
            Test->TestTrue(TEXT("Right foot is a real evaluated rig bone"),Mesh->GetBoneIndex(TEXT("foot_r"))>=0);
            CheckInsignia(Player.Get(),true);
            RecordTorsoFit();
            Player->SetActorRotation(FRotator::ZeroRotator); Capture(TEXT("idle")); Next(2);
        }
        else if (Phase==2 && Age>1) { StartMove(EKeys::W,3); }
        else if (Phase==3 && Age>1.4) { EndMove(EKeys::W,TEXT("forward"),FVector(1,0,0)); StartMove(EKeys::D,4); }
        else if (Phase==4 && Age>1.4) { EndMove(EKeys::D,TEXT("right"),FVector(0,1,0)); StartMove(EKeys::S,5); }
        else if (Phase==5 && Age>1.4) { EndMove(EKeys::S,TEXT("backward"),FVector(-1,0,0)); Next(6); }
        else if (Phase==6 && Age>0.6)
        {
            GroundZ=Player->GetActorLocation().Z; StandingFoot=Foot(); Key(EKeys::SpaceBar,true); Next(7);
        }
        else if (Phase==7 && Age>0.32)
        {
            Key(EKeys::SpaceBar,false);
            Test->TestTrue(TEXT("Real jump input lifts collision actor"),Player->GetActorLocation().Z-GroundZ>95);
            Test->TestTrue(TEXT("Jump changes evaluated leg pose, not only actor position"),FVector::Dist(Foot(),StandingFoot)>7);
            Capture(TEXT("jump")); Next(8);
        }
        else if (Phase==8 && Age>0.8)
        {
            Test->TestTrue(TEXT("Gameplay jump lands at original height"),FMath::Abs(Player->GetActorLocation().Z-GroundZ)<3);
            Capture(TEXT("land")); Player->SetWorldDormant(true); Next(9);
        }
        else if (Phase==9 && Age>0.3)
        {
            Test->TestTrue(TEXT("Dormant actor hidden"),Player->IsHidden());
            Test->TestFalse(TEXT("Dormancy cancels skeletal evaluation"),Mesh->IsComponentTickEnabled());
            Player->SetWorldDormant(false); Next(10);
        }
        else if (Phase==10 && Age>0.4)
        {
            Test->TestFalse(TEXT("Wake restores visible actor"),Player->IsHidden());
            Test->TestTrue(TEXT("Wake restores skeletal evaluation"),Mesh->IsComponentTickEnabled());
            Test->TestTrue(TEXT("Wake does not explode bones"),Foot().Size()<250);
            const FVector At=Player->GetActorLocation();
            Infected=World->SpawnActor<ABiellaInfected>(At+FVector(350,-125,0),FRotator::ZeroRotator);
            Rival=World->SpawnActor<ABiellaRival>(At+FVector(350,125,0),FRotator::ZeroRotator);
            if (!Infected.IsValid() || !Rival.IsValid()) { return Finish(false,TEXT("missing_npc_fixture")); }
            CheckInsignia(Infected.Get(),true); CheckInsignia(Rival.Get(),true);
            Next(12);
        }
        else if (Phase==12 && Age>0.7)
        {
            NPCStart=Infected->GetActorLocation();
            InfectedMin=InfectedMax=NPCFoot(Infected.Get()); RivalMin=RivalMax=NPCFoot(Rival.Get());
            Next(13);
        }
        else if (Phase==13 && Age>1.4)
        {
            Test->TestTrue(TEXT("Shared NPC movement displaces collision actor"),Infected->GetActorLocation().X-NPCStart.X>200);
            Test->TestTrue(TEXT("Unarmed NPC gait animates bones"),FVector::Dist(InfectedMin,InfectedMax)>20);
            Test->TestTrue(TEXT("Rifle NPC gait animates bones"),FVector::Dist(RivalMin,RivalMax)>20);
            const auto* Unarmed=Cast<UBiellaCharacterAnimInstance>(Infected->CharacterMesh->GetAnimInstance());
            const auto* Armed=Cast<UBiellaCharacterAnimInstance>(Rival->CharacterMesh->GetAnimInstance());
            Test->TestTrue(TEXT("Infected selects unarmed motion from actual displacement"),Unarmed && !Unarmed->GetPresentationSample().bArmed && Unarmed->GetPresentationSample().Speed>150);
            Test->TestTrue(TEXT("Rival selects rifle motion from actual displacement"),Armed && Armed->GetPresentationSample().bArmed && Armed->GetPresentationSample().Speed>150);
            Capture(TEXT("npc_gaits"));
            Vehicle=World->SpawnActor<ABiellaVehicle>(Player->GetActorLocation()+FVector(0,230,30),FRotator::ZeroRotator);
            if (!Vehicle.IsValid()) { return Finish(false,TEXT("missing_vehicle_fixture")); }
            Next(14);
        }
        else if (Phase==14 && Age>2 && !Vehicle->IsHeld())
        {
            Test->TestTrue(TEXT("Actual vehicle accepts driver"),Vehicle->TryEnter(Player.Get())); Next(15);
        }
        else if (Phase==15 && Age>0.6)
        {
            Test->TestTrue(TEXT("Seat evaluates skeletal driver"),Mesh->IsVisible() && Mesh->IsComponentTickEnabled() && Cast<UBiellaCharacterAnimInstance>(Mesh->GetAnimInstance())->GetPresentationSample().bSeated);
            Test->TestFalse(TEXT("Seat replaces fitted predecessor body"),Player->BodyMesh->IsVisible());
            Test->TestFalse(TEXT("Seat hides held weapon"),Player->WeaponMesh->IsVisible());
            CheckInsignia(Player.Get(),true); Capture(TEXT("seat")); Next(16);
        }
        else if (Phase==16 && Age>0.4)
        {
            Test->TestTrue(TEXT("Actual vehicle exit succeeds"),Vehicle->TryExit()); Next(17);
        }
        else if (Phase==17 && Age>0.8)
        {
            Test->TestTrue(TEXT("Exit restores on-foot rig and weapon"),Mesh->IsVisible() && Mesh->IsComponentTickEnabled() && Player->WeaponMesh->IsVisible());
            Test->TestFalse(TEXT("Exit hides seated blockout"),Player->BodyMesh->IsVisible());
            CheckInsignia(Player.Get(),true); Capture(TEXT("dismount")); Next(18);
        }
        else if (Phase==18 && Age>0.4)
        {
            Player->ApplyDemoDamage(1000,nullptr,TEXT("animation_cancellation")); Next(11);
        }
        else if (Phase==11 && Age>0.3)
        {
            Test->TestTrue(TEXT("Damage reaches actual defeat state"),Player->IsDefeated());
            Test->TestFalse(TEXT("Defeated character no longer presents active rig"),Mesh->IsVisible());
            Test->TestFalse(TEXT("Defeat stops skeletal evaluation"),Mesh->IsComponentTickEnabled());
            CheckInsignia(Player.Get(),false);
            return Finish(!Test->HasAnyErrors(),TEXT(""));
        }
        return false;
    }
private:
    void RecordTorsoFit()
    {
        const auto* Asset=Mesh->GetSkeletalMeshAsset();
        const auto& Skeleton=Asset->GetRefSkeleton();
        const FVector Torso=FAnimationRuntime::GetComponentSpaceTransformRefPose(Skeleton,Skeleton.FindBoneIndex(TEXT("spine_05"))).GetLocation();
        FString Data=FString::Printf(TEXT("reference_spine_05=%s\n"),*Torso.ToString());
#if WITH_EDITOR
        if (const auto* Model=Asset->GetImportedModel(); Model && Model->LODModels.Num())
        {
            FVector Low(UE_BIG_NUMBER),High(-UE_BIG_NUMBER); int32 Count=0;
            for (const auto& Section:Model->LODModels[0].Sections) for (const auto& Vertex:Section.SoftVertices)
            {
                const FVector P(Vertex.Position);
                if (FMath::Abs(P.X)<12 && FMath::Abs(P.Z-Torso.Z)<10)
                { Low=Low.ComponentMin(P); High=High.ComponentMax(P); ++Count; }
            }
            Data+=FString::Printf(TEXT("torso_surface_vertices=%d min=%s max=%s\n"),Count,*Low.ToString(),*High.ToString());
        }
#endif
        TArray<UStaticMeshComponent*> Parts; Player->GetComponents(Parts);
        for (const auto* Part:Parts) if (Part->ComponentHasTag(TEXT("D03RoleInsignia")))
        { Data+=FString::Printf(TEXT("%s actual_mesh_space=%s\n"),*Part->GetName(),*Part->GetComponentTransform().GetRelativeTransform(Mesh->GetComponentTransform()).ToString()); }
        Test->TestTrue(TEXT("Torso fit evidence saved"),FFileHelper::SaveStringToFile(Data,*FPaths::Combine(Output,TEXT("torso-fit.txt"))));
    }
    void BeforeTick(UWorld* W,ELevelTick,float DeltaSeconds)
    {
        if (!bReload || !W || W==OldWorld.Get() || !W->IsGameWorld()) { return; }
        for (TActorIterator<ABiellaPopulationDirector> It(W);It;++It) { It->MaxActive=0; }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It) if (!It->IsA<ABiellaStreamingCharacter>())
        { It->SetActorTickEnabled(false); It->PawnMovement->SetComponentTickEnabled(false); }
        if (Phase==13 && Infected.IsValid() && Rival.IsValid())
        {
            Infected->MoveTowardLocation(Infected->GetActorLocation()+FVector(1000,0,0),DeltaSeconds);
            Rival->MoveTowardLocation(Rival->GetActorLocation()+FVector(1000,0,0),DeltaSeconds);
        }
    }
    void CheckInsignia(ABiellaDemoPawn* Pawn,bool Visible)
    {
        TArray<UStaticMeshComponent*> Parts; Pawn->GetComponents(Parts); int32 Count=0;
        for (auto* Part:Parts) if (Part->ComponentHasTag(TEXT("D03RoleInsignia")))
        {
            ++Count;
            Test->TestTrue(TEXT("Role insignia follows torso bone"),Part->GetAttachParent()==Pawn->CharacterMesh && Part->GetAttachSocketName()==TEXT("spine_05"));
            Test->TestTrue(TEXT("Role insignia cannot alter collision/navigation"),Part->GetCollisionEnabled()==ECollisionEnabled::NoCollision && !Part->CanEverAffectNavigation());
            Test->TestEqual(TEXT("Role insignia obeys lifecycle visibility"),Part->IsVisible(),Visible);
            Test->TestTrue(TEXT("Role insignia remains fitted within torso width"),Part->GetRelativeScale3D().GetAbsMax()<0.3);
        }
        Test->TestEqual(TEXT("Each role keeps distinct front/back insignia"),Count,Pawn->Team==EDemo01Team::Player ? 2 : 4);
    }
    FVector NPCFoot(ABiellaDemoPawn* Pawn) const { return Pawn->CharacterMesh->GetSocketTransform(TEXT("foot_l"),RTS_Component).GetLocation(); }
    FVector Foot() const { return Mesh->GetSocketTransform(TEXT("foot_l"),RTS_Component).GetLocation(); }
    void Key(FKey K,bool Down) { PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),K,Down ? IE_Pressed : IE_Released,FPlatformTime::Cycles64())); }
    void Next(int32 P) { Phase=P; PhaseStart=World->GetTimeSeconds(); }
    void StartMove(FKey K,int32 P) { Start=Player->GetActorLocation(); FootMin=FootMax=Foot(); Key(K,true); Next(P); }
    void EndMove(FKey K,const TCHAR* Label,FVector Direction)
    {
        Key(K,false); const FVector Delta=Player->GetActorLocation()-Start;
        Test->TestTrue(FString(Label)+TEXT(" input moves in requested direction"),FVector::DotProduct(Delta,Direction)>150);
        Test->TestTrue(FString(Label)+TEXT(" gait animates actual foot bones"),FVector::Dist(FootMin,FootMax)>20);
        Capture(Label);
    }
    void Capture(const FString& Name) { FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),Name+TEXT(".png")),true,false,false,FIntRect(),true); }
    void Frame()
    {
        if (bFinished || !Mesh.IsValid()) { return; }
        const auto P=Player->GetActorLocation(), F=Foot();
        FootMin=FootMin.ComponentMin(F); FootMax=FootMax.ComponentMax(F);
        if (Phase==13 && Infected.IsValid() && Rival.IsValid())
        {
            const FVector A=NPCFoot(Infected.Get()),B=NPCFoot(Rival.Get());
            InfectedMin=InfectedMin.ComponentMin(A); InfectedMax=InfectedMax.ComponentMax(A);
            RivalMin=RivalMin.ComponentMin(B); RivalMax=RivalMax.ComponentMax(B);
        }
        Csv+=FString::Printf(TEXT("%llu,%.6f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%d,%d\n"),
            static_cast<unsigned long long>(GFrameCounter),World->GetTimeSeconds(),Phase,P.X,P.Y,P.Z,F.X,F.Y,F.Z,Mesh->IsVisible(),Mesh->IsComponentTickEnabled());
    }
    bool Finish(bool Good,const TCHAR* Error)
    {
        if (bFinished) { return true; } bFinished=true; Good &= !Test->HasAnyErrors();
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"error\":\"%s\"}\n"),Good ? TEXT("true") : TEXT("false"),Error);
        const bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("poses.csv"))) && FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")));
        if (!Good || !Saved) { Test->AddError(FString(TEXT("animation_evidence_failed: "))+Error); }
        return true;
    }
    FAutomationTestBase* Test; FString Output,Csv=TEXT("frame,time,phase,x,y,z,foot_x,foot_y,foot_z,visible,tick\n");
    double Started,PhaseStart=0,GroundZ=0; int32 Phase=0; bool bReload=false,bFinished=false;
    FVector Start,FootMin,FootMax,StandingFoot,NPCStart,InfectedMin,InfectedMax,RivalMin,RivalMax; FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld; TWeakObjectPtr<APlayerController> PC;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player; TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TWeakObjectPtr<ABiellaInfected> Infected; TWeakObjectPtr<ABiellaRival> Rival; TWeakObjectPtr<ABiellaVehicle> Vehicle;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaAnimationTest,"BiellaGames.D03.Animation",EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaAnimationTest::RunTest(const FString&)
{
    FString Out; FParse::Value(FCommandLine::Get(),TEXT("BiellaAnimationOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaAnimationOutput is required")); return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FAnimationScenario(this,Out)); return true;
}
#endif
