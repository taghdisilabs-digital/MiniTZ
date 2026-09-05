// Copyright Biella Games. All Rights Reserved.

#include "BiellaGameplayHUD.h"

#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesCharacter.h"
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

UTextBlock* AddText(UWidgetTree* WidgetTree, UPanelWidget* Parent, const TCHAR* InitialText,
    int32 FontSize, const FLinearColor& Color)
{
    if (!WidgetTree || !Parent)
    {
        return nullptr;
    }

    UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
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

UBorder* AddCard(UWidgetTree* WidgetTree, UCanvasPanel* Canvas, const FMargin& Offsets)
{
    if (!WidgetTree || !Canvas)
    {
        return nullptr;
    }

    UBorder* Card = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    Card->SetBrushColor(HudPanelColor);
    if (UCanvasPanelSlot* CanvasSlot = Canvas->AddChildToCanvas(Card))
    {
        CanvasSlot->SetAnchors(FAnchors(0.0f, 0.0f));
        CanvasSlot->SetOffsets(Offsets);
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

void UBiellaGameplayHUD::NativeConstruct()
{
    Super::NativeConstruct();
    BuildLayout();
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

    RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
    WidgetTree->RootWidget = RootCanvas;

    UBorder* ObjectiveCard = AddCard(WidgetTree, RootCanvas,
        FMargin(32.0f, 28.0f, 450.0f, 178.0f));
    if (ObjectiveCard)
    {
        UVerticalBox* Stack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        ObjectiveCard->SetContent(Stack);
        AddText(WidgetTree, Stack, TEXT("OBJECTIVE // DEMO 01"), 12, HudAccentColor);
        ObjectiveText = AddText(WidgetTree, Stack, TEXT("Waiting for objective..."), 22,
            FLinearColor::White);
        ObjectiveProgressText = AddText(WidgetTree, Stack, TEXT("PROGRESS 00 / 00"), 14,
            HudSecondaryColor);
        PhaseText = AddText(WidgetTree, Stack, TEXT("INTRO"), 12, HudSuccessColor);
        AddVerticalPadding(ObjectiveText, FMargin(0.0f, 10.0f, 0.0f, 5.0f));
    }

    UBorder* StatusCard = AddCard(WidgetTree, RootCanvas,
        FMargin(-350.0f, 28.0f, -32.0f, 270.0f));
    if (StatusCard)
    {
        if (UCanvasPanelSlot* CanvasSlot = Cast<UCanvasPanelSlot>(StatusCard->Slot))
        {
            CanvasSlot->SetAnchors(FAnchors(1.0f, 0.0f));
            CanvasSlot->SetAlignment(FVector2D(0.0f, 0.0f));
        }
        UVerticalBox* Stack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        StatusCard->SetContent(Stack);
        AddText(WidgetTree, Stack, TEXT("PLAYER STATUS"), 12, HudAccentColor);
        AddText(WidgetTree, Stack, TEXT("HEALTH"), 11, HudSecondaryColor);

        USizeBox* HealthBarSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        HealthBarSize->SetHeightOverride(12.0f);
        HealthBar = WidgetTree->ConstructWidget<UProgressBar>(UProgressBar::StaticClass());
        HealthBar->SetPercent(1.0f);
        HealthBar->SetFillColorAndOpacity(HudSuccessColor);
        HealthBarSize->AddChild(HealthBar);
        Stack->AddChild(HealthBarSize);
        AddVerticalPadding(HealthBarSize, FMargin(0.0f, 3.0f, 0.0f, 6.0f));

        HealthText = AddText(WidgetTree, Stack, TEXT("100 / 100"), 24, FLinearColor::White);
        AmmoText = AddText(WidgetTree, Stack, TEXT("AMMO 60"), 19, HudWarningColor);
        ThreatsText = AddText(WidgetTree, Stack, TEXT("THREATS 02"), 14, HudSecondaryColor);
    }

    UBorder* CountdownCard = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    CountdownCard->SetBrushColor(HudPanelColor);
    if (UCanvasPanelSlot* CanvasSlot = RootCanvas->AddChildToCanvas(CountdownCard))
    {
        CanvasSlot->SetAnchors(FAnchors(0.5f, 1.0f));
        CanvasSlot->SetAlignment(FVector2D(0.5f, 1.0f));
        CanvasSlot->SetOffsets(FMargin(-150.0f, -92.0f, 150.0f, -30.0f));
        CanvasSlot->SetZOrder(10);
    }
    UVerticalBox* CountdownStack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    CountdownCard->SetContent(CountdownStack);
    AddText(WidgetTree, CountdownStack, TEXT("THREAT COUNTDOWN"), 11, HudWarningColor);
    CountdownText = AddText(WidgetTree, CountdownStack, TEXT("02 TARGETS REMAIN"), 20,
        FLinearColor::White);

    UTextBlock* Crosshair = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    Crosshair->SetText(FText::FromString(TEXT("+")));
    FSlateFontInfo CrosshairFont = Crosshair->GetFont();
    CrosshairFont.Size = 22;
    Crosshair->SetFont(CrosshairFont);
    Crosshair->SetColorAndOpacity(FSlateColor(HudAccentColor));
    Crosshair->SetJustification(ETextJustify::Center);
    Crosshair->SetShadowOffset(FVector2D(1.0f, 1.0f));
    if (UCanvasPanelSlot* CanvasSlot = RootCanvas->AddChildToCanvas(Crosshair))
    {
        CanvasSlot->SetAnchors(FAnchors(0.5f, 0.5f));
        CanvasSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        CanvasSlot->SetOffsets(FMargin(-12.0f, -14.0f, 12.0f, 14.0f));
        CanvasSlot->SetZOrder(20);
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
        AmmoText->SetText(FText::FromString(FString::Printf(TEXT("AMMO %02d"), Ammo)));
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
