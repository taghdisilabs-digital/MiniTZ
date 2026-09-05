// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesCharacter.h"

#include "BiellaGamesGameModeBase.h"
#include "BiellaPlaytestTelemetry.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Kismet/GameplayStatics.h"
#include "CollisionQueryParams.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"
#include "GameFramework/SpringArmComponent.h"

ABiellaGamesCharacter::ABiellaGamesCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    Team = EDemo01Team::Player;
    MaxHealth = 100.0f;
    MovementSpeed = 520.0f;
    if (PawnMovement)
    {
        PawnMovement->MaxSpeed = MovementSpeed;
    }

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(Collision.Get());
    CameraBoom->TargetArmLength = 520.0f;
    CameraBoom->SetRelativeRotation(FRotator(-18.0f, 0.0f, 0.0f));
    CameraBoom->bDoCollisionTest = true;
    CameraBoom->ProbeSize = 12.0f;

    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;

    WeaponMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("WeaponMesh"));
    WeaponMesh->SetupAttachment(Collision.Get());
    WeaponMesh->SetRelativeLocation(FVector(55.0f, 0.0f, 35.0f));
    WeaponMesh->SetRelativeScale3D(FVector(0.7f, 0.16f, 0.16f));
    WeaponMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WeaponCube(
        TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (WeaponCube.Succeeded())
    {
        WeaponMesh->SetStaticMesh(WeaponCube.Object);
    }
}

void ABiellaGamesCharacter::BeginPlay()
{
    Super::BeginPlay();
    EnsureInputActions();
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        if (ULocalPlayer* LocalPlayer = PC->GetLocalPlayer())
        {
            if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
                LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
            {
                Subsystem->AddMappingContext(InputContext, 0);
            }
        }
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL PLAYER_PAWN_READY mesh=true collision=pawn"));
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL CAMERA_READY boom=%.1f collision_test=%s probe=%.1f"),
        CameraBoom ? CameraBoom->TargetArmLength : 0.0f,
        CameraBoom && CameraBoom->bDoCollisionTest ? TEXT("true") : TEXT("false"),
        CameraBoom ? CameraBoom->ProbeSize : 0.0f);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL AIM_READY yaw_input=MouseX pitch_input=MouseY clamped=true"));
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INPUT_READY actions=10 mappings=10"));
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL LOCOMOTION_READY speed=%.1f jump=true"), MovementSpeed);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL WEAPON_READY equipped=true ammo=%d trace=visibility"), Ammo);
}

void ABiellaGamesCharacter::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (IsDefeated())
    {
        return;
    }
    FireCooldownRemaining = FMath::Max(0.0f, FireCooldownRemaining - DeltaTime);
    if (bJumping)
    {
        JumpElapsed = FMath::Min(JumpElapsed + DeltaTime, 0.8f);
        const float Height = FMath::Sin((JumpElapsed / 0.8f) * PI) * 140.0f;
        FVector Location = GetActorLocation();
        Location.Z = JumpBaseZ + Height;
        SetActorLocation(Location, true);
        if (JumpElapsed >= 0.8f)
        {
            bJumping = false;
            Location.Z = JumpBaseZ;
            SetActorLocation(Location, true);
        }
    }
}

void ABiellaGamesCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    EnsureInputActions();
    if (UEnhancedInputComponent* Enhanced = Cast<UEnhancedInputComponent>(PlayerInputComponent))
    {
        Enhanced->BindAction(MoveForwardAction.Get(), ETriggerEvent::Triggered, this,
            &ABiellaGamesCharacter::MoveForward);
        Enhanced->BindAction(MoveBackwardAction.Get(), ETriggerEvent::Triggered, this,
            &ABiellaGamesCharacter::MoveBackward);
        Enhanced->BindAction(MoveRightAction.Get(), ETriggerEvent::Triggered, this,
            &ABiellaGamesCharacter::MoveRight);
        Enhanced->BindAction(MoveLeftAction.Get(), ETriggerEvent::Triggered, this,
            &ABiellaGamesCharacter::MoveLeft);
        Enhanced->BindAction(JumpAction.Get(), ETriggerEvent::Started, this,
            &ABiellaGamesCharacter::JumpStarted);
        Enhanced->BindAction(JumpAction.Get(), ETriggerEvent::Completed, this,
            &ABiellaGamesCharacter::JumpEnded);
        Enhanced->BindAction(SprintAction.Get(), ETriggerEvent::Started, this,
            &ABiellaGamesCharacter::SprintStarted);
        Enhanced->BindAction(SprintAction.Get(), ETriggerEvent::Completed, this,
            &ABiellaGamesCharacter::SprintEnded);
        Enhanced->BindAction(SprintAction.Get(), ETriggerEvent::Canceled, this,
            &ABiellaGamesCharacter::SprintEnded);
        Enhanced->BindAction(LookYawAction.Get(), ETriggerEvent::Triggered, this,
            &ABiellaGamesCharacter::LookYaw);
        Enhanced->BindAction(LookPitchAction.Get(), ETriggerEvent::Triggered, this,
            &ABiellaGamesCharacter::LookPitch);
        Enhanced->BindAction(FireAction.Get(), ETriggerEvent::Started, this,
            &ABiellaGamesCharacter::FireWeapon);
    }
}

