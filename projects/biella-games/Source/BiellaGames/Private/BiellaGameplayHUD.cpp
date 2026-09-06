// Copyright Biella Games. All Rights Reserved.

#include "BiellaGameplayHUD.h"

#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesCharacter.h"
#include "BiellaVehicle.h"
#include "EngineUtils.h"
#include "BiellaGamesGameState.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/PanelWidget.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Kismet/GameplayStatics.h"

namespace
{
const FLinearColor HudPanelColor(0.008f, 0.015f, 0.025f, 0.90f);
const FLinearColor HudAccentColor(0.16f, 0.82f, 1.0f, 1.0f);
const FLinearColor HudSecondaryColor(0.62f, 0.70f, 0.78f, 1.0f);
const FLinearColor HudWarningColor(1.0f, 0.55f, 0.16f, 1.0f);
const FLinearColor HudSuccessColor(0.20f, 1.0f, 0.48f, 1.0f);
const FLinearColor HudFailureColor(1.0f, 0.15f, 0.10f, 1.0f);
const FLinearColor HudTerminalBackdropColor(0.002f, 0.006f, 0.012f, 0.84f);
const FLinearColor HudTerminalCardColor(0.008f, 0.015f, 0.025f, 0.97f);

UTextBlock* AddText(UWidgetTree* WidgetTree, UPanelWidget* Parent, const TCHAR* InitialText,
    int32 FontSize, const FLinearColor& Color, const FName Name = NAME_None)
{
    if (!WidgetTree || !Parent)
    {
        return nullptr;
    }

    UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), Name);
    Text->SetText(FText::FromString(InitialText));
    FSlateFontInfo Font = Text->GetFont();
    Font.Size = FontSize;
    Text->SetFont(Font);
    Text->SetColorAndOpacity(FSlateColor(Color));
    Text->SetShadowOffset(FVector2D(1.0f, 1.0f));
    Text->SetShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.80f));
    Parent->AddChild(Text);

    if (UVerticalBoxSlot* VerticalSlot = Cast<UVerticalBoxSlot>(Text->Slot))
    {
        VerticalSlot->SetPadding(FMargin(0.0f, 2.0f, 0.0f, 2.0f));
    }
    return Text;
}

UBorder* AddCard(UWidgetTree* WidgetTree, UCanvasPanel* Canvas, const FName Name,
    const FVector2D& Anchor, const FVector2D& Alignment,
    const FVector2D& Position, const FVector2D& Size)
{
    if (!WidgetTree || !Canvas)
    {
        return nullptr;
    }

    UBorder* Card = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), Name);
    Card->SetBrushColor(HudPanelColor);
    Card->SetPadding(FMargin(18.0f, 14.0f));
    if (UCanvasPanelSlot* CanvasSlot = Canvas->AddChildToCanvas(Card))
    {
        // Non-stretched canvas slots use a position and a positive size,
        // not left/top/right/bottom inset margins.
        CanvasSlot->SetAnchors(FAnchors(Anchor.X, Anchor.Y));
        CanvasSlot->SetAlignment(Alignment);
        CanvasSlot->SetPosition(Position);
        CanvasSlot->SetSize(Size);
        CanvasSlot->SetZOrder(10);
    }
    return Card;
}

void AddVerticalPadding(UWidget* Widget, const FMargin& Padding)
{
    if (UVerticalBoxSlot* Slot = Widget ? Cast<UVerticalBoxSlot>(Widget->Slot) : nullptr)
    {
        Slot->SetPadding(Padding);
    }
}

const TCHAR* PhaseLabel(EDemo01Phase Phase)
{
    switch (Phase)
    {
    case EDemo01Phase::Intro: return TEXT("INTRO");
    case EDemo01Phase::Active: return TEXT("ACTIVE");
    case EDemo01Phase::Success: return TEXT("SUCCESS");
    case EDemo01Phase::Failure: return TEXT("FAILURE");
    default: return TEXT("UNKNOWN");
    }
}
}

TSharedRef<SWidget> UBiellaGameplayHUD::RebuildWidget()
{
    // Initialize is idempotent and creates the native WidgetTree. The tree must
    // exist before Super chooses its Slate root; NativeConstruct runs later.
    Initialize();
    BuildLayout();
    return Super::RebuildWidget();
}

void UBiellaGameplayHUD::NativeConstruct()
{
    Super::NativeConstruct();
    RefreshFromRuntime();
}

void UBiellaGameplayHUD::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
    Super::NativeTick(MyGeometry, InDeltaTime);
    RefreshFromRuntime();
}

