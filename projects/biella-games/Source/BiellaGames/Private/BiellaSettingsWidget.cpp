// Copyright Biella Games. All Rights Reserved.

#include "BiellaSettingsWidget.h"

#include "BiellaGameUserSettings.h"
#include "BiellaGameplayHUD.h"
#include "BiellaGamesPlayerController.h"
#include "BiellaRuntimeText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/CheckBox.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/PanelWidget.h"
#include "Components/SizeBox.h"
#include "Components/Slider.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"

namespace
{
const FLinearColor BackdropColor(0.002f, 0.006f, 0.012f, 0.94f);
const FLinearColor CardColor(0.008f, 0.015f, 0.025f, 0.98f);
const FLinearColor AccentColor(0.16f, 0.82f, 1.0f, 1.0f);
const FLinearColor SecondaryColor(0.62f, 0.70f, 0.78f, 1.0f);

UTextBlock* MakeSettingsText(UWidgetTree* WidgetTree, const FText& Text,
    int32 FontSize, const FLinearColor& Color, const FName Name = NAME_None)
{
    if (!WidgetTree)
    {
        return nullptr;
    }
    UTextBlock* TextBlock = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), Name);
    TextBlock->SetText(Text);
    FSlateFontInfo Font = TextBlock->GetFont();
    Font.Size = FontSize;
    TextBlock->SetFont(Font);
    TextBlock->SetColorAndOpacity(FSlateColor(Color));
    TextBlock->SetShadowOffset(FVector2D(1.0f, 1.0f));
    TextBlock->SetShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f));
    return TextBlock;
}

UTextBlock* AddSettingsText(UWidgetTree* WidgetTree, UPanelWidget* Parent,
    const FText& Text, int32 FontSize, const FLinearColor& Color, const FName Name = NAME_None)
{
    if (!WidgetTree || !Parent)
    {
        return nullptr;
    }
    UTextBlock* TextBlock = MakeSettingsText(WidgetTree, Text, FontSize, Color, Name);
    Parent->AddChild(TextBlock);
    if (UVerticalBoxSlot* Slot = Cast<UVerticalBoxSlot>(TextBlock->Slot))
    {
        Slot->SetPadding(FMargin(0.0f, 5.0f, 0.0f, 5.0f));
    }
    return TextBlock;
}

void SetRowPadding(UWidget* Widget, const FMargin& Padding)
{
    if (UVerticalBoxSlot* Slot = Widget ? Cast<UVerticalBoxSlot>(Widget->Slot) : nullptr)
    {
        Slot->SetPadding(Padding);
    }
}

UHorizontalBox* AddSettingRow(UWidgetTree* WidgetTree, UVerticalBox* Parent,
    const FText& Label, const FName Name)
{
    UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), Name);
    Parent->AddChild(Row);
    SetRowPadding(Row, FMargin(0.0f, 3.0f, 0.0f, 3.0f));
    UTextBlock* LabelText = AddSettingsText(WidgetTree, Row, Label, 16, SecondaryColor);
    if (UHorizontalBoxSlot* LabelSlot = LabelText ? Cast<UHorizontalBoxSlot>(LabelText->Slot) : nullptr)
    {
        LabelSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
        LabelSlot->SetPadding(FMargin(0.0f, 0.0f, 18.0f, 0.0f));
    }
    return Row;
}

void AddSliderToRow(UWidgetTree* WidgetTree, UHorizontalBox* Row, TObjectPtr<USlider>& Slider,
    TObjectPtr<UTextBlock>& ValueText, const FName SliderName, const FName ValueName)
{
    USizeBox* SliderSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    SliderSize->SetWidthOverride(260.0f);
    Slider = WidgetTree->ConstructWidget<USlider>(USlider::StaticClass(), SliderName);
    Slider->SetStepSize(0.01f);
    Slider->SetMinValue(0.0f);
    Slider->SetMaxValue(1.0f);
    SliderSize->AddChild(Slider.Get());
    Row->AddChild(SliderSize);
    if (UHorizontalBoxSlot* SliderSlot = Cast<UHorizontalBoxSlot>(SliderSize->Slot))
    {
        SliderSlot->SetPadding(FMargin(0.0f, 0.0f, 16.0f, 0.0f));
    }
    ValueText = AddSettingsText(WidgetTree, Row, FText::FromString(TEXT("1.00")), 16,
        FLinearColor::White, ValueName);
    if (UHorizontalBoxSlot* ValueSlot = ValueText ? Cast<UHorizontalBoxSlot>(ValueText->Slot) : nullptr)
    {
        ValueSlot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    }
}

