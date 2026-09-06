// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaVehicle.h"
#include "BiellaCharacterAnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "BiellaVehiclePresentation.h"
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaGamesGameState.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "AudioDevice.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Components/AudioComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DynamicRHI.h"
#include "Engine/Engine.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/World.h"
#include "Engine/DamageEvents.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMemory.h"
#include "HAL/IConsoleManager.h"
#include "InputKeyEventArgs.h"
#include "InputActionValue.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "Sound/SoundWaveProcedural.h"
#if WITH_EDITOR
#include "ShaderCompiler.h"
#endif
namespace
{
// Input enters PlayerController through real key events. No test writes a car
// transform or velocity. Only the on-foot fixture relocates using streamed
// placement. Legacy AI is held so car/player causality can be measured alone.
class FVehicleScenario : public IAutomationLatentCommand
{
public:
    FVehicleScenario(FAutomationTestBase* T,FString Out):Test(T),Output(Out),Started(FPlatformTime::Seconds())
    {
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FVehicleScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FVehicleScenario::Frame);
        Csv=TEXT("frame,wall_seconds,wall_ms,sim_ms,phase,x,y,z,yaw,roll,pitch,speed,velocity,contacts,travel,spin,throttle,steering,brake,held,dormant,health,impacts,driver,player_health,ammo,audio,resident_bytes\n");
        bPresentation=FParse::Param(FCommandLine::Get(),TEXT("BiellaVehiclePresentation"));
        bPresentationDisabled=FParse::Param(FCommandLine::Get(),TEXT("BiellaVehiclePresentationDisabled"));
        bDriver=FParse::Param(FCommandLine::Get(),TEXT("BiellaDriverPresentation"));
        bDriverDisabled=FParse::Param(FCommandLine::Get(),TEXT("BiellaDriverPresentationDisabled"));
        if (bDriver) { IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Animation.DriverPose"))->Set(bDriverDisabled ? 0:1,ECVF_SetByCode); }
        DriverCsv=TEXT("frame,phase,mounted,alive,enabled,stable,visible,blockout,seated,pelvis_error,feet_error,hands_error,length_error,root_error,wheel_visible,wheel_collision,action_weight,steering,grip_error,wheel_expected\n");
        PoseCsv=TEXT("frame,phase,rig_visible,dormant,updates,wheel_error,axle_error,spin_error,link_error,root_error,paint_error,body_visible,cosmetic_collision,rigid_visible,rigid_center_error,rigid_axle_error,rigid_spin_error,rigid_radius_error,rigid_body_error\n");
        if (bPresentation) { IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Vehicle.SkeletalPresentation"))->Set(bPresentationDisabled ? 0:1,ECVF_SetByCode); }
    }
    ~FVehicleScenario()
    {
        FWorldDelegates::OnWorldTickStart.Remove(TickHandle);
        FCoreDelegates::OnEndFrame.Remove(FrameHandle);
    }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>200) { return Finish(false,TEXT("scenario_timeout")); }
        if (Test->HasAnyErrors()) { return Finish(false,TEXT("assertion_failed")); }
        if (!bReload)
        {
            for (const auto& C:GEngine->GetWorldContexts())
            { if (auto* W=C.World(); W && W->IsGameWorld() && W->HasBegunPlay())
              { OldWorld=W; bReload=true; UGameplayStatics::OpenLevel(W,TEXT("/Game/Maps/BiellaOpenWorldMap")); break; } }
            return false;
        }
        if (Phase==30)
        {
            for (const auto& C:GEngine->GetWorldContexts())
            {
                UWorld* W=C.World(); if (!W || W==World.Get() || !W->IsGameWorld() || !W->HasBegunPlay()) { continue; }
                int32 Count=0; ABiellaVehicle* New=nullptr;
                for (TActorIterator<ABiellaVehicle> It(W);It;++It) { ++Count; New=*It; }
                Check(Count==1 && New!=Car.Get() && New->GetHealth()==100 && !New->GetDriver(),TEXT("Restart creates exactly one clean vehicle"));
                auto* P=Cast<ABiellaStreamingCharacter>(W->GetFirstPlayerController()->GetPawn());
                Check(P && P!=Player.Get() && !P->GetVehicle() && P->GetHealth()==100 && P->GetAmmo()==60,TEXT("Restart creates clean player"));
                Check(!OldAudio.IsValid() || !OldAudio->IsPlaying(),TEXT("Old engine audio stopped on teardown"));
                if (bPresentation)
                {
                    Check(!OldRig.IsValid() || !OldRig->IsRegistered(),TEXT("Old cosmetic rig unregistered on restart"));
                    Check(New && New->GetSkeletalPresentation()->IsRigReady(),TEXT("Restart creates a ready independent rig"));
                    Check(PoseFrames>300 && (bPresentationDisabled || (VisibleFrames>200 && MaxWheelError<.1 && MaxAxleError<.1 && MaxSpinError<.1 && MaxLinkError<.1)),TEXT("Evaluated rig follows wheel and suspension state"));
                    Check(FallbackFrames>10 && DormantFrames>10,TEXT("Fallback and dormant presentation sampled"));
                }
                if (bDriver)
                {
                    Check(DriverFrames>300 && (bDriverDisabled || SeatedFrames>200),TEXT("Driver pose evaluated across actual driving"));
                    Check(DriverFallbackFrames>10 && DriverExitFrames>10 && DriverDefeatFrames>10,TEXT("Driver fallback exit and defeat observed"));
                    Check(P && !P->GetVehicle() && !Cast<UBiellaCharacterAnimInstance>(P->CharacterMesh->GetAnimInstance())->GetPresentationSample().bSeated,TEXT("Restart clears seat pose"));
                }
                Event(TEXT("restart_clean")); return Finish(true,TEXT(""));
            }
            return false;
        }
        if (!World.IsValid())
        {
            for (const auto& C:GEngine->GetWorldContexts())
            { if (auto* W=C.World(); W && W!=OldWorld.Get() && W->IsGameWorld() && W->HasBegunPlay()) { World=W; break; } }
            if (!World.IsValid()) { return false; }
            PC=World->GetFirstPlayerController(); Player=Cast<ABiellaStreamingCharacter>(PC->GetPawn());
            int32 Count=0; for (TActorIterator<ABiellaVehicle> It(World.Get());It;++It) { Car=*It; ++Count; }
            if (Count!=1 || !Player.IsValid()) { return Finish(false,TEXT("vehicle_or_player_missing")); }
            Player->Health=73;
            Check(!Car->TryEnter(nullptr),TEXT("Invalid driver rejected"));
            Check(Player->RequestRelocation(Car->GetActorLocation()+FVector(0,-250,-20)),TEXT("Supported approach requested"));
            Next(1,TEXT("approach"));
        }
        const double Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1)
        {
            if (Player->IsRelocationPending() || !Player->IsTraversalReady() || Car->IsHeld() || Car->GetContactCount()!=4 || Age<3) { return false; }
#if WITH_EDITOR
            if (GShaderCompilingManager && GShaderCompilingManager->IsCompiling()) { return false; }
#endif
            Obstacle=Box(Car->GetActorLocation()+FVector(0,-125,50),FVector(0.4,0.2,2.0));
            Check(!Car->TryEnter(Player.Get()) && Car->GetLastRejection()==TEXT("entry_obstructed"),TEXT("Entry cannot pass through wall"));
            Obstacle->Destroy(); Obstacle.Reset();
            SavedAmmo=Player->GetAmmo(); SavedHealth=Player->GetHealth();
            Capture(TEXT("approach")); Next(22,TEXT("approach_capture"));
        }
        else if (Phase==22 && Age>0.3 && !FScreenshotRequest::IsScreenshotRequested())
        {
            Key(EKeys::E,true); Next(2,TEXT("enter_key"));
        }
        else if (Phase==2 && Age>0.35)
        {
            if (bDriver)
            {
                if (!bDriverCamera)
                {
                    Car->CameraBoom->TargetArmLength=230; Car->CameraBoom->SocketOffset=FVector(0,0,50);
                    Car->CameraBoom->SetRelativeRotation(FRotator(-10,65,0)); bDriverCamera=true;
                }
                if (Age>.8 && !bDriverCaptured) { Capture(TEXT("cockpit")); bDriverCaptured=true; }
                if (Age>1.2 && !FScreenshotRequest::IsScreenshotRequested() && !bDriverFrontCamera)
                {
                    Car->CameraBoom->TargetArmLength=180; Car->CameraBoom->SocketOffset=FVector(0,0,25);
                    Car->CameraBoom->SetRelativeRotation(FRotator(-8,135,0)); bDriverFrontCamera=true;
                }
                if (Age>1.65 && !bDriverFrontCaptured) { Capture(TEXT("cockpit_front")); bDriverFrontCaptured=true; }
                if (Age<2.2 || FScreenshotRequest::IsScreenshotRequested()) { return false; }
                Car->CameraBoom->TargetArmLength=750; Car->CameraBoom->SocketOffset=FVector(0,0,180);
                Car->CameraBoom->SetRelativeRotation(FRotator(-14,0,0));
            }
            Key(EKeys::E,false);
            Check(Car->GetDriver()==Player.Get() && Player->GetVehicle()==Car.Get() && PC->GetPawn()==Player.Get(),TEXT("E mounts existing possessed player"));
            Check(!Player->GetActorEnableCollision() && !Player->PawnMovement->IsComponentTickEnabled(),TEXT("Walking physics suspended while mounted"));
            Check(PC->GetViewTarget()==Car.Get(),TEXT("Vehicle camera active"));
            Check(!Player->RequestRelocation(FVector(12000,0,90)),TEXT("Mounted relocation rejected"));
            Check(!Car->TryEnter(Player.Get()),TEXT("Duplicate entry rejected"));
            Start=Car->GetActorLocation(); InitialYaw=Car->GetActorRotation().Yaw;
            UAudioMixerBlueprintLibrary::StartRecordingOutput(World.Get(),20.0f); bRecording=true;
            Key(EKeys::W,true); Next(3,TEXT("accelerate"));
        }
        else if (Phase==3 && Age>1.5)
        {
            Check(Car->GetThrottle()>0.9 && Car->GetSpeed()>250 && Car->GetActorLocation().X>Start.X+150,TEXT("W accelerates physical chassis"));
            Check(!Car->TryExit() && Car->GetLastRejection()==TEXT("exit_speed_or_roll"),TEXT("Moving exit rejected"));
            Check(Car->EngineAudio->IsPlaying(),TEXT("Engine audio active"));
            UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE_AUDIO app_volume=%.3f unfocused=%.3f focus=%d primary=%.3f muted=%d world_allowed=%d sound=%s pitch=%.3f volume=%.3f"),
                FApp::GetVolumeMultiplier(),FApp::GetUnfocusedVolumeMultiplier(),FApp::HasFocus(),
                World->GetAudioDevice()->GetPrimaryVolume(),World->GetAudioDevice()->IsAudioDeviceMuted(),World->bAllowAudioPlayback,
                *GetNameSafe(Car->EngineAudio->Sound),Car->EngineAudio->PitchMultiplier,Car->EngineAudio->VolumeMultiplier);
            Key(EKeys::D,true); Next(4,TEXT("steer_right"));
        }
        else if (Phase==4 && Age>0.3)
        {
            Check(Car->GetSteering()>0.9,TEXT("D drives steering"));
            TurnYaw=Car->GetActorRotation().Yaw;
            Check(FMath::Abs(FMath::FindDeltaAngleDegrees(InitialYaw,TurnYaw))>0.5,TEXT("Steering turns chassis"));
            Key(EKeys::D,false); Key(EKeys::A,true); Next(5,TEXT("steer_left"));
        }
        else if (Phase==5 && Age>0.3)
        { Check(Car->GetSteering()<-0.9,TEXT("A drives opposite steering")); Key(EKeys::A,false); Next(6,TEXT("streamed_traversal")); }
        else if (Phase==6)
        {
            if (!bSupportTested && Car->GetActorLocation().X>Start.X+2600)
            {
                FHitResult H; FCollisionQueryParams Q(SCENE_QUERY_STAT(VehicleTestFloor),false,Car.Get()); Q.AddIgnoredActor(Player.Get());
                const FVector P=Car->GetActorLocation()+Car->GetActorForwardVector()*800;
                Check(World->LineTraceSingleByObjectType(H,P+FVector(0,0,100),P-FVector(0,0,300),FCollisionObjectQueryParams(ECC_WorldStatic),Q),TEXT("Fault fixture finds real streamed floor"));
                MissingFloor=H.GetComponent();
                if (!MissingFloor.IsValid()) { return Finish(false,TEXT("missing_floor_fixture")); }
                MissingFloor->SetCollisionEnabled(ECollisionEnabled::NoCollision);
                SupportRemovedAt=World->TimeSeconds; bSupportTested=true; Event(TEXT("support_removed"));
                return false;
            }
            if (MissingFloor.IsValid())
            {
                if (World->TimeSeconds-SupportRemovedAt<0.5) { return false; }
                Check(Car->IsHeld() && Car->Chassis->GetPhysicsLinearVelocity().IsNearlyZero() && Car->GetActorLocation().Z>30,TEXT("Absent terrain safely holds physical vehicle"));
                Event(TEXT("support_hold")); MissingFloor->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics); MissingFloor.Reset(); Event(TEXT("support_restored"));
                return false;
            }
            if (Car->GetActorLocation().X<Start.X+6500) { return false; }
            Check(FMath::Abs(Car->GetActorLocation().Y)<1450 && Car->GetActorLocation().Z>30,TEXT("Physical traverse remains supported on authored street"));
            Capture(TEXT("driving")); Key(EKeys::W,false); Key(EKeys::SpaceBar,true);
            BrakeAt=Car->GetActorLocation(); Next(7,TEXT("brake"));
        }
        else if (Phase==7)
        {
            if (bPresentation && !bPresentationDisabled && Age>.4 && !FScreenshotRequest::IsScreenshotRequested())
            { IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Vehicle.SkeletalPresentation"))->Set(0,ECVF_SetByCode); }
            if (Age<=1.5) { return false; }
            Check(FMath::Abs(Car->GetSpeed())<30 && FVector::Dist(BrakeAt,Car->GetActorLocation())<1000,TEXT("Brake stops chassis within bounded distance"));
            ReverseAt=Car->GetActorLocation(); Key(EKeys::SpaceBar,false); Key(EKeys::S,true); Next(8,TEXT("reverse"));
        }
        else if (Phase==8 && Age>1.5)
        {
            Check(Car->GetSpeed()<-250 && FVector::DotProduct(Car->GetActorLocation()-ReverseAt,Car->GetActorForwardVector())<-150,TEXT("S reverses chassis"));
            Key(EKeys::S,false); Key(EKeys::SpaceBar,true); Next(9,TEXT("reverse_brake"));
        }
        else if (Phase==9 && Age>1.5)
        {
            Check(FMath::Abs(Car->GetSpeed())<30,TEXT("Reverse braking works"));
            WallAt=Car->GetActorLocation()+Car->GetActorForwardVector()*1600; WallAt.Z=100;
            Obstacle=Box(WallAt,FVector(0.4,10,2),FRotator(0,Car->GetActorRotation().Yaw,0));
            ImpactBefore=Car->GetImpactCount(); FeedbackBefore=UBiellaGameplayFeedback::Get(World.Get())->GetEventCount(EBiellaFeedbackCue::Impact);
            Key(EKeys::SpaceBar,false); Key(EKeys::W,true); Next(10,TEXT("collision_approach"));
        }
        else if (Phase==10 && Car->GetImpactCount()>ImpactBefore)
        {
            Check(Car->GetHealth()<100 && Car->GetHealth()>0,TEXT("Collision impulse damages vehicle"));
            Check(UBiellaGameplayFeedback::Get(World.Get())->GetEventCount(EBiellaFeedbackCue::Impact)>FeedbackBefore,TEXT("Collision produces runtime feedback"));
            Key(EKeys::W,false); Key(EKeys::SpaceBar,true); Capture(TEXT("impact")); Next(11,TEXT("collision_response"));
        }
        else if (Phase==11 && Age>1.5)
        {
            Check(FMath::Abs(Car->GetSpeed())<30,TEXT("Wall blocks vehicle"));
            Check(FVector::DotProduct(Car->GetActorLocation()-WallAt,Car->GetActorForwardVector())<-120,TEXT("Chassis did not tunnel through wall"));
            Obstacle->Destroy(); Obstacle.Reset();
            for (float Side:{-1.0f,1.0f})
            { Blockers.Add(Box(Car->GetActorLocation()+Car->GetActorRightVector()*Side*180+FVector(0,0,80),FVector(5,0.2,2),FRotator(0,Car->GetActorRotation().Yaw,0))); }
            Check(!Car->TryExit() && Car->GetLastRejection()==TEXT("exit_obstructed"),TEXT("Both thin side walls prevent exit"));
            for (auto& B:Blockers) { B->Destroy(); } Blockers.Empty();
            Key(EKeys::SpaceBar,false); Key(EKeys::E,true); Next(12,TEXT("exit_key"));
        }
        else if (Phase==12 && Age>0.4)
        {
            Key(EKeys::E,false);
            Check(!Car->GetDriver() && !Player->GetVehicle() && PC->GetPawn()==Player.Get(),TEXT("E safely restores original player"));
            Check(PC->GetViewTarget()==Player.Get() && Player->GetActorEnableCollision() && Player->PawnMovement->IsComponentTickEnabled(),TEXT("Camera collision and walking restored"));
            Check(Player->GetHealth()==SavedHealth && Player->GetAmmo()==SavedAmmo,TEXT("Player health and inventory preserved"));
            Check(!Car->EngineAudio->IsPlaying(),TEXT("Engine audio stops on exit"));
            Capture(TEXT("exited")); WalkAt=Player->GetActorLocation(); Key(EKeys::S,true); Next(13,TEXT("walking_resumed"));
        }
        else if (Phase==13 && Age>0.7)
        {
            Key(EKeys::S,false); Check(FVector::Dist(WalkAt,Player->GetActorLocation())>100,TEXT("Walking key moves player after exit"));
            UAudioMixerBlueprintLibrary::StopRecordingOutput(World.Get(),EAudioRecordingExportType::WavFile,TEXT("vehicle"),Output); bRecording=false;
            ParkedAt=Car->GetActorLocation(); ParkedHealth=Car->GetHealth();
            Check(Player->RequestRelocation(FVector(21000,0,90)),TEXT("Departure requested")); Next(14,TEXT("depart"));
        }
        else if (Phase==14 && Age>3 && !Player->IsRelocationPending())
        {
            Check(Car->IsParkedDormant() && Car->IsHeld() && !Car->Chassis->IsSimulatingPhysics() && Car->IsHidden(),TEXT("Distant parked vehicle sleeps without retaining streamed road"));
            ParkedAt=Car->GetActorLocation(); Next(15,TEXT("parked"));
        }
        else if (Phase==15 && Age>2)
        {
            Check(Car->GetActorLocation().Equals(ParkedAt,0.01) && Car->GetHealth()==ParkedHealth,TEXT("Dormancy retains exact vehicle state"));
            FHitResult Floor; FCollisionQueryParams Q(SCENE_QUERY_STAT(VehicleTestUnload),false,Car.Get());
            Check(!World->LineTraceSingleByObjectType(Floor,ParkedAt,ParkedAt-FVector(0,0,300),FCollisionObjectQueryParams(ECC_WorldStatic),Q),TEXT("Parked road collision actually unloaded"));
            Check(Player->RequestRelocation(ParkedAt+Car->GetActorRightVector()*-260),TEXT("Return requested")); Next(16,TEXT("return"));
        }
        else if (Phase==16 && Age>3 && !Player->IsRelocationPending() && Player->IsTraversalReady() && !Car->IsHeld())
        {
            Check(!Car->IsParkedDormant() && !Car->IsHidden() && Car->GetHealth()==ParkedHealth,TEXT("Same damaged car resumes"));
            Key(EKeys::E,true); Next(17,TEXT("reenter"));
        }
        else if (Phase==17 && Age>0.4)
        {
            Key(EKeys::E,false); Check(Car->GetDriver()==Player.Get(),TEXT("Reentry after streaming works"));
            for (int32 I=0;I<2;++I)
            {
                FVector At=Car->GetActorLocation()+Car->GetActorForwardVector()*(800+I*900); At.Z=90;
                UClass* Class=I==0 ? ABiellaInfected::StaticClass() : ABiellaRival::StaticClass();
                auto* Target=World->SpawnActor<ABiellaDemoPawn>(Class,At,FRotator::ZeroRotator);
                Target->Tags.Add(TEXT("D02Population")); Target->Health=1;
                ContactTargets.Add(Target);
            }
            Key(EKeys::W,true); Next(21,TEXT("npc_contact_approach"));
        }
        else if (Phase==21 && ContactTargets.Num()==2 && ContactTargets[0]->IsDefeated() && ContactTargets[1]->IsDefeated())
        {
            Check(Car->GetImpactCount()>=3,TEXT("Chaos contact damages infected and rival through shared gameplay"));
            Event(TEXT("npc_contact_confirmed")); Car->TakeDamage(1000,FDamageEvent(),PC.Get(),Player.Get()); Next(18,TEXT("disabled"));
        }
        else if (Phase==18 && Age>1.5)
        {
            Check(Car->GetHealth()==0 && FMath::Abs(Car->GetSpeed())<30 && Car->IsBraking(),TEXT("Disabled vehicle ignores throttle and brakes"));
            Key(EKeys::W,false); Player->ApplyDemoDamage(1000,nullptr,TEXT("vehicle_test_defeat")); Key(EKeys::W,true); Next(19,TEXT("driver_defeated"));
        }
        else if (Phase==19 && Age>1)
        {
            Check(Player->IsDefeated() && Car->IsBraking() && Car->GetThrottle()==0 && !Car->EngineAudio->IsPlaying(),TEXT("Defeat gates driving and audio"));
            Capture(TEXT("disabled")); Key(EKeys::W,false); Next(20,TEXT("restart_wait"));
        }
        else if (Phase==20 && Age>1 && !FScreenshotRequest::IsScreenshotRequested())
        { OldAudio=Car->EngineAudio; OldRig=Car->GetSkeletalPresentation(); Key(EKeys::R,true); Next(30,TEXT("restart_key")); }
        return false;
    }