void UBiellaGameplayHUD::BuildLayout()
{
    if (!WidgetTree || WidgetTree->RootWidget)
    {
        return;
    }

    RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("HudRoot"));
    WidgetTree->RootWidget = RootCanvas;
    RootCanvas->SetVisibility(ESlateVisibility::SelfHitTestInvisible);

    UBorder* ObjectiveCard = AddCard(WidgetTree, RootCanvas, TEXT("ObjectiveCard"),
        FVector2D::ZeroVector, FVector2D::ZeroVector,
        FVector2D(32.0f, 28.0f), FVector2D(480.0f, 200.0f));
    if (ObjectiveCard)
    {
        UVerticalBox* Stack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        ObjectiveCard->SetContent(Stack);
        AddText(WidgetTree, Stack, TEXT("OBJECTIVE // DEMO 01"), 14, HudAccentColor,
            TEXT("ObjectiveLabel"));
        ObjectiveText = AddText(WidgetTree, Stack, TEXT("Waiting for objective..."), 22,
            FLinearColor::White, TEXT("ObjectiveText"));
        ObjectiveText->SetAutoWrapText(true);
        ObjectiveProgressText = AddText(WidgetTree, Stack, TEXT("PROGRESS 00 / 00"), 14,
            HudSecondaryColor, TEXT("ObjectiveProgressText"));
        PhaseText = AddText(WidgetTree, Stack, TEXT("INTRO"), 14, HudSuccessColor,
            TEXT("PhaseText"));
        AddVerticalPadding(ObjectiveText, FMargin(0.0f, 8.0f, 0.0f, 8.0f));
    }

    UBorder* StatusCard = AddCard(WidgetTree, RootCanvas, TEXT("StatusCard"),
        FVector2D(1.0f, 0.0f), FVector2D(1.0f, 0.0f),
        FVector2D(-32.0f, 28.0f), FVector2D(280.0f, 246.0f));
    if (StatusCard)
    {
        UVerticalBox* Stack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        StatusCard->SetContent(Stack);
        AddText(WidgetTree, Stack, TEXT("PLAYER STATUS"), 14, HudAccentColor,
            TEXT("StatusLabel"));
        AddText(WidgetTree, Stack, TEXT("HEALTH"), 14, HudSecondaryColor, TEXT("HealthLabel"));

        USizeBox* HealthBarSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        HealthBarSize->SetHeightOverride(12.0f);
        HealthBar = WidgetTree->ConstructWidget<UProgressBar>(UProgressBar::StaticClass(), TEXT("HealthBar"));
        HealthBar->SetPercent(1.0f);
        HealthBar->SetFillColorAndOpacity(HudSuccessColor);
        HealthBarSize->AddChild(HealthBar);
        Stack->AddChild(HealthBarSize);
        AddVerticalPadding(HealthBarSize, FMargin(0.0f, 3.0f, 0.0f, 6.0f));

        HealthText = AddText(WidgetTree, Stack, TEXT("100 / 100"), 24, FLinearColor::White,
            TEXT("HealthText"));
        AmmoText = AddText(WidgetTree, Stack, TEXT("AMMO 60"), 20, HudWarningColor,
            TEXT("AmmoText"));
        ThreatsText = AddText(WidgetTree, Stack, TEXT("THREATS 02"), 14, HudSecondaryColor,
            TEXT("ThreatsText"));
    }

    UBorder* CountdownCard = AddCard(WidgetTree, RootCanvas, TEXT("CountdownCard"),
        FVector2D(0.5f, 1.0f), FVector2D(0.5f, 1.0f),
        FVector2D(0.0f, -28.0f), FVector2D(320.0f, 92.0f));
    UVerticalBox* CountdownStack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    CountdownCard->SetContent(CountdownStack);
    VehiclePrompt=AddText(WidgetTree,CountdownStack,TEXT(""),14,HudWarningColor,TEXT("VehiclePrompt"));
    UTextBlock* CountdownLabel = AddText(WidgetTree, CountdownStack, TEXT("THREAT COUNTDOWN"),
        14, HudWarningColor, TEXT("CountdownLabel"));
    CountdownLabel->SetJustification(ETextJustify::Center);
    CountdownText = AddText(WidgetTree, CountdownStack, TEXT("02 TARGETS REMAIN"), 20,
        FLinearColor::White, TEXT("CountdownText"));
    CountdownText->SetJustification(ETextJustify::Center);

    // Geometry keeps the sight centered independently of font bearings. Dark
    // backing preserves the cyan strokes against both sky and shadowed cover.
    UCanvasPanel* Crosshair = WidgetTree->ConstructWidget<UCanvasPanel>(
        UCanvasPanel::StaticClass(), TEXT("Crosshair"));
    Crosshair->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (UCanvasPanelSlot* CanvasSlot = RootCanvas->AddChildToCanvas(Crosshair))
    {
        CanvasSlot->SetAnchors(FAnchors(0.5f, 0.5f));
        CanvasSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        CanvasSlot->SetPosition(FVector2D::ZeroVector);
        CanvasSlot->SetSize(FVector2D(24.0f, 24.0f));
        CanvasSlot->SetZOrder(20);
    }
    auto AddSightStroke = [this, Crosshair](const FVector2D& Position,
        const FVector2D& Size, const FLinearColor& Color, const int32 ZOrder)
    {
        UBorder* Stroke = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
        Stroke->SetBrushColor(Color);
        Stroke->SetPadding(FMargin(0.0f));
        UCanvasPanelSlot* Slot = Crosshair->AddChildToCanvas(Stroke);
        Slot->SetAnchors(FAnchors(0.5f, 0.5f));
        Slot->SetAlignment(FVector2D(0.5f, 0.5f));
        Slot->SetPosition(Position);
        Slot->SetSize(Size);
        Slot->SetZOrder(ZOrder);
    };
    for (const float Direction : {-1.0f, 1.0f})
    {
        AddSightStroke(FVector2D(Direction * 7.0f, 0.0f), FVector2D(8.0f, 4.0f),
            FLinearColor::Black, 0);
        AddSightStroke(FVector2D(0.0f, Direction * 7.0f), FVector2D(4.0f, 8.0f),
            FLinearColor::Black, 0);
        AddSightStroke(FVector2D(Direction * 7.0f, 0.0f), FVector2D(6.0f, 2.0f),
            HudAccentColor, 1);
        AddSightStroke(FVector2D(0.0f, Direction * 7.0f), FVector2D(2.0f, 6.0f),
            HudAccentColor, 1);
    }

    TerminalOverlay = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("TerminalOverlay"));
    TerminalOverlay->SetBrushColor(HudTerminalBackdropColor);
    TerminalOverlay->SetPadding(FMargin(0.0f));
    TerminalOverlay->SetVisibility(ESlateVisibility::Collapsed);
    if (UCanvasPanelSlot* CanvasSlot = RootCanvas->AddChildToCanvas(TerminalOverlay))
    {
        CanvasSlot->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
        CanvasSlot->SetOffsets(FMargin(0.0f));
        CanvasSlot->SetZOrder(100);
    }

    UCanvasPanel* TerminalCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
    TerminalOverlay->SetContent(TerminalCanvas);

    UBorder* TerminalCard = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("TerminalCard"));
    TerminalCard->SetBrushColor(HudTerminalCardColor);
    TerminalCard->SetPadding(FMargin(36.0f, 30.0f));
    TerminalCard->SetVerticalAlignment(VAlign_Center);
    if (UCanvasPanelSlot* CanvasSlot = TerminalCanvas->AddChildToCanvas(TerminalCard))
    {
        CanvasSlot->SetAnchors(FAnchors(0.5f, 0.5f));
        CanvasSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        CanvasSlot->SetPosition(FVector2D::ZeroVector);
        CanvasSlot->SetSize(FVector2D(760.0f, 340.0f));
        CanvasSlot->SetZOrder(1);
    }

    UVerticalBox* TerminalStack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    TerminalCard->SetContent(TerminalStack);
    auto AddTerminalText = [this, TerminalStack](const TCHAR* InitialText, int32 FontSize,
        const FLinearColor& Color, const FName Name) -> UTextBlock*
    {
        UTextBlock* Text = AddText(WidgetTree, TerminalStack, InitialText, FontSize, Color, Name);
        if (Text)
        {
            Text->SetJustification(ETextJustify::Center);
            Text->SetAutoWrapText(true);
        }
        return Text;
    };
    AddTerminalText(TEXT("DEMO 01 // TERMINAL STATE"), 14, HudAccentColor, TEXT("TerminalLabel"));
    TerminalTitle = AddTerminalText(TEXT("SUCCESS // ARENA CLEARED"), 28, HudSuccessColor,
        TEXT("TerminalTitle"));
    AddVerticalPadding(TerminalTitle, FMargin(0.0f, 18.0f, 0.0f, 10.0f));
    TerminalMessage = AddTerminalText(TEXT("Arena cleared."), 18, FLinearColor::White,
        TEXT("TerminalMessage"));
    AddVerticalPadding(TerminalMessage, FMargin(0.0f, 0.0f, 0.0f, 24.0f));
    RestartPrompt = AddTerminalText(TEXT("PRESS R TO RESTART"), 18, HudWarningColor,
        TEXT("RestartPrompt"));
}