void AddCheckBoxToRow(UWidgetTree* WidgetTree, UHorizontalBox* Row, TObjectPtr<UCheckBox>& CheckBox,
    TObjectPtr<UTextBlock>& ValueText, const FName CheckBoxName, const FName ValueName)
{
    CheckBox = WidgetTree->ConstructWidget<UCheckBox>(UCheckBox::StaticClass(), CheckBoxName);
    CheckBox->SetContent(MakeSettingsText(WidgetTree, FText::FromString(TEXT("")), 16,
        FLinearColor::White));
    Row->AddChild(CheckBox.Get());
    if (UHorizontalBoxSlot* CheckSlot = Cast<UHorizontalBoxSlot>(CheckBox->Slot))
    {
        CheckSlot->SetPadding(FMargin(0.0f, 0.0f, 16.0f, 0.0f));
    }
    ValueText = AddSettingsText(WidgetTree, Row, FText::FromString(TEXT("OFF")), 16,
        FLinearColor::White, ValueName);
}
}

TSharedRef<SWidget> UBiellaSettingsWidget::RebuildWidget()
{
    Initialize();
    BuildLayout();
    return Super::RebuildWidget();
}

void UBiellaSettingsWidget::NativeConstruct()
{
    Super::NativeConstruct();
    SetIsFocusable(true);
    RefreshFromSettings();
}

