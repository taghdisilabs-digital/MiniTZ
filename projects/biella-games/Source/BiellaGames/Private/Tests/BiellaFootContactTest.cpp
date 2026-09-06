// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaCharacterAnimInstance.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaVehicle.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "InputKeyEventArgs.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace
{
class FFootContactScenario : public IAutomationLatentCommand
{
public:
    FFootContactScenario(FAutomationTestBase* T,FString Out,bool Disabled):Test(T),Output(Out),bDisabled(Disabled),Started(FPlatformTime::Seconds())
    {
        TickHandle=FWorldDelegates::OnWorldPreActorTick.AddRaw(this,&FFootContactScenario::Freeze);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FFootContactScenario::Frame);
        CVar=IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Animation.FootPlacement"));
        OriginalCVar=CVar->GetInt(); CVar->Set(Disabled ? 0 : 1,ECVF_SetByCode);
    }
    ~FFootContactScenario()
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle); FCoreDelegates::OnEndFrame.Remove(FrameHandle);
        if (PC.IsValid()) { Key(EKeys::W,false);Key(EKeys::SpaceBar,false); }
        CVar->Set(OriginalCVar,ECVF_SetByCode);
    }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>120) { Test->AddError(TEXT("Foot contact timeout"));return Finish(); }
        if (Test->HasAnyErrors()) { return Finish(); }
        UWorld* Candidate=nullptr;
        for (const auto& C:GEngine->GetWorldContexts()) if (auto* W=C.World();W&&W->IsGameWorld()&&W->HasBegunPlay()) { Candidate=W;break; }
        if (!Candidate) { return false; }
        if (!bReload) { OldWorld=Candidate;bReload=true;UGameplayStatics::OpenLevel(Candidate,TEXT("/Game/Maps/BiellaGameplayMap"));return false; }
        if (!World.IsValid())
        {
            if (Candidate==OldWorld.Get()) { return false; } World=Candidate;
            PC=World->GetFirstPlayerController(); Player=PC.IsValid() ? Cast<ABiellaGamesCharacter>(PC->GetPawn()) : nullptr;
            if (!Player.IsValid()) { Test->AddError(TEXT("Missing gameplay player"));return Finish(); }
            Mesh=Player->CharacterMesh; Anim=Cast<UBiellaCharacterAnimInstance>(Mesh->GetAnimInstance());
            if (!Anim.IsValid()) { Test->AddError(TEXT("Missing native animation"));return Finish(); }
            if (auto* Mode=World->GetAuthGameMode<ABiellaGamesGameModeBase>()) { Mode->SetActorTickEnabled(false); }
            Player->PawnMovement->StopMovementImmediately();
            Player->SetActorLocationAndRotation(FVector(-1000,-900,1088),FRotator::ZeroRotator);
            PC->SetControlRotation(FRotator(-12,0,0));
            if (auto* Boom=Player->FindComponentByClass<USpringArmComponent>())
            { Boom->TargetArmLength=360;Boom->SocketOffset=FVector(0,45,25); }
            Pad=MakePad(FVector(-1000,-900,980),FVector(6,6,0.4));
            const auto& Skeleton=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
            for (int32 I=0;I<2;++I)
            { Sole[I]=FAnimationRuntime::GetComponentSpaceTransformRefPose(Skeleton,Skeleton.FindBoneIndex(Names[I])).GetLocation().Z*Mesh->GetComponentScale().Z; }
            Next(1);return false;
        }
        const float Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1&&Age>2)
        {
            if (!CaptureFrame) for (int32 I=0;I<2;++I) { FlatRotation[I]=Mesh->GetSocketQuaternion(Names[I]); }
            RecordCheck(TEXT("flat"),true);if (!Capture(TEXT("flat"))) { return false; }
            Pad->SetActorRotation(FRotator(0,0,25));Next(2);
        }
        else if (Phase==2&&Age>1.2)
        {
            RecordCheck(TEXT("slope_positive"),true);if (!Capture(TEXT("slope_positive"))) { return false; }
            Pad->SetActorRotation(FRotator(0,0,-25));Next(3);
        }
        else if (Phase==3&&Age>1.2)
        {
            RecordCheck(TEXT("slope_negative"),true);if (!Capture(TEXT("slope_negative"))) { return false; }
            Pad->SetActorEnableCollision(false);Pad->SetActorHiddenInGame(true);
            Left=MakePad(FVector(-1000,-1050,992),FVector(6,3,0.4));
            Right=MakePad(FVector(-1000,-750,968),FVector(6,3,0.4)); Next(4);
        }
        else if (Phase==4&&Age>1.2)
        {
            RecordCheck(TEXT("split_levels"),true);if (!Capture(TEXT("split_levels"))) { return false; }
            if (bDisabled) { Next(19);return false; }
            Left->SetActorEnableCollision(false);Left->SetActorHiddenInGame(true);Next(5);
        }
        else if (Phase==5&&Age>0.5)
        {
            if (!CaptureFrame) Test->TestTrue(TEXT("Missing support releases exactly its contact"),
                (Weight(0)==0 && Weight(1)>0.99f)||(Weight(1)==0 && Weight(0)>0.99f));
            RecordCheck(TEXT("missing_one_support"),false);if (!Capture(TEXT("missing_one_support"))) { return false; }
            Left->SetActorEnableCollision(true);Left->SetActorHiddenInGame(false);Key(EKeys::SpaceBar,true);Next(6);
        }
        else if (Phase==6&&Age>0.30)
        {
            Key(EKeys::SpaceBar,false);
            if (!CaptureFrame) Test->TestTrue(TEXT("Enhanced Input starts real jump"),Player->IsGameplayJumping()&&Player->GetActorLocation().Z>1180);
            CheckCleared(TEXT("Jump immediately clears contacts"));if (!Capture(TEXT("jump"))) { return false; }Next(7);
        }
        else if (Phase==7&&Age>1.2)
        {
            RecordCheck(TEXT("land"),true);
            Test->TestTrue(TEXT("Jump returns capsule height"),FMath::Abs(Player->GetActorLocation().Z-1088)<0.1);
            Left->SetActorEnableCollision(false);Left->SetActorHiddenInGame(true);Right->SetActorEnableCollision(false);Right->SetActorHiddenInGame(true);
            Pad->SetActorEnableCollision(true);Pad->SetActorHiddenInGame(false);Pad->SetActorRotation(FRotator(0,0,60));Next(8);
        }
        else if (Phase==8&&Age>0.6)
        {
            CheckCleared(TEXT("Steep surface cannot plant feet"));RecordCheck(TEXT("steep_rejected"),false);
            Pad->SetActorRotation(FRotator::ZeroRotator);Pad->SetActorLocation(FVector(-1000,-900,930));Next(9);
        }
        else if (Phase==9&&Age>0.6)
        {
            CheckCleared(TEXT("Deep gap cannot stretch legs"));RecordCheck(TEXT("gap_rejected"),false);
            Pad->SetActorLocation(FVector(-1000,-900,980));Next(10);
        }
        else if (Phase==10&&Age>0.6)
        {
            RecordCheck(TEXT("reacquired"),true);Player->SetWorldDormant(true);
            CheckCleared(TEXT("Dormancy clears contacts before tick stops"));Next(11);
        }
        else if (Phase==11&&Age>0.2) { Player->SetWorldDormant(false);Next(12); }
        else if (Phase==12&&Age>0.6)
        {
            RecordCheck(TEXT("wake"),true);WalkStart=Player->GetActorLocation();Key(EKeys::W,true);Next(13);
        }
        else if (Phase==13&&Age>0.55)
        {
            Key(EKeys::W,false);Test->TestTrue(TEXT("Real input still drives locomotion"),Player->GetActorLocation().X-WalkStart.X>50);
            if (!Capture(TEXT("moving"))) { return false; }Next(14);
        }
        else if (Phase==14&&Age>0.5)
        {
            Test->TestTrue(TEXT("IK never moves gameplay capsule vertically"),FMath::Abs(Player->GetActorLocation().Z-1088)<0.1);
            Player->SetActorLocation(FVector(-1000,-900,1088));Next(15);
        }
        else if (Phase==15&&Age>0.6)
        {
            RecordCheck(TEXT("after_teleport"),true);
            Pad->GetStaticMeshComponent()->SetWorldScale3D(FVector(12,12,0.4));
            Vehicle=World->SpawnActor<ABiellaVehicle>(Player->GetActorLocation()+FVector(0,230,30),FRotator::ZeroRotator);
            Test->TestTrue(TEXT("Vehicle fixture spawned"),Vehicle.IsValid());Next(20);
        }
        else if (Phase==20&&Age>2&&!Vehicle->IsHeld())
        {
            Test->TestTrue(TEXT("Actual vehicle entry"),Vehicle.IsValid()&&Vehicle->TryEnter(Player.Get()));
            CheckCleared(TEXT("Vehicle entry clears foot contacts"));Next(16);
        }
        else if (Phase==16&&Age>0.3)
        {
            Test->TestTrue(TEXT("Actual vehicle exit"),Vehicle->TryExit());
            Player->SetActorLocation(FVector(-1000,-900,1088));Next(17);
        }
        else if (Phase==17&&Age>0.7)
        {
            RecordCheck(TEXT("after_seat"),true);if (!Capture(TEXT("after_seat"))) { return false; }
            Player->ApplyDemoDamage(1000,nullptr,TEXT("D03 foot cancellation"));
            Test->TestTrue(TEXT("Actual defeat"),Player->IsDefeated());CheckCleared(TEXT("Defeat clears foot contacts"));Next(18);
        }
        else if ((Phase==18||Phase==19)&&Age>0.3) { return Finish(); }
        return false;
    }