void ABiellaGamesCharacter::MoveForward(const FInputActionValue& Value)
{
    if (IsDefeated()) { return; }
    AddMovementInput(GetActorForwardVector(), Value.Get<float>() * (bSprintHeld ? 1.35f : 1.0f));
}

void ABiellaGamesCharacter::MoveBackward(const FInputActionValue& Value)
{
    if (IsDefeated()) { return; }
    AddMovementInput(-GetActorForwardVector(), Value.Get<float>() * (bSprintHeld ? 1.35f : 1.0f));
}

void ABiellaGamesCharacter::MoveRight(const FInputActionValue& Value)
{
    if (IsDefeated()) { return; }
    AddMovementInput(GetActorRightVector(), Value.Get<float>() * (bSprintHeld ? 1.35f : 1.0f));
}

void ABiellaGamesCharacter::MoveLeft(const FInputActionValue& Value)
{
    if (IsDefeated()) { return; }
    AddMovementInput(-GetActorRightVector(), Value.Get<float>() * (bSprintHeld ? 1.35f : 1.0f));
}

void ABiellaGamesCharacter::JumpStarted(const FInputActionValue& Value)
{
    if (!IsDefeated() && !bJumping)
    {
        bJumping = true;
        JumpElapsed = 0.0f;
        JumpBaseZ = GetActorLocation().Z;
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL JUMP_STARTED"));
    }
}

void ABiellaGamesCharacter::LookYaw(const FInputActionValue& Value)
{
    const float DeltaYaw = Value.Get<float>() * 0.8f;
    AddActorLocalRotation(FRotator(0.0f, DeltaYaw, 0.0f));
}

void ABiellaGamesCharacter::LookPitch(const FInputActionValue& Value)
{
    if (!CameraBoom)
    {
        return;
    }
    FRotator Rotation = CameraBoom->GetRelativeRotation();
    Rotation.Pitch = FMath::Clamp(Rotation.Pitch + Value.Get<float>() * 0.6f, -55.0f, 12.0f);
    CameraBoom->SetRelativeRotation(Rotation);
}

void ABiellaGamesCharacter::JumpEnded(const FInputActionValue& Value)
{
}

void ABiellaGamesCharacter::SprintStarted(const FInputActionValue& Value)
{
    if (IsDefeated()) { return; }
    bSprintHeld = true;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL SPRINT_STARTED"));
}

void ABiellaGamesCharacter::SprintEnded(const FInputActionValue& Value)
{
    bSprintHeld = false;
}

void ABiellaGamesCharacter::FireWeapon(const FInputActionValue& Value)
{
    if (IsDefeated() || FireCooldownRemaining > 0.0f || Ammo <= 0)
    {
        if (Ammo <= 0)
        {
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL WEAPON_DRY ammo=0"));
        }
        return;
    }
    TArray<AActor*> Candidates;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABiellaDemoPawn::StaticClass(), Candidates);
    ABiellaDemoPawn* BestTarget = nullptr;
    float BestDistanceSq = TNumericLimits<float>::Max();
    for (AActor* Candidate : Candidates)
    {
        ABiellaDemoPawn* Pawn = Cast<ABiellaDemoPawn>(Candidate);
        if (!IsValid(Pawn) || Pawn == this || Pawn->IsDefeated() || Pawn->GetTeam() == GetTeam())
        {
            continue;
        }
        const float DistanceSq = FVector::DistSquared(GetActorLocation(), Pawn->GetActorLocation());
        if (DistanceSq < BestDistanceSq)
        {
            BestDistanceSq = DistanceSq;
            BestTarget = Pawn;
        }
    }
    if (BestTarget)
    {
        FireWeaponAt(BestTarget, 34.0f, TEXT("player_fire"));
    }
}