void UBiellaSettingsWidget::BuildLayout()
{
    if (!WidgetTree || WidgetTree->RootWidget)
    {
        return;
    }

    RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("SettingsRoot"));
    WidgetTree->RootWidget = RootCanvas;
    RootCanvas->SetVisibility(ESlateVisibility::Visible);

    UBorder* Backdrop = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("SettingsBackdrop"));
    Backdrop->SetBrushColor(BackdropColor);
    Backdrop->SetPadding(FMargin(0.0f));
    RootCanvas->AddChildToCanvas(Backdrop);
    if (UCanvasPanelSlot* BackdropSlot = Cast<UCanvasPanelSlot>(Backdrop->Slot))
    {
        BackdropSlot->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
        BackdropSlot->SetOffsets(FMargin(0.0f));
        BackdropSlot->SetZOrder(0);
    }

    USizeBox* CardSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("SettingsCardSize"));
    CardSize->SetWidthOverride(760.0f);
    CardSize->SetHeightOverride(600.0f);
    RootCanvas->AddChildToCanvas(CardSize);
    if (UCanvasPanelSlot* CardSlot = Cast<UCanvasPanelSlot>(CardSize->Slot))
    {
        CardSlot->SetAnchors(FAnchors(0.5f, 0.5f));
        CardSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        CardSlot->SetPosition(FVector2D::ZeroVector);
        CardSlot->SetSize(FVector2D(760.0f, 600.0f));
        CardSlot->SetZOrder(1);
    }

    UBorder* Card = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("SettingsCard"));
    Card->SetBrushColor(CardColor);
    Card->SetPadding(FMargin(34.0f, 28.0f));
    CardSize->AddChild(Card);

    UVerticalBox* Stack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("SettingsStack"));
    Card->SetContent(Stack);
    UTextBlock* Title = AddSettingsText(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_title"))), 28, AccentColor, TEXT("SettingsTitle"));
    if (Title)
    {
        SetRowPadding(Title, FMargin(0.0f, 0.0f, 0.0f, 4.0f));
    }
    UTextBlock* Hint = AddSettingsText(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_hint"))), 14, SecondaryColor, TEXT("SettingsHint"));
    if (Hint)
    {
        Hint->SetAutoWrapText(true);
        SetRowPadding(Hint, FMargin(0.0f, 0.0f, 0.0f, 22.0f));
    }

    UHorizontalBox* SensitivityXRow = AddSettingRow(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_sensitivity_x"))), TEXT("SensitivityXRow"));
    AddSliderToRow(WidgetTree, SensitivityXRow, SensitivityXSlider, SensitivityXValue,
        TEXT("SensitivityXSlider"), TEXT("SensitivityXValue"));

    UHorizontalBox* SensitivityYRow = AddSettingRow(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_sensitivity_y"))), TEXT("SensitivityYRow"));
    AddSliderToRow(WidgetTree, SensitivityYRow, SensitivityYSlider, SensitivityYValue,
        TEXT("SensitivityYSlider"), TEXT("SensitivityYValue"));

    UHorizontalBox* InvertYRow = AddSettingRow(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_invert_y"))), TEXT("InvertYRow"));
    AddCheckBoxToRow(WidgetTree, InvertYRow, InvertYCheckBox, InvertYValue,
        TEXT("InvertYCheckBox"), TEXT("InvertYValue"));

    UHorizontalBox* MotionBlurRow = AddSettingRow(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_motion_blur"))), TEXT("MotionBlurRow"));
    AddCheckBoxToRow(WidgetTree, MotionBlurRow, MotionBlurCheckBox, MotionBlurValue,
        TEXT("MotionBlurCheckBox"), TEXT("MotionBlurValue"));

    UHorizontalBox* HUDScaleRow = AddSettingRow(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_hud_scale"))), TEXT("HUDScaleRow"));
    AddSliderToRow(WidgetTree, HUDScaleRow, HUDScaleSlider, HUDScaleValue,
        TEXT("HUDScaleSlider"), TEXT("HUDScaleValue"));

    UButton* ApplyButton = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("ApplyResumeButton"));
    ApplyButton->SetContent(MakeSettingsText(WidgetTree,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_apply_resume"))), 18, FLinearColor::White));
    Stack->AddChild(ApplyButton);
    if (UVerticalBoxSlot* ButtonSlot = Cast<UVerticalBoxSlot>(ApplyButton->Slot))
    {
        ButtonSlot->SetPadding(FMargin(0.0f, 28.0f, 0.0f, 8.0f));
    }

    UTextBlock* Footer = AddSettingsText(WidgetTree, Stack,
        BiellaRuntimeText::Resolve(FName(TEXT("settings_pause_hint"))), 14, SecondaryColor, TEXT("SettingsFooter"));
    if (Footer)
    {
        Footer->SetJustification(ETextJustify::Center);
    }

    SensitivityXSlider->OnValueChanged.AddDynamic(this, &UBiellaSettingsWidget::OnSensitivityXChanged);
    SensitivityYSlider->OnValueChanged.AddDynamic(this, &UBiellaSettingsWidget::OnSensitivityYChanged);
    InvertYCheckBox->OnCheckStateChanged.AddDynamic(this, &UBiellaSettingsWidget::OnInvertYChanged);
    MotionBlurCheckBox->OnCheckStateChanged.AddDynamic(this, &UBiellaSettingsWidget::OnMotionBlurChanged);
    HUDScaleSlider->OnValueChanged.AddDynamic(this, &UBiellaSettingsWidget::OnHUDScaleChanged);
    ApplyButton->OnClicked.AddDynamic(this, &UBiellaSettingsWidget::OnApplyResumeClicked);
}

void UBiellaSettingsWidget::OpenSettings()
{
    RefreshFromSettings();
    SetVisibility(ESlateVisibility::Visible);
    SetIsEnabled(true);
}

void UBiellaSettingsWidget::CloseSettings()
{
    SetVisibility(ESlateVisibility::Collapsed);
}

bool UBiellaSettingsWidget::IsSettingsOpen() const
{
    return GetVisibility() != ESlateVisibility::Collapsed && GetVisibility() != ESlateVisibility::Hidden;
}

void UBiellaSettingsWidget::RefreshFromSettings()
{
    const UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get();
    if (!Settings || !SensitivityXSlider || !SensitivityYSlider || !HUDScaleSlider ||
        !InvertYCheckBox || !MotionBlurCheckBox)
    {
        return;
    }

    bRefreshingControls = true;
    SensitivityXSlider->SetValue(ToNormalized(Settings->GetLookSensitivityX(),
        UBiellaGameUserSettings::MinLookSensitivity, UBiellaGameUserSettings::MaxLookSensitivity));
    SensitivityYSlider->SetValue(ToNormalized(Settings->GetLookSensitivityY(),
        UBiellaGameUserSettings::MinLookSensitivity, UBiellaGameUserSettings::MaxLookSensitivity));
    HUDScaleSlider->SetValue(ToNormalized(Settings->GetHUDScale(),
        UBiellaGameUserSettings::MinHUDScale, UBiellaGameUserSettings::MaxHUDScale));
    InvertYCheckBox->SetIsChecked(Settings->IsInvertYEnabled());
    MotionBlurCheckBox->SetIsChecked(Settings->IsMotionBlurEnabled());
    UpdateValueLabels();
    bRefreshingControls = false;
}

void UBiellaSettingsWidget::ApplyAndSave()
{
    if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
    {
        Settings->ApplySettings(false);
        UE_LOG(LogTemp, Display, TEXT("D05_SIGNAL SETTINGS_SAVED scope=GameUserSettings"));
    }
}

float UBiellaSettingsWidget::GetSensitivityXControlValue() const
{
    return SensitivityXSlider ? SensitivityXSlider->GetValue() : -1.0f;
}

float UBiellaSettingsWidget::GetSensitivityYControlValue() const
{
    return SensitivityYSlider ? SensitivityYSlider->GetValue() : -1.0f;
}

float UBiellaSettingsWidget::GetHUDScaleControlValue() const
{
    return HUDScaleSlider ? HUDScaleSlider->GetValue() : -1.0f;
}

void UBiellaSettingsWidget::OnSensitivityXChanged(float Value)
{
    if (!bRefreshingControls)
    {
        if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
        {
            Settings->SetLookSensitivityX(FromNormalized(Value,
                UBiellaGameUserSettings::MinLookSensitivity, UBiellaGameUserSettings::MaxLookSensitivity));
            ApplyLiveSettings();
        }
    }
    UpdateValueLabels();
}

void UBiellaSettingsWidget::OnSensitivityYChanged(float Value)
{
    if (!bRefreshingControls)
    {
        if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
        {
            Settings->SetLookSensitivityY(FromNormalized(Value,
                UBiellaGameUserSettings::MinLookSensitivity, UBiellaGameUserSettings::MaxLookSensitivity));
            ApplyLiveSettings();
        }
    }
    UpdateValueLabels();
}

void UBiellaSettingsWidget::OnInvertYChanged(bool bIsChecked)
{
    if (!bRefreshingControls)
    {
        if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
        {
            Settings->SetInvertYEnabled(bIsChecked);
            ApplyLiveSettings();
        }
    }
    UpdateValueLabels();
}

void UBiellaSettingsWidget::OnMotionBlurChanged(bool bIsChecked)
{
    if (!bRefreshingControls)
    {
        if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
        {
            Settings->SetMotionBlurEnabled(bIsChecked);
            ApplyLiveSettings();
        }
    }
    UpdateValueLabels();
}

void UBiellaSettingsWidget::OnHUDScaleChanged(float Value)
{
    if (!bRefreshingControls)
    {
        if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
        {
            Settings->SetHUDScale(FromNormalized(Value,
                UBiellaGameUserSettings::MinHUDScale, UBiellaGameUserSettings::MaxHUDScale));
            ApplyLiveSettings();
        }
    }
    UpdateValueLabels();
}

void UBiellaSettingsWidget::OnApplyResumeClicked()
{
    ApplyAndSave();
    if (ABiellaGamesPlayerController* Controller =
            Cast<ABiellaGamesPlayerController>(GetOwningPlayer()))
    {
        Controller->ResumeFromSettings();
    }
}

void UBiellaSettingsWidget::ApplyLiveSettings()
{
    if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
    {
        Settings->ApplyRuntimeSettings();
    }
    if (ABiellaGamesPlayerController* Controller =
            Cast<ABiellaGamesPlayerController>(GetOwningPlayer()))
    {
        if (UBiellaGameplayHUD* HUD = Controller->GetGameplayHUD())
        {
            HUD->ApplyUserSettings();
        }
    }
}

void UBiellaSettingsWidget::UpdateValueLabels()
{
    const UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get();
    if (!Settings)
    {
        return;
    }
    if (SensitivityXValue)
    {
        SensitivityXValue->SetText(FText::FromString(FString::Printf(TEXT("%.2f"), Settings->GetLookSensitivityX())));
    }
    if (SensitivityYValue)
    {
        SensitivityYValue->SetText(FText::FromString(FString::Printf(TEXT("%.2f"), Settings->GetLookSensitivityY())));
    }
    if (HUDScaleValue)
    {
        HUDScaleValue->SetText(FText::FromString(FString::Printf(TEXT("%.2fx"), Settings->GetHUDScale())));
    }
    if (InvertYValue)
    {
        InvertYValue->SetText(Settings->IsInvertYEnabled() ?
            BiellaRuntimeText::Resolve(FName(TEXT("settings_on"))) :
            BiellaRuntimeText::Resolve(FName(TEXT("settings_off"))));
    }
    if (MotionBlurValue)
    {
        MotionBlurValue->SetText(Settings->IsMotionBlurEnabled() ?
            BiellaRuntimeText::Resolve(FName(TEXT("settings_on"))) :
            BiellaRuntimeText::Resolve(FName(TEXT("settings_off"))));
    }
}

float UBiellaSettingsWidget::FromNormalized(float Value, float Min, float Max)
{
    return FMath::Lerp(Min, Max, FMath::Clamp(Value, 0.0f, 1.0f));
}

float UBiellaSettingsWidget::ToNormalized(float Value, float Min, float Max)
{
    return FMath::GetRangePct(Min, Max, FMath::Clamp(Value, Min, Max));
}