private:
    AStaticMeshActor* MakePad(FVector Position,FVector Scale)
    {
        auto* A=World->SpawnActor<AStaticMeshActor>(Position,FRotator::ZeroRotator);
        auto* M=A->GetStaticMeshComponent();M->SetMobility(EComponentMobility::Movable);
        M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
        M->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_DemoReadability.M_DemoReadability")));
        M->SetWorldScale3D(Scale);M->SetCollisionProfileName(TEXT("BlockAll"));M->SetCollisionObjectType(ECC_WorldStatic);
        // These animated test surfaces isolate cosmetic contact. Object traces
        // still hit real collision, while platform insertion cannot depenetrate
        // the floating gameplay capsule or rewrite the jump's starting height.
        M->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
        return A;
    }
    void Freeze(UWorld* W,ELevelTick,float)
    {
        if (!World.IsValid()||W!=World.Get()) { return; }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It) if (*It!=Player.Get())
        { It->SetActorTickEnabled(false);It->PawnMovement->StopMovementImmediately();It->PawnMovement->SetComponentTickEnabled(false); }
    }
    float Weight(int32 I) const { return Anim->GetPresentationSample().Feet[I].Weight; }
    void CheckCleared(const TCHAR* Label) { if (CaptureFrame) { return; } Test->TestTrue(Label,Weight(0)==0&&Weight(1)==0); }
    void Key(FKey K,bool Down) { PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),K,Down?IE_Pressed:IE_Released,FPlatformTime::Cycles64())); }
    void Next(int32 P) { Phase=P;PhaseStart=World->GetTimeSeconds(); }
    bool Capture(const FString& Label)
    {
        // Screenshot requests are consumed later in the frame. Keep the tested
        // terrain and pose condition intact until its rendered frame is saved.
        if (!CaptureFrame)
        {
            CaptureFrame=GFrameCounter;
            FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),Label+TEXT(".png")),true,false,false,FIntRect(),true);
            return false;
        }
        if (GFrameCounter<CaptureFrame+2) { return false; }
        CaptureFrame=0;return true;
    }
    float Error(int32 I,FVector& Normal) const
    {
        const FVector Foot=Mesh->GetSocketLocation(Names[I]);FHitResult Hit;
        FCollisionQueryParams Q(SCENE_QUERY_STAT(FootContactTest),false,Player.Get());
        if (!World->LineTraceSingleByObjectType(Hit,Foot+FVector(0,0,60),Foot-FVector(0,0,100),FCollisionObjectQueryParams(ECC_WorldStatic),Q)) { Normal=FVector::ZeroVector;return 999; }
        Normal=Hit.ImpactNormal;return FVector::DotProduct(Foot-Hit.ImpactPoint,Normal)-Sole[I];
    }
    void RecordCheck(const TCHAR* Label,bool Fit)
    {
        if (CaptureFrame) { return; }
        float LargestError=0;
        for (int32 I=0;I<2;++I)
        {
            FVector Normal;const float E=Error(I,Normal);LargestError=FMath::Max(LargestError,FMath::Abs(E));
            const FQuat Delta=Mesh->GetSocketQuaternion(Names[I])*FlatRotation[I].Inverse();
            const float Angle=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Delta.RotateVector(FVector::UpVector),Normal),-1.,1.)));
            Checks+=FString::Printf(TEXT("%s,%d,%.6f,%.6f,%.6f,%.6f\n"),Label,I,E,Angle,Weight(I),Player->GetActorLocation().Z);
            if (Fit&&!bDisabled)
            {
                Test->TestTrue(FString(Label)+TEXT(" evaluated sole contacts real collision plane"),FMath::Abs(E)<2);
                Test->TestTrue(FString(Label)+TEXT(" foot follows terrain angle"),Angle<8);
                Test->TestTrue(FString(Label)+TEXT(" contact reaches full weight"),Weight(I)>0.99f);
            }
        }
        if (bDisabled && FString(Label)==TEXT("split_levels"))
        { Test->TestTrue(TEXT("Disabled native control exposes foot contact error"),LargestError>8); }
    }
    void Frame()
    {
        if (bFinished||!Mesh.IsValid()) { return; }
        const auto L=Mesh->GetSocketLocation(Names[0]),R=Mesh->GetSocketLocation(Names[1]),P=Mesh->GetSocketLocation(TEXT("pelvis"));
        const auto A=Player->GetActorLocation();FVector N;const float LE=Error(0,N),RE=Error(1,N);
        Csv+=FString::Printf(TEXT("%llu,%.6f,%d,%.6f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n"),
            static_cast<unsigned long long>(GFrameCounter),World->GetTimeSeconds(),Phase,World->GetTimeSeconds()-PhaseStart,
            A.X,A.Y,A.Z,L.X,L.Y,L.Z,R.X,R.Y,R.Z,P.Z,Weight(0),Weight(1),FMath::Max(FMath::Abs(LE),FMath::Abs(RE)));
    }
    bool Finish()
    {
        if (bFinished) { return true; } bFinished=true;
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"disabled\":%s,\"sole_left\":%.6f,\"sole_right\":%.6f}\n"),
            Test->HasAnyErrors()?TEXT("false"):TEXT("true"),bDisabled?TEXT("true"):TEXT("false"),Sole[0],Sole[1]);
        Test->TestTrue(TEXT("Save pose evidence"),FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("poses.csv"))));
        Test->TestTrue(TEXT("Save independent contact checks"),FFileHelper::SaveStringToFile(Checks,*FPaths::Combine(Output,TEXT("checks.csv"))));
        Test->TestTrue(TEXT("Save result"),FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json"))));return true;
    }
    FAutomationTestBase* Test;FString Output;bool bDisabled,bReload=false,bFinished=false;
    uint64 CaptureFrame=0;
    double Started,PhaseStart=0;int32 Phase=0,OriginalCVar=1;IConsoleVariable* CVar=nullptr;
    float Sole[2]={0,0};FQuat FlatRotation[2];FVector WalkStart;
    const FName Names[2]={TEXT("foot_l"),TEXT("foot_r")};
    FString Csv=TEXT("frame,time,phase,age,actor_x,actor_y,actor_z,left_x,left_y,left_z,right_x,right_y,right_z,pelvis_z,left_weight,right_weight,max_contact_error\n");
    FString Checks=TEXT("phase,foot,sole_error,normal_angle,weight,capsule_z\n");
    FDelegateHandle TickHandle,FrameHandle;TWeakObjectPtr<UWorld> World,OldWorld;
    TWeakObjectPtr<APlayerController> PC;TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;TWeakObjectPtr<UBiellaCharacterAnimInstance> Anim;
    TWeakObjectPtr<AStaticMeshActor> Pad,Left,Right;TWeakObjectPtr<ABiellaVehicle> Vehicle;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaFootContactTest,"BiellaGames.D03.FootContact",EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FBiellaFootContactTest::RunTest(const FString&)
{
    FString Out;FParse::Value(FCommandLine::Get(),TEXT("BiellaFootContactOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaFootContactOutput is required"));return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FFootContactScenario(this,Out,FParse::Param(FCommandLine::Get(),TEXT("BiellaContactDisabled"))));return true;
}
#endif