void UBiellaGameplayHUD::UpdateTerminalOverlay(EDemo01Phase Phase, const FString& Objective)
{
    const bool bShouldShow = Phase == EDemo01Phase::Success || Phase == EDemo01Phase::Failure;
    const bool bIsFailure = Phase == EDemo01Phase::Failure;
    const FString Title = bShouldShow ?
        (bIsFailure ? TEXT("FAILURE // YOU WERE DEFEATED") : TEXT("SUCCESS // ARENA CLEARED")) : TEXT("");
    const FString Message = bShouldShow ? Objective : TEXT("");
    const FString Prompt = bShouldShow ? TEXT("PRESS R TO RESTART") : TEXT("");

    if (TerminalOverlay)
    {
        TerminalOverlay->SetVisibility(bShouldShow ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
    }
    if (TerminalTitle)
    {
        TerminalTitle->SetText(FText::FromString(Title));
        TerminalTitle->SetColorAndOpacity(FSlateColor(bIsFailure ? HudFailureColor : HudSuccessColor));
    }
    if (TerminalMessage)
    {
        TerminalMessage->SetText(FText::FromString(Message));
    }
    if (RestartPrompt)
    {
        RestartPrompt->SetText(FText::FromString(Prompt));
    }

    const bool bChanged = bTerminalOverlayVisible != bShouldShow ||
        DisplayedTerminalTitle != Title || DisplayedTerminalMessage != Message ||
        DisplayedRestartPrompt != Prompt;
    bTerminalOverlayVisible = bShouldShow;
    DisplayedTerminalTitle = Title;
    DisplayedTerminalMessage = Message;
    DisplayedRestartPrompt = Prompt;

    if (bChanged && bShouldShow)
    {
        UE_LOG(LogTemp, Display,
            TEXT("D01_SIGNAL HUD_TERMINAL_OVERLAY phase=%s title=%s message=%s prompt=%s source=runtime"),
            PhaseLabel(Phase), *Title, *Message, *Prompt);
    }
}

void UBiellaGameplayHUD::RefreshFromRuntime()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    if (!Player.IsValid())
    {
        Player = Cast<ABiellaGamesCharacter>(GetOwningPlayerPawn());
    }
    if (!GameState.IsValid())
    {
        GameState = World->GetGameState<ABiellaGamesGameState>();
    }
    if (!ObjectiveManager.IsValid())
    {
        ObjectiveManager = Cast<ABiellaDemoObjectiveManager>(
            UGameplayStatics::GetActorOfClass(World, ABiellaDemoObjectiveManager::StaticClass()));
    }

    if (!Player.IsValid() || !GameState.IsValid())
    {
        bRuntimeBound = false;
        UpdateTerminalOverlay(EDemo01Phase::Intro, TEXT(""));
        return;
    }

    const float MaxHealth = FMath::Max(Player->MaxHealth, 1.0f);
    const float Health = FMath::Clamp(Player->GetHealth(), 0.0f, MaxHealth);
    const int32 Ammo = FMath::Max(Player->GetAmmo(), 0);
    const int32 Remaining = FMath::Max(GameState->InfectedRemaining, 0);
    const int32 Target = ObjectiveManager.IsValid() ?
        FMath::Max(ObjectiveManager->TargetCount, Remaining) : Remaining;
    const int32 Progress = ObjectiveManager.IsValid() ?
        FMath::Clamp(ObjectiveManager->ProgressCount, 0, Target) : FMath::Clamp(Target - Remaining, 0, Target);
    const FString Objective = !GameState->ObjectiveText.IsEmpty() ? GameState->ObjectiveText :
        ObjectiveManager.IsValid() ? ObjectiveManager->ObjectiveStatus : TEXT("Objective pending.");
    const int32 Phase = static_cast<int32>(GameState->Phase);

    if (HealthBar)
    {
        HealthBar->SetPercent(Health / MaxHealth);
        HealthBar->SetFillColorAndOpacity(Health <= 25.0f ? FLinearColor(1.0f, 0.12f, 0.08f, 1.0f) :
            Health <= 50.0f ? HudWarningColor : HudSuccessColor);
    }
    if (HealthText)
    {
        HealthText->SetText(FText::FromString(FString::Printf(TEXT("%03.0f / %03.0f"), Health, MaxHealth)));
    }
    if (AmmoText)
    {
        const auto* V=Player->GetVehicle();
        AmmoText->SetText(FText::FromString(V ? FString::Printf(TEXT("%02.0f km/h  CAR %.0f%%"),FMath::Abs(V->GetSpeed())*0.036f,V->GetHealth()) : FString::Printf(TEXT("AMMO %02d"), Ammo)));
    }
    if (VehiclePrompt)
    {
        FString Hint;
        if (Player.IsValid() && Player->GetVehicle())
        {
            const auto* V=Player->GetVehicle();
            Hint=V->IsHeld() ? TEXT("Waiting for road collision") : TEXT("W/S Drive / reverse | A/D Steer | SPACE Brake | E Exit");
            if (V->GetHealth()<=0) { Hint=TEXT("Vehicle disabled | Stop, then E to exit"); }
            else if (V->GetLastRejection()==TEXT("exit_obstructed")) { Hint=TEXT("Exit blocked | Move to a clear space"); }
            else if (V->GetLastRejection()==TEXT("exit_speed_or_roll")) { Hint=TEXT("Stop upright before exiting"); }
        }
        else if (Player.IsValid())
        {
            for (TActorIterator<ABiellaVehicle> It(GetWorld());It;++It)
            {
                if (FVector::Dist(It->GetActorLocation(),Player->GetActorLocation())<320)
                { Hint=It->GetHealth()>0 ? TEXT("E Drive vehicle") : TEXT("Vehicle disabled"); break; }
            }
        }
        VehiclePrompt->SetText(FText::FromString(Hint));
        VehiclePrompt->SetVisibility(Hint.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
    }
    if (ThreatsText)
    {
        ThreatsText->SetText(FText::FromString(FString::Printf(TEXT("THREATS %02d"), Remaining)));
    }
    if (CountdownText)
    {
        CountdownText->SetText(FText::FromString(
            FString::Printf(TEXT("%02d TARGET%s REMAIN"), Remaining, Remaining == 1 ? TEXT("") : TEXT("S"))));
    }
    if (ObjectiveText)
    {
        ObjectiveText->SetText(FText::FromString(Objective));
    }
    if (ObjectiveProgressText)
    {
        ObjectiveProgressText->SetText(FText::FromString(
            FString::Printf(TEXT("PROGRESS %02d / %02d"), Progress, Target)));
    }
    if (PhaseText)
    {
        PhaseText->SetText(FText::FromString(PhaseLabel(GameState->Phase)));
        PhaseText->SetColorAndOpacity(GameState->Phase == EDemo01Phase::Failure ?
            FSlateColor(FLinearColor(1.0f, 0.15f, 0.10f, 1.0f)) :
            GameState->Phase == EDemo01Phase::Success ? FSlateColor(HudSuccessColor) :
            FSlateColor(HudSecondaryColor));
    }
    UpdateTerminalOverlay(GameState->Phase, Objective);

    const bool bChanged = !FMath::IsNearlyEqual(DisplayedHealth, Health, 0.01f) ||
        DisplayedAmmo != Ammo || DisplayedThreatCountdown != Remaining ||
        DisplayedObjectiveProgress != Progress || DisplayedObjectiveTarget != Target ||
        DisplayedObjectiveText != Objective || DisplayedPhase != Phase;

    DisplayedHealth = Health;
    DisplayedAmmo = Ammo;
    DisplayedThreatCountdown = Remaining;
    DisplayedObjectiveProgress = Progress;
    DisplayedObjectiveTarget = Target;
    DisplayedObjectiveText = Objective;
    DisplayedPhase = Phase;
    bRuntimeBound = true;

    if (!bLoggedReady)
    {
        bLoggedReady = true;
        UE_LOG(LogTemp, Display,
            TEXT("D01_SIGNAL HUD_READY health=%.1f/%.1f ammo=%d countdown=%d objective=%s progress=%d/%d phase=%s source=runtime"),
            Health, MaxHealth, Ammo, Remaining, *Objective, Progress, Target,
            PhaseLabel(GameState->Phase));
    }
    else if (bChanged)
    {
        UE_LOG(LogTemp, Display,
            TEXT("D01_SIGNAL HUD_UPDATE health=%.1f/%.1f ammo=%d countdown=%d objective=%s progress=%d/%d phase=%s source=runtime"),
            Health, MaxHealth, Ammo, Remaining, *Objective, Progress, Target,
            PhaseLabel(GameState->Phase));
    }
}