bool ABiellaGamesCharacter::FireWeaponAt(ABiellaDemoPawn* Target, float DamageAmount,
    const FString& DamageTag)
{
    if (!IsValid(Target) || Target == this || Target->GetTeam() == GetTeam() ||
        Target->IsDefeated() || IsDefeated() || FireCooldownRemaining > 0.0f ||
        Ammo <= 0 || !GetWorld() || !FMath::IsFinite(DamageAmount) || DamageAmount <= 0.0f)
    {
        return false;
    }
    const FVector Start = FollowCamera ? FollowCamera->GetComponentLocation() : GetActorLocation();
    const FVector End = Target->GetActorLocation();
    FCollisionQueryParams TraceParams(SCENE_QUERY_STAT(Demo01WeaponTrace), true, this);
    FHitResult Hit;
    const bool bTraceHit = GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, TraceParams);
    const bool bTargetVisible = bTraceHit && Hit.GetActor() == Target;
    if (!bTargetVisible)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL WEAPON_BLOCKED target=%s blocker=%s"),
            *Target->GetName(), Hit.GetActor() ? *Hit.GetActor()->GetName() : TEXT("unknown"));
        if (HasAuthority())
        {
            UBiellaPlaytestTelemetry::Record(GetWorld(), TEXT("weapon_blocked"), {
                {TEXT("owner"), UBiellaPlaytestTelemetry::ActorId(this)},
                {TEXT("target"), UBiellaPlaytestTelemetry::ActorId(Target)},
                {TEXT("blocker"), UBiellaPlaytestTelemetry::ActorId(Hit.GetActor())}});
        }
        return false;
    }
    const float Applied = Target->ApplyDemoDamage(DamageAmount, this, DamageTag);
    if (Applied <= 0.0f)
    {
        return false;
    }
    --Ammo;
    FireCooldownRemaining = 0.25f;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL WEAPON_FIRE owner=%s target=%s hit=true damage=%.1f ammo=%d"),
        *GetName(), *Target->GetName(), Applied, Ammo);
    if (HasAuthority())
    {
        UBiellaPlaytestTelemetry::Record(GetWorld(), TEXT("weapon_fire"), {
            {TEXT("owner"), UBiellaPlaytestTelemetry::ActorId(this)},
            {TEXT("target"), UBiellaPlaytestTelemetry::ActorId(Target)},
            {TEXT("damage"), FString::Printf(TEXT("%.3f"), Applied)},
            {TEXT("ammo"), FString::FromInt(Ammo)}});
    }
    return true;
}

void ABiellaGamesCharacter::Defeat(const FString& Reason)
{
    Super::Defeat(Reason);
    bJumping = false;
    bSprintHeld = false;
    FireCooldownRemaining = 0.0f;
    ConsumeMovementInputVector();
    if (PawnMovement)
    {
        PawnMovement->StopMovementImmediately();
    }
    if (WeaponMesh)
    {
        WeaponMesh->SetVisibility(false);
    }
    if (ABiellaGamesGameModeBase* Mode = GetWorld() ?
        GetWorld()->GetAuthGameMode<ABiellaGamesGameModeBase>() : nullptr)
    {
        Mode->HandlePlayerDefeat(this, Reason);
    }
}

void ABiellaGamesCharacter::EnsureInputActions()
{
    if (InputContext)
    {
        return;
    }
    InputContext = NewObject<UInputMappingContext>(this, TEXT("Demo01InputContext"));
    auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type)
    {
        UInputAction* Action = NewObject<UInputAction>(this, FName(Name));
        Action->ValueType = Type;
        return Action;
    };
    const EInputActionValueType Axis = EInputActionValueType::Axis1D;
    const EInputActionValueType Bool = EInputActionValueType::Boolean;
    MoveForwardAction = MakeAction(TEXT("MoveForward"), Axis);
    MoveBackwardAction = MakeAction(TEXT("MoveBackward"), Axis);
    MoveRightAction = MakeAction(TEXT("MoveRight"), Axis);
    MoveLeftAction = MakeAction(TEXT("MoveLeft"), Axis);
    LookYawAction = MakeAction(TEXT("LookYaw"), Axis);
    LookPitchAction = MakeAction(TEXT("LookPitch"), Axis);
    FireAction = MakeAction(TEXT("Fire"), Bool);
    JumpAction = MakeAction(TEXT("Jump"), Bool);
    SprintAction = MakeAction(TEXT("Sprint"), Bool);
    RestartAction = MakeAction(TEXT("Restart"), Bool);

    InputContext->MapKey(MoveForwardAction.Get(), EKeys::W);
    InputContext->MapKey(MoveBackwardAction.Get(), EKeys::S);
    InputContext->MapKey(MoveRightAction.Get(), EKeys::D);
    InputContext->MapKey(MoveLeftAction.Get(), EKeys::A);
    InputContext->MapKey(LookYawAction.Get(), EKeys::MouseX);
    InputContext->MapKey(LookPitchAction.Get(), EKeys::MouseY);
    InputContext->MapKey(FireAction.Get(), EKeys::LeftMouseButton);
    InputContext->MapKey(JumpAction.Get(), EKeys::SpaceBar);
    InputContext->MapKey(SprintAction.Get(), EKeys::LeftShift);
    InputContext->MapKey(RestartAction.Get(), EKeys::R);
}