private:
    bool Check(bool V,const TCHAR* Why) { return Test->TestTrue(Why,V); }
    void Key(FKey K,bool Down)
    {
        PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),K,Down ? IE_Pressed : IE_Released,FPlatformTime::Cycles64()));
        UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE_KEY key=%s down=%d"),*K.ToString(),Down);
    }
    AStaticMeshActor* Box(FVector At,FVector Scale,FRotator Rotation=FRotator::ZeroRotator)
    {
        auto* B=World->SpawnActor<AStaticMeshActor>(At,Rotation);
        B->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
        B->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
        B->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
        B->GetStaticMeshComponent()->SetCanEverAffectNavigation(false); B->SetActorScale3D(Scale); return B;
    }
    void BeforeTick(UWorld* W,ELevelTick,float)
    {
        if (!bReload || !W || W==OldWorld.Get() || !W->IsGameWorld()) { return; }
        for (TActorIterator<ABiellaPopulationDirector> It(W);It;++It) { It->MaxActive=0; }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It)
        { if (!It->IsA<ABiellaStreamingCharacter>()) { It->SetActorTickEnabled(false); It->PawnMovement->SetComponentTickEnabled(false); } }
    }
    void Next(int32 P,const TCHAR* Name)
    {
        Phase=P; PhaseStart=World->GetTimeSeconds(); Event(Name);
        if (bPresentation && !bPresentationDisabled && P==8)
        { IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Vehicle.SkeletalPresentation"))->Set(1,ECVF_SetByCode); }
    }
    void Event(const TCHAR* Name)
    {
        const FString E=FString::Printf(TEXT("D02_VEHICLE_TEST event=%s phase=%d time=%.6f\n"),Name,Phase,FPlatformTime::Seconds()-Started);
        Events+=E; UE_LOG(LogTemp,Display,TEXT("%s"),*E);
    }
    void Capture(const TCHAR* Name) { FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),FString(Name)+TEXT(".png")),true,false,false,FIntRect(),true); }
    void Frame()
    {
        if (bFinished || !Car.IsValid() || !Player.IsValid() || Phase>=30) { return; }
        const double Now=FPlatformTime::Seconds(); if (LastWall==0) { LastWall=Now; return; }
        const FVector At=Car->GetActorLocation(); const FRotator R=Car->GetActorRotation();
        Csv+=FString::Printf(TEXT("%llu,%.9f,%.6f,%.6f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%d,%.4f,%.4f,%.3f,%.3f,%d,%d,%d,%.4f,%d,%d,%.3f,%d,%d,%llu\n"),
            static_cast<unsigned long long>(GFrameCounter),Now-Started,(Now-LastWall)*1000,FApp::GetDeltaTime()*1000,Phase,At.X,At.Y,At.Z,R.Yaw,R.Roll,R.Pitch,Car->GetSpeed(),Car->Chassis->GetPhysicsLinearVelocity().Size(),Car->GetContactCount(),Car->GetWheelTravel(0),Car->GetWheelSpin(),Car->GetThrottle(),Car->GetSteering(),Car->IsBraking(),Car->IsHeld(),Car->IsParkedDormant(),Car->GetHealth(),Car->GetImpactCount(),Car->GetDriver()!=nullptr,Player->GetHealth(),Player->GetAmmo(),Car->EngineAudio->IsPlaying(),static_cast<unsigned long long>(FPlatformMemory::GetStats().UsedPhysical));
        LastWall=Now;
        if (bPresentation) { SamplePresentation(); }
        if (bDriver) { SampleDriver(); }
    }
    void SampleDriver()
    {
        auto* Mesh=Player->CharacterMesh.Get();
        auto* Anim=Cast<UBiellaCharacterAnimInstance>(Mesh->GetAnimInstance());
        if (!Check(Anim!=nullptr,TEXT("Driver retains shared animation instance"))) { return; }
        const auto& Sample=Anim->GetPresentationSample();
        const bool Mounted=Player->GetVehicle()==Car.Get(), Alive=!Player->IsDefeated();
        const bool Enabled=Mounted && Alive && Player->IsSkeletalDriverEnabled();
        const bool WheelExpected=Car->IsCockpitReady() && !Car->IsParkedDormant();
        const int32 State=int32(Mounted)+2*int32(Alive)+4*int32(Enabled)+8*int32(WheelExpected);
        StableDriverFrames=State==LastDriverState ? StableDriverFrames+1:0; LastDriverState=State;
        const bool Stable=StableDriverFrames>=2;
        double PelvisError=0,FeetError=0,HandsError=0,LengthError=0,RootError=0,GripError=0;
        auto* Wheel=Car->GetSteeringWheel();
        const bool WheelCollision=Wheel->GetCollisionEnabled()!=ECollisionEnabled::NoCollision || Wheel->CanEverAffectNavigation();
        const float Actions=Sample.AimWeight+Sample.FireWeight+Sample.HitWeight+Sample.JumpWeight+Sample.Feet[0].Weight+Sample.Feet[1].Weight;
        if (Stable)
        {
            Check(!WheelCollision && Wheel->GetStaticMesh() && Wheel->IsRenderStateCreated(),TEXT("Cockpit wheel is registered cosmetic geometry"));
            Check(Wheel->IsVisible()==WheelExpected,TEXT("Cockpit follows vehicle fallback and dormancy"));
            if (Mounted)
            {
                Check(Mesh->IsVisible()==Enabled && Player->BodyMesh->IsVisible()==(Alive && !Enabled),TEXT("Mounted driver has exactly one active representation"));
                Check(Sample.bSeated==Enabled && !Player->WeaponMesh->IsVisible() && Actions==0,TEXT("Seat state cancels on-foot layers and weapon"));
                Check(!Player->GetActorEnableCollision() && !Player->PawnMovement->IsComponentTickEnabled(),TEXT("Pose never restores mounted collision or locomotion"));
                RootError=FVector::Dist(Player->GetRootComponent()->GetRelativeLocation(),FVector(-20,-38,76));
                RootError+=Player->GetRootComponent()->GetRelativeRotation().Quaternion().AngularDistance(FQuat::Identity);
                RootError+=FVector::Dist(Mesh->GetRelativeLocation(),FVector(0,0,-88));
                Check(RootError<.001,TEXT("Seated pose preserves gameplay attachment and mesh origin"));
                if (Enabled)
                {
                    auto InCar=[&](FName Bone) { return Car->GetActorTransform().InverseTransformPosition(Mesh->GetBoneLocation(Bone)); };
                    PelvisError=FVector::Dist(InCar(TEXT("pelvis")),FVector(-4.875,-24.75,-23));
                    const FName Ends[]={TEXT("foot_l"),TEXT("foot_r"),TEXT("hand_l"),TEXT("hand_r")};
                    const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
                    for (int32 I=0;I<4;++I)
                    {
                        const float Side=I%2==0 ? -1.f:1.f;
                        const FVector Target=I<2 ? FVector(65,-24.75+Side*12,-38) : Wheel->GetRelativeTransform().TransformPosition(FVector(-9,Side*16.5,0));
                        const double Error=FVector::Dist(InCar(Ends[I]),Target);
                        if (I<2) { FeetError=FMath::Max(FeetError,Error); } else { HandsError=FMath::Max(HandsError,Error); }
                        int32 Bone=Ref.FindBoneIndex(Ends[I]);
                        for (int32 J=0;J<2;++J)
                        {
                            const int32 Parent=Ref.GetParentIndex(Bone);
                            const double Actual=FVector::Dist(Mesh->GetBoneLocation(Ref.GetBoneName(Bone),EBoneSpaces::ComponentSpace),Mesh->GetBoneLocation(Ref.GetBoneName(Parent),EBoneSpaces::ComponentSpace));
                            LengthError=FMath::Max(LengthError,FMath::Abs(Actual-Ref.GetRefBonePose()[Bone].GetLocation().Size())); Bone=Parent;
                        }
                    }
                    for (const TCHAR* Side:{TEXT("l"),TEXT("r")})
                    {
                        auto InWheel=[&](const TCHAR* Prefix) { return Wheel->GetComponentTransform().InverseTransformPosition(Mesh->GetBoneLocation(FName(*FString::Printf(TEXT("%s_%s"),Prefix,Side)))); };
                        const FVector Outer=InWheel(TEXT("middle_01")),Inner=InWheel(TEXT("middle_03")),Thumb=InWheel(TEXT("thumb_03"));
                        const double OuterRadius=FVector2D(Outer.Y,Outer.Z).Size(),InnerRadius=FVector2D(Inner.Y,Inner.Z).Size();
                        // Physical rim radius is 14 cm: curled fingers must
                        // span its outer and inner edges, with the thumb above.
                        for (double Error:{16.-OuterRadius,OuterRadius-19.,9.-InnerRadius,InnerRadius-14.,FMath::Abs(Outer.X)-5.,FMath::Abs(Inner.X)-5.,2.5-Thumb.Z})
                        { GripError=FMath::Max(GripError,Error); }
                    }
                    Check(GripError<.001,TEXT("Evaluated fingers curl around both moving rim grips with thumbs above"));
                    if (FMath::Max3(PelvisError,FeetError,HandsError)>=.5 || LengthError>=.05)
                    { UE_LOG(LogTemp,Error,TEXT("D03_DRIVER_CONTACT pelvis=%.4f feet=%.4f hands=%.4f length=%.4f"),PelvisError,FeetError,HandsError,LengthError); }
                    Check(FMath::Max3(PelvisError,FeetError,HandsError)<.5 && LengthError<.05,TEXT("Evaluated driver reaches seat footwell and moving wheel without limb stretching"));
                    ++SeatedFrames;
                }
                else if (Alive) { ++DriverFallbackFrames; }
                else { ++DriverDefeatFrames; }
            }
            else { Check(!Sample.bSeated,TEXT("Dismount clears seated pose")); if (Phase==13) { ++DriverExitFrames; } }
        }
        ++DriverFrames;
        DriverCsv+=FString::Printf(TEXT("%llu,%d,%d,%d,%d,%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d,%.6f,%.6f,%.6f,%d\n"),
            static_cast<unsigned long long>(GFrameCounter),Phase,Mounted,Alive,Enabled,Stable,Mesh->IsVisible(),Player->BodyMesh->IsVisible(),Sample.bSeated,
            PelvisError,FeetError,HandsError,LengthError,RootError,Wheel->IsVisible(),WheelCollision,Actions,Car->GetSteering(),GripError,WheelExpected);
    }
    void SamplePresentation()
    {
        auto* Rig=Car->GetSkeletalPresentation();
        const bool Visible=Rig && Rig->IsVisible();
        double WheelError=0, AxleError=0, SpinError=0, LinkError=0;
        double RigidCenterError=0, RigidAxleError=0, RigidSpinError=0, RigidRadiusError=0, RigidBodyError=0;
        auto* RigBody=Car->GetPresentationBody();
        int32 RigidVisible=RigBody->IsVisible() ? 1:0;
        bool CosmeticCollision=Rig->GetCollisionEnabled()!=ECollisionEnabled::NoCollision || Rig->CanEverAffectNavigation();
        for (int32 I=-1;I<4;++I)
        {
            auto* Part=I<0 ? RigBody:Car->GetPresentationTire(I);
            if (I>=0 && Part->IsVisible()) { ++RigidVisible; }
            CosmeticCollision |= Part->GetCollisionEnabled()!=ECollisionEnabled::NoCollision || Part->CanEverAffectNavigation();
            Check(Part->GetStaticMesh() && Part->IsRegistered() && Part->IsRenderStateCreated(),TEXT("Rigid vehicle parts have registered render geometry"));
            Check(Part->GetAttachParent()==Rig && Part->GetAttachSocketName()==(I<0 ? FName(TEXT("OffroadCar")):UBiellaVehiclePresentation::WheelBone(I)),TEXT("Rigid parts attach to the evaluated rig"));
        }
        Check(RigidVisible==(Visible ? 5:0),TEXT("Body and all tires follow rig visibility"));
        if (Visible)
        {
            ++VisibleFrames;
            const FTransform BodyLocal=RigBody->GetComponentTransform().GetRelativeTransform(Rig->GetComponentTransform());
            RigidBodyError=BodyLocal.GetLocation().Size()+BodyLocal.GetRotation().AngularDistance(FQuat::Identity)+(BodyLocal.GetScale3D()-FVector::OneVector).Size();
            for (int32 I=0;I<4;++I)
            {
                auto* Tire=Car->GetPresentationTire(I);
                const FTransform TireLocal=Tire->GetComponentTransform().GetRelativeTransform(Car->GetActorTransform());
                const auto Bounds=Tire->GetStaticMesh()->GetBounds();
                RigidCenterError=FMath::Max(RigidCenterError,FVector::Dist(TireLocal.TransformPosition(Bounds.Origin),Car->GetWheelCenter(I)));
                const FQuat Steer=FRotator(0,I<2 ? Car->GetSteering()*28:0,0).Quaternion();
                const FQuat ExpectedRotation=Steer*FQuat(FVector::RightVector,FMath::DegreesToRadians(Car->GetWheelSpin()));
                auto Angle=[](const FVector& A,const FVector& B) { return FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(A,B),-1.,1.))); };
                RigidAxleError=FMath::Max(RigidAxleError,Angle(TireLocal.GetRotation().RotateVector(FVector::RightVector),ExpectedRotation.RotateVector(FVector::RightVector)));
                RigidSpinError=FMath::Max(RigidSpinError,Angle(TireLocal.GetRotation().RotateVector(FVector::UpVector),ExpectedRotation.RotateVector(FVector::UpVector)));
                RigidRadiusError=FMath::Max(RigidRadiusError,FMath::Abs(FMath::Max(Bounds.BoxExtent.X,Bounds.BoxExtent.Z)*TireLocal.GetScale3D().X-38.));
                const FTransform Wheel=Rig->GetBoneTransformByName(UBiellaVehiclePresentation::WheelBone(I),EBoneSpaces::ComponentSpace);
                WheelError=FMath::Max(WheelError,FVector::Dist(Rig->GetRelativeTransform().TransformPosition(Wheel.GetLocation()),Car->GetWheelCenter(I)));
                const FVector Axis=Wheel.GetRotation().RotateVector(FVector::RightVector);
                const FVector Expected=FRotator(0,I<2 ? Car->GetSteering()*28 : 0,0).RotateVector(-FVector::RightVector);
                AxleError=FMath::Max(AxleError,FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Axis,Expected),-1.,1.))));
                const auto& Ref=Rig->GetSkinnedAsset()->GetRefSkeleton();
                int32 BoneIndex=Ref.FindBoneIndex(UBiellaVehiclePresentation::WheelBone(I));
                FTransform Reference=Ref.GetRefBonePose()[BoneIndex];
                while ((BoneIndex=Ref.GetParentIndex(BoneIndex))>=0) { Reference*=Ref.GetRefBonePose()[BoneIndex]; }
                // Remove the authored orientation, including the rear-left
                // wheel's distinct basis, then observe the actual spoke vector.
                const FQuat Delta=Wheel.GetRotation()*Reference.GetRotation().Inverse();
                const FVector Spoke=Delta.RotateVector(FVector::UpVector);
                const FVector ExpectedSpoke=FRotator(0,I<2 ? Car->GetSteering()*28 : 0,0).RotateVector(
                    FQuat(FVector::RightVector,FMath::DegreesToRadians(Car->GetWheelSpin())).RotateVector(FVector::UpVector));
                SpinError=FMath::Max(SpinError,FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Spoke,ExpectedSpoke),-1.,1.))));
                const TCHAR* Suffixes[4]={TEXT("FL"),TEXT("FR"),TEXT("BL"),TEXT("BR")};
                auto Point=[&](const TCHAR* Prefix) { return Rig->GetBoneLocationByName(FName(*FString::Printf(TEXT("%s_%s"),Prefix,Suffixes[I])),EBoneSpaces::ComponentSpace); };
                LinkError=FMath::Max(LinkError,FVector::Dist(Point(TEXT("LowerControlArm_End")),Point(TEXT("HUB"))));
                LinkError=FMath::Max(LinkError,FVector::Dist(Point(TEXT("UpperControlArm_End")),Point(I<2 ? TEXT("HUB_Upper") : TEXT("HUB_Upper_Mnt"))));
                LinkError=FMath::Max(LinkError,FVector::Dist(Point(TEXT("SpringDamper_End")),Point(TEXT("SpringDamper_Mount"))));
            }
            MaxWheelError=FMath::Max(MaxWheelError,WheelError); MaxAxleError=FMath::Max(MaxAxleError,AxleError); MaxSpinError=FMath::Max(MaxSpinError,SpinError); MaxLinkError=FMath::Max(MaxLinkError,LinkError);
            Check(FMath::Max3(RigidCenterError,RigidAxleError,RigidSpinError)<.1 && RigidRadiusError<.01 && RigidBodyError<.01,TEXT("Rendered tire centers, axes, spin, radius and body follow authoritative vehicle state"));
        }
        bool BodyVisible=false;
        TArray<UStaticMeshComponent*> Parts; Car->GetComponents(Parts);
        for (auto* Part:Parts) { if (Part->GetName()==TEXT("Body")) { BodyVisible=Part->IsVisible(); } }
        const bool Dormant=Car->IsParkedDormant();
        if (Dormant) { ++DormantFrames; }
        if (BodyVisible) { ++FallbackFrames; }
        const double RootError=Rig->GetBoneLocationByName(TEXT("OffroadCar"),EBoneSpaces::ComponentSpace).Size();
        double PaintError=0;
        const FLinearColor ExpectedPaint=FLinearColor(.12,.24,.18)*(.25f+.75f*Car->GetHealth()/100);
        for (int32 I:{0,2})
        {
            auto* M=Cast<UMaterialInstanceDynamic>(Rig->GetMaterial(I));
            if (!Check(M!=nullptr,TEXT("Rig owns dynamic paint material"))) { continue; }
            PaintError=FMath::Max(PaintError,double(FLinearColor::Dist(M->K2_GetVectorParameterValue(TEXT("Paint Tint")),ExpectedPaint)));
        }
        for (int32 I:{0,3})
        {
            auto* M=Cast<UMaterialInstanceDynamic>(RigBody->GetMaterial(I));
            if (!Check(M!=nullptr,TEXT("Body owns dynamic paint material"))) { continue; }
            PaintError=FMath::Max(PaintError,double(FLinearColor::Dist(M->K2_GetVectorParameterValue(TEXT("Paint Tint")),ExpectedPaint)));
        }
        Check(PaintError<.001,TEXT("Rig paint follows authoritative damage"));
        Check(!CosmeticCollision && RootError<.01,TEXT("Cosmetic rig preserves collision/navigation/root authority"));
        Check(!(Visible && BodyVisible) && (!Dormant || (!Visible && !BodyVisible)),TEXT("Exclusive representation and dormant hiding"));
        if (bPresentationDisabled) { Check(!Visible,TEXT("Disabled negative control keeps rig hidden")); }
        if (Dormant && bWasDormant) { Check(Rig->GetPoseUpdates()==LastPoseUpdates,TEXT("Dormancy stops rig evaluation")); }
        LastPoseUpdates=Rig->GetPoseUpdates(); bWasDormant=Dormant;
        ++PoseFrames;
        PoseCsv+=FString::Printf(TEXT("%llu,%d,%d,%d,%llu,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f\n"),
            static_cast<unsigned long long>(GFrameCounter),Phase,Visible,Dormant,static_cast<unsigned long long>(LastPoseUpdates),WheelError,AxleError,SpinError,LinkError,RootError,PaintError,BodyVisible,CosmeticCollision,RigidVisible,RigidCenterError,RigidAxleError,RigidSpinError,RigidRadiusError,RigidBodyError);
    }
    bool Finish(bool Good,const TCHAR* Error)
    {
        if (bFinished) { return true; } bFinished=true; Good &= !Test->HasAnyErrors();
        if (bRecording && World.IsValid()) { UAudioMixerBlueprintLibrary::StopRecordingOutput(World.Get(),EAudioRecordingExportType::WavFile,TEXT("vehicle"),Output); }
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"rhi\":\"%s\",\"fixed_timestep\":%s,\"benchmark\":%s,\"error\":\"%s\"}\n"),Good ? TEXT("true") : TEXT("false"),GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"),FApp::UseFixedTimeStep() ? TEXT("true") : TEXT("false"),FApp::IsBenchmarking() ? TEXT("true") : TEXT("false"),Error);
        bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("frames.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(Events,*FPaths::Combine(Output,TEXT("events.log")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        if (bPresentation) { Saved &= FFileHelper::SaveStringToFile(PoseCsv,*FPaths::Combine(Output,TEXT("vehicle-pose.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM); }
        if (bDriver) { Saved &= FFileHelper::SaveStringToFile(DriverCsv,*FPaths::Combine(Output,TEXT("driver-pose.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM); }
        if (!Good || !Saved) { Test->AddError(FString(TEXT("vehicle_evidence_failed: "))+Error); }
        return true;
    }
    FAutomationTestBase* Test; FString Output,Csv,Events;
    double Started,PhaseStart=0,LastWall=0; int32 Phase=0,ImpactBefore=0,FeedbackBefore=0,SavedAmmo=0;
    float SavedHealth=0,InitialYaw=0,TurnYaw=0,ParkedHealth=0;
    bool bReload=false,bFinished=false,bRecording=false;
    bool bSupportTested=false;
    bool bPresentation=false,bPresentationDisabled=false,bWasDormant=false;
    bool bDriver=false,bDriverDisabled=false,bDriverCamera=false,bDriverCaptured=false,bDriverFrontCamera=false,bDriverFrontCaptured=false;
    int32 DriverFrames=0,SeatedFrames=0,DriverFallbackFrames=0,DriverExitFrames=0,DriverDefeatFrames=0,LastDriverState=-1,StableDriverFrames=0;
    FString DriverCsv;
    FString PoseCsv;
    int32 PoseFrames=0,VisibleFrames=0,FallbackFrames=0,DormantFrames=0;
    double MaxWheelError=0,MaxAxleError=0,MaxSpinError=0,MaxLinkError=0;
    uint64 LastPoseUpdates=0;
    float SupportRemovedAt=0;
    FVector Start,BrakeAt,ReverseAt,WallAt,WalkAt,ParkedAt;
    FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld;
    TWeakObjectPtr<APlayerController> PC;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player;
    TWeakObjectPtr<ABiellaVehicle> Car;
    TWeakObjectPtr<UAudioComponent> OldAudio;
    TWeakObjectPtr<UBiellaVehiclePresentation> OldRig;
    TWeakObjectPtr<AStaticMeshActor> Obstacle;
    TArray<TWeakObjectPtr<AStaticMeshActor>> Blockers;
    TWeakObjectPtr<UPrimitiveComponent> MissingFloor;
    TArray<TWeakObjectPtr<ABiellaDemoPawn>> ContactTargets;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaVehicleTest,"BiellaGames.D02.Vehicle",EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaVehicleTest::RunTest(const FString&)
{
    FString Out; FParse::Value(FCommandLine::Get(),TEXT("BiellaVehicleOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaVehicleOutput is required")); return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FVehicleScenario(this,Out)); return true;
}
#endif
